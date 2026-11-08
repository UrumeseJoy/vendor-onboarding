import json

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.demo_cases import CASES_DIR, load_index, load_submission
from app.main import app
from app.models import Stage

STAGES = [s.value for s in Stage]
ACCOUNT_NUMBERS = {load_submission(e["case_id"]).bank.account_number for e in load_index()}


@pytest.fixture
def client(tmp_path, monkeypatch, db_url):
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("STAGE_DELAY_MS", "0")
    monkeypatch.setenv("EXTRACTOR_MODE", "mock")
    with TestClient(app) as c:
        yield c


# ---------- helpers ----------

def read_events(client, run_id) -> list[tuple[str, dict]]:
    """Read the SSE stream until it ends ("done" or "error"). Returns (event, data) pairs."""
    events, event_type = [], None
    with client.stream("GET", f"/api/runs/{run_id}/events") as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_type:
                events.append((event_type, json.loads(line.split(":", 1)[1].strip())))
                event_type = None
    return events


def wait_for_run(client, run_id) -> dict:
    """Wait for a run to finish; returns its decision."""
    events = read_events(client, run_id)
    assert events and events[-1][0] == "done", events[-1:]
    return events[-1][1]["decision"]


def run_demo(client, case_id, vendor_id=None) -> tuple[dict, dict]:
    body = {"vendor_id": vendor_id} if vendor_id else None
    response = client.post(f"/api/demo-cases/{case_id}/run", json=body)
    assert response.status_code == 202, response.text
    started = response.json()
    return started, wait_for_run(client, started["run_id"])


def case_upload(case_id, replace: dict | None = None):
    """Multipart parts for a case's submission and sample PDFs. replace: filename -> new bytes."""
    submission = json.loads((CASES_DIR / case_id / "submission.json").read_text())
    files = []
    for doc in submission["documents"]:
        content = (replace or {}).get(doc["filename"]) or (CASES_DIR / case_id / "files" / doc["filename"]).read_bytes()
        files.append(("files", (doc["filename"], content, "application/pdf")))
    return {"submission": json.dumps(submission)}, files


def fresh_pdf(tmp_path) -> bytes:
    path = tmp_path / "other.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(100, 750, "A PDF that is not one of the samples")
    c.save()
    return path.read_bytes()


def checks_of(run: dict) -> list[dict]:
    return [c for stage in run["stages"] for c in stage["checks"]]


# ---------- basics ----------

def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "extractor_mode": "mock", "demo_mode": False,
                                                 "reset_requires_token": False}


def test_demo_cases_listed(client):
    cases = client.get("/api/demo-cases").json()
    assert len(cases) == 8
    detail = client.get("/api/demo-cases/01_happy_path").json()
    assert detail["submission"]["bank"]["account_number"] == "••••5678"
    assert len(detail["documents"]) == 3
    assert client.get("/api/demo-cases/99_nope").status_code == 404


# ---------- uploads ----------

def test_upload_case_01_is_approved(client):
    data, files = case_upload("01_happy_path")
    response = client.post("/api/vendors", data=data, files=files)
    assert response.status_code == 202, response.text
    body = response.json()
    assert set(body) == {"run_id", "vendor_id"}
    assert wait_for_run(client, body["run_id"])["status"] == "APPROVED"


def test_sse_stream_has_every_stage_in_order(client):
    response = client.post("/api/demo-cases/01_happy_path/run")
    run_id = response.json()["run_id"]
    events = read_events(client, run_id)
    stage_events = [d for e, d in events if e == "stage"]
    assert len(stage_events) == 2 * len(STAGES)
    assert [d["stage"] for d in stage_events[0::2]] == STAGES
    assert [d["stage"] for d in stage_events[1::2]] == STAGES
    assert all(d["status"] == "RUNNING" for d in stage_events[0::2])
    assert all(d["status"] != "RUNNING" for d in stage_events[1::2])
    assert events[-1][0] == "done" and events[-1][1]["decision"]["status"] == "APPROVED"
    assert events[-1][1]["run_id"] == run_id


def test_sse_replays_from_database_when_not_in_memory(client):
    from app.run_events import registry

    started, _ = run_demo(client, "02_bank_name_mismatch")
    with registry._lock:  # simulate a server restart / expiry
        registry._runs.clear()
    events = read_events(client, started["run_id"])
    assert [d["stage"] for e, d in events if e == "stage"] == STAGES
    assert events[-1][0] == "done" and events[-1][1]["decision"]["status"] == "REJECTED"


