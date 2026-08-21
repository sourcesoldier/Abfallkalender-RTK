"""End-to-end setup test for the Abfallkalender RTK config entry."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.abfallkalender_rtk.const import (  # noqa: E402
    CONF_ACTIVE_YEAR,
    CONF_SCAN_INTERVAL_DAYS,
    CONF_TRACKED_TYPES,
    CONF_URL_TEMPLATE,
    DOMAIN,
)

FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "abfallkalender-2026-erbach-hattenheim-rauenthal.pdf"
)
TEMPLATE = (
    "https://www.eltville.de/pdf-dokumente/buergerservice-rathaus/service/"
    "abfallkalender-{year}-erbach-hattenheim-rauenthal.pdf"
)
ALL_TYPES = ["BM", "GT", "PM", "RM", "SM"]


def _mock_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Abfallkalender RTK",
        data={CONF_URL_TEMPLATE: TEMPLATE, CONF_ACTIVE_YEAR: 2026},
        options={CONF_SCAN_INTERVAL_DAYS: 1, CONF_TRACKED_TYPES: ALL_TYPES},
    )


@pytest.mark.freeze_time("2026-06-15")
async def test_setup_creates_entities(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(TEMPLATE.format(year=2026), content=FIXTURE.read_bytes())
    aioclient_mock.get(TEMPLATE.format(year=2027), status=404)

    entry = _mock_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    # Combined next-pickup sensor resolves to a future date.
    next_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_next_pickup"
    )
    assert next_id is not None
    state = hass.states.get(next_id)
    assert state is not None
    assert state.state >= "2026-06-15"
    assert state.attributes["days_to"] >= 0

    # Per-bin sensors exist for each tracked type.
    for code in ALL_TYPES:
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_next_{code.lower()}"
            )
            is not None
        )

    # Problem sensor is off after a clean load.
    problem_id = ent_reg.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_problem"
    )
    assert hass.states.get(problem_id).state == "off"


@pytest.mark.freeze_time("2026-06-15")
async def test_calendar_returns_events(hass: HomeAssistant, aioclient_mock) -> None:
    from datetime import datetime

    from homeassistant.components.calendar import DOMAIN as CAL_DOMAIN

    aioclient_mock.get(TEMPLATE.format(year=2026), content=FIXTURE.read_bytes())
    aioclient_mock.get(TEMPLATE.format(year=2027), status=404)

    entry = _mock_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    cal_id = ent_reg.async_get_entity_id(
        "calendar", DOMAIN, f"{entry.entry_id}_calendar"
    )
    assert cal_id is not None

    result = await hass.services.async_call(
        CAL_DOMAIN,
        "get_events",
        {
            "entity_id": cal_id,
            "start_date_time": datetime(2026, 1, 1),
            "end_date_time": datetime(2026, 12, 31, 23, 59),
        },
        blocking=True,
        return_response=True,
    )
    events = result[cal_id]["events"]
    assert len(events) == 58
