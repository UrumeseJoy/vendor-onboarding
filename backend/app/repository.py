"""Reading and writing vendors and pipeline runs. Every function takes a Session."""

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.db import PROCESSING, PipelineRunRecord, Vendor
from app.models import KnownAccount, PipelineRun, VendorStatus, VendorSubmission, mask_account
from app.security import last4, submission_fingerprint


def next_vendor_id(session: Session) -> str:
    """VND-<year>-<4-digit sequence>, e.g. VND-2026-0001."""
    prefix = f"VND-{datetime.now(timezone.utc).year}-"
    existing = session.exec(select(Vendor.vendor_id).where(Vendor.vendor_id.like(f"{prefix}%"))).all()
    highest = max((int(v.removeprefix(prefix)) for v in existing), default=0)
    return f"{prefix}{highest + 1:04d}"


def reserve_vendor(session: Session, submission: VendorSubmission, attempts: int = 5) -> str:
    """Create the Vendor row now (status PROCESSING) so its ID is taken before the run finishes.
    If two submissions grab the same ID at the same moment, the loser retries with the next one."""
    for _ in range(attempts):
        vendor_id = next_vendor_id(session)
        now = datetime.now(timezone.utc)
        session.add(Vendor(vendor_id=vendor_id, legal_name=submission.legal_name,
                           country=submission.country.value, status=PROCESSING, risk_score=0,
                           created_at=now, updated_at=now))
        try:
            session.commit()
            return vendor_id
        except IntegrityError:
            session.rollback()
    raise RuntimeError("Could not assign a vendor ID; please try again.")


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
        had_errors=run.had_errors, upload_id=run.upload_id, submission_json=masked_submission.model_dump_json(),
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


def recover_interrupted_vendors(session: Session) -> int:
    """Fail safe after a restart: a vendor still PROCESSING has no live run any more (runs live in this
    process's memory), so it is set to PENDING for manual review. Returns how many were recovered."""
    stuck = session.exec(select(Vendor).where(Vendor.status == PROCESSING)).all()
    now = datetime.now(timezone.utc)
    for vendor in stuck:
        vendor.status, vendor.updated_at = VendorStatus.PENDING.value, now
        session.add(vendor)
    session.commit()
    return len(stuck)


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
    """Every bank account on file, as fingerprints (used to spot duplicates).
    A REJECTED vendor's account is not "in use": otherwise an impostor who tried a real vendor's
    account (and was rejected) would get the real vendor rejected as a duplicate on its next run."""
    vendors = session.exec(select(Vendor).where(Vendor.account_fingerprint != None,  # noqa: E711
                                                Vendor.status != VendorStatus.REJECTED.value)).all()
    return [KnownAccount(vendor_id=v.vendor_id, legal_name=v.legal_name,
                         account_fingerprint=v.account_fingerprint, account_last4=v.account_last4 or "")
            for v in vendors]


def status_counts(session: Session) -> dict[VendorStatus, int]:
    """How many vendors are in each status (by latest status)."""
    counts = Counter(session.exec(select(Vendor.status)).all())
    return {status: counts.get(status.value, 0) for status in VendorStatus}


def count_runs(session: Session) -> int:
    return session.exec(select(func.count()).select_from(PipelineRunRecord)).one()


def update_run_email(session: Session, run_id: str, email) -> PipelineRun | None:
    """Replace a run's vendor email (e.g. after a person approves it) and re-save the run."""
    record = session.get(PipelineRunRecord, run_id)
    if record is None:
        return None
    run = PipelineRun.model_validate_json(record.run_json)
    run.email = email
    record.run_json = run.model_dump_json()
    session.add(record)
    session.commit()
    return run
