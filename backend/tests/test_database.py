from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel

from app.db import get_engine, init_db
from app.demo_cases import CASES_DIR, load_expected, load_index, load_submission, seed_demo_cases, vendor_id_for
from app.extraction.mock_extractor import mock_extract
from app.models import CheckResult, VendorStatus
from app.repository import (
    get_run, get_vendor, get_vendor_runs, list_vendors, known_accounts, next_vendor_id, status_counts,
)
from app.service import VendorNotFound, process_submission

YEAR = datetime.now(timezone.utc).year


@pytest.fixture
def session(db_url):
    engine = get_engine(db_url)
    init_db(engine)
    with Session(engine) as s:
        yield s


def process(session, case_id, vendor_id=None):
    case_dir = CASES_DIR / case_id
    return process_submission(session, load_submission(case_id), lambda sub: mock_extract(case_dir, sub), vendor_id)


def failed_ids(run):
    return {c.check_id for r in run.stages for c in r.checks if c.result == CheckResult.FAIL}


def test_vendor_ids_are_sequential(session):
    assert next_vendor_id(session) == f"VND-{YEAR}-0001"
    assert process(session, "01_happy_path").vendor_id == f"VND-{YEAR}-0001"
    assert process(session, "02_bank_name_mismatch").vendor_id == f"VND-{YEAR}-0002"
    assert next_vendor_id(session) == f"VND-{YEAR}-0003"


def test_case_01_creates_one_vendor_and_one_run(session):
    run = process(session, "01_happy_path")
    vendor = get_vendor(session, run.vendor_id)
    assert vendor.status == "APPROVED" and vendor.run_count == 1 and vendor.latest_run_id == run.run_id
    assert len(list_vendors(session)) == 1
    runs = get_vendor_runs(session, run.vendor_id)
    assert len(runs) == 1 and runs[0].run_number == 1
    assert get_run(session, run.run_id).model_dump(mode="json") == run.model_dump(mode="json")


def test_case_07_alone_is_approved(session):
    assert process(session, "07_duplicate_bank").decision.status == VendorStatus.APPROVED


def test_case_07_after_case_01_is_rejected_as_duplicate(session):
    first = process(session, "01_happy_path")
    second = process(session, "07_duplicate_bank")
    assert second.decision.status == VendorStatus.REJECTED
    assert "DUPLICATE_BANK_ACCOUNT" in failed_ids(second)
    dup = next(c for r in second.stages for c in r.checks if c.check_id == "DUPLICATE_BANK_ACCOUNT")
    assert dup.details["other_vendor_id"] == first.vendor_id


def test_resubmission_keeps_both_runs(session):
    first = process(session, "04_wrong_document")
    second = process(session, "05_resubmission", vendor_id=first.vendor_id)
    assert second.vendor_id == first.vendor_id
    vendor = get_vendor(session, first.vendor_id)
    assert vendor.status == "APPROVED" and vendor.run_count == 2 and vendor.latest_run_id == second.run_id
    runs = get_vendor_runs(session, first.vendor_id)
    assert [(r.run_number, r.status) for r in runs] == [(1, "PENDING"), (2, "APPROVED")]
    assert "DUPLICATE_BANK_ACCOUNT" not in failed_ids(second)  # does not match itself
    assert len(list_vendors(session)) == 1


def test_unknown_vendor_id_raises(session):
    with pytest.raises(VendorNotFound, match="VND-2026-9999"):
        process(session, "05_resubmission", vendor_id="VND-2026-9999")
    assert list_vendors(session) == []


def test_full_seed_matches_every_expected_status(session):
    rows = seed_demo_cases(session)
    assert len(rows) == len(load_index())
    assert all(r["match"] for r in rows), [r for r in rows if not r["match"]]


def test_no_full_account_number_stored_anywhere(session):
    seed_demo_cases(session)
    secrets = {load_submission(e["case_id"]).bank.account_number for e in load_index()}
    assert len(secrets) == 6  # cases 01/07 and 04/05 share an account
    checked_values = 0
    for table in SQLModel.metadata.tables.values():
        for row in session.exec(text(f"SELECT * FROM {table.name}")).all():
            for value in row:
                if isinstance(value, str):
                    checked_values += 1
                    for secret in secrets:
                        assert secret not in value, f"full account number found in table {table.name}"
    assert checked_values > 50
    # what we do keep for display / duplicate detection
    vendor = get_vendor(session, f"VND-{YEAR}-0001")  # case 01, the first vendor seeded
    assert vendor.account_last4 == "5678" and len(vendor.account_fingerprint) == 64


def test_known_accounts_come_from_the_database(session):
    process(session, "01_happy_path")
    process(session, "03_pan_gstin_mismatch")
    accounts = known_accounts(session)
    assert len(accounts) == 2 and all(len(a.account_fingerprint) == 64 for a in accounts)


def test_status_counts_after_seeding(session):
    seed_demo_cases(session)
    latest = {}
    for entry in load_index():  # a resubmission shares its original's vendor ID, so the later case wins
        latest[vendor_id_for(entry["case_id"])] = load_expected(entry["case_id"])["expected_status"]
    expected = {s: sum(v == s.value for v in latest.values()) for s in VendorStatus}
    assert status_counts(session) == expected
    assert sum(expected.values()) == len(list_vendors(session)) == 7
