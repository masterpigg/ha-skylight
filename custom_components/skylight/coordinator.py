"""Polls Skylight for chores, lists, calendar events and reward points."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SkylightAuthError, SkylightClient, SkylightError
from .const import (
    CALENDAR_LOOKAHEAD_DAYS,
    CONF_FRAME_ID,
    DOMAIN,
    LOGGER,
    UPDATE_INTERVAL_MINUTES,
)


@dataclass
class SkylightData:
    """One poll's worth of Skylight data."""

    people: dict[str, str] = field(default_factory=dict)  # category id -> name
    chores: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # person id -> chores
    lists: dict[str, str] = field(default_factory=dict)  # list id -> label
    list_items: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    events: list[CalendarEvent] = field(default_factory=list)
    points: dict[str, dict[str, int]] = field(default_factory=dict)  # person id -> balances


def _rel_id(item: dict[str, Any], name: str) -> str | None:
    data = (item.get("relationships", {}).get(name) or {}).get("data")
    return str(data["id"]) if data else None


def parse_events(body: dict[str, Any]) -> list[CalendarEvent]:
    """Convert a calendar_events response into Home Assistant events."""
    events: list[CalendarEvent] = []
    for item in body.get("data", []):
        attrs = item["attributes"]
        try:
            start: date | datetime = datetime.fromisoformat(attrs["starts_at"])
            end: date | datetime = datetime.fromisoformat(attrs["ends_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if attrs.get("all_day"):
            start, end = start.date(), end.date()
            if end <= start:
                end = start + timedelta(days=1)
        elif end <= start:
            end = start + timedelta(minutes=1)
        events.append(
            CalendarEvent(
                start=start,
                end=end,
                summary=attrs.get("summary") or "(no title)",
                description=attrs.get("description"),
                location=attrs.get("location"),
                uid=str(item["id"]),
            )
        )

    def _key(event: CalendarEvent) -> datetime:
        return event.start_datetime_local

    return sorted(events, key=_key)


class SkylightCoordinator(DataUpdateCoordinator[SkylightData]):
    """Fetches everything the entities show, every few minutes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SkylightClient) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.client = client
        self.frame_id: str = entry.data[CONF_FRAME_ID]

    async def async_get_events(self, start: date, end: date) -> list[CalendarEvent]:
        """Fetch calendar events for a date range (used by the calendar view)."""
        body = await self.client.get(
            f"/api/frames/{self.frame_id}/calendar_events",
            {
                "date_min": start.isoformat(),
                "date_max": end.isoformat(),
                "timezone": self.hass.config.time_zone,
            },
        )
        return parse_events(body)

    async def _async_update_data(self) -> SkylightData:
        frame = f"/api/frames/{self.frame_id}"
        today = dt_util.now().date()
        try:
            categories, chores, lists, points, events = await asyncio.gather(
                self.client.get(f"{frame}/categories"),
                self.client.get(
                    f"{frame}/chores",
                    {"after": today.isoformat(), "before": today.isoformat(), "include_late": "true"},
                ),
                self.client.get(f"{frame}/lists"),
                self.client.get(f"{frame}/reward_points"),
                self.async_get_events(today, today + timedelta(days=CALENDAR_LOOKAHEAD_DAYS)),
            )
        except SkylightAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (SkylightError, aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(str(err)) from err

        data = SkylightData(events=events)
        for cat in categories.get("data", []):
            if cat["attributes"].get("selected_for_chore_chart"):
                data.people[str(cat["id"])] = cat["attributes"]["label"]
        data.chores = {person: [] for person in data.people}
        for chore in chores.get("data", []):
            person = _rel_id(chore, "category")
            if person in data.chores:
                data.chores[person].append(chore)
        for lst in lists.get("data", []):
            data.lists[str(lst["id"])] = lst["attributes"].get("label") or "List"
            data.list_items[str(lst["id"])] = []
        for item in lists.get("included", []):
            if item.get("type") != "list_item":
                continue
            list_id = _rel_id(item, "list")
            if list_id in data.list_items:
                data.list_items[list_id].append(item)
        for items in data.list_items.values():
            items.sort(key=lambda i: i["attributes"].get("position") or 0)
        for row in points if isinstance(points, list) else []:
            person = str(row.get("category_id"))
            if person in data.people:
                data.points[person] = {
                    "balance": row.get("current_point_balance") or 0,
                    "lifetime": row.get("lifetime_points_earned") or 0,
                }
        return data
