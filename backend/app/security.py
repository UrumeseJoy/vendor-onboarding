"""Bank account fingerprints, so duplicates can be found without storing account numbers.

A fingerprint is an HMAC-SHA256 of "<account number>|<IFSC or routing number>" using a secret key.
Without the key it cannot be reversed or guessed by trying account numbers.
"""

import hashlib
import hmac
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from app.models import Country, VendorSubmission

load_dotenv(Path(__file__).parent.parent / ".env")  # backend/.env; does not override real env vars

logger = logging.getLogger(__name__)

DEV_KEY = "insecure-development-key"
_warned = False


def _key() -> bytes:
    global _warned
    key = os.getenv("ACCOUNT_HASH_KEY")
    if not key:
        if not _warned:
            logger.warning("ACCOUNT_HASH_KEY is not set; using an insecure development key.")
            _warned = True
        key = DEV_KEY
    return key.encode()


def account_fingerprint(account_number: str, bank_code: str) -> str:
    """Keyed fingerprint of an account at a bank branch (bank_code = IFSC or routing number)."""
    message = f"{account_number.replace(' ', '')}|{bank_code.replace(' ', '').upper()}"
    return hmac.new(_key(), message.encode(), hashlib.sha256).hexdigest()


def bank_code_for(submission: VendorSubmission) -> str:
    """IFSC for India, routing number for the US."""
    bank = submission.bank
    return (bank.ifsc if submission.country == Country.IN else bank.routing_number) or ""


def submission_fingerprint(submission: VendorSubmission) -> str | None:
    """Fingerprint of the submission's bank account, or None if it has no account number."""
    if not submission.bank.account_number:
        return None
    return account_fingerprint(submission.bank.account_number, bank_code_for(submission))


def last4(account_number: str) -> str:
    return account_number.replace(" ", "")[-4:]
