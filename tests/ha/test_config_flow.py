"""Config flow test with mocked PDF download."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402

from custom_components.abfallkalender_rtk.const import (  # noqa: E402
    CONF_NAME,
    CONF_PDF_URL,
    CONF_SCAN_INTERVAL_DAYS,
    CONF_TRACKED_TYPES,
    DEFAULT_PDF_URL,
    DOMAIN,
)

FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "abfallkalender-2026-erbach-hattenheim-rauenthal.pdf"
)
TEMPLATE_2026 = (
    "https://www.eltville.de/pdf-dokumente/buergerservice-rathaus/service/"
    "abfallkalender-2026-erbach-hattenheim-rauenthal.pdf"
)


async def test_user_flow_success(hass: HomeAssistant, aioclient_mock) -> None:
    pdf = FIXTURE.read_bytes()
    # The entered URL (with cid) is validated; the templated URL is loaded on setup.
    aioclient_mock.get(DEFAULT_PDF_URL, content=pdf)
    aioclient_mock.get(TEMPLATE_2026, content=pdf)
    aioclient_mock.get(
        "https://www.eltville.de/pdf-dokumente/buergerservice-rathaus/service/"
        "abfallkalender-2027-erbach-hattenheim-rauenthal.pdf",
        status=404,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Abfallkalender RTK",
            CONF_PDF_URL: DEFAULT_PDF_URL,
            CONF_SCAN_INTERVAL_DAYS: "1",
            CONF_TRACKED_TYPES: ["BM", "GT", "PM", "RM", "SM"],
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Abfallkalender RTK"
    assert result2["data"]["active_year"] == 2026
    assert "{year}" in result2["data"]["url_template"]


async def test_user_flow_bad_url(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "X",
            CONF_PDF_URL: "https://example.com/no-year.pdf",
            CONF_SCAN_INTERVAL_DAYS: "1",
            CONF_TRACKED_TYPES: ["BM"],
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_url"}
