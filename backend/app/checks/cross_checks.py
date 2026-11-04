"""Stage 5 checks: do the form, the documents and the IDs agree with each other?

Fields the extractor was not confident about (untrusted) are skipped, never reported
as mismatches. HARD failures that point to possible fraud carry details["review_note"]
for the internal team instead of a vendor instruction.
"""

from app.checks.base import field_label, join_words, make_check
from app.checks.extraction_checks import untrusted_fields
from app.checks.format_checks import GSTIN_RE, PAN_RE
from app.checks.name_match import classify_score, name_score
from app.config import get_rules, state_name_for_gst_code
from app.models import (
    CheckOutcome, CheckResult, Country, DocType, ExtractedDocument, Stage, VendorSubmission, mask_account,
)

BANK_DOC_TYPES = {DocType.CANCELLED_CHEQUE, DocType.BANK_LETTER}

# Document field -> where the same value lives on the form (dotted path).
NAME_FIELD = "legal_name"
EXACT_FIELDS = {
    "pan": "pan", "gstin": "gstin", "ein": "ein",
    "account_number": "bank.account_number", "ifsc": "bank.ifsc", "routing_number": "bank.routing_number",
}


def _cross(check_id, result, reason, **details) -> CheckOutcome:
    return make_check(check_id, Stage.CROSS_CHECK, result, reason, details)


def _form_value(submission: VendorSubmission, dotted: str) -> str:
    obj = submission
    for part in dotted.split("."):
        obj = getattr(obj, part, None)
    return obj or ""


def _show(field: str, value: str) -> str:
    """Account numbers are always masked in reasons and details."""
    return mask_account(value) if field == "account_number" else value


def _squash(value: str) -> str:
    return value.replace(" ", "").upper()


# ---------- PAN inside GSTIN ----------

def check_pan_in_gstin(pan: str, gstin: str) -> CheckOutcome:
    pan_in_gstin = gstin[2:12]
    if pan_in_gstin != pan:
        return _cross(
            "PAN_IN_GSTIN", CheckResult.FAIL,
            f"The PAN inside the GSTIN ({pan_in_gstin}) does not match the PAN provided ({pan}). "
            f"The GST registration may belong to a different business.",
            pan=pan, pan_in_gstin=pan_in_gstin,
            review_note="Possible use of another business's GST registration. Verify before proceeding.")
    return _cross("PAN_IN_GSTIN", CheckResult.PASS, "The PAN inside the GSTIN matches the PAN provided.",
                  pan=pan, pan_in_gstin=pan_in_gstin)


# ---------- GST state vs address state ----------

def check_gst_state(gstin: str, state: str) -> CheckOutcome:
    code = gstin[:2]
    gst_state = state_name_for_gst_code(code)
    if gst_state is None:
        return _cross(
            "GST_STATE_MATCH", CheckResult.FAIL,
            f"The first two digits of the GSTIN ({code}) are not a valid GST state code.",
            gst_state_code=code, form_state=state,
            action_required="Please check your GSTIN and provide the correct number.")
    if gst_state.lower() != state.strip().lower():
        return _cross(
            "GST_STATE_MATCH", CheckResult.FAIL,
            f"The GSTIN is registered in {gst_state} (state code {code}), but the state given on the form is {state}.",
            gst_state_code=code, gst_state=gst_state, form_state=state,
            action_required=f"Please confirm your registered state, or provide the GSTIN registered for {state}.")
    return _cross("GST_STATE_MATCH", CheckResult.PASS,
                  f"The GSTIN state code {code} matches the state on the form ({gst_state}).",
                  gst_state_code=code, gst_state=gst_state, form_state=state)


# ---------- Bank holder name vs company name ----------

def check_bank_name(compared: str, where: str, legal_name: str, holder_name: str) -> CheckOutcome:
    """compared: 'form' or 'document:<filename>'. where: how to say it in a sentence."""
    score = name_score(legal_name, holder_name)
    result = classify_score(score)
    details = {"compared": compared, "legal_name": legal_name, "holder_name": holder_name, "score": score}
    if result == CheckResult.PASS:
        return _cross("BANK_NAME_MATCH", result,
                      f"The bank account holder name {where} ('{holder_name}') matches the company name "
                      f"('{legal_name}'), score {score}.", **details)
    if result == CheckResult.WARN:
        return _cross("BANK_NAME_MATCH", result,
                      f"The bank account holder name {where} ('{holder_name}') is similar to, but not the same "
                      f"as, the company name ('{legal_name}'), score {score}.",
                      action_required="Please confirm that this bank account belongs to the company, for example "
                                      "with a bank letter on the bank's letterhead showing the company name.",
                      **details)
    return _cross("BANK_NAME_MATCH", result,
                  f"The bank account holder name {where} ('{holder_name}') does not match the company name "
                  f"('{legal_name}'), score {score}. The account may belong to someone else.",
                  review_note="Possible payment diversion: the bank account is not in the company's name. "
                              "Review before any payment is set up.",
                  **details)


