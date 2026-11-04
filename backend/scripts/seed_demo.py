"""Fill the database with the demo cases, processed through the real service.

Run from the backend folder:
    python -m scripts.seed_demo --reset
"""

import argparse
import sys

from sqlmodel import Session, SQLModel

from app.db import get_engine, init_db
from app.demo_cases import seed_demo_cases
from app.repository import list_vendors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete and recreate the database first")
    args = parser.parse_args()

    engine = get_engine()
    if args.reset:
        SQLModel.metadata.drop_all(engine)
    init_db(engine)

    with Session(engine) as session:
        if list_vendors(session):
            sys.exit("The database already has vendors. Run with --reset to start from scratch.")
        rows = seed_demo_cases(session)

    print(f"  {'Case':<24} {'Vendor ID':<15} {'Run':<4} {'Status':<10} Matches expected")
    for r in rows:
        print(f"  {r['case_id']:<24} {r['vendor_id']:<15} {r['run_number']:<4} {r['status']:<10} "
              f"{'✓' if r['match'] else '✗ (expected ' + r['expected'] + ')'}")
    print(f"\n  {sum(r['match'] for r in rows)} of {len(rows)} cases match the expected status.")
    sys.exit(0 if all(r["match"] for r in rows) else 1)


if __name__ == "__main__":
    main()
