"""Skylight chores (per person) and lists as read-only to-do lists."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SkylightConfigEntry
from .coordinator import SkylightCoordinator
from .entity import SkylightEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SkylightConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[TodoListEntity] = [
        SkylightChoreList(coordinator, person_id, name)
        for person_id, name in coordinator.data.people.items()
    ]
    entities += [
        SkylightList(coordinator, list_id, label) for list_id, label in coordinator.data.lists.items()
    ]
    async_add_entities(entities)


def _status(value: str | None) -> TodoItemStatus:
    return TodoItemStatus.COMPLETED if value == "completed" else TodoItemStatus.NEEDS_ACTION


def _due(value: Any) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


class SkylightChoreList(SkylightEntity, TodoListEntity):
    """Today's chores (plus overdue ones) for one person."""

    _attr_icon = "mdi:broom"

    def __init__(self, coordinator: SkylightCoordinator, person_id: str, name: str) -> None:
        super().__init__(coordinator, f"chores_{person_id}")
        self._person_id = person_id
        self._attr_name = f"{name} chores"

    @property
    def todo_items(self) -> list[TodoItem]:
        items = []
        for chore in self.coordinator.data.chores.get(self._person_id, []):
            attrs = chore["attributes"]
            emoji = attrs.get("emoji_icon")
            summary = attrs.get("summary") or "Chore"
            items.append(
                TodoItem(
                    summary=f"{emoji} {summary}" if emoji else summary,
                    uid=f"{chore['id']}_{attrs.get('start')}",
                    status=_status(attrs.get("status")),
                    due=_due(attrs.get("start")),
                    description=attrs.get("description"),
                )
            )
        return items


class SkylightList(SkylightEntity, TodoListEntity):
    """A Skylight list (grocery, to-do, ...)."""

    _attr_icon = "mdi:format-list-checks"

    def __init__(self, coordinator: SkylightCoordinator, list_id: str, label: str) -> None:
        super().__init__(coordinator, f"list_{list_id}")
        self._list_id = list_id
        self._attr_name = label

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                summary=item["attributes"].get("label") or "Item",
                uid=str(item["id"]),
                status=_status(item["attributes"].get("status")),
            )
            for item in self.coordinator.data.list_items.get(self._list_id, [])
        ]
