"""Database tables (SQLModel) and engine setup. SQLite locally, Postgres when deployed.

No full bank account number is ever stored here: only a keyed fingerprint and the last 4 digits.
"""

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import Engine
from sqlmodel import Field, SQLModel, create_engine

load_dotenv(Path(__file__).parent.parent / ".env")  # backend/.env; does not override real env vars

DEFAULT_DATABASE_URL = "sqlite:///./vendor_onboarding.db"

# Status of a vendor whose first run is still in progress (reserves its vendor ID).
PROCESSING = "PROCESSING"


class Vendor(SQLModel, table=True):
    """One row per vendor: its latest status plus pointers to its runs."""
    vendor_id: str = Field(primary_key=True)
    legal_name: str
    country: str
    status: str
    risk_score: int
    account_fingerprint: str | None = Field(default=None, index=True)
    account_last4: str | None = None
    created_at: datetime
    updated_at: datetime
    latest_run_id: str | None = None
    run_count: int = 0


class PipelineRunRecord(SQLModel, table=True):
    """One row per pipeline run, so every decision can be explained later (audit trail)."""
    run_id: str = Field(primary_key=True)
    vendor_id: str = Field(foreign_key="vendor.vendor_id", index=True)
    run_number: int  # 1, 2, ... per vendor
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    risk_score: int
    had_errors: bool = False
    upload_id: str | None = None  # where the run's documents are stored ("demo:<case_id>" for demo cases)
    submission_json: str  # the submission with the account number masked
    run_json: str         # the full PipelineRun


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
