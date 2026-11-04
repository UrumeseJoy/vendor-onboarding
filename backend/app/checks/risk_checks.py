"""Stage 6 checks: risk flags. These are signals for the internal reviewer, not instructions to
the vendor, so they carry details["review_note"] and a details["score"], never action_required.

known_accounts is passed in (the pipeline supplies it later); this module reads no database or files.
"""

from app.checks.base import make_check
from app.config import get_rules
from app.models import CheckOutcome, CheckResult, Country, KnownAccount, Stage, VendorSubmission, mask_account


def _risk(check_id, result, reason, **details) -> CheckOutcome:
    if result == CheckResult.FAIL:
        details["score"] = get_rules().risk.flags[check_id].score
    return make_check(check_id, Stage.RISK, result, reason, details)


def _squash(value: str | None) -> str:
    return (value or "").replace(" ", "").upper()


def check_free_email(email: str) -> CheckOutcome:
    domain = email.rsplit("@", 1)[-1].strip().lower() if "@" in email else ""
    if domain in get_rules().risk.free_email_domains:
        return _risk("FREE_EMAIL_DOMAIN", CheckResult.FAIL,
                     f"The contact email uses a free personal email service ({domain}) rather than a company domain.",
                     domain=domain,
                     review_note="Weak signal on its own. Check that the vendor is a real business with a company website.")
    return _risk("FREE_EMAIL_DOMAIN", CheckResult.PASS, "The contact email uses a company domain.", domain=domain)


def check_bank_country(submission: VendorSubmission) -> CheckOutcome:
    bank, company = submission.bank.bank_country, submission.country
    if bank != company:
        return _risk("BANK_COUNTRY_MISMATCH", CheckResult.FAIL,
                     f"The bank account is in {bank.value} but the company is registered in {company.value}.",
                     bank_country=bank.value, company_country=company.value,
                     review_note="Payments would go to a different country than the vendor's registration. "
                                 "Confirm there is a business reason.")
    return _risk("BANK_COUNTRY_MISMATCH", CheckResult.PASS,
                 "The bank account is in the same country as the company.",
                 bank_country=bank.value, company_country=company.value)


def check_duplicate_account(submission: VendorSubmission, vendor_id: str,
                            known_accounts: list[KnownAccount]) -> CheckOutcome:
    bank = submission.bank
    account = _squash(bank.account_number)
    is_india = submission.country == Country.IN
    branch = _squash(bank.ifsc if is_india else bank.routing_number)  # IFSC (India) or routing (US)

    for known in known_accounts:
        if known.vendor_id == vendor_id:
            continue  # a resubmission must not match itself
        known_branch = _squash(known.ifsc if is_india else known.routing_number)
        if _squash(known.account_number) == account and known_branch == branch:
            masked = mask_account(bank.account_number)
            return _risk(
                "DUPLICATE_BANK_ACCOUNT", CheckResult.FAIL,
                f"The bank account {masked} is already registered to another vendor, "
                f"{known.legal_name} ({known.vendor_id}).",
                other_vendor_id=known.vendor_id, other_vendor_name=known.legal_name, account_number=masked,
                review_note=f"Possible duplicate or fraudulent vendor: the same bank account is already used by "
                            f"{known.legal_name} ({known.vendor_id}). Check whether the two vendors are related "
                            f"before approving either.")
    return _risk("DUPLICATE_BANK_ACCOUNT", CheckResult.PASS,
                 "This bank account is not registered to any other vendor.")


def run_risk_checks(submission: VendorSubmission, vendor_id: str,
                    known_accounts: list[KnownAccount]) -> list[CheckOutcome]:
    results = [check_free_email(submission.contact_email), check_bank_country(submission)]
    if submission.bank.account_number:  # a missing account is the completeness stage's job
        results.append(check_duplicate_account(submission, vendor_id, known_accounts))
    return results


def compute_risk_score(outcomes: list[CheckOutcome]) -> int:
    """Sum the scores of failed RISK checks, capped at 100."""
    total = sum(o.details.get("score", 0) for o in outcomes
                if o.stage == Stage.RISK and o.result == CheckResult.FAIL)
    return min(total, 100)
