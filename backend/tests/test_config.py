import copy

import pytest
import yaml
from pydantic import ValidationError

from app.config import RULES_PATH, RulesConfig, RulesError, get_rules, load_rules, state_name_for_gst_code
from app.models import Country, DocType


def raw_rules() -> dict:
    """The real rules as a plain dict, safe to modify in a test."""
    return copy.deepcopy(yaml.safe_load(RULES_PATH.read_text()))


def test_rules_load():
    assert isinstance(get_rules(), RulesConfig)


def test_pass_threshold_above_warn():
    nm = get_rules().name_match
    assert nm.pass_threshold == 90
    assert nm.warn_threshold == 75
    assert nm.pass_threshold > nm.warn_threshold


def test_state_name_for_gst_code():
    assert state_name_for_gst_code("33") == "Tamil Nadu"
    assert state_name_for_gst_code("99") is None


def test_india_required_documents():
    docs = get_rules().required_documents[Country.IN]
    assert [DocType.GST_CERTIFICATE] in docs
    bank = next(group for group in docs if DocType.CANCELLED_CHEQUE in group)
    assert DocType.BANK_LETTER in bank


def test_pass_below_warn_rejected():
    data = raw_rules()
    data["name_match"]["pass_threshold"] = 70
    with pytest.raises(ValidationError, match="pass_threshold must be greater"):
        RulesConfig(**data)


def test_invalid_doctype_rejected():
    data = raw_rules()
    data["required_documents"]["IN"].append(["PASSPORT"])
    with pytest.raises(ValidationError):
        RulesConfig(**data)


def test_invalid_file_gives_clear_error(tmp_path):
    bad = tmp_path / "rules.yaml"
    data = raw_rules()
    data["extraction"]["min_field_confidence"] = 1.5
    bad.write_text(yaml.safe_dump(data))
    with pytest.raises(RulesError, match="min_field_confidence"):
        load_rules(bad)


def test_check_severity_unknown_id_rejected():
    data = raw_rules()
    data["check_severity"]["NOT_A_CHECK"] = "HARD"
    with pytest.raises(ValidationError, match="NOT_A_CHECK"):
        RulesConfig(**data)


def test_check_severity_invalid_value_rejected():
    data = raw_rules()
    data["check_severity"]["PAN_FORMAT"] = "MEDIUM"
    with pytest.raises(ValidationError):
        RulesConfig(**data)
