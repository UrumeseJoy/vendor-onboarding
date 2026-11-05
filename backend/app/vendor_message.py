"""Stage 8: the message to the vendor.

- APPROVED: a fixed welcome template.
- REJECTED: a fixed neutral template. NEVER written by AI and never states a reason.
- PENDING: an AI draft (Gemini) built only from the decision's missing_items, or a template that
  lists them. An AI draft is only accepted if it passes safety_problem(); otherwise the template is used.

Only action_required text (missing_items) ever reaches the vendor (design rule 12).
"""

import logging
import re

from app import llm
from app.models import Decision, VendorEmail, VendorStatus

logger = logging.getLogger(__name__)

SIGN_OFF = "Kind regards,\nProcurement Team"
VENDOR_ID_RE = re.compile(r"VND-\d{4}-\d{4}", re.IGNORECASE)
FORBIDDEN_PHRASES = ("risk score", "fraud")
# Words in a missing item that do not need to survive in an AI rewrite
FILLER_WORDS = {"please", "upload", "provide", "your", "with", "that", "this", "from", "place", "instead", "ensure"}


def welcome_email(legal_name: str) -> VendorEmail:
    return VendorEmail(
        subject="Welcome: your vendor onboarding is complete", generated_by="template",
        body=f"Dear {legal_name},\n\nThank you for completing our vendor onboarding. Your details have been "
             f"verified and your application is approved. Our procurement team will be in touch about next "
             f"steps.\n\n{SIGN_OFF}")


def rejection_email(legal_name: str) -> VendorEmail:
    return VendorEmail(
        subject="Update on your vendor onboarding", generated_by="template",
        body=f"Dear {legal_name},\n\nThank you for your interest in working with us. We are unable to proceed "
             f"with your onboarding at this time. If you have any questions, please contact our procurement "
             f"team.\n\n{SIGN_OFF}")


def pending_template_email(legal_name: str, missing_items: list[str], fallback_reason: str | None = None) -> VendorEmail:
    if missing_items:
        bullets = "\n".join(f"- {item}" for item in missing_items)
        middle = f"To continue, please take care of the following:\n\n{bullets}\n\nOnce we receive this, we will carry on with your application."
    else:
        middle = "Our team is reviewing your submission and will contact you if we need anything further."
    return VendorEmail(
        subject="Action needed: your vendor onboarding", generated_by="template", fallback_reason=fallback_reason,
        body=f"Dear {legal_name},\n\nThank you for submitting your vendor onboarding application. "
             f"{middle}\n\n{SIGN_OFF}")


def _key_words(item: str) -> list[str]:
    words = [w.rstrip(".").lower() for w in re.findall(r"[A-Za-z0-9_.\-]+", item)]
    return [w for w in words if len(w) >= 4 and w not in FILLER_WORDS]


def _shares_phrase(text: str, note: str, size: int = 6) -> bool:
    """True if `text` contains any run of `size` consecutive words from `note`."""
    words = re.findall(r"\w+", note.lower())
    squashed = " ".join(re.findall(r"\w+", text.lower()))
    if len(words) <= size:
        return " ".join(words) in squashed
    return any(" ".join(words[i:i + size]) in squashed for i in range(len(words) - size + 1))


def safety_problem(draft: dict, missing_items: list[str], review_notes: list[str]) -> str | None:
    """Why an AI draft must not be used, or None if it is safe."""
    text = f"{draft.get('subject', '')}\n{draft.get('body', '')}"
    lowered = text.lower()
    if not draft.get("subject", "").strip() or not draft.get("body", "").strip():
        return "the AI draft was empty"
    for item in missing_items:
        missing = [w for w in _key_words(item) if w not in lowered]
        if missing:
            return f"the AI draft left out part of a requested item (missing: {', '.join(missing)})"
    if VENDOR_ID_RE.search(text):
        return "the AI draft mentioned a vendor ID"
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            return f"the AI draft contained the forbidden word '{phrase}'"
    if any(_shares_phrase(text, note) for note in review_notes):
        return "the AI draft repeated an internal review note"
    return None


def build_vendor_email(legal_name: str, decision: Decision, use_ai: bool) -> tuple[VendorEmail, str]:
    """Returns (email, one-line summary saying how it was made)."""
    if decision.status == VendorStatus.APPROVED:
        return welcome_email(legal_name), "Welcome email drafted from a fixed template."
    if decision.status == VendorStatus.REJECTED:
        return rejection_email(legal_name), "Neutral rejection email drafted from a fixed template (no reason given)."

    items = decision.missing_items
    if not items:
        return pending_template_email(legal_name, items), "Holding email drafted from a template (nothing for the vendor to fix)."
    if not use_ai:
        return pending_template_email(legal_name, items), "Email drafted from a template (AI drafting is off)."
    try:
        draft = llm.draft_vendor_email(legal_name, decision.status.value, items)
    except Exception as error:
        logger.warning("AI email draft failed: %s", error)
        reason = f"the AI draft could not be created ({type(error).__name__})"
        return (pending_template_email(legal_name, items, reason),
                f"Email drafted from a template: {reason}.")
    problem = safety_problem(draft, items, decision.review_notes)
    if problem:
        return (pending_template_email(legal_name, items, problem),
                f"Email drafted from a template: {problem}.")
    return (VendorEmail(subject=draft["subject"], body=draft["body"], generated_by="ai"),
            "Email drafted by AI and passed the safety check.")
