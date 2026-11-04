"""Pydantic models for data flowing through the pipeline.

These validate SHAPE only (types, required fields). They deliberately do NOT
check ID formats (PAN/GSTIN/IFSC...): a badly formatted ID must be accepted
here so the format-check stage can record it as a FAIL with a clear reason.
The only normalisation: strip whitespace, and uppercase PAN, GSTIN and IFSC.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ---------- Enums (str enums serialise cleanly to JSON) ----------

class Country(str, Enum):
    IN = "IN"
    US = "US"


class DocType(str, Enum):
    GST_CERTIFICATE = "GST_CERTIFICATE"
    PAN_CARD = "PAN_CARD"
    CANCELLED_CHEQUE = "CANCELLED_CHEQUE"
    BANK_LETTER = "BANK_LETTER"
    W9_FORM = "W9_FORM"
    INVOICE = "INVOICE"
    UNKNOWN = "UNKNOWN"


# Short plain-English names for document types, used in reasons and vendor messages.
DOC_TYPE_LABELS = {
    "GST_CERTIFICATE": "GST registration certificate",
    "PAN_CARD": "PAN card",
    "CANCELLED_CHEQUE": "cancelled cheque",
    "BANK_LETTER": "bank letter",
    "W9_FORM": "Form W-9",
    "INVOICE": "invoice",
    "UNKNOWN": "unrecognised document",
}

# Optional extra detail, added only to instructions for the vendor (action_required).
DOC_TYPE_HINTS = {
    "GST_CERTIFICATE": "Form GST REG-06",
    "BANK_LETTER": "on the bank's letterhead",
}


class CheckResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


class Severity(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"


class Stage(str, Enum):
    INTAKE = "INTAKE"
    EXTRACTION = "EXTRACTION"
    COMPLETENESS = "COMPLETENESS"
    FORMAT = "FORMAT"
    CROSS_CHECK = "CROSS_CHECK"
    RISK = "RISK"
    DECISION = "DECISION"
    VENDOR_MESSAGE = "VENDOR_MESSAGE"


class StageStatus(str, Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class VendorStatus(str, Enum):
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


# Every check ID in the project (kept in sync with the "Check IDs" section of CLAUDE.md).
CHECK_IDS = frozenset({
    "INTAKE_VALID",
    "DOC_READABLE", "EXTRACTION_CONFIDENCE",
    "REQUIRED_FIELDS", "REQUIRED_DOCUMENTS", "DOC_TYPE_MATCH",
    "PAN_FORMAT", "GSTIN_FORMAT", "GSTIN_CHECKSUM", "IFSC_FORMAT", "EIN_FORMAT", "ROUTING_FORMAT",
    "PAN_IN_GSTIN", "GST_STATE_MATCH", "BANK_NAME_MATCH", "DOC_FIELDS_MATCH",
    "FREE_EMAIL_DOMAIN", "BANK_COUNTRY_MISMATCH", "DUPLICATE_BANK_ACCOUNT",
})


# ---------- Helpers ----------

def mask_account(number: str) -> str:
    """Mask a bank account number, showing only the last 4 digits."""
    number = (number or "").strip()
    return "••••" + number[-4:]


# ---------- Submission models ----------

class BankDetails(BaseModel):
    """Bank details as typed into the vendor form."""
    holder_name: str
    account_number: str
    ifsc: str | None = None            # India only
    routing_number: str | None = None  # US only
    bank_country: Country

    @field_validator("holder_name", "account_number", "routing_number", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("ifsc", mode="before")
    @classmethod
    def _strip_upper(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


class UploadedDocument(BaseModel):
    """A file the vendor uploaded, with the document type they CLAIM it is."""
    slot: DocType
    filename: str


class VendorSubmission(BaseModel):
    """The full vendor form. Country-specific fields are optional here;
    the completeness stage decides what is actually required."""
    legal_name: str
    country: Country
    state: str
    address: str
    contact_email: str
    pan: str | None = None
    gstin: str | None = None
    ein: str | None = None
    bank: BankDetails
    documents: list[UploadedDocument] = Field(default_factory=list)

    @field_validator("legal_name", "state", "address", "contact_email", "ein", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("pan", "gstin", mode="before")
    @classmethod
    def _strip_upper(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


class KnownAccount(BaseModel):
    """A bank account already on file for an existing vendor (used to spot duplicates)."""
    vendor_id: str
    legal_name: str
    account_number: str
    ifsc: str | None = None
    routing_number: str | None = None


# ---------- Extraction models ----------

class ExtractedDocument(BaseModel):
    """What the AI read from one uploaded PDF: detected type, fields, confidence."""
    filename: str
    slot: DocType                      # type the vendor claimed
    detected_type: DocType             # type the AI found
    fields: dict[str, str] = Field(default_factory=dict)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    overall_confidence: float = Field(ge=0, le=1)


# ---------- Result models ----------

class CheckOutcome(BaseModel):
    """The structured result of one deterministic check."""
    check_id: str                      # e.g. "GSTIN_FORMAT"
    stage: Stage
    result: CheckResult
    severity: Severity
    reason: str
    details: dict = Field(default_factory=dict)  # e.g. expected vs found, match score


class StageResult(BaseModel):
    """The outcome of one pipeline stage, stored for the audit trail."""
    stage: Stage
    status: StageStatus
    checks: list[CheckOutcome] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: str = ""


class Decision(BaseModel):
    """The final decision for a vendor run, with every reason."""
    vendor_id: str
    status: VendorStatus
    reasons: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)  # what the vendor must provide/fix
    risk_score: int = Field(ge=0, le=100)
    decided_by: str = "rules_v1"