# ---------- Document fields vs form fields ----------

def check_doc_fields(submission: VendorSubmission, doc: ExtractedDocument) -> CheckOutcome:
    untrusted = untrusted_fields(doc)
    skipped = sorted(f for f in (set(EXACT_FIELDS) | {NAME_FIELD}) & untrusted & set(doc.fields))
    mismatches, problems, compared = [], [], []
    severe = False  # True if any exact field differs or any name scores FAIL

    for field, doc_value in doc.fields.items():
        if field in untrusted:
            continue
        if field == NAME_FIELD:
            form_value = submission.legal_name
            score = name_score(form_value, doc_value)
            outcome = classify_score(score)
            compared.append(field)
            if outcome != CheckResult.PASS:
                mismatches.append({"field": field, "form_value": form_value, "document_value": doc_value,
                                   "score": score})
                problems.append(f"the company name ('{doc_value}') does not fully match the form "
                                f"('{form_value}'), score {score}")
                severe = severe or outcome == CheckResult.FAIL
        elif field in EXACT_FIELDS:
            form_value = _form_value(submission, EXACT_FIELDS[field])
            if not form_value:
                continue  # missing on the form: the completeness stage reports that
            compared.append(field)
            if _squash(doc_value) != _squash(form_value):
                mismatches.append({"field": field, "form_value": _show(field, form_value),
                                   "document_value": _show(field, doc_value)})
                problems.append(f"the {field_label(field)} ({_show(field, doc_value)}) does not match the "
                                f"form ({_show(field, form_value)})")
                severe = True

    details = {"filename": doc.filename, "compared_fields": compared, "mismatches": mismatches,
               "skipped_untrusted": skipped}
    note = f" (not compared because unclear: {join_words([field_label(f) for f in skipped])})" if skipped else ""

    if severe:
        return _cross("DOC_FIELDS_MATCH", CheckResult.FAIL,
                      f"On {doc.filename}, " + "; ".join(problems) + ".",
                      review_note="The document disagrees with the submitted form. Check which is correct "
                                  "before proceeding.", **details)
    if mismatches:  # only names in the WARN band
        return _cross("DOC_FIELDS_MATCH", CheckResult.WARN,
                      f"On {doc.filename}, " + "; ".join(problems) + ".",
                      action_required=f"Please confirm the company name on {doc.filename} is your registered "
                                      f"name, or upload a document showing the name exactly as on your form.",
                      **details)
    if not compared:
        return _cross("DOC_FIELDS_MATCH", CheckResult.PASS,
                      f"No values on {doc.filename} could be compared{note}.", **details)
    return _cross("DOC_FIELDS_MATCH", CheckResult.PASS,
                  f"The values on {doc.filename} match the form{note}.", **details)


# ---------- Runner ----------

def run_cross_checks(submission: VendorSubmission, docs: list[ExtractedDocument]) -> list[CheckOutcome]:
    results: list[CheckOutcome] = []

    if submission.country == Country.IN:
        if submission.pan and submission.gstin and PAN_RE.fullmatch(submission.pan) \
                and GSTIN_RE.fullmatch(submission.gstin):
            results.append(check_pan_in_gstin(submission.pan, submission.gstin))
        if submission.gstin and GSTIN_RE.fullmatch(submission.gstin):
            results.append(check_gst_state(submission.gstin, submission.state))

    if submission.bank.holder_name:
        results.append(check_bank_name("form", "on the form", submission.legal_name, submission.bank.holder_name))
    for doc in docs:
        if doc.detected_type == doc.slot and doc.detected_type in BANK_DOC_TYPES \
                and "holder_name" in doc.fields and "holder_name" not in untrusted_fields(doc):
            results.append(check_bank_name(f"document:{doc.filename}", f"on {doc.filename}",
                                           submission.legal_name, doc.fields["holder_name"]))

    for doc in docs:
        if doc.detected_type == doc.slot and doc.detected_type not in (DocType.INVOICE, DocType.UNKNOWN):
            results.append(check_doc_fields(submission, doc))
    return results
