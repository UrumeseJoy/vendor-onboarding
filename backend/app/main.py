"""FastAPI app: submit vendors, watch runs live (SSE), read results.

Run from the backend folder:
    uvicorn app.main:app --reload

Never returns a full bank account number: stored runs only hold masked numbers, and demo
submissions are masked before they are sent.
"""

import asyncio
import json
import shutil
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from sqlmodel import Session, delete
from sse_starlette.sse import EventSourceResponse

from app.db import PipelineRunRecord, Vendor, get_engine, init_db
from app.demo_cases import CASES_DIR, load_index, load_submission
from app.extraction.factory import lazy_extractor
from app.config import get_rules
from app.models import PipelineRun, VendorEmail, VendorSubmission, mask_account
from app.repository import (
    count_runs, get_run, get_vendor, get_vendor_runs, list_vendors, status_counts, update_run_email,
)
from app.run_events import registry
from app.service import VendorNotFound, submit_in_background
from app.settings import demo_mode, extractor_mode, frontend_origins, storage_dir
from app.storage import (
    MAX_FILE_BYTES, UploadError, demo_files, document_path, match_submission_files, save_uploads,
    validate_uploads,
)

SSE_POLL_SECONDS = 0.05


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    init_db(engine)
    app.state.engine = engine
    yield
    engine.dispose()


