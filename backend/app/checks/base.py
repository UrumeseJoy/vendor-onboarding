"""Shared helper for building check results."""

from app.config import get_rules
from app.models import CheckOutcome, CheckResult, Stage


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
