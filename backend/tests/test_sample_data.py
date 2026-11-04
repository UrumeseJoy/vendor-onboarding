import json
import re
from pathlib import Path

import pytest

from app.checks.id_utils import aba_routing_valid, gstin_checksum
from app.models import VendorStatus, VendorSubmission

BACKEND = Path(__file__).parent.parent
CASES_DIR = BACKEND / "sample_data" / "cases"
CLAUDE_MD = BACKEND.parent / "CLAUDE.md"

CASE_IDS = sorted(p.name for p in CASES_DIR.iterdir() if p.is_dir())


def load(case_id: str, name: str):
    return json.loads((CASES_DIR / case_id / name).read_text())


def valid_check_ids() -> set[str]:
    """Read the check IDs listed in the 'Check IDs' section of CLAUDE.md."""
    section = CLAUDE_MD.read_text().split("## Check IDs")[1].split("\n## ")[0]
    ids = set()
    for line in section.splitlines():
        if line.startswith("- ") and ":" in line:
            text = re.sub(r"\(.*?\)", "", line.split(":", 1)[1])  # drop "(comments)"
            ids.update(part.strip() for part in text.split(",") if part.strip())
    return ids


def test_gstin_checksum_known_real_example():
    # A real published GSTIN, so we are not only testing the function against itself.
    assert gstin_checksum("27AAPFU0939F1Z") == "V"


@pytest.mark.parametrize("case_id", [c for c in CASE_IDS if not c.startswith("08")])
def test_gstin_checksum_in_each_indian_case(case_id):
    gstin = load(case_id, "submission.json")["gstin"]
    assert len(gstin) == 15
    assert gstin_checksum(gstin[:14]) == gstin[14]


def test_aba_routing_case_08():
    routing = load("08_us_vendor", "submission.json")["bank"]["routing_number"]
    assert aba_routing_valid(routing)
    changed = routing[:-1] + str((int(routing[-1]) + 1) % 10)
    assert not aba_routing_valid(changed)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_submission_validates(case_id):
    VendorSubmission(**load(case_id, "submission.json"))


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_documents_match_submission(case_id):
    uploaded = {d["filename"] for d in load(case_id, "submission.json")["documents"]}
    described = {d["filename"] for d in load(case_id, "documents.json")}
    assert uploaded == described


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_expected_values_are_valid(case_id):
    expected = load(case_id, "expected.json")
    VendorStatus(expected["expected_status"])
    unknown = set(expected["expected_failed_checks"]) - valid_check_ids()
    assert not unknown, f"unknown check IDs: {unknown}"


def test_index_lists_all_cases():
    index = json.loads((CASES_DIR / "index.json").read_text())
    assert len(index) == 8
    assert [c["case_id"] for c in index] == CASE_IDS
    for entry in index:
        assert (CASES_DIR / entry["case_id"]).is_dir()
        assert entry["expected_status"] == load(entry["case_id"], "expected.json")["expected_status"]


def test_check_ids_in_code_match_claude_md():
    from app.models import CHECK_IDS
    assert CHECK_IDS == valid_check_ids()
