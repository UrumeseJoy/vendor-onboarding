"""Gemini features, tested offline: app.llm functions are replaced with fakes."""

import json
import os
import shutil

import pytest
from fastapi.testclient import TestClient

from app import llm
from app.demo_cases import CASES_DIR, load_submission, vendor_id_for
from app.extraction.gemini_extractor import gemini_extract, verify_against_text
from app.extraction.mock_extractor import build_sample_index, file_sha256
from app.main import app
from app.models import CheckResult, DocType, Stage, StageStatus, VendorStatus
from app.pipeline import run_pipeline
from app.storage import demo_files
from app.vendor_message import safety_problem


def perfect_reply(pdf_bytes: bytes, claimed_slot) -> dict:
    """What an ideal Gemini would say for a sample PDF (taken from documents.json)."""
    import hashlib
    _, entry = build_sample_index()[hashlib.sha256(pdf_bytes).hexdigest()]
    return {"detected_type": entry["actual_type"], "fields": dict(entry["fields"]),
            "field_confidence": dict(entry["mock_confidence"]), "notes": ""}


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def fake(pdf_bytes, claimed_slot):
        calls.append(claimed_slot)
        return perfect_reply(pdf_bytes, claimed_slot)

    monkeypatch.setattr(llm, "extract_document", fake)
    return calls


def run_with_gemini(case_id, ai_emails=False):
    sub = load_submission(case_id)
    return run_pipeline(sub, vendor_id_for(case_id), lambda s: gemini_extract(s, demo_files(case_id, s)), [],
                        ai_emails=ai_emails)


def stage(run, s):
    return next(r for r in run.stages if r.stage == s)


# ---------- extraction ----------

def test_gemini_extract_builds_documents_from_fake_reply(fake_llm):
    case_id = "01_happy_path"
    sub = load_submission(case_id)
    docs = gemini_extract(sub, demo_files(case_id, sub))
    assert [d.slot for d in docs] == [d.slot for d in sub.documents]
    gst = docs[0]
    assert gst.detected_type == DocType.GST_CERTIFICATE
    assert gst.fields["gstin"] == sub.gstin
    assert all(c >= 0.95 for c in gst.field_confidence.values())  # found in the PDF's text
    assert gst.overall_confidence == pytest.approx(sum(gst.field_confidence.values()) / len(gst.field_confidence))


def test_value_missing_from_text_layer_is_capped_at_half(monkeypatch):
    def lying(pdf_bytes, slot):
        reply = perfect_reply(pdf_bytes, slot)
        if reply["detected_type"] == "GST_CERTIFICATE":
            reply["fields"]["gstin"] = "33AABCS9999K1ZN"  # not what the document says
        return reply

    monkeypatch.setattr(llm, "extract_document", lying)
    case_id = "01_happy_path"
    sub = load_submission(case_id)
    gst = gemini_extract(sub, demo_files(case_id, sub))[0]
    assert gst.field_confidence["gstin"] <= 0.5
    assert "gstin: not found in document text" in gst.notes
    assert gst.field_confidence["legal_name"] >= 0.95  # the honest fields are still trusted


def test_image_only_pdf_keeps_geminis_confidence(fake_llm):
    case_id = "06_blurry_scan"
    sub = load_submission(case_id)
    cheque = next(d for d in gemini_extract(sub, demo_files(case_id, sub)) if d.filename == "cancelled_cheque.pdf")
    assert cheque.field_confidence["account_number"] == 0.52 and cheque.field_confidence["ifsc"] == 0.48
    assert cheque.notes == []


def test_verify_against_text_ignores_case_and_spaces():
    reading = {"fields": {"pan": "aabcs 1234k"}, "field_confidence": {"pan": 0.6}}
    confidence, notes = verify_against_text(reading, "PAN\nAABCS1234K is the number printed on this card")
    assert confidence["pan"] == 0.95 and notes == []


