"""Tests for URL normalization and rollover URL building."""

from __future__ import annotations

import pytest

from ackrtk.url import (
    UrlError,
    build_url,
    normalize_url,
)

ELTVILLE = (
    "https://www.eltville.de/pdf-dokumente/buergerservice-rathaus/service/"
    "abfallkalender-2026-erbach-hattenheim-rauenthal.pdf?cid=aqe"
)


def test_normalize_strips_query_and_templatizes_year():
    template, year = normalize_url(ELTVILLE)
    assert year == 2026
    assert "?cid" not in template
    assert "{year}" in template
    assert template.endswith("abfallkalender-{year}-erbach-hattenheim-rauenthal.pdf")


def test_build_url_roundtrip_next_year():
    template, year = normalize_url(ELTVILLE)
    next_url = build_url(template, year + 1)
    assert "abfallkalender-2027-erbach-hattenheim-rauenthal.pdf" in next_url
    assert "2026" not in next_url


def test_normalize_without_year_raises():
    with pytest.raises(UrlError):
        normalize_url("https://example.com/abfallkalender.pdf")


def test_year_boundary_not_confused_by_other_digits():
    url = "https://x.test/2026/abfall-2026-nord.pdf"
    template, year = normalize_url(url)
    # Only the path year is templatized; both 2026 occurrences are in the path,
    # first match wins and is replaced.
    assert year == 2026
    assert build_url(template, 2027) == "https://x.test/2027/abfall-2026-nord.pdf"
