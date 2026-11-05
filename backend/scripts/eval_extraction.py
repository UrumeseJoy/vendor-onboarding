"""How accurate is the Gemini extractor on the sample PDFs?

Run from the backend folder (needs GEMINI_API_KEY; results are cached, so re-runs are free):
    python -m scripts.eval_extraction

Compares detected_type and every field against what each case's documents.json says is printed on
the document. Exact match after trimming. Note the blurry scan is DESIGNED to be hard to read.
"""

import json
import sys
import time

from app.demo_cases import CASES_DIR, load_index, load_submission
from app.extraction.gemini_extractor import gemini_extract
from app.llm import LLMError, model_name
from app.storage import demo_files


RATE_LIMIT_ATTEMPTS = 6
RATE_LIMIT_PAUSE_SECONDS = 30


def read_case(case_id, submission):
    """Read a case's documents. On a rate limit, wait and try again: files already read are cached,
    so each retry only pays for what is still missing. Returns None if it still fails."""
    for attempt in range(1, RATE_LIMIT_ATTEMPTS + 1):
        try:
            return gemini_extract(submission, demo_files(case_id, submission))
        except LLMError as error:
            limited = "rate-limiting" in str(error)
            if not limited or attempt == RATE_LIMIT_ATTEMPTS:
                print(f"  ERROR: {error}")
                return None
            print(f"  rate limited; waiting {RATE_LIMIT_PAUSE_SECONDS}s (attempt {attempt}/{RATE_LIMIT_ATTEMPTS})...", flush=True)
            time.sleep(RATE_LIMIT_PAUSE_SECONDS)


def main() -> None:
    type_ok = type_total = field_ok = field_total = 0
    mismatches, errors = [], []
    for entry in load_index():
        case_id = entry["case_id"]
        submission = load_submission(case_id)
        expected = {e["filename"]: e for e in json.loads((CASES_DIR / case_id / "documents.json").read_text())}
        print(f"\n{case_id}")
        extracted = read_case(case_id, submission)
        if extracted is None:
            errors.append(case_id)
            continue
        for doc in extracted:
            want = expected[doc.filename]
            type_total += 1
            right_type = doc.detected_type.value == want["actual_type"]
            type_ok += right_type
            matched, total = 0, len(want["fields"])
            for name, value in want["fields"].items():
                got = doc.fields.get(name)
                field_total += 1
                if got is not None and got.strip() == value.strip():
                    field_ok += 1
                    matched += 1
                else:
                    mismatches.append(f"{case_id}/{doc.filename}: {name}: expected {value!r}, got {got!r} "
                                      f"(confidence {doc.field_confidence.get(name, '-')})")
            extra = sorted(set(doc.fields) - set(want["fields"]))
            print(f"  {doc.filename:<22} type {'✓' if right_type else '✗ got ' + doc.detected_type.value:<12}"
                  f" fields {matched}/{total}  overall confidence {doc.overall_confidence:.2f}"
                  + (f"  extra fields: {', '.join(extra)}" if extra else ""))
            for note in doc.notes:
                print(f"      note: {note}")

    print(f"\n=== Overall (model: {model_name()}) ===")
    if errors:
        print(f"  Cases that could not be read at all (Gemini errors): {', '.join(errors)}")
    if not type_total:
        sys.exit("  Nothing could be evaluated.")
    print(f"  Document type accuracy:  {type_ok}/{type_total} ({type_ok / type_total:.0%})")
    print(f"  Field exact-match:       {field_ok}/{field_total} ({field_ok / field_total:.0%})")
    if mismatches:
        print(f"\n  Mismatches ({len(mismatches)}):")
        for line in mismatches:
            print(f"    - {line}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
