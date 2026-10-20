"""Shared entity base providing device grouping."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AbfallkalenderCoordinator


class AbfallkalenderEntity(CoordinatorEntity[AbfallkalenderCoordinator]):
    """Base entity binding all platform entities to one device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AbfallkalenderCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Stadt Eltville / RTK",
            model="Abfallkalender",
        )

    async def async_added_to_hass(self) -> None:
        """Re-evaluate date-relative state at the start of every day.

        Next-pickup values, days_to, is_today etc. depend on today's date, but the
        coordinator only refreshes every 1 or 7 days.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_midnight_refresh, hour=0, minute=0, second=1
            )
        )

    @callback
    def _async_midnight_refresh(self, _now: datetime) -> None:
        self.async_write_ha_state()
