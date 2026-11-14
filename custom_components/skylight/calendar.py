"""The Skylight frame's calendar (read-only)."""

from __future__ import annotations

from datetime import datetime

import aiohttp

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SkylightConfigEntry
from .api import SkylightError
from .coordinator import SkylightCoordinator
from .entity import SkylightEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SkylightConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([SkylightCalendar(entry.runtime_data)])


class SkylightCalendar(SkylightEntity, CalendarEntity):
    """All events shown on the Skylight."""

    _attr_name = "Calendar"

    def __init__(self, coordinator: SkylightCoordinator) -> None:
        super().__init__(coordinator, "calendar")

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next event."""
        now = dt_util.now()
        for event in self.coordinator.data.events:
            if event.end_datetime_local > now:
                return event
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        try:
            events = await self.coordinator.async_get_events(
                dt_util.as_local(start_date).date(), dt_util.as_local(end_date).date()
            )
        except (SkylightError, aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(f"Could not load Skylight events: {err}") from err
        return [
            event
            for event in events
            if event.end_datetime_local > start_date and event.start_datetime_local < end_date
        ]
