"""Loads and validates rules.yaml.

The Pydantic models below describe the structure of the file. If the file is
wrong, get_rules() raises a RulesError that says what is wrong.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.models import CHECK_IDS, Country, DocType, Severity

RULES_PATH = Path(__file__).parent / "rules.yaml"

RISK_CHECK_IDS = {"FREE_EMAIL_DOMAIN", "BANK_COUNTRY_MISMATCH", "DUPLICATE_BANK_ACCOUNT"}
# Form fields a rule may require ("bank.x" = field x of the bank details).
FORM_FIELDS = {"legal_name", "state", "address", "contact_email", "pan", "gstin", "ein",
               "bank.holder_name", "bank.account_number", "bank.ifsc", "bank.routing_number", "bank.bank_country"}


class RulesError(Exception):
    """rules.yaml is missing or invalid."""


class NameMatchRules(BaseModel):
    """Thresholds and abbreviation expansions for fuzzy company-name matching."""
    pass_threshold: int = Field(ge=0, le=100)
    warn_threshold: int = Field(ge=0, le=100)
    normalise: dict[str, str]

    @model_validator(mode="after")
    def _pass_above_warn(self):
        if self.pass_threshold <= self.warn_threshold:
            raise ValueError("pass_threshold must be greater than warn_threshold")
        return self


class ExtractionRules(BaseModel):
    """Minimum confidence for trusting what was read from a document."""
    min_field_confidence: float = Field(ge=0, le=1)
    min_document_confidence: float = Field(ge=0, le=1)


class RiskFlagRule(BaseModel):
    """One risk flag: how serious it is and how much it adds to the risk score."""
    severity: Severity
    score: int = Field(ge=0, le=100)


class RiskRules(BaseModel):
    """Free-email domain list and the risk flags."""
    free_email_domains: list[str]
    review_threshold: int = Field(ge=0, le=100)  # risk score at which a vendor goes to review
    flags: dict[str, RiskFlagRule]


class RulesConfig(BaseModel):
    """The whole rules.yaml file."""
    required_fields: dict[Country, list[str]]
    required_documents: dict[Country, list[list[DocType]]]  # each inner list: any one of these
    name_match: NameMatchRules
    extraction: ExtractionRules
    risk: RiskRules
    expected_fields: dict[DocType, list[list[str]]]  # per document type: groups, one field of each required
    check_severity: dict[str, Severity]  # check ID -> how serious a non-pass is
    gst_state_codes: dict[str, str]

    @model_validator(mode="after")
    def _risk_flags_agree_with_check_severity(self):
        for flag, rule in self.risk.flags.items():
            if self.check_severity.get(flag) != rule.severity:
                raise ValueError(
                    f"risk flag {flag} has severity {rule.severity.value} in risk.flags but "
                    f"{getattr(self.check_severity.get(flag), 'value', None)} in check_severity")
        return self

    @model_validator(mode="after")
    def _complete(self):
        """Fail at load time, not halfway through a run, if a section is incomplete."""
        problems = []
        for section in ("required_fields", "required_documents"):
            missing = [c.value for c in Country if c not in getattr(self, section)]
            if missing:
                problems.append(f"{section} has no entry for {', '.join(missing)}")
        missing_ids = sorted(CHECK_IDS - set(self.check_severity))
        if missing_ids:
            problems.append(f"check_severity has no severity for {missing_ids}")
        if set(self.risk.flags) != RISK_CHECK_IDS:
            problems.append(f"risk.flags must list exactly {sorted(RISK_CHECK_IDS)}")
        for country, fields in self.required_fields.items():
            unknown = [f for f in fields if f not in FORM_FIELDS]
            if unknown:
                problems.append(f"required_fields.{country.value} has unknown fields {unknown}")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @field_validator("expected_fields")
    @classmethod
    def _expected_groups_not_empty(cls, v):
        for doc_type, groups in v.items():
            if not groups or any(not group for group in groups):
                raise ValueError(f"expected_fields for {doc_type.value} must be a list of non-empty groups")
        return v

    @field_validator("check_severity")
    @classmethod
    def _known_check_ids(cls, v):
        unknown = sorted(set(v) - CHECK_IDS)
        if unknown:
            raise ValueError(f"check_severity has unknown check IDs: {unknown}")
        return v


def load_rules(path: Path = RULES_PATH) -> RulesConfig:
    """Read and validate a rules file (no caching)."""
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as e:
        raise RulesError(f"Cannot read rules file {path}: {e}") from e
    try:
        return RulesConfig(**data)
    except (ValidationError, TypeError) as e:
        raise RulesError(f"Invalid rules file {path}:\n{e}") from e


@lru_cache
def get_rules() -> RulesConfig:
    """Load rules.yaml once and reuse it."""
    return load_rules()


def state_name_for_gst_code(code: str) -> str | None:
    """Return the state name for a 2-digit GST code, or None if unknown."""
    return get_rules().gst_state_codes.get(code)
