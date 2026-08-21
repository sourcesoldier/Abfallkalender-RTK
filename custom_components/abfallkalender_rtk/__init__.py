"""The Abfallkalender RTK integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AbfallkalenderCoordinator

PLATFORMS: list[Platform] = [
    Platform.CALENDAR,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

type AbfallkalenderConfigEntry = ConfigEntry[AbfallkalenderCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: AbfallkalenderConfigEntry
) -> bool:
    """Set up Abfallkalender RTK from a config entry."""
    coordinator = AbfallkalenderCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AbfallkalenderConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: AbfallkalenderConfigEntry
) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
