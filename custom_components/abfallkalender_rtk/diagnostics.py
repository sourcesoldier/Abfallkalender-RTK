"""Diagnostics dump for support and debugging."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import AbfallkalenderConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AbfallkalenderConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "state": {
            "loaded_years": sorted(data.loaded_years),
            "event_count": len(data.events),
            "coverage_until": data.coverage_until().isoformat()
            if data.coverage_until()
            else None,
            "problem_reason": data.problem_reason,
            "last_error": data.last_error,
            "last_success": data.last_success.isoformat()
            if data.last_success
            else None,
        },
        "events": {
            day.isoformat(): sorted(codes) for day, codes in sorted(data.events.items())
        },
    }
