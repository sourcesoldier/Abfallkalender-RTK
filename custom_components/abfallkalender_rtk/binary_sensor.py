"""Binary sensor exposing integration health for automations."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AbfallkalenderConfigEntry
from .coordinator import AbfallkalenderCoordinator
from .entity import AbfallkalenderEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AbfallkalenderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diagnostic problem sensor."""
    async_add_entities([AbfallkalenderProblemSensor(entry.runtime_data)])


class AbfallkalenderProblemSensor(AbfallkalenderEntity, BinarySensorEntity):
    """On when the last data refresh reported a problem."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "problem"

    def __init__(self, coordinator: AbfallkalenderCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_problem"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.problem_reason is not None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.coordinator.data
        coverage = data.coverage_until()
        today = datetime.now().date()
        stale_days = None
        if data.last_success is not None:
            stale_days = (datetime.now() - data.last_success).days
        return {
            "reason": data.problem_reason,
            "last_error": data.last_error,
            "last_success": data.last_success,
            "data_stale_days": stale_days,
            "coverage_until": coverage,
            "coverage_days_left": (coverage - today).days if coverage else None,
            "loaded_years": sorted(data.loaded_years),
        }
