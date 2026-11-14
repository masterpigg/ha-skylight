"""Reward-point balances per person."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SkylightConfigEntry
from .coordinator import SkylightCoordinator
from .entity import SkylightEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SkylightConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SkylightPoints(coordinator, person_id, name)
        for person_id, name in coordinator.data.people.items()
        if person_id in coordinator.data.points
    )


class SkylightPoints(SkylightEntity, SensorEntity):
    """Current reward-point balance for one person."""

    _attr_icon = "mdi:star-circle"
    _attr_native_unit_of_measurement = "points"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SkylightCoordinator, person_id: str, name: str) -> None:
        super().__init__(coordinator, f"points_{person_id}")
        self._person_id = person_id
        self._attr_name = f"{name} reward points"

    @property
    def native_value(self) -> int | None:
        row = self.coordinator.data.points.get(self._person_id)
        return row["balance"] if row else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        row = self.coordinator.data.points.get(self._person_id)
        return {"lifetime_points": row["lifetime"]} if row else None