app = FastAPI(title="Vendor Onboarding API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=frontend_origins(), allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


def get_session(request: Request):
    """One database session per request. Tests can override this dependency."""
    with Session(request.app.state.engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# ---------- helpers ----------

def _demo_case_ids() -> list[str]:
    return [entry["case_id"] for entry in load_index()]


def _require_demo_case(case_id: str) -> None:
    if case_id not in _demo_case_ids():  # also blocks path tricks: only known case IDs are accepted
        raise HTTPException(404, f"Demo case '{case_id}' not found.")


def _masked(submission: VendorSubmission) -> dict:
    bank = submission.bank.model_copy(update={"account_number": mask_account(submission.bank.account_number)})
    return submission.model_copy(update={"bank": bank}).model_dump(mode="json")


def _parse_submission(text: str) -> VendorSubmission:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"The 'submission' field is not valid JSON ({e.msg} at line {e.lineno}, "
                                 f"column {e.colno}).")
    try:
        return VendorSubmission.model_validate(data)
    except ValidationError as e:
        # Only field names and messages: never echo the submitted values back.
        problems = "; ".join(f"{'.'.join(str(p) for p in err['loc']) or 'submission'}: {err['msg']}"
                             for err in e.errors())
        raise HTTPException(400, f"The submission is incomplete or has the wrong shape: {problems}.")


def _start(session: Session, submission: VendorSubmission, extractor, vendor_id: str | None,
           upload_id: str) -> dict:
    try:
        run_id, vendor_id = submit_in_background(session.get_bind(), submission, extractor, registry,
                                                 vendor_id=vendor_id, upload_id=upload_id)
    except VendorNotFound as e:
        raise HTTPException(404, str(e))
    return {"run_id": run_id, "vendor_id": vendor_id}


def _submit_uploads(session: Session, submission_text: str, files: list[UploadFile],
                    vendor_id: str | None) -> dict:
    """Shared by new submissions and resubmissions. Everything is validated before anything is saved."""
    submission = _parse_submission(submission_text)
    uploads = [(f.filename or "", f.file.read(MAX_FILE_BYTES + 1)) for f in files]
    try:
        uploads = validate_uploads(uploads)
        submission = match_submission_files(submission, [name for name, _ in uploads])
    except UploadError as e:
        raise HTTPException(400, str(e))
    if vendor_id is not None and get_vendor(session, vendor_id) is None:
        raise HTTPException(404, f"No vendor with ID {vendor_id}.")
    upload_id, stored = save_uploads(uploads)
    return _start(session, submission, lazy_extractor(stored), vendor_id, upload_id)


def _vendor_summary(v: Vendor) -> dict:
    return {"vendor_id": v.vendor_id, "legal_name": v.legal_name, "country": v.country, "status": v.status,
            "risk_score": v.risk_score, "run_count": v.run_count, "updated_at": v.updated_at}


def _run_summary(r: PipelineRunRecord) -> dict:
    return {"run_id": r.run_id, "run_number": r.run_number, "status": r.status, "risk_score": r.risk_score,
            "started_at": r.started_at, "finished_at": r.finished_at, "had_errors": r.had_errors}


# ---------- routes ----------

@app.get("/api/health")
def health():
    return {"status": "ok", "extractor_mode": extractor_mode(), "demo_mode": demo_mode()}


@app.get("/api/demo-cases")
def demo_cases():
    return load_index()


@app.get("/api/demo-cases/{case_id}")
def demo_case(case_id: str):
    _require_demo_case(case_id)
    entry = next(e for e in load_index() if e["case_id"] == case_id)
    submission = load_submission(case_id)
    return {**entry, "submission": _masked(submission),
            "documents": [{**d.model_dump(mode="json"),
                           "file_url": f"/api/demo-cases/{case_id}/files/{d.filename}"} for d in submission.documents]}


@app.get("/api/demo-cases/{case_id}/files/{filename}")
def demo_case_file(case_id: str, filename: str):
    _require_demo_case(case_id)
    path = document_path(f"demo:{case_id}", filename)
    if path is None:
        raise HTTPException(404, f"File '{filename}' not found in demo case '{case_id}'.")
    return FileResponse(path, media_type="application/pdf", filename=filename)


class DemoRunRequest(BaseModel):
    vendor_id: str | None = None  # set to resubmit for an existing vendor


@app.post("/api/demo-cases/{case_id}/run", status_code=202)
def run_demo_case(case_id: str, session: SessionDep, body: DemoRunRequest | None = None):
    _require_demo_case(case_id)
    submission = load_submission(case_id)
    vendor_id = body.vendor_id if body else None
    return _start(session, submission, lazy_extractor(demo_files(case_id, submission)), vendor_id,
                  upload_id=f"demo:{case_id}")


@app.post("/api/vendors", status_code=202)
def submit_vendor(session: SessionDep, submission: Annotated[str, Form()],
                  files: Annotated[list[UploadFile], File()] = []):  # noqa: B006 (FastAPI default)
    return _submit_uploads(session, submission, files, vendor_id=None)


@app.post("/api/vendors/{vendor_id}/resubmit", status_code=202)
def resubmit_vendor(vendor_id: str, session: SessionDep, submission: Annotated[str, Form()],
                    files: Annotated[list[UploadFile], File()] = []):  # noqa: B006
    if get_vendor(session, vendor_id) is None:
        raise HTTPException(404, f"No vendor with ID {vendor_id}.")
    return _submit_uploads(session, submission, files, vendor_id=vendor_id)


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, session: SessionDep):
    """Server-sent events: every stage as it starts and finishes, then "done" (or "error")."""
    if registry.exists(run_id):
        async def live():
            index = 0
            while True:
                events, finished = registry.since(run_id, index)
                for event in events:
                    yield {"event": event["type"], "data": json.dumps(event["data"])}
                index += len(events)
                if finished or await request.is_disconnected():
                    return
                await asyncio.sleep(SSE_POLL_SECONDS)
        return EventSourceResponse(live())

    run = get_run(session, run_id)  # no longer in memory: replay the saved result
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found.")

    async def replay():
        for stage in run.stages:
            yield {"event": "stage", "data": stage.model_dump_json()}
        yield {"event": "done", "data": json.dumps({
            "run_id": run.run_id, "vendor_id": run.vendor_id,
            "decision": run.decision.model_dump(mode="json") if run.decision else None})}
    return EventSourceResponse(replay())


