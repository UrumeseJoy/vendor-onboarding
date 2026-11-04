import json
from pathlib import Path

import pytest

from app.checks.base import MissingSeverityError, make_check
from app.checks.format_checks import (
    check_ein_format, check_gstin_checksum, check_gstin_format, check_ifsc_format,
    check_pan_format, check_routing_format, run_format_checks,
)
from app.models import CheckResult, Severity, Stage, VendorSubmission

CASES_DIR = Path(__file__).parent.parent / "sample_data" / "cases"
VALID_GSTIN = "33AABCS1234K1ZN"


def case_submission(case_id: str) -> VendorSubmission:
    return VendorSubmission(**json.loads((CASES_DIR / case_id / "submission.json").read_text()))


def ids_of(outcomes):
    return [o.check_id for o in outcomes]


# ---- PAN ----
def test_pan_valid_company_passes():
    r = check_pan_format("AABCS1234K")
    assert r.result == CheckResult.PASS and r.stage == Stage.FORMAT


def test_pan_bad_format_fails_with_example():
    r = check_pan_format("ABC123")
    assert r.result == CheckResult.FAIL
    assert "ABCDE1234F" in r.reason


def test_pan_individual_is_warn():
    r = check_pan_format("AABPS1234K")
    assert r.result == CheckResult.WARN
    assert r.details["holder_type"] == "Individual"


# ---- GSTIN ----
def test_gstin_valid_passes():
    assert check_gstin_format(VALID_GSTIN).result == CheckResult.PASS
    assert check_gstin_checksum(VALID_GSTIN).result == CheckResult.PASS


def test_gstin_wrong_length_fails_and_checksum_not_run():
    sub = case_submission("01_happy_path").model_copy(update={"gstin": VALID_GSTIN[:14]})
    results = run_format_checks(sub)
    assert "GSTIN_FORMAT" in ids_of(results)
    assert "GSTIN_CHECKSUM" not in ids_of(results)
    assert next(r for r in results if r.check_id == "GSTIN_FORMAT").result == CheckResult.FAIL


def test_gstin_wrong_check_character_fails_checksum():
    bad = VALID_GSTIN[:14] + "Q"
    assert check_gstin_format(bad).result == CheckResult.PASS
    r = check_gstin_checksum(bad)
    assert r.result == CheckResult.FAIL
    assert r.details["expected"] == "N" and r.details["found"] == "Q"


# ---- IFSC ----
def test_ifsc_valid_passes():
    assert check_ifsc_format("HDFC0001234").result == CheckResult.PASS


def test_ifsc_fifth_char_not_zero_fails_soft():
    r = check_ifsc_format("HDFC1001234")
    assert r.result == CheckResult.FAIL
    assert r.severity == Severity.SOFT


# ---- EIN and routing ----
def test_ein():
    assert check_ein_format("84-1234567").result == CheckResult.PASS
    r = check_ein_format("841234567")
    assert r.result == CheckResult.FAIL and r.severity == Severity.HARD


def test_routing():
    assert check_routing_format("123456780").result == CheckResult.PASS
    bad_checksum = check_routing_format("123456781")
    assert bad_checksum.result == CheckResult.FAIL and bad_checksum.severity == Severity.SOFT
    assert check_routing_format("12345").result == CheckResult.FAIL


# ---- run_format_checks ----
def test_us_submission_runs_only_us_checks():
    assert ids_of(run_format_checks(case_submission("08_us_vendor"))) == ["EIN_FORMAT", "ROUTING_FORMAT"]


def test_indian_submission_runs_only_indian_checks():
    assert ids_of(run_format_checks(case_submission("01_happy_path"))) == [
        "PAN_FORMAT", "GSTIN_FORMAT", "GSTIN_CHECKSUM", "IFSC_FORMAT"]


def test_missing_gstin_skips_gstin_checks():
    sub = case_submission("01_happy_path").model_copy(update={"gstin": None})
    assert ids_of(run_format_checks(sub)) == ["PAN_FORMAT", "IFSC_FORMAT"]


@pytest.mark.parametrize("case_id", sorted(p.name for p in CASES_DIR.iterdir() if p.is_dir()))
def test_sample_cases_have_no_format_failures(case_id):
    results = run_format_checks(case_submission(case_id))
    assert results
    assert all(r.result != CheckResult.FAIL for r in results)


# ---- make_check ----
def test_make_check_requires_configured_severity():
    with pytest.raises(MissingSeverityError, match="INTAKE_VALID"):
        make_check("INTAKE_VALID", Stage.INTAKE, CheckResult.PASS, "ok")
