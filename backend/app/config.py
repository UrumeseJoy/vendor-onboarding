"""Loads and validates rules.yaml.

The Pydantic models below describe the structure of the file. If the file is
wrong, get_rules() raises a RulesError that says what is wrong.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.models import Country, DocType, Severity

RULES_PATH = Path(__file__).parent / "rules.yaml"


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
    flags: dict[str, RiskFlagRule]


class RulesConfig(BaseModel):
    """The whole rules.yaml file."""
    required_fields: dict[Country, list[str]]
    required_documents: dict[Country, list[list[DocType]]]  # each inner list: any one of these
    name_match: NameMatchRules
    extraction: ExtractionRules
    risk: RiskRules
    gst_state_codes: dict[str, str]


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
