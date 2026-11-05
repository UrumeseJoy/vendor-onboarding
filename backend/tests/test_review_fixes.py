"""Regression tests for the bugs found in the full project review. Each failed before its fix."""

import copy
import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from google.genai import errors
from sqlmodel import Session

from app import llm
from app.checks.format_checks import check_ifsc_format, check_routing_format
from app.config import RULES_PATH, RulesError, load_rules
from app.db import PROCESSING, Vendor, get_engine, init_db
from app.demo_cases import CASES_DIR, load_submission
from app.extraction.mock_extractor import mock_extract
from app.main import app
from app.models import CheckResult, ExtractedDocument, VendorStatus
from app.pipeline import run_pipeline
from app.service import process_submission

BACKEND = Path(__file__).parent.parent


def case_extractor(case_id):
    return lambda submission: mock_extract(CASES_DIR / case_id, submission)


def run_case(submission, case_id, extractor=None):
    return run_pipeline(submission, "VND-2026-0099", extractor or case_extractor(case_id), [], ai_emails=False)


# ---------- 1. a rejected impostor must not get the real vendor rejected ----------

def test_real_vendor_resubmitting_is_not_a_duplicate_of_a_rejected_impostor(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    init_db(engine)
    with Session(engine) as session:
        real = process_submission(session, load_submission("01_happy_path"), case_extractor("01_happy_path"))
        impostor = process_submission(session, load_submission("07_duplicate_bank"),
                                      case_extractor("07_duplicate_bank"))
        again = process_submission(session, load_submission("01_happy_path"), case_extractor("01_happy_path"),
                                   vendor_id=real.vendor_id)
    assert impostor.decision.status == VendorStatus.REJECTED  # the impostor is still caught
    assert again.decision.status == VendorStatus.APPROVED


def test_vendor_rejected_for_another_reason_still_holds_its_account(tmp_path):
    """Case 02 was rejected for a bank name mismatch: its account may belong to a bad actor, so reuse is flagged."""
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    init_db(engine)
    with Session(engine) as session:
        first = process_submission(session, load_submission("02_bank_name_mismatch"),
                                   case_extractor("02_bank_name_mismatch"))
        reuse = load_submission("01_happy_path")
        reuse.bank = load_submission("02_bank_name_mismatch").bank.model_copy()
        second = process_submission(session, reuse, case_extractor("01_happy_path"))
    assert first.decision.status == VendorStatus.REJECTED
    flagged = [c for s in second.stages for c in s.checks
               if c.check_id == "DUPLICATE_BANK_ACCOUNT" and c.result == CheckResult.FAIL]
    assert flagged and flagged[0].details["other_vendor_id"] == first.vendor_id


# ---------- 2. a failed read must not ask the vendor for documents they already sent ----------

def test_extraction_error_never_asks_for_documents_already_uploaded():
    def broken(submission):
        raise RuntimeError("Gemini is overloaded")

    run = run_case(load_submission("01_happy_path"), "01_happy_path", extractor=broken)
    assert run.decision.status == VendorStatus.PENDING and run.had_errors
    assert not any("upload" in item.lower() for item in run.decision.missing_items)
    assert "upload" not in run.email.body.lower()
    completeness = next(s for s in run.stages if s.stage.value == "COMPLETENESS")
    assert [c.check_id for c in completeness.checks] == ["REQUIRED_FIELDS"]


# ---------- 3. a vendor left PROCESSING by a crash is recovered on startup ----------

def test_vendor_left_processing_is_recovered_on_startup(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    url = f"sqlite:///{tmp_path}/api.db"
    engine = get_engine(url)
    init_db(engine)
    with Session(engine) as session:  # the state a crash mid-run leaves behind
        now = datetime.now(timezone.utc)
        session.add(Vendor(vendor_id="VND-2026-0001", legal_name="Stuck Ltd", country="IN", status=PROCESSING,
                           risk_score=0, created_at=now, updated_at=now))
        session.commit()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    with TestClient(app) as client:
        vendor = client.get("/api/vendors/VND-2026-0001").json()
        assert vendor["status"] == "PENDING"  # never APPROVED, and no longer "processing" forever
        assert client.get("/api/stats").json()["status_counts"]["PENDING"] == 1


# ---------- 4. IFSC / routing typos tell the vendor what to fix (rule 9) ----------

def test_ifsc_typo_with_an_unreadable_cheque_asks_the_vendor_to_fix_it():
    submission = load_submission("06_blurry_scan")
    submission.bank.ifsc = "HDFC1001234"  # 5th character must be 0
    run = run_case(submission, "06_blurry_scan")
    assert run.decision.status == VendorStatus.PENDING
    assert any("IFSC" in item for item in run.decision.missing_items)


@pytest.mark.parametrize("routing", ["12345", "123456789"])  # wrong length; fails the ABA checksum
def test_routing_format_failures_carry_a_vendor_action(routing):
    outcome = check_routing_format(routing)
    assert outcome.result == CheckResult.FAIL and "routing number" in outcome.details["action_required"]


def test_ifsc_format_failure_carries_a_vendor_action():
    assert "IFSC" in check_ifsc_format("BAD").details["action_required"]


# ---------- 5. the reader's free-text notes never keep a full account number ----------

def test_notes_quoting_an_account_number_are_masked():
    def reader(submission):
        return [ExtractedDocument(
            filename=d.filename, slot=d.slot, detected_type=d.slot, fields={"account_number": "50100123455678"},
            field_confidence={"account_number": 1.0}, overall_confidence=1.0,
            notes=["Account number 5010 0123 4556 78 is printed twice.", "Dated 2026-01-15.",
                   "A second account 12345678 is crossed out."])
            for d in submission.documents]

    run = run_case(load_submission("01_happy_path"), "01_happy_path", extractor=reader)
    notes = " ".join(n for d in run.documents for n in d.notes)
    assert "5010 0123 4556 78" not in notes and "••••5678" in notes
    assert "2026-01-15" in notes  # short numbers such as dates are left alone


# ---------- 6. an incomplete rules.yaml fails at load time ----------

def _broken(change):
    data = copy.deepcopy(yaml.safe_load(RULES_PATH.read_text()))
    change(data)
    return data


@pytest.mark.parametrize("change", [
    lambda d: d["check_severity"].pop("IFSC_FORMAT"),
    lambda d: d["risk"]["flags"].pop("FREE_EMAIL_DOMAIN"),
    lambda d: d["required_fields"].pop("US"),
    lambda d: d["required_documents"].pop("US"),
    lambda d: d["required_fields"]["IN"].append("bank.ifcs"),
], ids=["missing-severity", "missing-risk-flag", "missing-country-fields", "missing-country-docs", "typo-field"])
def test_incomplete_rules_file_is_rejected(tmp_path, change):
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(_broken(change)))
    with pytest.raises(RulesError):
        load_rules(path)


# ---------- 7. a spent daily quota is not retried ----------

def test_daily_quota_error_from_the_sdk_is_not_retried():
    quota = errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message":
                                              "Quota exceeded for GenerateRequestsPerDayPerProjectPerModel-FreeTier"}})
    calls, sleeps = [], []

    def failing():
        calls.append(1)
        raise quota

    with pytest.raises(llm.LLMError) as info:
        llm._with_retries(failing, sleep=sleeps.append)
    assert info.value.kind == "daily_quota" and len(calls) == 1 and sleeps == []


# ---------- 9. .env.example lists every setting the code reads ----------

def test_env_example_lists_every_setting_the_code_reads():
    read = set()
    for path in (BACKEND / "app").rglob("*.py"):
        read |= set(re.findall(r'getenv\("([A-Z_]+)"', path.read_text()))
    example = (BACKEND / ".env.example").read_text()
    assert read and not [name for name in read if name not in example]

