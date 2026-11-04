"""Run a sample case through the pipeline and print a stage-by-stage report.

Run from the backend folder:
    python -m scripts.run_case 04_wrong_document
    python -m scripts.run_case --all
"""

import argparse
import os
import sys

from app.demo_cases import load_expected, load_index, load_submission, run_demo_case
from app.models import CheckResult, PipelineRun, StageStatus, VendorStatus

USE_COLOUR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
COLOURS = {"green": "32", "yellow": "33", "red": "31", "grey": "90", "bold": "1"}

STAGE_SYMBOL = {
    StageStatus.PASSED: ("✓", "green"), StageStatus.WARNING: ("!", "yellow"),
    StageStatus.FAILED: ("✗", "red"), StageStatus.SKIPPED: ("–", "grey"),
}
CHECK_SYMBOL = {CheckResult.FAIL: ("✗", "red"), CheckResult.WARN: ("!", "yellow")}
STATUS_COLOUR = {VendorStatus.APPROVED: "green", VendorStatus.PENDING: "yellow", VendorStatus.REJECTED: "red"}


def paint(text: str, colour: str) -> str:
    return f"\033[{COLOURS[colour]}m{text}\033[0m" if USE_COLOUR else text


def print_report(case_id: str, run: PipelineRun) -> None:
    sub = load_submission(case_id)
    print(paint(f"\n=== {case_id}: {sub.legal_name} ({run.vendor_id}) ===", "bold"))
    for stage in run.stages:
        symbol, colour = STAGE_SYMBOL.get(stage.status, ("?", "grey"))
        print(f"  {paint(symbol, colour)} {stage.stage.value:<15} {stage.summary}")
        for check in stage.checks:
            if check.result in CHECK_SYMBOL:
                sym, col = CHECK_SYMBOL[check.result]
                print(f"      {paint(sym, col)} {check.check_id} [{check.severity.value}]: {check.reason}")

    d = run.decision
    if d is None:
        print(paint("\n  No decision was made.", "red"))
        return
    print(f"\n  Final status: {paint(d.status.value, STATUS_COLOUR[d.status])}    Risk score: {d.risk_score}"
          f"    Checks: {d.checks_summary}")
    for title, items in [("Reasons (internal)", d.reasons),
                         ("Missing items (for the vendor)", d.missing_items),
                         ("Review notes (internal)", d.review_notes)]:
        if items:
            print(f"  {title}:")
            for item in items:
                print(f"    - {item}")


def run_all() -> bool:
    rows = []
    for entry in load_index():
        case_id = entry["case_id"]
        run = run_demo_case(case_id)
        print_report(case_id, run)
        expected = load_expected(case_id)["expected_status"]
        actual = run.decision.status.value if run.decision else "NONE"
        rows.append((case_id, expected, actual, expected == actual))

    print(paint("\n=== Summary ===", "bold"))
    print(f"  {'Case':<24} {'Expected':<10} {'Actual':<10} Match")
    for case_id, expected, actual, ok in rows:
        mark = paint("✓", "green") if ok else paint("✗", "red")
        print(f"  {case_id:<24} {expected:<10} {actual:<10} {mark}")
    passed = sum(ok for *_, ok in rows)
    print(f"\n  {passed} of {len(rows)} cases match the expected status.")
    return passed == len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case_id", nargs="?", help="case folder name, e.g. 04_wrong_document")
    parser.add_argument("--all", action="store_true", help="run every case in index.json order")
    args = parser.parse_args()
    if args.all:
        sys.exit(0 if run_all() else 1)
    if not args.case_id:
        parser.error("give a case_id or --all")
    print_report(args.case_id, run_demo_case(args.case_id))


if __name__ == "__main__":
    main()
