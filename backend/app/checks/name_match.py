"""Fuzzy company-name matching (RapidFuzz) with thresholds from rules.yaml."""

import re

from rapidfuzz import fuzz

from app.config import get_rules
from app.models import CheckResult


def normalise_name(name: str) -> str:
    """Lowercase, expand '&', drop punctuation, collapse spaces, then expand whole-word
    abbreviations (pvt -> private, ltd -> limited ...) using the map in rules.yaml.
    Whole words only, so 'co' never changes 'coimbatore'."""
    abbreviations = get_rules().name_match.normalise
    text = name.lower()
    if "&" in abbreviations:
        text = text.replace("&", f" {abbreviations['&']} ")
    text = re.sub(r"[^\w\s]", " ", text)  # punctuation becomes a space, so "Pvt.Ltd." still splits
    words = text.split()                  # split() also collapses repeated spaces
    return " ".join(abbreviations.get(word, word) for word in words)


def name_score(a: str, b: str) -> int:
    """Similarity of two names, 0-100, ignoring word order.

    We deliberately use token_sort_ratio and NOT partial_ratio, token_set_ratio or WRatio.
    Those reward one name being CONTAINED in the other, so "R. Sharma" would score high
    against "Sharma Electronics Private Limited" and a bank account in an individual's
    name (payment diversion fraud) would pass as the company's own.
    """
    return round(fuzz.token_sort_ratio(normalise_name(a), normalise_name(b)))


def classify_score(score: int) -> CheckResult:
    """PASS at or above pass_threshold, WARN at or above warn_threshold, otherwise FAIL."""
    rules = get_rules().name_match
    if score >= rules.pass_threshold:
        return CheckResult.PASS
    if score >= rules.warn_threshold:
        return CheckResult.WARN
    return CheckResult.FAIL
