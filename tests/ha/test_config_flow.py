"""Config flow test with mocked PDF download."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402

from custom_components.abfallkalender_rtk.const import (  # noqa: E402
    CONF_DISCOVERY_START,
    CONF_ENABLE_PERSISTENT_NOTIFICATION,
    CONF_LOOKAHEAD_DAYS,
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


async def test_options_flow_rejects_invalid_discovery_start(
    hass: HomeAssistant,
) -> None:
    """An invalid MM-DD is reported as a field error instead of being stored."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.abfallkalender_rtk.const import (
        CONF_ACTIVE_YEAR,
        CONF_URL_TEMPLATE,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Abfallkalender RTK",
        data={CONF_URL_TEMPLATE: TEMPLATE_2026.replace("2026", "{year}"), CONF_ACTIVE_YEAR: 2026},
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_PDF_URL: DEFAULT_PDF_URL,
            CONF_SCAN_INTERVAL_DAYS: "1",
            CONF_TRACKED_TYPES: ["BM"],
            CONF_LOOKAHEAD_DAYS: 60,
            CONF_DISCOVERY_START: "13-45",
            CONF_ENABLE_PERSISTENT_NOTIFICATION: False,
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_DISCOVERY_START: "invalid_discovery_start"}
