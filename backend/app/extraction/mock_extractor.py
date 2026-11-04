"""Mock document extractor: the offline / demo-fallback replacement for Gemini.

Instead of reading the PDFs, it looks up what each file contains in the case's
documents.json and returns it in the same shape (ExtractedDocument) that the real
Gemini extractor will return. This keeps the demo and the tests fast, free and
repeatable, and works with no internet or API key.
"""

import json
from pathlib import Path
from statistics import mean

from app.models import DocType, ExtractedDocument, VendorSubmission


def mock_extract(case_dir: Path, submission: VendorSubmission) -> list[ExtractedDocument]:
    """Build one ExtractedDocument per uploaded file from the case's documents.json."""
    entries = {e["filename"]: e for e in json.loads((case_dir / "documents.json").read_text())}
    results = []
    for uploaded in submission.documents:
        entry = entries.get(uploaded.filename)
        if entry is None:  # file we know nothing about: unreadable
            results.append(ExtractedDocument(
                filename=uploaded.filename, slot=uploaded.slot,
                detected_type=DocType.UNKNOWN, fields={}, field_confidence={}, overall_confidence=0.0))
            continue
        confidences = entry["mock_confidence"]
        results.append(ExtractedDocument(
            filename=uploaded.filename,
            slot=uploaded.slot,
            detected_type=DocType(entry["actual_type"]),
            fields=entry["fields"],
            field_confidence=confidences,
            overall_confidence=mean(confidences.values()) if confidences else 0.0,
        ))
    return results
