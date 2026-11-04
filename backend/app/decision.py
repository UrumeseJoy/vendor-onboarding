"""Stage 7: the decision. Plain, deterministic rules (see the Decision rule in CLAUDE.md).

- Severity only matters for FAIL results.
- Any HARD FAIL (any stage)                         -> REJECTED
- Otherwise: any SOFT FAIL outside the RISK stage,
  any WARN, risk_score >= review_threshold,
  or any stage that errored (fail safe)             -> PENDING
- Otherwise                                         -> APPROVED

SOFT risk flags never cause PENDING on their own; they add up in risk_score.
"""

from app.checks.risk_checks import compute_risk_score
from app.config import get_rules
from app.models import CheckOutcome, CheckResult, Decision, Severity, Stage, VendorStatus

# How each risk flag is named in a sentence
RISK_FLAG_NAMES = {
    "FREE_EMAIL_DOMAIN": "free email domain",
    "BANK_COUNTRY_MISMATCH": "bank account in a different country",
    "DUPLICATE_BANK_ACCOUNT": "bank account already used by another vendor",
}
RISK_FLAG_NOTES = {
    "FREE_EMAIL_DOMAIN": "contact email uses a free email domain",
    "BANK_COUNTRY_MISMATCH": "bank account is in a different country from the company",
    "DUPLICATE_BANK_ACCOUNT": "bank account is already used by another vendor",
}


def _unique(items: list[str]) -> list[str]:
    """Remove duplicates, keep the original order."""
    return list(dict.fromkeys(items))


def decide(vendor_id: str, outcomes: list[CheckOutcome], had_errors: bool,
           errored_stages: list[str]) -> Decision:
    threshold = get_rules().risk.review_threshold
    risk_score = compute_risk_score(outcomes)

    fails = [o for o in outcomes if o.result == CheckResult.FAIL]
    hard_fails = [o for o in fails if o.severity == Severity.HARD]
    soft_fails = [o for o in fails if o.severity == Severity.SOFT and o.stage != Stage.RISK]
    warns = [o for o in outcomes if o.result == CheckResult.WARN]
    risk_flags = [o for o in fails if o.stage == Stage.RISK]
    risk_blocks = risk_score >= threshold

    if hard_fails:
        status = VendorStatus.REJECTED
        reasons = [o.reason for o in hard_fails]
    elif soft_fails or warns or risk_blocks or had_errors:
        status = VendorStatus.PENDING
        reasons = [o.reason for o in soft_fails + warns]
        if risk_blocks:
            flags = ", ".join(RISK_FLAG_NAMES.get(o.check_id, o.check_id) for o in risk_flags)
            reasons.append(f"Risk score {risk_score} reached the review threshold of {threshold}: {flags}.")
        reasons += [f"The {stage} stage hit a processing error, so this vendor needs manual review."
                    for stage in errored_stages]
    else:
        status = VendorStatus.APPROVED
        passed = sum(o.result == CheckResult.PASS for o in outcomes)
        if risk_flags:
            reasons = [f"{passed} of {len(outcomes)} checks passed; no blocking issues found."]
            reasons += [f"Note: {RISK_FLAG_NOTES.get(o.check_id, o.check_id)} (risk score {risk_score}, "
                        f"below the review threshold of {threshold})." for o in risk_flags]
        else:
            reasons = [f"All {len(outcomes)} checks passed."]

    # Vendor instructions only matter when the vendor can fix something (PENDING).
    missing_items = []
    if status == VendorStatus.PENDING:
        missing_items = _unique([o.details["action_required"] for o in soft_fails + warns
                                 if o.details.get("action_required")])

    return Decision(
        vendor_id=vendor_id,
        status=status,
        reasons=reasons,
        missing_items=missing_items,
        risk_score=risk_score,
        review_notes=_unique([o.details["review_note"] for o in outcomes if o.details.get("review_note")]),
        checks_summary={r.value: sum(o.result == r for o in outcomes) for r in CheckResult},
    )
