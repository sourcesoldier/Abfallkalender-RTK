"""Constants for the Abfallkalender RTK integration."""

from __future__ import annotations

import re
from datetime import date
from typing import Final

DOMAIN: Final = "abfallkalender_rtk"

# Config / options keys
CONF_PDF_URL: Final = "pdf_url"
CONF_NAME: Final = "name"
CONF_SCAN_INTERVAL_DAYS: Final = "scan_interval_days"
CONF_TRACKED_TYPES: Final = "tracked_types"
CONF_LOOKAHEAD_DAYS: Final = "lookahead_days"
CONF_DISCOVERY_START: Final = "discovery_start"
CONF_ENABLE_PERSISTENT_NOTIFICATION: Final = "enable_persistent_notification"

# Internal config entry data (derived, not user-entered directly)
CONF_URL_TEMPLATE: Final = "url_template"
CONF_ACTIVE_YEAR: Final = "active_year"

# Defaults
DEFAULT_NAME: Final = "Abfallkalender RTK"
DEFAULT_SCAN_INTERVAL_DAYS: Final = 1
DEFAULT_PDF_URL: Final = (
    "https://www.eltville.de/pdf-dokumente/buergerservice-rathaus/service/"
    "abfallkalender-2026-erbach-hattenheim-rauenthal.pdf?cid=aqe"
)
DEFAULT_LOOKAHEAD_DAYS: Final = 60
DEFAULT_DISCOVERY_START: Final = "10-01"  # MM-DD, earliest date to probe next year
DEFAULT_ENABLE_PERSISTENT_NOTIFICATION: Final = False

# Year placeholder used inside the stored URL template.
YEAR_PLACEHOLDER: Final = "{year}"

# HTTP
USER_AGENT: Final = (
    "Mozilla/5.0 (compatible; HomeAssistant-AbfallkalenderRTK/1.0; +https://github.com/)"
)
HTTP_TIMEOUT_SECONDS: Final = 60

# Escalate transient network failures only after this many consecutive misses.
NETWORK_FAILURE_THRESHOLD: Final = 3

# Waste type metadata. Keys match parser codes.
WASTE_TYPES: Final[dict[str, dict[str, str]]] = {
    "BM": {"label": "Biomüll", "icon": "mdi:leaf"},
    "GT": {"label": "Gelbe Tonne", "icon": "mdi:recycle"},
    "PM": {"label": "Papiermüll", "icon": "mdi:newspaper"},
    "RM": {"label": "Restmüll", "icon": "mdi:trash-can"},
    "SM": {"label": "Sondermüll", "icon": "mdi:flask-outline"},
}

# Failure reason identifiers, also used as Repairs issue ids / translation keys.
REASON_NETWORK: Final = "network"
REASON_NOT_FOUND: Final = "not_found"
REASON_PARSE_ERROR: Final = "parse_error"
REASON_ROLLOVER_OVERDUE: Final = "rollover_overdue"


_MONTH_DAY_RE: Final = re.compile(r"^(\d{2})-(\d{2})$")


def parse_month_day(raw: object) -> tuple[int, int] | None:
    """Parse an "MM-DD" string into (month, day), or None if invalid.

    Validated against a non-leap year so the result is valid in every year.
    """
    if not isinstance(raw, str) or not (match := _MONTH_DAY_RE.match(raw.strip())):
        return None
    month, day = int(match[1]), int(match[2])
    try:
        date(2001, month, day)
    except ValueError:
        return None
    return month, day
