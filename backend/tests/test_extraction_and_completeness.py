import json
from pathlib import Path

from app.checks.completeness_checks import run_completeness_checks
from app.checks.extraction_checks import run_extraction_checks, untrusted_fields
from app.extraction.mock_extractor import mock_extract
from app.models import CheckResult, DocType, UploadedDocument, VendorSubmission

CASES_DIR = Path(__file__).parent.parent / "sample_data" / "cases"


def load_case(case_id: str):
    case_dir = CASES_DIR / case_id
    sub = VendorSubmission(**json.loads((case_dir / "submission.json").read_text()))
    return case_dir, sub, mock_extract(case_dir, sub)


def run_all(sub, docs):
    return run_extraction_checks(docs) + run_completeness_checks(sub, docs)


def find(results, check_id, filename=None):
    return [r for r in results if r.check_id == check_id
            and (filename is None or r.details.get("filename") == filename)]


def assert_fails_have_action(results):
    for r in results:
        if r.result == CheckResult.FAIL:
            assert r.details.get("action_required"), f"{r.check_id} has no action_required"


def test_mock_extract_case_01():
    _, _, docs = load_case("01_happy_path")
    assert len(docs) == 3
    assert all(d.detected_type == d.slot for d in docs)
    assert all(0 < d.overall_confidence <= 1 for d in docs)


def test_case_01_has_no_fail_or_warn():
    _, sub, docs = load_case("01_happy_path")
    assert all(r.result == CheckResult.PASS for r in run_all(sub, docs))


def test_case_04_wrong_document():
    _, sub, docs = load_case("04_wrong_document")
    results = run_all(sub, docs)
    mismatch = find(results, "DOC_TYPE_MATCH", "gst_certificate.pdf")[0]
    assert mismatch.result == CheckResult.FAIL
    assert mismatch.details["claimed"] == "GST_CERTIFICATE" and mismatch.details["detected"] == "INVOICE"
    missing = find(results, "REQUIRED_DOCUMENTS")[0]
    assert missing.result == CheckResult.FAIL
    assert "GST registration certificate" in missing.reason
    assert_fails_have_action(results)


def test_case_06_blurry_cheque():
    _, sub, docs = load_case("06_blurry_scan")
    results = run_all(sub, docs)
    r = find(results, "EXTRACTION_CONFIDENCE", "cancelled_cheque.pdf")[0]
    assert r.result == CheckResult.FAIL
    assert {"account_number", "ifsc"} <= set(r.details["low_confidence_fields"])
    cheque = next(d for d in docs if d.filename == "cancelled_cheque.pdf")
    assert {"account_number", "ifsc"} <= untrusted_fields(cheque)
    assert_fails_have_action(results)
    # the other documents are fine
    assert find(results, "EXTRACTION_CONFIDENCE", "gst_certificate.pdf")[0].result == CheckResult.PASS


def test_case_08_us_documents_satisfied():
    _, sub, docs = load_case("08_us_vendor")
    assert find(run_completeness_checks(sub, docs), "REQUIRED_DOCUMENTS")[0].result == CheckResult.PASS


def test_bank_letter_satisfies_indian_bank_requirement():
    _, sub, docs = load_case("01_happy_path")
    for d in docs:
        if d.slot == DocType.CANCELLED_CHEQUE:
            d.slot = d.detected_type = DocType.BANK_LETTER
    assert find(run_completeness_checks(sub, docs), "REQUIRED_DOCUMENTS")[0].result == CheckResult.PASS


def test_missing_ifsc_fails_required_fields():
    _, sub, docs = load_case("01_happy_path")
    sub = sub.model_copy(update={"bank": sub.bank.model_copy(update={"ifsc": ""})})
    results = run_completeness_checks(sub, docs)
    r = find(results, "REQUIRED_FIELDS")[0]
    assert r.result == CheckResult.FAIL
    assert "IFSC" in r.reason
    assert_fails_have_action(results)


def test_file_missing_from_documents_json_is_unknown_and_unreadable():
    case_dir, sub, _ = load_case("01_happy_path")
    sub = sub.model_copy(update={"documents": sub.documents + [UploadedDocument(slot=DocType.PAN_CARD, filename="mystery.pdf")]})
    docs = mock_extract(case_dir, sub)
    mystery = docs[-1]
    assert mystery.detected_type == DocType.UNKNOWN and mystery.fields == {} and mystery.overall_confidence == 0
    results = run_extraction_checks(docs)
    r = find(results, "DOC_READABLE", "mystery.pdf")[0]
    assert r.result == CheckResult.FAIL
    assert_fails_have_action(results)
