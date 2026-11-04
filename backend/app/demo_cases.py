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
            account_number=sub.bank.account_number, ifsc=sub.bank.ifsc,
            routing_number=sub.bank.routing_number))
    return accounts


def run_demo_case(case_id: str, on_stage: OnStage | None = None) -> PipelineRun:
    case_dir = CASES_DIR / case_id
    return run_pipeline(
        submission=load_submission(case_id),
        vendor_id=vendor_id_for(case_id),
        extractor=lambda submission: mock_extract(case_dir, submission),
        known_accounts=known_accounts_for(case_id),
        on_stage=on_stage,
    )
