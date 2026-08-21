"""Calendar platform: one all-day event per collection day."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AbfallkalenderConfigEntry
from .const import WASTE_TYPES
from .coordinator import AbfallkalenderCoordinator
from .entity import AbfallkalenderEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AbfallkalenderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar entity."""
    async_add_entities([AbfallkalenderCalendar(entry.runtime_data)])


def _summary(codes: set[str], tracked: list[str]) -> str:
    """Human-readable summary listing the tracked bins on a day."""
    labels = [
        WASTE_TYPES[c]["label"] for c in tracked if c in codes and c in WASTE_TYPES
    ]
    return ", ".join(labels)


class AbfallkalenderCalendar(AbfallkalenderEntity, CalendarEntity):
    """Exposes collection days as all-day calendar events."""

    _attr_translation_key = "collection"

    def __init__(self, coordinator: AbfallkalenderCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_calendar"

    def _day_events(self) -> list[tuple[date, set[str]]]:
        tracked = self.coordinator.tracked_types
        result = []
        for day, codes in self.coordinator.data.events.items():
            visible = codes & set(tracked)
            if visible:
                result.append((day, visible))
        return sorted(result, key=lambda item: item[0])

    def _to_event(self, day: date, codes: set[str]) -> CalendarEvent:
        tracked = self.coordinator.tracked_types
        return CalendarEvent(
            summary=_summary(codes, tracked),
            start=day,
            end=day + timedelta(days=1),
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Next upcoming collection event."""
        today = datetime.now().date()
        for day, codes in self._day_events():
            if day >= today:
                return self._to_event(day, codes)
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start = start_date.date()
        end = end_date.date()
        return [
            self._to_event(day, codes)
            for day, codes in self._day_events()
            if start <= day <= end
        ]
