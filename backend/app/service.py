"""Processing a vendor submission: pipeline + database, either in one go or in the background.

Two phases, so an API can answer immediately:
  start_submission  - resolve the vendor ID (reserve a new one, or check it exists) and pick a run_id
  run_submission    - run the pipeline and save the run
process_submission does both in one call; submit_in_background runs the second phase in a thread.
"""

import logging
import threading
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.models import Decision, PipelineRun, StageResult, StageStatus, VendorStatus, VendorSubmission
from app.pipeline import Extractor, OnStage, run_pipeline
from app.repository import get_vendor, known_accounts, reserve_vendor, save_run
from app.run_events import RunEvents
from app.settings import stage_delay_ms

logger = logging.getLogger(__name__)


class VendorNotFound(Exception):
    """A resubmission named a vendor ID that does not exist."""


def start_submission(session: Session, submission: VendorSubmission,
                     vendor_id: str | None = None) -> tuple[str, str]:
    """New vendor if vendor_id is None (its ID is reserved now), otherwise a resubmission.
    Returns (vendor_id, run_id)."""
    if vendor_id is None:
        vendor_id = reserve_vendor(session, submission)
    elif get_vendor(session, vendor_id) is None:
        raise VendorNotFound(f"No vendor with ID {vendor_id}. A resubmission must use an existing vendor ID.")
    return vendor_id, str(uuid.uuid4())


def run_submission(session: Session, submission: VendorSubmission, extractor: Extractor, vendor_id: str,
                   run_id: str, on_stage: OnStage | None = None, upload_id: str | None = None) -> PipelineRun:
    run = run_pipeline(submission, vendor_id, extractor, known_accounts(session), on_stage,
                       run_id=run_id, upload_id=upload_id)
    save_run(session, submission, run)
    return run


def process_submission(session: Session, submission: VendorSubmission, extractor: Extractor,
                       vendor_id: str | None = None, on_stage: OnStage | None = None,
                       upload_id: str | None = None) -> PipelineRun:
    """Start and run in one call (scripts and tests)."""
    vendor_id, run_id = start_submission(session, submission, vendor_id)
    return run_submission(session, submission, extractor, vendor_id, run_id, on_stage, upload_id)


# ---------- background processing (API) ----------

def submit_in_background(engine: Engine, submission: VendorSubmission, extractor: Extractor,
                         events: RunEvents, vendor_id: str | None = None,
                         upload_id: str | None = None) -> tuple[str, str]:
    """Reserve the IDs now, run the pipeline in a background thread. Returns (run_id, vendor_id).
    Raises VendorNotFound before anything starts if a resubmission names an unknown vendor."""
    with Session(engine) as session:
        vendor_id, run_id = start_submission(session, submission, vendor_id)
    events.create(run_id, upload_id=upload_id, filenames=[d.filename for d in submission.documents])
    threading.Thread(target=_run_in_background, name=f"run-{run_id[:8]}", daemon=True,
                     args=(engine, submission, extractor, events, vendor_id, run_id, upload_id)).start()
    return run_id, vendor_id


def _run_in_background(engine: Engine, submission: VendorSubmission, extractor: Extractor, events: RunEvents,
                       vendor_id: str, run_id: str, upload_id: str | None) -> None:
    delay = stage_delay_ms() / 1000

    def on_stage(stage: StageResult) -> None:
        events.publish(run_id, "stage", stage.model_dump(mode="json"))
        if stage.status != StageStatus.RUNNING and delay:
            time.sleep(delay)  # lets a person watch each stage finish

    try:
        with Session(engine) as session:  # this thread's own session
            run = run_submission(session, submission, extractor, vendor_id, run_id, on_stage, upload_id)
        events.publish(run_id, "done", {"run_id": run_id, "vendor_id": vendor_id,
                                        "decision": run.decision.model_dump(mode="json")})
    except Exception as error:
        logger.exception("Background run %s failed", run_id)
        _save_fallback_run(engine, submission, vendor_id, run_id, upload_id, error)
        events.publish(run_id, "error", {
            "run_id": run_id, "vendor_id": vendor_id,
            "message": "Processing failed. The vendor has been set to PENDING for manual review."})


def _save_fallback_run(engine: Engine, submission: VendorSubmission, vendor_id: str, run_id: str,
                       upload_id: str | None, error: Exception) -> None:
    """Fail safe: record a PENDING run so the vendor is never left without a decision."""
    now = datetime.now(timezone.utc)
    run = PipelineRun(
        run_id=run_id, vendor_id=vendor_id, started_at=now, finished_at=now, had_errors=True,
        upload_id=upload_id,
        decision=Decision(vendor_id=vendor_id, status=VendorStatus.PENDING, risk_score=0,
                          reasons=[f"Processing error ({type(error).__name__}); manual review required."]))
    try:
        with Session(engine) as session:
            save_run(session, submission, run)
    except Exception:
        logger.exception("Could not save the fallback run %s", run_id)
