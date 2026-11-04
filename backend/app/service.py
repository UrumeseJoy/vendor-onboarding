"""The one entry point for processing a vendor submission: pipeline + database."""

from sqlmodel import Session

from app.models import PipelineRun, VendorSubmission
from app.pipeline import Extractor, OnStage, run_pipeline
from app.repository import get_vendor, known_accounts, next_vendor_id, save_run


class VendorNotFound(Exception):
    """A resubmission named a vendor ID that does not exist."""


def process_submission(session: Session, submission: VendorSubmission, extractor: Extractor,
                       vendor_id: str | None = None, on_stage: OnStage | None = None) -> PipelineRun:
    """New vendor if vendor_id is None, otherwise a resubmission for that existing vendor."""
    if vendor_id is None:
        vendor_id = next_vendor_id(session)
    elif get_vendor(session, vendor_id) is None:
        raise VendorNotFound(f"No vendor with ID {vendor_id}. A resubmission must use an existing vendor ID.")
    run = run_pipeline(submission, vendor_id, extractor, known_accounts(session), on_stage)
    save_run(session, submission, run)
    return run
