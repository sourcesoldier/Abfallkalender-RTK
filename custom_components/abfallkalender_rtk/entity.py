"""Shared entity base providing device grouping."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
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
