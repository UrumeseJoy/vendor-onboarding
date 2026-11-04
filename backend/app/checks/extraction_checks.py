"""Stage 2 checks: could each document be read, and were the values read clearly?"""

from app.checks.base import doc_label, field_label, join_words, lower_label, make_check
from app.config import get_rules
from app.models import CheckOutcome, CheckResult, DocType, ExtractedDocument, Stage


def untrusted_fields(doc: ExtractedDocument) -> set[str]:
    """Fields read with confidence below min_field_confidence. Later stages must not trust these."""
    minimum = get_rules().extraction.min_field_confidence
    return {name for name, conf in doc.field_confidence.items() if conf < minimum}


def is_unreadable(doc: ExtractedDocument) -> bool:
    return doc.detected_type == DocType.UNKNOWN and not doc.fields


def check_doc_readable(doc: ExtractedDocument) -> CheckOutcome:
    if is_unreadable(doc):
        return make_check(
            "DOC_READABLE", Stage.EXTRACTION, CheckResult.FAIL,
            f"We couldn't read {doc.filename} or tell what type of document it is.",
            {"filename": doc.filename, "claimed": doc.slot.value,
             "action_required": f"Please upload a clear, readable copy of your {lower_label(doc.slot)}."})
    return make_check(
        "DOC_READABLE", Stage.EXTRACTION, CheckResult.PASS,
        f"{doc.filename} was read successfully (it looks like: {doc_label(doc.detected_type)}).",
        {"filename": doc.filename, "detected": doc.detected_type.value})


def check_extraction_confidence(doc: ExtractedDocument) -> CheckOutcome:
    rules = get_rules().extraction
    low = {name: doc.field_confidence[name] for name in doc.field_confidence if name in untrusted_fields(doc)}
    low_overall = doc.overall_confidence < rules.min_document_confidence
    if low or low_overall:
        if low:
            names = join_words([field_label(n) for n in low])
            reason = f"We couldn't clearly read the {names} on {doc.filename}."
        else:
            reason = f"We couldn't clearly read {doc.filename}; the scan quality is too low."
        return make_check(
            "EXTRACTION_CONFIDENCE", Stage.EXTRACTION, CheckResult.FAIL, reason,
            {"filename": doc.filename, "low_confidence_fields": low,
             "overall_confidence": round(doc.overall_confidence, 2),
             "action_required": f"Please upload a clearer photo or scan of your {lower_label(doc.slot)}."})
    return make_check(
        "EXTRACTION_CONFIDENCE", Stage.EXTRACTION, CheckResult.PASS,
        f"All values on {doc.filename} were read clearly.",
        {"filename": doc.filename, "overall_confidence": round(doc.overall_confidence, 2)})


def run_extraction_checks(docs: list[ExtractedDocument]) -> list[CheckOutcome]:
    """DOC_READABLE for every document; EXTRACTION_CONFIDENCE for every readable one
    (an unreadable file is already reported, so we don't report it twice)."""
    results = []
    for doc in docs:
        results.append(check_doc_readable(doc))
        if not is_unreadable(doc):
            results.append(check_extraction_confidence(doc))
    return results
