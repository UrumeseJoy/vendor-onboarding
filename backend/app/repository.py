"""Reading and writing vendors and pipeline runs. Every function takes a Session."""

from collections import Counter
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.db import PipelineRunRecord, Vendor
from app.models import KnownAccount, PipelineRun, VendorStatus, VendorSubmission, mask_account
from app.security import last4, submission_fingerprint


def next_vendor_id(session: Session) -> str:
    """VND-<year>-<4-digit sequence>, e.g. VND-2026-0001."""
    prefix = f"VND-{datetime.now(timezone.utc).year}-"
    existing = session.exec(select(Vendor.vendor_id).where(Vendor.vendor_id.like(f"{prefix}%"))).all()
    highest = max((int(v.removeprefix(prefix)) for v in existing), default=0)
    return f"{prefix}{highest + 1:04d}"


def save_run(session: Session, submission: VendorSubmission, run: PipelineRun) -> Vendor:
    """Store a run. Creates the Vendor on its first run, otherwise updates it.
    The full account number is never written; only its fingerprint, last 4 digits and a masked copy."""
    now = datetime.now(timezone.utc)
    status = run.decision.status.value if run.decision else VendorStatus.PENDING.value
    risk_score = run.decision.risk_score if run.decision else 0

    vendor = session.get(Vendor, run.vendor_id)
    if vendor is None:
        vendor = Vendor(vendor_id=run.vendor_id, legal_name=submission.legal_name,
                        country=submission.country.value, status=status, risk_score=risk_score,
                        created_at=now, updated_at=now)
    run_number = vendor.run_count + 1

    masked_bank = submission.bank.model_copy(update={"account_number": mask_account(submission.bank.account_number)})
    masked_submission = submission.model_copy(update={"bank": masked_bank})
    session.add(PipelineRunRecord(
        run_id=run.run_id, vendor_id=run.vendor_id, run_number=run_number,
        started_at=run.started_at, finished_at=run.finished_at, status=status, risk_score=risk_score,
        had_errors=run.had_errors, submission_json=masked_submission.model_dump_json(),
        run_json=run.model_dump_json()))

    vendor.legal_name = submission.legal_name
    vendor.country = submission.country.value
    vendor.status, vendor.risk_score = status, risk_score
    vendor.account_fingerprint = submission_fingerprint(submission)
    vendor.account_last4 = last4(submission.bank.account_number) if submission.bank.account_number else None
    vendor.updated_at = now
    vendor.latest_run_id = run.run_id
    vendor.run_count = run_number
    session.add(vendor)
    session.commit()
    session.refresh(vendor)
    return vendor


def get_vendor(session: Session, vendor_id: str) -> Vendor | None:
    return session.get(Vendor, vendor_id)


def list_vendors(session: Session) -> list[Vendor]:
    """Newest updated first."""
    return list(session.exec(select(Vendor).order_by(Vendor.updated_at.desc(), Vendor.vendor_id.desc())).all())


def get_vendor_runs(session: Session, vendor_id: str) -> list[PipelineRunRecord]:
    """Oldest first."""
    return list(session.exec(select(PipelineRunRecord).where(PipelineRunRecord.vendor_id == vendor_id)
                             .order_by(PipelineRunRecord.run_number)).all())


def get_run(session: Session, run_id: str) -> PipelineRun | None:
    record = session.get(PipelineRunRecord, run_id)
    return PipelineRun.model_validate_json(record.run_json) if record else None


def known_accounts(session: Session) -> list[KnownAccount]:
    """Every bank account on file, as fingerprints (used to spot duplicates)."""
    vendors = session.exec(select(Vendor).where(Vendor.account_fingerprint != None)).all()  # noqa: E711
    return [KnownAccount(vendor_id=v.vendor_id, legal_name=v.legal_name,
                         account_fingerprint=v.account_fingerprint, account_last4=v.account_last4 or "")
            for v in vendors]


def status_counts(session: Session) -> dict[VendorStatus, int]:
    """How many vendors are in each status (by latest status)."""
    counts = Counter(session.exec(select(Vendor.status)).all())
    return {status: counts.get(status.value, 0) for status in VendorStatus}
