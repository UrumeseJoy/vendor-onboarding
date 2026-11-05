"""Mock document extractor: the offline / demo-fallback replacement for Gemini.

Instead of reading the PDFs, it looks up what each file contains in the case's
documents.json and returns it in the same shape (ExtractedDocument) that the real
Gemini extractor will return. This keeps the demo and the tests fast, free and
repeatable, and works with no internet or API key.

Two ways to look a file up:
- mock_extract: by filename, inside one known case folder (scripts and tests).
- hash_lookup_extract: by the SHA-256 of the file's bytes, for files uploaded through
  the API. A sample PDF is recognised whatever it is called; any other file is UNKNOWN.
"""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from statistics import mean

from app.models import DocType, ExtractedDocument, UploadedDocument, VendorSubmission

SAMPLE_CASES_DIR = Path(__file__).parent.parent.parent / "sample_data" / "cases"


def _extracted(uploaded: UploadedDocument, entry: dict | None) -> ExtractedDocument:
    """Turn a documents.json entry into an ExtractedDocument (UNKNOWN if there is no entry)."""
    if entry is None:  # a file we know nothing about: unreadable
        return ExtractedDocument(filename=uploaded.filename, slot=uploaded.slot, detected_type=DocType.UNKNOWN,
                                 fields={}, field_confidence={}, overall_confidence=0.0)
    confidences = entry["mock_confidence"]
    return ExtractedDocument(
        filename=uploaded.filename,
        slot=uploaded.slot,
        detected_type=DocType(entry["actual_type"]),
        fields=entry["fields"],
        field_confidence=confidences,
        overall_confidence=mean(confidences.values()) if confidences else 0.0,
    )


def mock_extract(case_dir: Path, submission: VendorSubmission) -> list[ExtractedDocument]:
    """Build one ExtractedDocument per uploaded file from the case's documents.json."""
    entries = {e["filename"]: e for e in json.loads((case_dir / "documents.json").read_text())}
    return [_extracted(uploaded, entries.get(uploaded.filename)) for uploaded in submission.documents]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache
def build_sample_index() -> dict[str, tuple[str, dict]]:
    """SHA-256 of every sample PDF -> (case_id, its documents.json entry). Built once."""
    index = {}
    for case_dir in sorted(p for p in SAMPLE_CASES_DIR.iterdir() if p.is_dir()):
        entries = {e["filename"]: e for e in json.loads((case_dir / "documents.json").read_text())}
        for pdf in sorted((case_dir / "files").glob("*.pdf")):
            if pdf.name in entries:
                # Identical files in two cases (e.g. the same PAN card in 04 and 05) carry identical data.
                index.setdefault(file_sha256(pdf), (case_dir.name, entries[pdf.name]))
    return index


def hash_lookup_extract(submission: VendorSubmission, stored_files: dict[str, Path]) -> list[ExtractedDocument]:
    """Recognise uploaded files by their content hash. Unknown files come back as UNKNOWN."""
    index = build_sample_index()
    results = []
    for uploaded in submission.documents:
        path = stored_files.get(uploaded.filename)
        match = index.get(file_sha256(path)) if path and path.is_file() else None
        results.append(_extracted(uploaded, match[1] if match else None))
    return results
