import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import RulesConfig
from app.checks.risk_checks import compute_risk_score, run_risk_checks
from app.security import account_fingerprint, bank_code_for, last4
from app.models import CheckResult, Country, KnownAccount, Severity, VendorSubmission
from tests.test_config import raw_rules

CASES_DIR = Path(__file__).parent.parent / "sample_data" / "cases"


def load_sub(case_id: str) -> VendorSubmission:
    return VendorSubmission(**json.loads((CASES_DIR / case_id / "submission.json").read_text()))


def known_from(case_id: str, vendor_id: str, bank_code: str | None = None) -> KnownAccount:
    """A known account for a case's bank account. bank_code overrides the IFSC/routing number."""
    sub = load_sub(case_id)
    code = bank_code if bank_code is not None else bank_code_for(sub)
    return KnownAccount(vendor_id=vendor_id, legal_name=sub.legal_name,
                        account_fingerprint=account_fingerprint(sub.bank.account_number, code),
                        account_last4=last4(sub.bank.account_number))


def by_id(results, check_id):
    return next(r for r in results if r.check_id == check_id)


def test_case_01_clean_no_known_accounts():
    results = run_risk_checks(load_sub("01_happy_path"), "VND-2026-0001", [])
    assert all(r.result == CheckResult.PASS for r in results)
    assert compute_risk_score(results) == 0


def test_free_email_scores_15():
    sub = load_sub("01_happy_path").model_copy(update={"contact_email": "sharmaelec@gmail.com"})
    results = run_risk_checks(sub, "VND-2026-0001", [])
    assert by_id(results, "FREE_EMAIL_DOMAIN").result == CheckResult.FAIL
    assert compute_risk_score(results) == 15


def test_bank_country_mismatch_scores_30():
    sub = load_sub("01_happy_path")
    sub = sub.model_copy(update={"bank": sub.bank.model_copy(update={"bank_country": Country.US})})
    results = run_risk_checks(sub, "VND-2026-0001", [])
    assert by_id(results, "BANK_COUNTRY_MISMATCH").result == CheckResult.FAIL
    assert compute_risk_score(results) == 30


def test_both_flags_score_45():
    sub = load_sub("01_happy_path")
    sub = sub.model_copy(update={"contact_email": "x@yahoo.com",
                                 "bank": sub.bank.model_copy(update={"bank_country": Country.US})})
    assert compute_risk_score(run_risk_checks(sub, "VND-2026-0001", [])) == 45


def test_case_07_duplicate_of_case_01():
    sub = load_sub("07_duplicate_bank")
    results = run_risk_checks(sub, "VND-2026-0007", [known_from("01_happy_path", "VND-2026-0001")])
    dup = by_id(results, "DUPLICATE_BANK_ACCOUNT")
    assert dup.result == CheckResult.FAIL and dup.severity == Severity.HARD
    assert dup.details["other_vendor_id"] == "VND-2026-0001"
    assert dup.details["other_vendor_name"] == "Sharma Electronics Pvt Ltd"
    assert dup.details["review_note"] and "action_required" not in dup.details
    assert compute_risk_score(results) == 100


def test_resubmission_does_not_match_itself():
    sub = load_sub("05_resubmission")
    results = run_risk_checks(sub, "VND-2026-0004", [known_from("04_wrong_document", "VND-2026-0004")])
    assert by_id(results, "DUPLICATE_BANK_ACCOUNT").result == CheckResult.PASS


def test_same_account_different_ifsc_passes():
    known = known_from("01_happy_path", "VND-2026-0001", bank_code="ICIC0002345")
    results = run_risk_checks(load_sub("07_duplicate_bank"), "VND-2026-0007", [known])
    assert by_id(results, "DUPLICATE_BANK_ACCOUNT").result == CheckResult.PASS


def test_us_duplicate_uses_routing_number():
    sub = load_sub("08_us_vendor")
    known = known_from("08_us_vendor", "VND-2026-0008")
    assert by_id(run_risk_checks(sub, "VND-2026-0009", [known]), "DUPLICATE_BANK_ACCOUNT").result == CheckResult.FAIL
    other_bank = known_from("08_us_vendor", "VND-2026-0008", bank_code="021000021")
    assert by_id(run_risk_checks(sub, "VND-2026-0009", [other_bank]), "DUPLICATE_BANK_ACCOUNT").result == CheckResult.PASS


def test_full_account_number_never_in_outcomes():
    sub = load_sub("07_duplicate_bank")
    results = run_risk_checks(sub, "VND-2026-0007", [known_from("01_happy_path", "VND-2026-0001")])
    text = json.dumps([r.model_dump(mode="json") for r in results], ensure_ascii=False)
    assert sub.bank.account_number not in text
    assert "••••5678" in text


def test_risk_flag_severity_must_agree_with_check_severity():
    data = raw_rules()
    data["risk"]["flags"]["FREE_EMAIL_DOMAIN"]["severity"] = "HARD"
    with pytest.raises(ValidationError, match="FREE_EMAIL_DOMAIN"):
        RulesConfig(**data)


def test_review_threshold_must_be_0_to_100():
    data = raw_rules()
    data["risk"]["review_threshold"] = 150
    with pytest.raises(ValidationError):
        RulesConfig(**data)


def test_fingerprint_is_stable_ignores_spaces_and_depends_on_bank_code():
    a = account_fingerprint("5020 0012 345678", "hdfc0001234")
    assert a == account_fingerprint("50200012345678", "HDFC0001234")
    assert a != account_fingerprint("50200012345678", "ICIC0002345")
    assert a != account_fingerprint("50200012345679", "HDFC0001234")
    assert "50200012345678" not in a and len(a) == 64


def test_fingerprint_depends_on_the_secret_key(monkeypatch):
    monkeypatch.setenv("ACCOUNT_HASH_KEY", "key-one")
    one = account_fingerprint("50200012345678", "HDFC0001234")
    monkeypatch.setenv("ACCOUNT_HASH_KEY", "key-two")
    assert one != account_fingerprint("50200012345678", "HDFC0001234")
