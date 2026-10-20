"""Tests for the MM-DD option parser."""

from __future__ import annotations

import pytest

from ackrtk.const import DEFAULT_DISCOVERY_START, parse_month_day


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10-01", (10, 1)),
        ("01-31", (1, 31)),
        ("12-31", (12, 31)),
        (" 10-01 ", (10, 1)),
        (DEFAULT_DISCOVERY_START, (10, 1)),
    ],
)
def test_valid_month_day(raw, expected):
    assert parse_month_day(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "abc", "1-1", "13-01", "00-10", "10-00", "02-30", "02-29", "10/01", "10-01-5", None, 5],
)
def test_invalid_month_day(raw):
    assert parse_month_day(raw) is None
