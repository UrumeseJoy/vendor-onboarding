"""Shared helpers for running the sample cases (used by scripts/run_case.py and the tests).

Rules:
- Vendor ID is VND-2026-00NN, where NN is the case number (01_happy_path -> VND-2026-0001).
- A case with "resubmission_of" in expected.json reuses that case's vendor ID.
- A case with "requires_prior_cases" gets those cases' bank accounts as known accounts.
"""

import json
from pathlib import Path

from app.extraction.mock_extractor import mock_extract
from app.models import KnownAccount, PipelineRun, VendorSubmission
from app.storage import demo_files
from app.security import last4, submission_fingerprint
from app.pipeline import OnStage, run_pipeline

CASES_DIR = Path(__file__).parent.parent / "sample_data" / "cases"


def load_index() -> list[dict]:
    return json.loads((CASES_DIR / "index.json").read_text())


def load_submission(case_id: str) -> VendorSubmission:
    return VendorSubmission(**json.loads((CASES_DIR / case_id / "submission.json").read_text()))


def load_expected(case_id: str) -> dict:
    return json.loads((CASES_DIR / case_id / "expected.json").read_text())


def vendor_id_for(case_id: str) -> str:
    original = load_expected(case_id).get("resubmission_of", case_id)
    return f"VND-2026-{int(original[:2]):04d}"


def known_accounts_for(case_id: str) -> list[KnownAccount]:
    accounts = []
    for prior in load_expected(case_id).get("requires_prior_cases", []):
        sub = load_submission(prior)
        accounts.append(KnownAccount(
            vendor_id=vendor_id_for(prior), legal_name=sub.legal_name,
            account_fingerprint=submission_fingerprint(sub), account_last4=last4(sub.bank.account_number)))
    return accounts


def run_demo_case(case_id: str, on_stage: OnStage | None = None, use_factory: bool = False) -> PipelineRun:
    """Run a demo case. use_factory=True reads the PDFs with the extractor chosen by EXTRACTOR_MODE
    (mock or Gemini); the default always uses the offline mock, so tests never need the network."""
    case_dir = CASES_DIR / case_id
    submission = load_submission(case_id)
    if use_factory:
        from app.extraction.factory import get_extractor
        extractor = get_extractor(demo_files(case_id, submission))
    else:
        extractor = lambda sub: mock_extract(case_dir, sub)  # noqa: E731
    return run_pipeline(
        submission=submission,
        vendor_id=vendor_id_for(case_id),
        extractor=extractor,
        known_accounts=known_accounts_for(case_id),
        on_stage=on_stage,
        upload_id=f"demo:{case_id}",
    )


def seed_demo_cases(session) -> list[dict]:
    """Process every demo case in index.json order through the real service and database.
    A resubmission uses the vendor ID its original case received. Duplicates are found because
    earlier vendors are already in the database."""
    from app.repository import get_vendor_runs
    from app.service import process_submission

    vendor_ids: dict[str, str] = {}
    rows = []
    for entry in load_index():
        case_id = entry["case_id"]
        expected = load_expected(case_id)
        original = expected.get("resubmission_of")
        case_dir = CASES_DIR / case_id
        run = process_submission(
            session, load_submission(case_id),
            extractor=lambda submission, case_dir=case_dir: mock_extract(case_dir, submission),
            vendor_id=vendor_ids[original] if original else None,
            upload_id=f"demo:{case_id}")
        vendor_ids[case_id] = run.vendor_id
        status = run.decision.status.value
        rows.append({"case_id": case_id, "vendor_id": run.vendor_id,
                     "run_number": len(get_vendor_runs(session, run.vendor_id)),
                     "status": status, "expected": expected["expected_status"],
                     "match": status == expected["expected_status"]})
    return rows
