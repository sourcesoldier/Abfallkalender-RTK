"""Pure PDF parser for the Eltville/RTK Abfallkalender grid layout.

No Home Assistant imports here so this module stays unit-testable in isolation.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date

import pdfplumber

# Waste-type codes as printed in the PDF. SM is printed as "SM*".
WASTE_CODES: tuple[str, ...] = ("BM", "GT", "PM", "RM", "SM")

_MONTH_NAMES = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
# Months present per grid page (pages 1 and 2 of the PDF).
_MONTHS_BY_PAGE = {0: (1, 2, 3, 4, 5, 6), 1: (7, 8, 9, 10, 11, 12)}

_YEAR_RE = re.compile(r"Abfallkalender\s+(20\d\d)")
# Minimum plausible number of collection days for a full year. Guards against
# a silently changed layout that would otherwise yield an empty calendar.
_MIN_EVENTS = 20


class ParseError(Exception):
    """Raised when the PDF does not match the expected layout."""


@dataclass
class ParsedCalendar:
    """Result of parsing one yearly Abfallkalender PDF."""

    year: int
    events: dict[date, set[str]] = field(default_factory=dict)


def _code_token(text: str) -> str | None:
    """Return the normalized waste code for a word, or None."""
    token = text.rstrip("*")
    return token if token in WASTE_CODES else None


def _nearest_column(x: float, centers: list[float]) -> int:
    """Index of the month column whose header center is closest to x."""
    return min(range(len(centers)), key=lambda i: abs(centers[i] - x))


def parse_pdf(data: bytes) -> ParsedCalendar:
    """Parse raw PDF bytes into a ParsedCalendar.

    Raises ParseError if the year cannot be read or the result looks implausible.
    """
    events: dict[date, set[str]] = {}
    year: int | None = None

    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as err:  # pdfminer raises various types on bad input
        raise ParseError(f"could not open PDF: {err}") from err

    with pdf:
        for page_index in (0, 1):
            if page_index >= len(pdf.pages):
                break
            page = pdf.pages[page_index]

            if year is None:
                match = _YEAR_RE.search(page.extract_text() or "")
                if match:
                    year = int(match.group(1))

            words = page.extract_words()
            headers = sorted(
                (w for w in words if 55 < w["top"] < 70 and w["text"] in _MONTH_NAMES),
                key=lambda w: w["x0"],
            )
            if len(headers) != 6:
                # Header row missing or malformed for this page.
                continue
            centers = [(w["x0"] + w["x1"]) / 2 for w in headers]

            # Index day-number anchors by rounded y so codes can find their day.
            day_rows: dict[int, list[tuple[float, int, int]]] = {}
            for w in words:
                if w["top"] <= 75 or not w["text"].isdigit():
                    continue
                day = int(w["text"])
                if not 1 <= day <= 31:
                    continue
                column = _nearest_column((w["x0"] + w["x1"]) / 2, centers)
                day_rows.setdefault(round(w["top"]), []).append((w["x0"], day, column))

            for w in words:
                if w["top"] <= 75:
                    continue
                code = _code_token(w["text"])
                if code is None:
                    continue
                column = _nearest_column((w["x0"] + w["x1"]) / 2, centers)
                month = _MONTHS_BY_PAGE[page_index][column]
                top = round(w["top"])
                row = day_rows.get(top, []) + day_rows.get(top + 1, []) + day_rows.get(top - 1, [])
                # Day number sits left of the code within the same column.
                candidates = [d for d in row if d[2] == column and d[0] < w["x0"]]
                if not candidates:
                    continue
                day = max(candidates, key=lambda d: d[0])[1]
                try:
                    day_date = date(year, month, day) if year else None
                except ValueError:
                    # Guards against a stray code mapped to an invalid date.
                    continue
                if day_date is not None:
                    events.setdefault(day_date, set()).add(code)

    if year is None:
        raise ParseError("could not determine calendar year from PDF")
    if len(events) < _MIN_EVENTS:
        raise ParseError(
            f"implausibly few collection days ({len(events)}); layout may have changed"
        )

    return ParsedCalendar(year=year, events=events)
