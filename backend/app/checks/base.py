"""Shared helper for building check results."""

from app.config import get_rules
from app.models import DOC_TYPE_LABELS, CheckOutcome, CheckResult, DocType, Stage


class MissingSeverityError(ValueError):
    """A check ID has no severity in rules.yaml."""


def make_check(check_id: str, stage: Stage, result: CheckResult, reason: str,
               details: dict | None = None) -> CheckOutcome:
    """Build a CheckOutcome. The severity always comes from rules.yaml, never a default."""
    severity = get_rules().check_severity.get(check_id)
    if severity is None:
        raise MissingSeverityError(
            f"No severity configured for check '{check_id}'. Add it to check_severity in rules.yaml."
        )
    return CheckOutcome(check_id=check_id, stage=stage, result=result, severity=severity,
                        reason=reason, details=details or {})


# ---------- Plain-English text helpers shared by the checks ----------

FIELD_LABELS = {
    "legal_name": "company name", "state": "state", "address": "address",
    "contact_email": "contact email", "pan": "PAN", "gstin": "GSTIN", "ein": "EIN",
    "bank.holder_name": "bank account holder name", "bank.account_number": "bank account number",
    "bank.ifsc": "bank IFSC code", "bank.routing_number": "bank routing number",
    "holder_name": "account holder name", "account_number": "account number", "ifsc": "IFSC",
    "routing_number": "routing number", "bank_name": "bank name",
}


def field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field.replace("_", " "))


def join_words(items: list[str], last_word: str = "and") -> str:
    """['a', 'b', 'c'] -> 'a, b and c'."""
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} {last_word} {items[-1]}"


def doc_label(doc_type: DocType) -> str:
    return DOC_TYPE_LABELS[doc_type.value]


def lower_label(doc_type: DocType) -> str:
    """Label for use mid-sentence: lowercase the first word unless it is an acronym (GST, PAN)."""
    label = doc_label(doc_type)
    return label[0].lower() + label[1:] if label[1].islower() else label


def with_article(text: str) -> str:
    return ("an " if text[0].lower() in "aeiou" else "a ") + text
