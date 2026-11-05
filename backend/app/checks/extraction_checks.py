"""Stage 2 checks: could each document be read, and were the values read clearly?"""

from app.checks.base import action_label, doc_label, field_label, join_words, make_check
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
             "action_required": f"Please upload a clear, readable copy of your {action_label(doc.slot)}."})
    return make_check(
        "DOC_READABLE", Stage.EXTRACTION, CheckResult.PASS,
        f"{doc.filename} was read successfully (it looks like: {doc_label(doc.detected_type)}).",
        {"filename": doc.filename, "detected": doc.detected_type.value})


def missing_expected_fields(doc: ExtractedDocument) -> list[str]:
    """Expected field groups with no field found on the document, e.g. ["ifsc"] or ["ifsc or routing_number"].
    Only for documents that are what the vendor claimed (and are a type we have expectations for)."""
    if doc.detected_type != doc.slot or doc.detected_type in (DocType.UNKNOWN, DocType.INVOICE):
        return []
    groups = get_rules().expected_fields.get(doc.detected_type, [])
    return [" or ".join(group) for group in groups if not any(name in doc.fields for name in group)]


def check_extraction_confidence(doc: ExtractedDocument) -> CheckOutcome:
    rules = get_rules().extraction
    low = {name: doc.field_confidence[name] for name in doc.field_confidence if name in untrusted_fields(doc)}
    missing = missing_expected_fields(doc)
    low_overall = doc.overall_confidence < rules.min_document_confidence
    if low or missing or low_overall:
        sentences = []
        if low:
            names = join_words([field_label(n) for n in low])
            sentences.append(f"We couldn't clearly read the {names} on {doc.filename}.")
        if missing:
            names = join_words([" or ".join(field_label(f) for f in group.split(" or ")) for group in missing])
            sentences.append(f"We couldn't find the {names} on {doc.filename}.")
        if not sentences:
            sentences.append(f"We couldn't clearly read {doc.filename}; the scan quality is too low.")
        action = f"Please upload a clearer photo or scan of your {action_label(doc.slot)}"
        if missing:
            shown = join_words([" or ".join(field_label(f) for f in group.split(" or ")) for group in missing])
            action += f", making sure the {shown} can be seen clearly"
        return make_check(
            "EXTRACTION_CONFIDENCE", Stage.EXTRACTION, CheckResult.FAIL, " ".join(sentences),
            {"filename": doc.filename, "low_confidence_fields": low, "missing_fields": missing,
             "overall_confidence": round(doc.overall_confidence, 2), "action_required": action + "."})
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