def test_cache_skips_the_llm_on_second_call(fake_llm):
    case_id = "01_happy_path"
    sub = load_submission(case_id)
    files = demo_files(case_id, sub)
    first = gemini_extract(sub, files)
    assert len(fake_llm) == 3
    second = gemini_extract(sub, files)
    assert len(fake_llm) == 3  # no new calls
    assert [d.model_dump() for d in first] == [d.model_dump() for d in second]


def test_cache_is_invalidated_by_a_new_prompt_version(fake_llm, monkeypatch):
    case_id = "01_happy_path"
    sub = load_submission(case_id)
    gemini_extract(sub, demo_files(case_id, sub))
    monkeypatch.setattr(llm, "PROMPT_VERSION", "v2")
    gemini_extract(sub, demo_files(case_id, sub))
    assert len(fake_llm) == 6


# ---------- decisions built on Gemini's reading ----------

def test_gemini_says_gst_slot_is_an_invoice_gives_pending(fake_llm):
    run = run_with_gemini("04_wrong_document")
    assert run.decision.status == VendorStatus.PENDING
    mismatch = [c for s in run.stages for c in s.checks if c.check_id == "DOC_TYPE_MATCH" and c.result == CheckResult.FAIL]
    assert [c.details["detected"] for c in mismatch] == ["INVOICE"]


def test_llm_error_fails_extraction_and_never_approves(monkeypatch):
    def broken(pdf_bytes, slot):
        raise llm.LLMError("Gemini is rate-limiting requests")

    monkeypatch.setattr(llm, "extract_document", broken)
    run = run_with_gemini("01_happy_path")
    assert stage(run, Stage.EXTRACTION).status == StageStatus.FAILED
    assert "rate-limiting" in stage(run, Stage.EXTRACTION).summary
    assert run.had_errors and run.decision.status != VendorStatus.APPROVED
    assert len(run.stages) == len(list(Stage))


# ---------- vendor emails ----------

def never_called(*args, **kwargs):
    raise AssertionError("the AI email drafter must not be called")


def test_rejected_email_is_fixed_template_and_ai_is_never_called(fake_llm, monkeypatch):
    monkeypatch.setattr(llm, "draft_vendor_email", never_called)
    run = run_with_gemini("02_bank_name_mismatch", ai_emails=True)
    assert run.decision.status == VendorStatus.REJECTED
    assert run.email.generated_by == "template" and run.email.status == "DRAFT"
    assert "unable to proceed" in run.email.body
    assert "Ramesh" not in run.email.body and "match" not in run.email.body.lower()


def test_approved_email_is_a_template(fake_llm, monkeypatch):
    monkeypatch.setattr(llm, "draft_vendor_email", never_called)
    run = run_with_gemini("01_happy_path", ai_emails=True)
    assert run.email.generated_by == "template" and "approved" in run.email.body


def good_draft(name, status, items):
    return {"subject": "Action needed on your onboarding",
            "body": f"Dear {name},\n\nA few things need attention:\n" + "\n".join(f"- {i}" for i in items)
                    + "\n\nThank you,\nProcurement Team"}


def test_good_ai_draft_is_used_for_pending(fake_llm, monkeypatch):
    monkeypatch.setattr(llm, "draft_vendor_email", good_draft)
    run = run_with_gemini("04_wrong_document", ai_emails=True)
    assert run.email.generated_by == "ai" and run.email.fallback_reason is None
    assert "AI" in stage(run, Stage.VENDOR_MESSAGE).summary


@pytest.mark.parametrize("bad_text, why", [
    ("This looks like fraud.", "fraud"),
    ("We saw this account is also used by VND-2026-0099.", "vendor ID"),
    ("Your risk score was too high.", "risk score"),
])
def test_unsafe_ai_draft_is_replaced_by_template(fake_llm, monkeypatch, bad_text, why):
    def bad_draft(name, status, items):
        draft = good_draft(name, status, items)
        draft["body"] += "\n" + bad_text
        return draft

    monkeypatch.setattr(llm, "draft_vendor_email", bad_draft)
    run = run_with_gemini("04_wrong_document", ai_emails=True)
    assert run.email.generated_by == "template"
    assert why in run.email.fallback_reason
    assert bad_text not in run.email.body
    assert "gst_certificate.pdf" in run.email.body  # the template still lists the missing item


