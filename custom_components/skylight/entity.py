"""Shared base for Skylight entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FRAME_NAME, DOMAIN
from .coordinator import SkylightCoordinator


class SkylightEntity(CoordinatorEntity[SkylightCoordinator]):
    """An entity that belongs to the Skylight frame."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SkylightCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.frame_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.frame_id)},
            name="Skylight",
            manufacturer="Skylight",
            model="Skylight Calendar",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://ourskylight.com",
            serial_number=coordinator.config_entry.data.get(CONF_FRAME_NAME),
        )
