import pytest

from app.demo_cases import CASES_DIR, load_expected, load_index, load_submission, run_demo_case
from app.extraction.mock_extractor import mock_extract
from app.models import CheckResult, Country, Stage, StageStatus, VendorStatus
from app.pipeline import run_pipeline

STAGE_ORDER = list(Stage)
CASE_IDS = [entry["case_id"] for entry in load_index()]


def stage(run, s: Stage):
    return next(r for r in run.stages if r.stage == s)


def all_checks(run):
    return [c for r in run.stages for c in r.checks]


def run_case01_with(**updates):
    """Run case 01 with some submission fields changed (bank fields via bank=dict)."""
    sub = load_submission("01_happy_path")
    bank_updates = updates.pop("bank", None)
    if bank_updates:
        updates["bank"] = sub.bank.model_copy(update=bank_updates)
    sub = sub.model_copy(update=updates)
    return run_pipeline(sub, "VND-2026-0001", lambda s: mock_extract(CASES_DIR / "01_happy_path", s), [])


# ---- every sample case ----

@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_matches_expected(case_id):
    expected = load_expected(case_id)
    run = run_demo_case(case_id)
    assert run.decision.status.value == expected["expected_status"]
    not_passed = {c.check_id for c in all_checks(run) if c.result in (CheckResult.FAIL, CheckResult.WARN)}
    assert set(expected["expected_failed_checks"]) <= not_passed
    assert [r.stage for r in run.stages] == STAGE_ORDER
    assert not run.had_errors


def test_case_01_approved_all_stages_passed():
    run = run_demo_case("01_happy_path")
    assert run.decision.status == VendorStatus.APPROVED
    assert run.decision.missing_items == []
    for r in run.stages:
        expected = StageStatus.SKIPPED if r.stage == Stage.VENDOR_MESSAGE else StageStatus.PASSED
        assert r.status == expected, r.stage
    assert run.decision.checks_summary["FAIL"] == 0


def test_case_04_pending_asks_for_gst_certificate():
    d = run_demo_case("04_wrong_document").decision
    assert d.status == VendorStatus.PENDING
    assert d.missing_items == [
        "Please upload your GST registration certificate (Form GST REG-06) in place of gst_certificate.pdf."]


def test_case_02_rejected_with_review_notes():
    d = run_demo_case("02_bank_name_mismatch").decision
    assert d.status == VendorStatus.REJECTED
    assert d.missing_items == []
    assert d.review_notes


# ---- risk score and the review threshold ----

def test_free_email_alone_still_approved():
    run = run_case01_with(contact_email="sharmaelec@gmail.com")
    assert run.decision.status == VendorStatus.APPROVED
    assert stage(run, Stage.RISK).status == StageStatus.WARNING
    assert any(line.startswith("Note:") for line in run.decision.reasons)
    assert run.decision.risk_score == 15


def test_free_email_and_bank_country_reach_threshold():
    run = run_case01_with(contact_email="sharmaelec@gmail.com", bank={"bank_country": Country.US})
    assert run.decision.status == VendorStatus.PENDING
    assert run.decision.risk_score == 45
    assert any("Risk score 45" in line for line in run.decision.reasons)


# ---- fail safe ----

def test_extractor_error_is_fail_safe():
    def broken_extractor(submission):
        raise RuntimeError("Gemini unavailable")

    run = run_pipeline(load_submission("01_happy_path"), "VND-2026-0001", broken_extractor, [])
    assert run.had_errors
    extraction = stage(run, Stage.EXTRACTION)
    assert extraction.status == StageStatus.FAILED
    assert "Processing error" in extraction.summary and "Gemini unavailable" in extraction.summary
    assert run.decision.status != VendorStatus.APPROVED
    assert [r.stage for r in run.stages] == STAGE_ORDER
    assert all(r.finished_at is not None for r in run.stages)
    assert any("EXTRACTION" in line for line in run.decision.reasons)


# ---- on_stage callback ----

def test_on_stage_called_running_then_final_in_order():
    events = []
    run_demo_case("01_happy_path", on_stage=lambda r: events.append((r.stage, r.status)))
    assert len(events) == 2 * len(STAGE_ORDER)
    assert [s for s, _ in events[0::2]] == STAGE_ORDER
    assert [s for s, _ in events[1::2]] == STAGE_ORDER
    assert all(status == StageStatus.RUNNING for _, status in events[0::2])
    assert all(status != StageStatus.RUNNING for _, status in events[1::2])


def test_failing_callback_does_not_break_run():
    def bad_callback(result):
        raise ValueError("UI disconnected")

    run = run_demo_case("01_happy_path", on_stage=bad_callback)
    assert run.decision.status == VendorStatus.APPROVED
    assert not run.had_errors
    assert len(run.stages) == len(STAGE_ORDER)


# ---- determinism ----

def test_same_input_same_output():
    def comparable(run):
        return {
            "decision": run.decision.model_dump(mode="json"),
            "stages": [r.model_dump(mode="json", exclude={"started_at", "finished_at"}) for r in run.stages],
        }

    for case_id in ["04_wrong_document", "07_duplicate_bank"]:
        assert comparable(run_demo_case(case_id)) == comparable(run_demo_case(case_id))