def test_non_sample_pdf_is_unknown_and_not_approved(client, tmp_path):
    data, files = case_upload("01_happy_path", replace={"gst_certificate.pdf": fresh_pdf(tmp_path)})
    run_id = client.post("/api/vendors", data=data, files=files).json()["run_id"]
    assert wait_for_run(client, run_id)["status"] != "APPROVED"
    run = client.get(f"/api/runs/{run_id}").json()
    unreadable = [c for c in checks_of(run) if c["check_id"] == "DOC_READABLE" and c["result"] == "FAIL"]
    assert [c["details"]["filename"] for c in unreadable] == ["gst_certificate.pdf"]


# ---------- demo runs, resubmission, duplicates ----------

def test_resubmission_via_demo_cases(client):
    first, decision1 = run_demo(client, "04_wrong_document")
    assert decision1["status"] == "PENDING"
    second, decision2 = run_demo(client, "05_resubmission", vendor_id=first["vendor_id"])
    assert second["vendor_id"] == first["vendor_id"]
    assert decision2["status"] == "APPROVED"
    vendor = client.get(f"/api/vendors/{first['vendor_id']}").json()
    assert vendor["status"] == "APPROVED" and vendor["run_count"] == 2
    assert [(r["run_number"], r["status"]) for r in vendor["runs"]] == [(1, "PENDING"), (2, "APPROVED")]


def test_duplicate_bank_account_rejected(client):
    first, _ = run_demo(client, "01_happy_path")
    _, decision = run_demo(client, "07_duplicate_bank")
    assert decision["status"] == "REJECTED"
    assert any(first["vendor_id"] in r for r in decision["reasons"])


# ---------- validation ----------

def test_txt_file_rejected(client):
    data, files = case_upload("01_happy_path")
    files[0] = ("files", ("notes.txt", b"%PDF pretend", "text/plain"))
    response = client.post("/api/vendors", data=data, files=files)
    assert response.status_code == 400 and "PDF" in response.json()["detail"]


def test_file_without_pdf_header_rejected(client):
    data, files = case_upload("01_happy_path", replace={"pan_card.pdf": b"just some text"})
    response = client.post("/api/vendors", data=data, files=files)
    assert response.status_code == 400 and "not a valid PDF" in response.json()["detail"]


def test_path_traversal_name_is_sanitised(client, tmp_path):
    submission = json.loads((CASES_DIR / "01_happy_path" / "submission.json").read_text())
    submission["documents"] = [{"slot": "GST_CERTIFICATE", "filename": "../../evil.pdf"}]
    pdf = (CASES_DIR / "01_happy_path" / "files" / "gst_certificate.pdf").read_bytes()
    response = client.post("/api/vendors", data={"submission": json.dumps(submission)},
                           files=[("files", ("../../evil.pdf", pdf, "application/pdf"))])
    assert response.status_code in (202, 400), response.text
    storage = (tmp_path / "storage").resolve()
    written = [p.resolve() for p in tmp_path.rglob("*") if p.is_file() and p.suffix == ".pdf"]
    assert all(storage in p.parents for p in written)
    assert not (tmp_path / "evil.pdf").exists() and not (tmp_path.parent / "evil.pdf").exists()
    if response.status_code == 202:
        wait_for_run(client, response.json()["run_id"])
        assert [p.name for p in written] == ["evil.pdf"]


def test_submission_file_without_upload_rejected(client):
    data, files = case_upload("01_happy_path")
    response = client.post("/api/vendors", data=data, files=files[:2])
    assert response.status_code == 400 and "not uploaded" in response.json()["detail"]


def test_bad_submission_json_rejected(client):
    response = client.post("/api/vendors", data={"submission": "{not json"})
    assert response.status_code == 400 and "not valid JSON" in response.json()["detail"]
    response = client.post("/api/vendors", data={"submission": json.dumps({"country": "IN"})})
    assert response.status_code == 400 and "legal_name" in response.json()["detail"]


