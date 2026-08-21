"""Helpers for URL normalization and year-based rollover.

The Eltville PDF URL embeds the calendar year in the path and the current
year's document is reachable via a redirecting, cid-less base URL. We store a
template with the year replaced by a placeholder so we can probe other years.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from .const import YEAR_PLACEHOLDER

_YEAR_IN_PATH = re.compile(r"(?<!\d)(20\d\d)(?!\d)")


class UrlError(Exception):
    """Raised when a URL does not contain a detectable calendar year."""


def normalize_url(url: str) -> tuple[str, int]:
    """Return (url_template, year) derived from a user-entered PDF URL.

    Drops the query string (the server re-adds the correct cid via redirect)
    and replaces the year in the path with a placeholder.
    """
    parts = urlsplit(url.strip())
    match = _YEAR_IN_PATH.search(parts.path)
    if not match:
        raise UrlError("no calendar year (20xx) found in URL path")

    year = int(match.group(1))
    templated_path = parts.path[: match.start()] + YEAR_PLACEHOLDER + parts.path[match.end() :]
    template = urlunsplit((parts.scheme, parts.netloc, templated_path, "", ""))
    return template, year


def build_url(template: str, year: int) -> str:
    """Fill a URL template with a concrete year."""
    return template.replace(YEAR_PLACEHOLDER, str(year))