@app.get("/api/runs/{run_id}")
def get_run_detail(run_id: str, session: SessionDep):
    record = session.get(PipelineRunRecord, run_id)
    if record is None:
        raise HTTPException(404, f"Run '{run_id}' not found. It may still be processing.")
    run = PipelineRun.model_validate_json(record.run_json)
    rules = get_rules()
    return {
        **run.model_dump(mode="json"),
        "run_number": record.run_number,
        "submission": json.loads(record.submission_json),  # stored with the account number masked
        "thresholds": {"name_pass": rules.name_match.pass_threshold, "name_warn": rules.name_match.warn_threshold,
                       "min_field_confidence": rules.extraction.min_field_confidence},
    }


@app.get("/api/runs/{run_id}/documents/{filename}")
def get_run_document(run_id: str, filename: str, session: SessionDep):
    record = session.get(PipelineRunRecord, run_id)
    if record is not None:
        upload_id = record.upload_id
        filenames = [d["filename"] for d in json.loads(record.submission_json).get("documents", [])]
    else:  # still running: the in-memory registry knows where its files are
        meta = registry.meta(run_id)
        if meta is None:
            raise HTTPException(404, f"Run '{run_id}' not found.")
        upload_id, filenames = meta.get("upload_id"), meta.get("filenames", [])
    path = document_path(upload_id, filename) if filename in filenames else None
    if path is None:
        raise HTTPException(404, f"Document '{filename}' not found for run '{run_id}'.")
    return FileResponse(path, media_type="application/pdf", filename=filename)


@app.get("/api/vendors")
def vendors(session: SessionDep):
    return [_vendor_summary(v) for v in list_vendors(session)]


@app.get("/api/vendors/{vendor_id}")
def vendor_detail(vendor_id: str, session: SessionDep):
    vendor = get_vendor(session, vendor_id)
    if vendor is None:
        raise HTTPException(404, f"No vendor with ID {vendor_id}.")
    return {**_vendor_summary(vendor), "account_last4": vendor.account_last4,
            "latest_run_id": vendor.latest_run_id, "created_at": vendor.created_at,
            "runs": [_run_summary(r) for r in get_vendor_runs(session, vendor_id)]}


@app.get("/api/stats")
def stats(session: SessionDep):
    counts = status_counts(session)
    return {"status_counts": {status.value: n for status, n in counts.items()},
            "total_vendors": len(list_vendors(session)), "total_runs": count_runs(session)}


class EmailApproval(BaseModel):
    subject: str | None = None  # a person's edits; leave out to approve the draft as written
    body: str | None = None


@app.post("/api/runs/{run_id}/email/approve")
def approve_email(run_id: str, session: SessionDep, edits: EmailApproval | None = None):
    """A person approves the vendor email (optionally editing it first). Sending is simulated."""
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found.")
    if run.email is None:
        raise HTTPException(404, "This run has no vendor email yet.")
    if run.email.status == "SENT":
        raise HTTPException(409, "This email has already been approved and sent.")
    subject = edits.subject if edits and edits.subject is not None else run.email.subject
    body = edits.body if edits and edits.body is not None else run.email.body
    if not subject.strip() or not body.strip():
        raise HTTPException(400, "The email subject and body cannot be empty.")
    approved = run.email.model_copy(update={
        "subject": subject, "body": body, "status": "SENT", "approved_at": datetime.now(timezone.utc),
        "edited": subject != run.email.subject or body != run.email.body})
    update_run_email(session, run_id, approved)  # simulated send: nothing is emailed
    return approved.model_dump(mode="json")


@app.post("/api/admin/reset-demo")
def reset_demo(session: SessionDep):
    """Delete all vendors, runs and uploads (keeps the extraction cache). Only when DEMO_MODE=true."""
    if not demo_mode():
        raise HTTPException(403, "Resetting is only allowed when DEMO_MODE=true.")
    runs = session.exec(delete(PipelineRunRecord)).rowcount
    vendors_deleted = session.exec(delete(Vendor)).rowcount
    session.commit()
    shutil.rmtree(storage_dir() / "uploads", ignore_errors=True)
    registry.clear()
    return {"deleted_vendors": vendors_deleted, "deleted_runs": runs}
