"""Chooses the document extractor from EXTRACTOR_MODE in .env.

- "mock" (default): recognise sample PDFs by their content hash (no AI, no internet).
- "gemini": read documents with Gemini (needs GEMINI_API_KEY).
- anything else: an error.
"""

from collections.abc import Callable
from pathlib import Path

from app.extraction.mock_extractor import hash_lookup_extract
from app.models import ExtractedDocument, VendorSubmission
from app.settings import extractor_mode

Extractor = Callable[[VendorSubmission], list[ExtractedDocument]]


class ExtractorNotAvailable(RuntimeError):
    """EXTRACTOR_MODE names an extractor that does not exist."""


def get_extractor(stored_files: dict[str, Path]) -> Extractor:
    """stored_files: submission filename -> path of the saved PDF."""
    mode = extractor_mode()
    if mode == "mock":
        return lambda submission: hash_lookup_extract(submission, stored_files)
    if mode == "gemini":
        from app.extraction.gemini_extractor import gemini_extract  # imported late: mock mode needs no SDK
        return lambda submission: gemini_extract(submission, stored_files)
    raise ExtractorNotAvailable(f"EXTRACTOR_MODE '{mode}' is not recognised. Use 'mock' or 'gemini'.")


def lazy_extractor(stored_files: dict[str, Path]) -> Extractor:
    """Pick the extractor only when the EXTRACTION stage runs, so a bad EXTRACTOR_MODE becomes a
    failed EXTRACTION stage (fail safe: PENDING) instead of a crash before the run starts."""
    return lambda submission: get_extractor(stored_files)(submission)
