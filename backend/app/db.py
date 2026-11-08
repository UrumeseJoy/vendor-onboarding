"""Database tables (SQLModel) and engine setup. SQLite locally, Postgres when deployed.

No full bank account number is ever stored here: only a keyed fingerprint and the last 4 digits.
"""

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import DateTime
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
    created_at: datetime = Field(sa_type=DateTime(timezone=True))  # timezone-aware on Postgres
    updated_at: datetime = Field(sa_type=DateTime(timezone=True))
    latest_run_id: str | None = None
    run_count: int = 0


class PipelineRunRecord(SQLModel, table=True):
    """One row per pipeline run, so every decision can be explained later (audit trail)."""
    run_id: str = Field(primary_key=True)
    vendor_id: str = Field(foreign_key="vendor.vendor_id", index=True)
    run_number: int  # 1, 2, ... per vendor
    started_at: datetime = Field(sa_type=DateTime(timezone=True))
    finished_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    status: str
    risk_score: int
    had_errors: bool = False
    upload_id: str | None = None  # where the run's documents are stored ("demo:<case_id>" for demo cases)
    # Plain text columns holding JSON: they behave the same on SQLite and Postgres.
    submission_json: str  # the submission with the account number masked
    run_json: str         # the full PipelineRun


def normalise_database_url(url: str) -> str:
    """Hosting providers hand out postgres:// or postgresql:// URLs; we use the psycopg (v3) driver."""
    url = url.strip()
    for old in ("postgres://", "postgresql://"):
        if url.startswith(old):
            return "postgresql+psycopg://" + url[len(old):]
    return url


def get_engine(database_url: str | None = None) -> Engine:
    url = normalise_database_url(database_url or os.getenv("DATABASE_URL", "") or DEFAULT_DATABASE_URL)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # pool_pre_ping: a free-tier database drops idle connections; test each one before using it
    return create_engine(url, pool_pre_ping=True)


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
