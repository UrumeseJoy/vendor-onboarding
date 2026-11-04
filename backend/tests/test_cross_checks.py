import json
from pathlib import Path

import pytest

from app.checks.cross_checks import run_cross_checks
from app.checks.name_match import classify_score, name_score, normalise_name
from app.extraction.mock_extractor import mock_extract
from app.models import CheckResult, VendorSubmission

CASES_DIR = Path(__file__).parent.parent / "sample_data" / "cases"


def load_case(case_id: str):
    case_dir = CASES_DIR / case_id
    sub = VendorSubmission(**json.loads((case_dir / "submission.json").read_text()))
    return sub, mock_extract(case_dir, sub)


def cross(case_id):
    return run_cross_checks(*load_case(case_id))


def find(results, check_id):
    return [r for r in results if r.check_id == check_id]


def not_ok(results):
    return [r for r in results if r.result != CheckResult.PASS]


# ---- name matching ----
def test_normalise_pvt_ltd():
    assert normalise_name("ABC Pvt. Ltd.") == normalise_name("ABC Private Limited") == "abc private limited"
    assert name_score("ABC Pvt. Ltd.", "ABC Private Limited") == 100


def test_normalise_whole_words_only():
    assert "coimbatore" in normalise_name("Kaveri Coimbatore Co").split()
    assert normalise_name("Kaveri Coimbatore Co") == "kaveri coimbatore company"


def test_ampersand_expands():
    assert normalise_name("Tom & Co") == "tom and company"


def test_containment_is_not_rewarded():
    assert name_score("R. Sharma", "Sharma Electronics Private Limited") < 75


def test_warn_band_pair_and_action_required():
    # Looks like a sister entity of the same business: close, but not the same company.
    holder, legal = "Malabar Spice Exports Private Limited", "Malabar Spices Pvt Ltd"
    score = name_score(legal, holder)
    assert 75 <= score < 90
    assert classify_score(score) == CheckResult.WARN
    sub, docs = load_case("04_wrong_document")
    sub = sub.model_copy(update={"bank": sub.bank.model_copy(update={"holder_name": holder})})
    r = [x for x in run_cross_checks(sub, docs) if x.check_id == "BANK_NAME_MATCH" and x.details["compared"] == "form"][0]
    assert r.result == CheckResult.WARN and r.details["action_required"]


# ---- sample cases ----
def test_case_01_clean():
    results = cross("01_happy_path")
    assert not not_ok(results)
    names = [r for r in find(results, "BANK_NAME_MATCH")]
    assert [r.details["score"] for r in names] == [100, 100]  # form, cheque


def test_case_02_bank_name_fails_form_and_cheque():
    names = find(cross("02_bank_name_mismatch"), "BANK_NAME_MATCH")
    assert len(names) == 2
    for r in names:
        assert r.result == CheckResult.FAIL and r.details["score"] < 75
        assert r.details["review_note"]


def test_case_03_pan_gstin_mismatch():
    results = cross("03_pan_gstin_mismatch")
    pan = find(results, "PAN_IN_GSTIN")[0]
    assert pan.result == CheckResult.FAIL
    assert pan.details["pan"] == "AABCD5679G" and pan.details["pan_in_gstin"] == "AABCD5678F"
    failed_docs = {r.details["filename"] for r in find(results, "DOC_FIELDS_MATCH") if r.result == CheckResult.FAIL}
    assert failed_docs == {"gst_certificate.pdf"}  # the PAN card agrees with the form


def test_case_04_invoice_not_compared():
    docs_checked = {r.details["filename"] for r in find(cross("04_wrong_document"), "DOC_FIELDS_MATCH")}
    assert docs_checked == {"pan_card.pdf", "cancelled_cheque.pdf"}


@pytest.mark.parametrize("case_id", ["05_resubmission", "08_us_vendor", "07_duplicate_bank"])
def test_clean_cases(case_id):
    assert not not_ok(cross(case_id))


def test_case_08_has_no_india_only_checks():
    results = cross("08_us_vendor")
    assert not find(results, "PAN_IN_GSTIN") and not find(results, "GST_STATE_MATCH")


def test_case_06_untrusted_fields_skipped():
    results = cross("06_blurry_scan")
    assert all(r.result != CheckResult.FAIL for r in results)
    cheque = [r for r in find(results, "DOC_FIELDS_MATCH") if r.details["filename"] == "cancelled_cheque.pdf"][0]
    assert {"account_number", "ifsc"} <= set(cheque.details["skipped_untrusted"])
    assert not cheque.details["mismatches"]


def test_account_numbers_masked_in_mismatch_details():
    sub, docs = load_case("01_happy_path")
    sub = sub.model_copy(update={"bank": sub.bank.model_copy(update={"account_number": "99999999999999"})})
    r = [x for x in run_cross_checks(sub, docs) if x.check_id == "DOC_FIELDS_MATCH"
         and x.details["filename"] == "cancelled_cheque.pdf"][0]
    assert r.result == CheckResult.FAIL
    assert "99999999999999" not in json.dumps(r.model_dump(mode="json"))
    assert "••••9999" in r.reason


def test_kerala_address_with_tamil_nadu_gstin():
    sub, docs = load_case("01_happy_path")
    r = find(run_cross_checks(sub.model_copy(update={"state": "Kerala"}), docs), "GST_STATE_MATCH")[0]
    assert r.result == CheckResult.FAIL
    assert r.details["action_required"]
