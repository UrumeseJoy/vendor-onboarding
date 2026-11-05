"""Runs the 8 pipeline stages in order and returns a PipelineRun.

Fail safe: every stage is wrapped in try/except. A stage that errors is marked FAILED,
the remaining stages still run, and the decision can never be APPROVED.
"""

import logging
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from app.checks.base import make_check
from app.checks.completeness_checks import check_required_fields, run_completeness_checks
from app.checks.cross_checks import run_cross_checks
from app.checks.extraction_checks import run_extraction_checks
from app.checks.format_checks import run_format_checks
from app.checks.risk_checks import compute_risk_score, run_risk_checks
from app.decision import RISK_FLAG_NAMES, decide
from app.settings import extractor_mode
from app.vendor_message import build_vendor_email
from app.models import (
    CheckOutcome, CheckResult, Decision, ExtractedDocument, KnownAccount, PipelineRun, Severity,
    Stage, StageResult, StageStatus, VendorStatus, VendorSubmission, mask_account,
)

logger = logging.getLogger(__name__)

Extractor = Callable[[VendorSubmission], list[ExtractedDocument]]
OnStage = Callable[[StageResult], None]

DECISION_STAGE_STATUS = {
    VendorStatus.APPROVED: StageStatus.PASSED,
    VendorStatus.PENDING: StageStatus.WARNING,
    VendorStatus.REJECTED: StageStatus.FAILED,
}
DECISION_SUMMARY = {
    VendorStatus.APPROVED: "Approved: all required checks passed.",
    VendorStatus.PENDING: "Pending: the vendor must fix something, or a person must review.",
    VendorStatus.REJECTED: "Rejected: a serious problem was found.",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def stage_status(stage: Stage, checks: list[CheckOutcome]) -> StageStatus:
    """Turn a stage's checks into one status."""
    if not checks:
        return StageStatus.SKIPPED
    fails = [c for c in checks if c.result == CheckResult.FAIL]
    if any(c.severity == Severity.HARD for c in fails):
        return StageStatus.FAILED
    if fails:  # only SOFT fails left
        return StageStatus.WARNING if stage == Stage.RISK else StageStatus.FAILED
    if any(c.result == CheckResult.WARN for c in checks):
        return StageStatus.WARNING
    return StageStatus.PASSED


def count_summary(checks: list[CheckOutcome], noun: str) -> str:
    """e.g. 'All 4 format checks passed.' / '1 of 4 format checks failed.'"""
    total = len(checks)
    if total == 0:
        return f"No {noun} to run."
    fails = sum(c.result == CheckResult.FAIL for c in checks)
    warns = sum(c.result == CheckResult.WARN for c in checks)
    if not fails and not warns:
        return f"All {total} {noun} passed."
    parts = []
    if fails:
        parts.append(f"{fails} of {total} {noun} failed")
    if warns:
        parts.append(f"{warns} {'needs' if warns == 1 else 'need'} review" if fails
                     else f"{warns} of {total} {noun} {'needs' if warns == 1 else 'need'} review")
    return " and ".join(parts) + "."


def extraction_summary(docs: list[ExtractedDocument], checks: list[CheckOutcome]) -> str:
    if not docs:
        return "No documents to read."
    unclear = {c.details.get("filename") for c in checks if c.result != CheckResult.PASS}
    noun = "document" if len(docs) == 1 else "documents"
    if not unclear:
        return f"{len(docs)} {noun} read, all clear."
    return f"{len(docs)} {noun} read; {len(unclear)} could not be read clearly."


def risk_summary(checks: list[CheckOutcome]) -> str:
    flags = [c for c in checks if c.result == CheckResult.FAIL]
    if not flags:
        return "No risk flags raised."
    names = ", ".join(RISK_FLAG_NAMES.get(c.check_id, c.check_id) for c in flags)
    return f"{len(flags)} risk flag{'s' if len(flags) > 1 else ''} raised: {names} (risk score {compute_risk_score(checks)})."


NUMBER_RUN_RE = re.compile(r"\d[\d -]*\d")  # digits, possibly split by spaces or dashes


def _mask_numbers(text: str, account_number: str | None) -> str:
    """Free text (the reader's notes) could quote an account number. Mask this document's account
    number, and any other run of 9+ digits (short numbers such as dates are left alone)."""
    account = re.sub(r"\D", "", account_number or "")

    def mask(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group())
        return mask_account(digits) if len(digits) >= 9 or (account and digits == account) else match.group()
    return NUMBER_RUN_RE.sub(mask, text)


def _masked_document(doc: ExtractedDocument) -> ExtractedDocument:
    """A copy safe to store and show: the account number is masked (rule 6, rule 13), in the
    fields and in any note that quotes it."""
    fields = dict(doc.fields)
    notes = [_mask_numbers(note, fields.get("account_number")) for note in doc.notes]
    if fields.get("account_number"):
        fields["account_number"] = mask_account(fields["account_number"])
    return doc.model_copy(update={"fields": fields, "notes": notes})


def _short_error(error: Exception) -> str:
    text = f"{type(error).__name__}: {error}"
    return text if len(text) <= 200 else text[:197] + "..."


def run_pipeline(submission: VendorSubmission, vendor_id: str, extractor: Extractor,
                 known_accounts: list[KnownAccount], on_stage: OnStage | None = None,
                 run_id: str | None = None, upload_id: str | None = None,
                 ai_emails: bool | None = None) -> PipelineRun:
    """run_id can be chosen by the caller (so it can be returned before the run starts).
    ai_emails: draft PENDING emails with AI. None = only when EXTRACTOR_MODE is "gemini"."""
    run = PipelineRun(run_id=run_id or str(uuid.uuid4()), vendor_id=vendor_id, started_at=_now(),
                      upload_id=upload_id)
    outcomes: list[CheckOutcome] = []
    errored_stages: list[str] = []
    docs: list[ExtractedDocument] = []  # filled by the EXTRACTION stage; stays empty if it fails

    def notify(result: StageResult) -> None:
        """Tell the caller about a stage. A broken callback must never break the run."""
        if on_stage is None:
            return
        try:
            on_stage(result.model_copy(deep=True))
        except Exception:
            logger.exception("on_stage callback failed for stage %s", result.stage.value)

    def run_stage(stage: Stage, work: Callable[[], tuple]) -> None:
        """work() returns (checks, summary) or (checks, summary, status_override)."""
        started = _now()
        notify(StageResult(stage=stage, status=StageStatus.RUNNING, started_at=started))
        try:
            checks, summary, *override = work()
            status = override[0] if override else stage_status(stage, checks)
        except Exception as error:
            logger.exception("Stage %s failed", stage.value)
            checks, status, summary = [], StageStatus.FAILED, f"Processing error: {_short_error(error)}"
            errored_stages.append(stage.value)
        result = StageResult(stage=stage, status=status, checks=checks, started_at=started,
                             finished_at=_now(), summary=summary)
        run.stages.append(result)
        outcomes.extend(checks)
        notify(result)

    # ---- the 8 stages ----

    def intake():
        check = make_check("INTAKE_VALID", Stage.INTAKE, CheckResult.PASS, "Submission received and validated.",
                           {"vendor_id": vendor_id})
        return [check], "Submission received and validated."

    def extraction():
        nonlocal docs
        docs = extractor(submission)
        run.documents = [_masked_document(d) for d in docs]
        checks = run_extraction_checks(docs)
        return checks, extraction_summary(docs, checks)

    def completeness():
        if Stage.EXTRACTION.value in errored_stages:
            # The documents were never read, so we cannot say any is missing or of the wrong type
            # (and must not ask the vendor to upload files they already sent). Only the form is checked;
            # the failed read already makes this vendor PENDING for manual review.
            checks = [check_required_fields(submission)]
            return checks, count_summary(checks, "completeness checks") + " Documents not checked: they could not be read."
        checks = run_completeness_checks(submission, docs)
        return checks, count_summary(checks, "completeness checks")

    def format_stage():
        checks = run_format_checks(submission)
        return checks, count_summary(checks, "format checks")

    def cross_check():
        checks = run_cross_checks(submission, docs)
        return checks, count_summary(checks, "cross-checks")

    def risk():
        checks = run_risk_checks(submission, vendor_id, known_accounts)
        return checks, risk_summary(checks)

    def decision():
        try:
            run.decision = decide(vendor_id, outcomes, bool(errored_stages), errored_stages)
        except Exception:
            # Fail safe: if the decision itself cannot be made, a person must review.
            run.decision = Decision(vendor_id=vendor_id, status=VendorStatus.PENDING, risk_score=0,
                                    reasons=["The decision could not be computed; manual review required."])
            raise
        status = run.decision.status
        return [], DECISION_SUMMARY[status], DECISION_STAGE_STATUS[status]

    def vendor_message():
        use_ai = extractor_mode() == "gemini" if ai_emails is None else ai_emails
        run.email, summary = build_vendor_email(submission.legal_name, run.decision, use_ai)
        return [], summary, StageStatus.PASSED

    run_stage(Stage.INTAKE, intake)
    run_stage(Stage.EXTRACTION, extraction)
    run_stage(Stage.COMPLETENESS, completeness)
    run_stage(Stage.FORMAT, format_stage)
    run_stage(Stage.CROSS_CHECK, cross_check)
    run_stage(Stage.RISK, risk)
    run_stage(Stage.DECISION, decision)
    run_stage(Stage.VENDOR_MESSAGE, vendor_message)

    run.had_errors = bool(errored_stages)
    run.finished_at = _now()
    return run
