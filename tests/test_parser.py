"""Tests for the pure PDF parser against the committed 2026 fixture."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ackrtk.parser import ParseError, parse_pdf

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "abfallkalender-2026-erbach-hattenheim-rauenthal.pdf"
)


@pytest.fixture(scope="module")
def parsed():
    return parse_pdf(FIXTURE.read_bytes())


def test_year(parsed):
    assert parsed.year == 2026


def test_total_collection_days(parsed):
    assert len(parsed.events) == 58


def test_type_counts(parsed):
    counts: dict[str, int] = {}
    for types in parsed.events.values():
        for code in types:
            counts[code] = counts.get(code, 0) + 1
    assert counts == {"BM": 41, "GT": 26, "RM": 26, "PM": 13, "SM": 11}


def test_spot_checks(parsed):
    assert parsed.events[date(2026, 1, 9)] == {"BM", "GT", "RM"}
    assert parsed.events[date(2026, 1, 3)] == {"PM"}
    assert parsed.events[date(2026, 1, 12)] == {"SM"}
    assert parsed.events[date(2026, 12, 24)] == {"BM", "GT", "RM"}


def test_parse_error_on_garbage():
    with pytest.raises(ParseError):
        parse_pdf(b"%PDF-1.4 not a real calendar")
