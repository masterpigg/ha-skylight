"""Unofficial, read-only Skylight Calendar integration.

Shows a Skylight frame's chores, lists, calendar and reward points in Home
Assistant. It never changes anything on the Skylight.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SkylightClient
from .coordinator import SkylightCoordinator

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR, Platform.TODO]

type SkylightConfigEntry = ConfigEntry[SkylightCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SkylightConfigEntry) -> bool:
    """Set up Skylight from a config entry."""

    @callback
    def _save_tokens(tokens: dict[str, Any]) -> None:
        # Skylight rotates the refresh token, so every new pair has to be kept.
        hass.config_entries.async_update_entry(entry, data={**entry.data, **tokens})

    client = SkylightClient(async_get_clientsession(hass), dict(entry.data), _save_tokens)
    coordinator = SkylightCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SkylightConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
