"""Stage 3 checks: is everything required present, and is each file the type claimed?"""

from app.checks.base import action_label, doc_label, field_label, join_words, make_check, with_article
from app.config import get_rules
from app.models import CheckOutcome, CheckResult, DocType, ExtractedDocument, Stage, VendorSubmission


def _value(submission: VendorSubmission, dotted: str):
    """Read 'bank.ifsc' style paths from the submission."""
    obj = submission
    for part in dotted.split("."):
        obj = getattr(obj, part, None)
    return obj


def check_required_fields(submission: VendorSubmission) -> CheckOutcome:
    required = get_rules().required_fields[submission.country]
    missing = [f for f in required if not _value(submission, f)]
    if missing:
        names = join_words([field_label(f) for f in missing])
        return make_check(
            "REQUIRED_FIELDS", Stage.COMPLETENESS, CheckResult.FAIL,
            f"Required details are missing: {names}.",
            {"missing_fields": missing, "action_required": f"Please provide: {names}."})
    return make_check("REQUIRED_FIELDS", Stage.COMPLETENESS, CheckResult.PASS,
                      "All required details were provided.", {"checked_fields": required})


def check_required_documents(submission: VendorSubmission, docs: list[ExtractedDocument]) -> CheckOutcome:
    detected = {d.detected_type for d in docs}  # what the files really are, not what the vendor claimed
    groups = get_rules().required_documents[submission.country]
    unmet = [group for group in groups if not detected & set(group)]
    if unmet:
        missing = [" or ".join(doc_label(t) for t in group) for group in unmet]
        to_upload = [" or ".join(action_label(t) for t in group) for group in unmet]
        return make_check(
            "REQUIRED_DOCUMENTS", Stage.COMPLETENESS, CheckResult.FAIL,
            f"Required documents are missing: {'; '.join(missing)}.",
            {"missing_documents": missing, "action_required": f"Please upload: {'; '.join(to_upload)}."})
    return make_check("REQUIRED_DOCUMENTS", Stage.COMPLETENESS, CheckResult.PASS,
                      "All required documents were provided.")


def check_doc_type_match(doc: ExtractedDocument) -> CheckOutcome:
    details = {"filename": doc.filename, "claimed": doc.slot.value, "detected": doc.detected_type.value}
    if doc.detected_type != doc.slot:
        if doc.detected_type == DocType.UNKNOWN:
            what = "could not be recognised as that type of document"
        else:
            what = f"appears to be {with_article(doc_label(doc.detected_type))}"
        return make_check(
            "DOC_TYPE_MATCH", Stage.COMPLETENESS, CheckResult.FAIL,
            f"The file uploaded as {doc_label(doc.slot)} ({doc.filename}) {what}.",
            {**details, "action_required":
                f"Please upload your {action_label(doc.slot)} in place of {doc.filename}."})
    return make_check("DOC_TYPE_MATCH", Stage.COMPLETENESS, CheckResult.PASS,
                      f"{doc.filename} is the {doc_label(doc.slot)} as expected.", details)


def run_completeness_checks(submission: VendorSubmission, docs: list[ExtractedDocument]) -> list[CheckOutcome]:
    return ([check_required_fields(submission), check_required_documents(submission, docs)]
            + [check_doc_type_match(d) for d in docs])
