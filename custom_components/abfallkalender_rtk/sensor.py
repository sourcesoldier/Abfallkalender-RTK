"""Sensor platform: next collection date per bin plus a combined sensor."""

from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AbfallkalenderConfigEntry
from .const import WASTE_TYPES
from .coordinator import AbfallkalenderCoordinator
from .entity import AbfallkalenderEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AbfallkalenderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up per-bin sensors and a combined next-pickup sensor."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        BinNextPickupSensor(coordinator, code)
        for code in coordinator.tracked_types
        if code in WASTE_TYPES
    ]
    entities.append(CombinedNextPickupSensor(coordinator))
    async_add_entities(entities)


def _day_attrs(day: date | None) -> dict[str, object]:
    """Common date-derived attributes shared by all sensors."""
    if day is None:
        return {"days_to": None, "weekday": None, "is_today": False, "is_tomorrow": False}
    today = dt_util.now().date()
    delta = (day - today).days
    return {
        "days_to": delta,
        "weekday": day.strftime("%A"),
        "is_today": delta == 0,
        "is_tomorrow": delta == 1,
    }


class BinNextPickupSensor(AbfallkalenderEntity, SensorEntity):
    """Next collection date for a single waste type."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: AbfallkalenderCoordinator, code: str) -> None:
        super().__init__(coordinator)
        self._code = code
        self._attr_translation_key = f"next_{code.lower()}"
        self._attr_icon = WASTE_TYPES[code]["icon"]
        self._attr_unique_id = f"{coordinator.entry.entry_id}_next_{code.lower()}"

    def _next_day(self) -> date | None:
        today = dt_util.now().date()
        days = sorted(
            day
            for day, codes in self.coordinator.data.events.items()
            if self._code in codes and day >= today
        )
        return days[0] if days else None

    @property
    def native_value(self) -> date | None:
        return self._next_day()

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return _day_attrs(self._next_day())


class CombinedNextPickupSensor(AbfallkalenderEntity, SensorEntity):
    """Next collection date across all tracked types, with the bin list."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_translation_key = "next_pickup"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: AbfallkalenderCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_next_pickup"

    def _next(self) -> tuple[date, set[str]] | None:
        today = dt_util.now().date()
        tracked = set(self.coordinator.tracked_types)
        upcoming = sorted(
            (day, codes & tracked)
            for day, codes in self.coordinator.data.events.items()
            if day >= today and codes & tracked
        )
        return upcoming[0] if upcoming else None

    @property
    def native_value(self) -> date | None:
        result = self._next()
        return result[0] if result else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        result = self._next()
        day = result[0] if result else None
        codes = result[1] if result else set()
        attrs = _day_attrs(day)
        attrs["types"] = sorted(codes)
        attrs["labels"] = [
            WASTE_TYPES[c]["label"] for c in sorted(codes) if c in WASTE_TYPES
        ]
        return attrs
