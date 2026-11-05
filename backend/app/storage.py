"""Saving uploaded PDFs safely, and finding a run's documents again.

Uploads go to STORAGE_DIR/uploads/<upload_id>/<filename>. Every filename is reduced to a safe
base name, so a name like "../../evil.pdf" can never write outside STORAGE_DIR.
Demo-case runs use the reference "demo:<case_id>" and are served from the sample folder.
"""

import re
import uuid
from pathlib import Path

from app.extraction.mock_extractor import SAMPLE_CASES_DIR
from app.models import VendorSubmission
from app.settings import storage_dir

MAX_FILES = 6
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
UPLOAD_ID_RE = re.compile(r"[0-9a-f]{32}")
CASE_ID_RE = re.compile(r"[0-9A-Za-z_]+")
DEMO_PREFIX = "demo:"


class UploadError(ValueError):
    """An upload was rejected. The message is safe to show to the user (HTTP 400)."""


def sanitise_filename(name: str) -> str:
    """Base name only, letters/digits/dot/dash/underscore only, no leading dots. Rejects empty names."""
    base = (name or "").replace("\\", "/").split("/")[-1]
    safe = re.sub(r"[^A-Za-z0-9._-]", "", base).lstrip(".")
    if not safe:
        raise UploadError(f"The file name '{name}' is not allowed. Use letters, digits, dots, dashes or underscores.")
    return safe


def validate_uploads(files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    """Check every upload; returns (safe name, content) pairs. Raises UploadError on the first problem."""
    if len(files) > MAX_FILES:
        raise UploadError(f"Too many files: {len(files)}. The maximum is {MAX_FILES}.")
    cleaned, seen = [], set()
    for original_name, content in files:
        name = sanitise_filename(original_name)
        if not name.lower().endswith(".pdf"):
            raise UploadError(f"'{name}' is not a PDF. Only .pdf files can be uploaded.")
        if len(content) > MAX_FILE_BYTES:
            raise UploadError(f"'{name}' is larger than the 10 MB limit.")
        if not content.startswith(b"%PDF"):
            raise UploadError(f"'{name}' is not a valid PDF file.")
        if name in seen:
            raise UploadError(f"The file name '{name}' was uploaded more than once.")
        seen.add(name)
        cleaned.append((name, content))
    return cleaned


def save_uploads(files: list[tuple[str, bytes]]) -> tuple[str, dict[str, Path]]:
    """Validate and save the uploads. Returns (upload_id, safe filename -> saved path)."""
    cleaned = validate_uploads(files)  # nothing is written unless every file is valid
    upload_id = uuid.uuid4().hex
    folder = (storage_dir() / "uploads" / upload_id).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    saved = {}
    for name, content in cleaned:
        path = (folder / name).resolve()
        if path.parent != folder:  # defence in depth: never write outside the upload folder
            raise UploadError(f"The file name '{name}' is not allowed.")
        path.write_bytes(content)
        saved[name] = path
    return upload_id, saved


def match_submission_files(submission: VendorSubmission, upload_names: list[str]) -> VendorSubmission:
    """Every document in the submission must match exactly one upload, and vice versa.
    Returns the submission with its document filenames replaced by the safe names."""
    claimed = [sanitise_filename(d.filename) for d in submission.documents]
    duplicates = sorted({n for n in claimed if claimed.count(n) > 1})
    if duplicates:
        raise UploadError(f"The submission lists the same file more than once: {', '.join(duplicates)}.")
    missing = [n for n in claimed if n not in upload_names]
    if missing:
        raise UploadError(f"The submission lists files that were not uploaded: {', '.join(missing)}.")
    extra = [n for n in upload_names if n not in claimed]
    if extra:
        raise UploadError(f"These uploaded files are not listed in the submission: {', '.join(extra)}.")
    documents = [d.model_copy(update={"filename": n}) for d, n in zip(submission.documents, claimed)]
    return submission.model_copy(update={"documents": documents})


def demo_files(case_id: str, submission: VendorSubmission) -> dict[str, Path]:
    """The sample PDFs of a demo case, keyed by submission filename."""
    folder = SAMPLE_CASES_DIR / case_id / "files"
    return {d.filename: folder / d.filename for d in submission.documents}


def document_path(upload_id: str | None, filename: str) -> Path | None:
    """Where a run's document lives, or None if the reference or name is not valid or the file is gone."""
    if not upload_id:
        return None
    try:
        if sanitise_filename(filename) != filename:
            return None
    except UploadError:
        return None
    if upload_id.startswith(DEMO_PREFIX):
        case_id = upload_id.removeprefix(DEMO_PREFIX)
        if not CASE_ID_RE.fullmatch(case_id):
            return None
        path = SAMPLE_CASES_DIR / case_id / "files" / filename
    elif UPLOAD_ID_RE.fullmatch(upload_id):
        path = storage_dir() / "uploads" / upload_id / filename
    else:
        return None
    return path if path.is_file() else None