def test_draft_missing_an_item_is_replaced(fake_llm, monkeypatch):
    monkeypatch.setattr(llm, "draft_vendor_email",
                        lambda n, s, items: {"subject": "Hello", "body": "Please send us some documents. Thanks."})
    run = run_with_gemini("04_wrong_document", ai_emails=True)
    assert run.email.generated_by == "template" and "left out" in run.email.fallback_reason


def test_draft_repeating_a_review_note_is_rejected():
    note = "Possible payment diversion: the bank account is not in the company's name."
    draft = {"subject": "Hi", "body": f"Please upload your certificate. {note}"}
    assert "review note" in safety_problem(draft, ["Please upload your certificate."], [note])


def test_ai_failure_falls_back_to_template(fake_llm, monkeypatch):
    def boom(*args):
        raise llm.LLMError("timeout")

    monkeypatch.setattr(llm, "draft_vendor_email", boom)
    run = run_with_gemini("04_wrong_document", ai_emails=True)
    assert run.email.generated_by == "template" and "could not be created" in run.email.fallback_reason
    assert stage(run, Stage.VENDOR_MESSAGE).status == StageStatus.PASSED


def test_mock_mode_never_uses_ai_for_email(monkeypatch):
    monkeypatch.setattr(llm, "draft_vendor_email", never_called)
    from app.demo_cases import run_demo_case
    assert run_demo_case("04_wrong_document").email.generated_by == "template"  # EXTRACTOR_MODE=mock


# ---------- llm.py behaviour (no network) ----------

class FakeAPIError(Exception):
    def __init__(self, code):
        self.code = code


def test_retries_transient_errors_then_gives_a_clear_error(monkeypatch):
    monkeypatch.setattr(llm, "_is_transient", lambda e: isinstance(e, FakeAPIError))
    attempts, sleeps = [], []

    def failing():
        attempts.append(1)
        raise FakeAPIError(429)

    with pytest.raises(llm.LLMError, match="rate-limiting"):
        llm._with_retries(failing, sleep=sleeps.append)
    assert len(attempts) == 3 and len(sleeps) == 2  # first try + 2 retries


def test_a_transient_error_that_recovers_succeeds(monkeypatch):
    monkeypatch.setattr(llm, "_is_transient", lambda e: True)
    outcomes = [FakeAPIError(503), "reply"]

    def flaky():
        value = outcomes.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    assert llm._with_retries(flaky, sleep=lambda s: None) == "reply"


def test_other_errors_are_not_retried(monkeypatch):
    attempts = []

    def failing():
        attempts.append(1)
        raise ValueError("bad request")

    with pytest.raises(llm.LLMError):
        llm._with_retries(failing, sleep=lambda s: None)
    assert len(attempts) == 1


def test_missing_api_key_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(llm.LLMError, match="GEMINI_API_KEY"):
        llm._client()


def test_only_llm_py_imports_the_gemini_sdk():
    """Design rule 2."""
    from pathlib import Path
    offenders = []
    for path in Path(llm.__file__).parent.rglob("*.py"):
        text = path.read_text()
        if path.name != "llm.py" and ("google.genai" in text or "from google import genai" in text):
            offenders.append(path.name)
    assert offenders == []


# ---------- approval and reset endpoints ----------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/api.db")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    with TestClient(app) as c:
        yield c


def finish(client, case_id, vendor_id=None):
    started = client.post(f"/api/demo-cases/{case_id}/run", json={"vendor_id": vendor_id} if vendor_id else None).json()
    with client.stream("GET", f"/api/runs/{started['run_id']}/events") as r:
        for _ in r.iter_lines():
            pass
    return started


