import json

import pytest
from pydantic import ValidationError

from app.models import Decision, VendorStatus, VendorSubmission, mask_account


def make_submission(**overrides):
    data = {
        "legal_name": "  Acme Private Limited ",
        "country": "IN",
        "state": "Tamil Nadu",
        "address": "1 Main Road, Chennai",
        "contact_email": "accounts@acme.in",
        "pan": " abcde1234f ",
        "gstin": " 33abcde1234f1z5 ",
        "bank": {
            "holder_name": "Acme Private Limited",
            "account_number": "50200012345678",
            "ifsc": " hdfc0001234 ",
            "bank_country": "IN",
        },
        "documents": [{"slot": "GST_CERTIFICATE", "filename": "gst.pdf"}],
    }
    data.update(overrides)
    return data


def test_valid_indian_submission_normalised():
    s = VendorSubmission(**make_submission())
    assert s.legal_name == "Acme Private Limited"
    assert s.pan == "ABCDE1234F"
    assert s.gstin == "33ABCDE1234F1Z5"
    assert s.bank.ifsc == "HDFC0001234"


def test_bad_pan_format_still_accepted():
    s = VendorSubmission(**make_submission(pan="abc123"))
    assert s.pan == "ABC123"


def test_missing_legal_name_rejected():
    data = make_submission()
    del data["legal_name"]
    with pytest.raises(ValidationError):
        VendorSubmission(**data)


def test_mask_account():
    assert mask_account("50200012345678") == "••••5678"
    assert mask_account("") == "••••"
    assert mask_account("12") == "••••12"


def test_decision_serialises_status_as_string():
    d = Decision(vendor_id="VND-2026-0001", status=VendorStatus.PENDING, risk_score=40)
    assert json.loads(d.model_dump_json())["status"] == "PENDING"
