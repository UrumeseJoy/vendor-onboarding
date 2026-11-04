import json
from pathlib import Path

import pymupdf
import pytest

CASES_DIR = Path(__file__).parent.parent / "sample_data" / "cases"

# Field whose value must appear in the text of a clean PDF of each type
KEY_FIELD = {
    "GST_CERTIFICATE": "gstin",
    "PAN_CARD": "pan",
    "CANCELLED_CHEQUE": "account_number",
    "BANK_LETTER": "account_number",
    "W9_FORM": "ein",
    "INVOICE": "invoice_number",
}

ENTRIES = [
    (case_dir.name, entry)
    for case_dir in sorted(CASES_DIR.iterdir())
    if case_dir.is_dir()
    for entry in json.loads((case_dir / "documents.json").read_text())
]
CLEAN = [(c, e) for c, e in ENTRIES if e["quality"] == "clean"]
BLURRY = [(c, e) for c, e in ENTRIES if e["quality"] == "blurry_scan"]


def ids(params):
    return [f"{case}/{entry['filename']}" for case, entry in params]


def open_pdf(case_id, entry):
    return pymupdf.open(CASES_DIR / case_id / "files" / entry["filename"])


@pytest.mark.parametrize("case_id,entry", ENTRIES, ids=ids(ENTRIES))
def test_pdf_exists_with_one_page(case_id, entry):
    path = CASES_DIR / case_id / "files" / entry["filename"]
    assert path.is_file()
    assert open_pdf(case_id, entry).page_count == 1


@pytest.mark.parametrize("case_id,entry", CLEAN, ids=ids(CLEAN))
def test_clean_pdf_has_key_value_and_specimen(case_id, entry):
    text = open_pdf(case_id, entry)[0].get_text()
    key = KEY_FIELD[entry["actual_type"]]
    assert entry["fields"][key] in text
    assert "SPECIMEN" in text


@pytest.mark.parametrize("case_id,entry", BLURRY, ids=ids(BLURRY))
def test_blurry_pdf_has_no_text_layer(case_id, entry):
    page = open_pdf(case_id, entry)[0]
    assert len(page.get_text().strip()) < 5
    assert page.get_images()  # it is an image-only page