def test_email_approval_once_then_409_and_records_edits(client):
    run_id = finish(client, "04_wrong_document")["run_id"]
    before = client.get(f"/api/runs/{run_id}").json()["email"]
    assert before["status"] == "DRAFT" and before["edited"] is False

    response = client.post(f"/api/runs/{run_id}/email/approve", json={"subject": "Please send your certificate"})
    assert response.status_code == 200
    sent = response.json()
    assert sent["status"] == "SENT" and sent["edited"] is True and sent["approved_at"]
    assert sent["subject"] == "Please send your certificate" and sent["body"] == before["body"]
    assert client.get(f"/api/runs/{run_id}").json()["email"]["status"] == "SENT"  # stored

    assert client.post(f"/api/runs/{run_id}/email/approve").status_code == 409


def test_email_approval_without_edits_is_not_marked_edited(client):
    run_id = finish(client, "01_happy_path")["run_id"]
    sent = client.post(f"/api/runs/{run_id}/email/approve").json()
    assert sent["status"] == "SENT" and sent["edited"] is False


def test_email_approval_unknown_run_and_empty_edit(client):
    assert client.post("/api/runs/nope/email/approve").status_code == 404
    run_id = finish(client, "01_happy_path")["run_id"]
    assert client.post(f"/api/runs/{run_id}/email/approve", json={"body": "  "}).status_code == 400


def test_reset_demo_clears_data_when_demo_mode_is_on(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "true")
    for case_id in ["01_happy_path", "02_bank_name_mismatch"]:
        finish(client, case_id)
    uploads = tmp_path / "storage" / "uploads" / "abc"
    uploads.mkdir(parents=True)
    (uploads / "x.pdf").write_bytes(b"%PDF")
    cache_file = tmp_path / "extraction-cache" / "keep.json"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("{}")

    response = client.post("/api/admin/reset-demo")
    assert response.status_code == 200 and response.json() == {"deleted_vendors": 2, "deleted_runs": 2}
    assert client.get("/api/vendors").json() == []
    assert client.get("/api/stats").json()["total_runs"] == 0
    assert not (tmp_path / "storage" / "uploads").exists()
    assert cache_file.exists()  # the extraction cache is kept


def test_reset_demo_is_forbidden_otherwise(client, monkeypatch):
    finish(client, "01_happy_path")
    for value in ["false", ""]:
        monkeypatch.setenv("DEMO_MODE", value)
        assert client.post("/api/admin/reset-demo").status_code == 403
    monkeypatch.delenv("DEMO_MODE", raising=False)
    assert client.post("/api/admin/reset-demo").status_code == 403
    assert len(client.get("/api/vendors").json()) == 1


# ---------- live (real Gemini) ----------

@pytest.mark.skipif(os.getenv("RUN_LIVE_GEMINI") != "1", reason="set RUN_LIVE_GEMINI=1 to call the real Gemini")
def test_live_gemini_reads_case_01_gst_certificate():
    pdf = (CASES_DIR / "01_happy_path" / "files" / "gst_certificate.pdf").read_bytes()
    reading = llm.extract_document(pdf, DocType.GST_CERTIFICATE)
    expected = json.loads((CASES_DIR / "01_happy_path" / "documents.json").read_text())[0]["fields"]
    assert reading["detected_type"] == "GST_CERTIFICATE"
    assert reading["fields"]["gstin"] == expected["gstin"]
    assert reading["fields"]["pan"] == expected["pan"]


def test_gemini_client_is_reused_not_recreated_per_call(monkeypatch):
    """A temporary client gets garbage-collected mid-request and closes the connection (a real bug
    found with the live API), so one client per API key must be kept alive."""
    created = []
    monkeypatch.setattr(llm.genai, "Client", lambda **kwargs: created.append(kwargs) or object())
    llm._make_client.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-1")
    assert llm._client() is llm._client()
    assert len(created) == 1
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-2")
    llm._client()
    assert len(created) == 2
    llm._make_client.cache_clear()


def test_unrecognised_extractor_mode_never_uses_ai_for_email(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_MODE", "banana")
    monkeypatch.setattr(llm, "draft_vendor_email", never_called)
    from app.demo_cases import run_demo_case
    assert run_demo_case("04_wrong_document").email.generated_by == "template"
