"""Document extraction with Gemini (via llm.py), with two safeguards:

1. Text-layer verification: if a PDF has real text, every value Gemini returns must actually appear
   in that text (ignoring case and spaces). A value that is not there is capped at confidence 0.5
   so later checks treat it as untrusted. Image-only PDFs keep Gemini's own confidence.
2. A file-based cache keyed by file hash, claimed slot, model and prompt version, so the same file
   never costs a second API call. Only sample documents are cached: a real vendor's document is
   never written to disk by the cache (its fields include a bank account number). Lookup order: runtime cache (.cache/extraction), then the committed
   read-only seed cache (sample_data/extraction_cache, the pre-read sample documents), then Gemini.

If Gemini fails for any file the error is raised, so the pipeline marks EXTRACTION as FAILED and the
vendor can never be approved on the back of a failed read.
"""

import json
import logging
from pathlib import Path
from statistics import mean

import pymupdf

from app import llm
from app.extraction.mock_extractor import build_sample_index, file_sha256
from app.models import DocType, ExtractedDocument, UploadedDocument, VendorSubmission
from app.settings import cache_dir, seed_cache_dir

logger = logging.getLogger(__name__)

VERIFIED_MIN_CONFIDENCE = 0.95    # value found in the PDF's own text
UNVERIFIED_MAX_CONFIDENCE = 0.5   # value NOT found in the PDF's own text
MIN_TEXT_LAYER_CHARS = 20


def _squash(text: str) -> str:
    return "".join(text.split()).lower()


def pdf_text(pdf_bytes: bytes) -> str:
    """All text in the PDF (empty for a scan with no text layer)."""
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def verify_against_text(reading: dict, text: str) -> tuple[dict[str, float], list[str]]:
    """Returns (adjusted confidences, notes). No text layer -> Gemini's confidences, unchanged."""
    confidence = dict(reading["field_confidence"])
    notes = []
    if len(text.strip()) < MIN_TEXT_LAYER_CHARS:
        return confidence, notes
    haystack = _squash(text)
    for name, value in reading["fields"].items():
        if _squash(value) in haystack:
            confidence[name] = max(confidence[name], VERIFIED_MIN_CONFIDENCE)
        else:
            confidence[name] = min(confidence[name], UNVERIFIED_MAX_CONFIDENCE)
            notes.append(f"{name}: not found in document text")
    return confidence, notes


# ---------- cache ----------

def _cache_meta(slot: DocType) -> dict:
    return {"model": llm.model_name(), "prompt_version": llm.PROMPT_VERSION, "slot": slot.value}


def _cache_path(sha: str) -> Path:
    return cache_dir() / f"{sha}.json"


def _read_cache_file(path: Path, slot: DocType) -> dict | None:
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return saved["reading"] if saved.get("meta") == _cache_meta(slot) else None


def _cache_read(sha: str, slot: DocType) -> dict | None:
    """Runtime cache first, then the committed seed cache (sample documents). Never written to."""
    return (_read_cache_file(_cache_path(sha), slot)
            or _read_cache_file(seed_cache_dir() / f"{sha}.json", slot))


def _cache_write(sha: str, slot: DocType, reading: dict) -> None:
    try:
        _cache_path(sha).parent.mkdir(parents=True, exist_ok=True)
        _cache_path(sha).write_text(json.dumps({"meta": _cache_meta(slot), "reading": reading}, indent=2))
    except OSError:
        logger.warning("Could not write the extraction cache", exc_info=True)


# ---------- extraction ----------

def _read_one(uploaded: UploadedDocument, pdf_bytes: bytes, sha: str) -> ExtractedDocument:
    reading = _cache_read(sha, uploaded.slot)
    if reading is None:
        reading = llm.extract_document(pdf_bytes, uploaded.slot)  # raises LLMError on failure
        if sha in build_sample_index():  # privacy: only the synthetic samples are ever cached,
            _cache_write(sha, uploaded.slot, reading)  # never a real vendor's document (rule 13)
    confidence, notes = verify_against_text(reading, pdf_text(pdf_bytes))
    return ExtractedDocument(
        filename=uploaded.filename, slot=uploaded.slot, detected_type=DocType(reading["detected_type"]),
        fields=reading["fields"], field_confidence=confidence,
        overall_confidence=mean(confidence.values()) if confidence else 0.0,
        notes=notes + ([reading["notes"]] if reading.get("notes") else []))


def gemini_extract(submission: VendorSubmission, stored_files: dict[str, Path]) -> list[ExtractedDocument]:
    """One ExtractedDocument per uploaded file. A file that was not stored is UNKNOWN."""
    results = []
    for uploaded in submission.documents:
        path = stored_files.get(uploaded.filename)
        if path is None or not path.is_file():
            results.append(ExtractedDocument(
                filename=uploaded.filename, slot=uploaded.slot, detected_type=DocType.UNKNOWN,
                fields={}, field_confidence={}, overall_confidence=0.0, notes=["file not found"]))
            continue
        results.append(_read_one(uploaded, path.read_bytes(), file_sha256(path)))
    return results
