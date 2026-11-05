"""Stage 4: format checks for PAN, GSTIN, IFSC (India) and EIN, routing number (US).

Each check takes the value (already stripped/uppercased by the models) and returns a CheckOutcome.
"""

import re

from app.checks.base import make_check
from app.checks.id_utils import aba_routing_valid, gstin_checksum
from app.models import CheckOutcome, CheckResult, Country, Stage, VendorSubmission

PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
GSTIN_RE = re.compile(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]")
IFSC_RE = re.compile(r"[A-Z]{4}0[A-Z0-9]{6}")
EIN_RE = re.compile(r"[0-9]{2}-[0-9]{7}")

# 4th character of a PAN = type of holder
PAN_HOLDER_TYPES = {
    "P": "Individual", "C": "Company", "F": "Firm/LLP", "H": "HUF", "A": "AOP",
    "T": "Trust", "B": "BOI", "L": "Local authority", "J": "Artificial juridical person",
    "G": "Government",
}


def _check(check_id, result, reason, **details) -> CheckOutcome:
    return make_check(check_id, Stage.FORMAT, result, reason, details)


def check_pan_format(pan: str) -> CheckOutcome:
    if not PAN_RE.fullmatch(pan):
        return _check("PAN_FORMAT", CheckResult.FAIL,
                      f"PAN '{pan}' is not valid. A PAN has 5 letters, 4 digits and 1 letter, like ABCDE1234F.",
                      field="pan", value=pan, expected="5 letters, 4 digits, 1 letter")
    holder_type = PAN_HOLDER_TYPES.get(pan[3], "Unknown")
    if pan[3] != "C":
        return _check("PAN_FORMAT", CheckResult.WARN,
                      f"PAN '{pan}' has a valid format, but its 4th character '{pan[3]}' means the holder is "
                      f"{holder_type}, not a company, while the vendor is registered as a company "
                      f"(a company PAN has 'C' as its 4th character).",
                      field="pan", value=pan, holder_type=holder_type, expected_holder_type="Company")
    return _check("PAN_FORMAT", CheckResult.PASS, "PAN format is valid (company holder type).",
                  field="pan", value=pan, holder_type=holder_type)


def check_gstin_format(gstin: str) -> CheckOutcome:
    if not GSTIN_RE.fullmatch(gstin):
        return _check("GSTIN_FORMAT", CheckResult.FAIL,
                      f"GSTIN '{gstin}' is not valid. A GSTIN has 15 characters: a 2-digit state code, the "
                      f"10-character PAN, one more character, the letter Z and a check character, "
                      f"like 33AABCS1234K1ZN.",
                      field="gstin", value=gstin, expected="15 characters, e.g. 33AABCS1234K1ZN",
                      found_length=len(gstin))
    return _check("GSTIN_FORMAT", CheckResult.PASS, "GSTIN format is valid.", field="gstin", value=gstin)


def check_gstin_checksum(gstin: str) -> CheckOutcome:
    """Only call this when the GSTIN format is already valid."""
    expected, found = gstin_checksum(gstin[:14]), gstin[14]
    if expected != found:
        return _check("GSTIN_CHECKSUM", CheckResult.FAIL,
                      f"GSTIN check character is wrong: expected '{expected}' but found '{found}'. "
                      f"The number may contain a typo or may not be a real registration.",
                      field="gstin", value=gstin, expected=expected, found=found)
    return _check("GSTIN_CHECKSUM", CheckResult.PASS, "GSTIN check character is correct.",
                  field="gstin", value=gstin, expected=expected, found=found)


def check_ifsc_format(ifsc: str) -> CheckOutcome:
    if not IFSC_RE.fullmatch(ifsc):
        return _check("IFSC_FORMAT", CheckResult.FAIL,
                      f"IFSC '{ifsc}' is not valid. An IFSC has 4 letters, the digit 0, then 6 letters or "
                      f"digits, like HDFC0001234.",
                      field="ifsc", value=ifsc, expected="4 letters, 0, 6 letters/digits",
                      action_required="Please check your bank's IFSC code and provide it again "
                                      "(11 characters, like HDFC0001234).")
    return _check("IFSC_FORMAT", CheckResult.PASS, "IFSC format is valid.", field="ifsc", value=ifsc)


def check_ein_format(ein: str) -> CheckOutcome:
    if not EIN_RE.fullmatch(ein):
        return _check("EIN_FORMAT", CheckResult.FAIL,
                      f"EIN '{ein}' is not valid. A US EIN has 2 digits, a hyphen and 7 digits, like 84-1234567.",
                      field="ein", value=ein, expected="NN-NNNNNNN")
    return _check("EIN_FORMAT", CheckResult.PASS, "EIN format is valid.", field="ein", value=ein)


def check_routing_format(routing: str) -> CheckOutcome:
    if not (len(routing) == 9 and routing.isascii() and routing.isdigit()):
        return _check("ROUTING_FORMAT", CheckResult.FAIL,
                      f"Routing number '{routing}' is not valid. A US routing number has exactly 9 digits, "
                      f"like 123456780.",
                      field="routing_number", value=routing, expected="9 digits",
                      action_required="Please check your bank's routing number and provide it again (9 digits).")
    if not aba_routing_valid(routing):
        return _check("ROUTING_FORMAT", CheckResult.FAIL,
                      f"Routing number '{routing}' has 9 digits but fails the standard bank checksum, "
                      f"so it may contain a typo.",
                      field="routing_number", value=routing, expected="9 digits passing the ABA checksum",
                      action_required="Please check your bank's routing number and provide it again (9 digits).")
    return _check("ROUTING_FORMAT", CheckResult.PASS, "Routing number format and checksum are valid.",
                  field="routing_number", value=routing)


def run_format_checks(submission: VendorSubmission) -> list[CheckOutcome]:
    """Run the format checks for the vendor's country. Missing fields are skipped
    (the completeness stage reports those)."""
    results: list[CheckOutcome] = []
    if submission.country == Country.IN:
        if submission.pan:
            results.append(check_pan_format(submission.pan))
        if submission.gstin:
            gstin_format = check_gstin_format(submission.gstin)
            results.append(gstin_format)
            if gstin_format.result == CheckResult.PASS:
                results.append(check_gstin_checksum(submission.gstin))
        if submission.bank.ifsc:
            results.append(check_ifsc_format(submission.bank.ifsc))
    else:
        if submission.ein:
            results.append(check_ein_format(submission.ein))
        if submission.bank.routing_number:
            results.append(check_routing_format(submission.bank.routing_number))
    return results
