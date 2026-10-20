"""End-to-end setup test for the Abfallkalender RTK config entry."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from homeassistant.util import dt as dt_util  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.abfallkalender_rtk.const import (  # noqa: E402
    CONF_ACTIVE_YEAR,
    CONF_DISCOVERY_START,
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


@pytest.mark.freeze_time("2026-06-15 12:00:00")
async def test_next_pickup_refreshes_at_midnight(
    hass: HomeAssistant, aioclient_mock, freezer
) -> None:
    """Date-relative state is re-evaluated at midnight without a coordinator refresh."""
    aioclient_mock.get(TEMPLATE.format(year=2026), content=FIXTURE.read_bytes())
    aioclient_mock.get(TEMPLATE.format(year=2027), status=404)

    entry = _mock_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    next_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_next_pickup"
    )
    before = hass.states.get(next_id)
    assert before.state < "2026-12-30"
    calls_before = len(aioclient_mock.mock_calls)

    # Jump to just after local midnight, long after the earlier pickup dates.
    later = dt_util.start_of_local_day(date(2026, 12, 30)) + timedelta(seconds=5)
    freezer.move_to(later)
    async_fire_time_changed(hass, later)
    await hass.async_block_till_done()

    after = hass.states.get(next_id)
    # No new download happened (the daily coordinator interval has not fired)...
    assert len(aioclient_mock.mock_calls) == calls_before
    # ...yet the state no longer points to a past date.
    assert after.state != before.state
    assert after.state in ("unknown", "unavailable") or after.state >= "2026-12-30"


@pytest.mark.freeze_time("2026-06-15")
async def test_invalid_discovery_start_does_not_break_setup(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """A stored, unparsable MM-DD falls back to the default instead of failing setup."""
    aioclient_mock.get(TEMPLATE.format(year=2026), content=FIXTURE.read_bytes())
    aioclient_mock.get(TEMPLATE.format(year=2027), status=404)

    entry = _mock_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        options={**entry.options, CONF_DISCOVERY_START: "not-a-date"},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