def test_unknown_vendor_and_run_are_404(client):
    data, files = case_upload("05_resubmission")
    assert client.post("/api/vendors/VND-2026-9999/resubmit", data=data, files=files).status_code == 404
    assert client.post("/api/demo-cases/05_resubmission/run", json={"vendor_id": "VND-2026-9999"}).status_code == 404
    assert client.get("/api/runs/no-such-run").status_code == 404
    assert client.get("/api/runs/no-such-run/events").status_code == 404
    assert client.get("/api/vendors/VND-2026-9999").status_code == 404


# ---------- documents, privacy, stats ----------

def test_document_download(client):
    started, _ = run_demo(client, "01_happy_path")
    response = client.get(f"/api/runs/{started['run_id']}/documents/gst_certificate.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf" and response.content.startswith(b"%PDF")

    data, files = case_upload("08_us_vendor")
    run_id = client.post("/api/vendors", data=data, files=files).json()["run_id"]
    wait_for_run(client, run_id)
    response = client.get(f"/api/runs/{run_id}/documents/w9_form.pdf")
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    assert client.get(f"/api/runs/{run_id}/documents/..%2F..%2Fapi.db").status_code == 404
    assert client.get(f"/api/runs/{run_id}/documents/other.pdf").status_code == 404


def test_no_response_contains_a_full_account_number(client):
    bodies = []
    for case_id in ["01_happy_path", "02_bank_name_mismatch", "06_blurry_scan", "07_duplicate_bank", "08_us_vendor"]:
        started, _ = run_demo(client, case_id)
        bodies.append(json.dumps(read_events(client, started["run_id"]), ensure_ascii=False))
        bodies.append(client.get(f"/api/runs/{started['run_id']}").text)
        bodies.append(client.get(f"/api/vendors/{started['vendor_id']}").text)
        bodies.append(client.get(f"/api/demo-cases/{case_id}").text)
    bodies += [client.get("/api/vendors").text, client.get("/api/stats").text, client.get("/api/demo-cases").text]
    for body in bodies:
        for number in ACCOUNT_NUMBERS:
            assert number not in body


def test_stats(client):
    run_demo(client, "01_happy_path")
    run_demo(client, "02_bank_name_mismatch")
    first, _ = run_demo(client, "04_wrong_document")
    run_demo(client, "05_resubmission", vendor_id=first["vendor_id"])
    run_demo(client, "06_blurry_scan")
    stats = client.get("/api/stats").json()
    assert stats["status_counts"] == {"APPROVED": 2, "PENDING": 1, "REJECTED": 1}
    assert stats["total_vendors"] == 4 and stats["total_runs"] == 5


def test_unsupported_extractor_mode_fails_safe_to_pending(client, monkeypatch):
    monkeypatch.setenv("EXTRACTOR_MODE", "banana")  # not a real mode
    started, decision = run_demo(client, "01_happy_path")
    assert decision["status"] == "PENDING"
    run = client.get(f"/api/runs/{started['run_id']}").json()
    extraction = next(s for s in run["stages"] if s["stage"] == "EXTRACTION")
    assert extraction["status"] == "FAILED" and "not recognised" in extraction["summary"]
    assert run["had_errors"] is True


def test_run_detail_includes_masked_documents_submission_and_thresholds(client):
    started, _ = run_demo(client, "01_happy_path")
    run = client.get(f"/api/runs/{started['run_id']}").json()
    assert [d["filename"] for d in run["documents"]] == ["gst_certificate.pdf", "pan_card.pdf", "cancelled_cheque.pdf"]
    cheque = run["documents"][2]
    assert cheque["fields"]["account_number"] == "••••5678"
    assert cheque["detected_type"] == "CANCELLED_CHEQUE" and cheque["field_confidence"]["ifsc"] > 0.9
    assert run["submission"]["bank"]["account_number"] == "••••5678"
    assert run["run_number"] == 1 and run["thresholds"]["name_pass"] == 90
    body = json.dumps(run, ensure_ascii=False)
    for number in ACCOUNT_NUMBERS:
        assert number not in body


def test_demo_case_detail_can_prefill_a_form(client):
    detail = client.get("/api/demo-cases/08_us_vendor").json()
    assert detail["expected_status"] == "APPROVED"
    assert detail["submission"]["ein"] == "84-1234567" and detail["submission"]["country"] == "US"
    for doc in detail["documents"]:
        assert client.get(doc["file_url"]).content.startswith(b"%PDF")
