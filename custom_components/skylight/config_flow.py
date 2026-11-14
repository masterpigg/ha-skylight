"""Sign in to Skylight through its own login page (OAuth + PKCE)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SkylightAuthError,
    SkylightClient,
    SkylightError,
    authorize_url,
    create_pkce,
    exchange_code,
    parse_redirect,
    refresh_tokens,
)
from .const import CONF_FRAME_ID, CONF_FRAME_NAME, CONF_REFRESH_TOKEN, DOMAIN, LOGGER

CONF_REDIRECT = "redirect"

SCHEMA = vol.Schema({vol.Optional(CONF_REDIRECT): str, vol.Optional(CONF_REFRESH_TOKEN): str})


class SkylightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle sign-in and re-sign-in."""

    VERSION = 1

    def __init__(self) -> None:
        self._verifier, self._challenge, self._state = create_pkce()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                if token := (user_input.get(CONF_REFRESH_TOKEN) or "").strip():
                    tokens = await refresh_tokens(session, token)
                elif redirect := (user_input.get(CONF_REDIRECT) or "").strip():
                    code = parse_redirect(redirect, self._state)
                    tokens = await exchange_code(session, code, self._verifier)
                else:
                    raise SkylightAuthError("Nothing entered")
                frames = await SkylightClient(session, tokens).frames()
            except SkylightAuthError:
                errors["base"] = "invalid_auth"
            except (SkylightError, aiohttp.ClientError, TimeoutError) as err:
                LOGGER.warning("Skylight sign-in failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not frames:
                    return self.async_abort(reason="no_frames")
                frame = frames[0]
                name = frame.get("attributes", {}).get("name") or "Skylight"
                data = {CONF_FRAME_ID: str(frame["id"]), CONF_FRAME_NAME: name, **tokens}
                await self.async_set_unique_id(str(frame["id"]))
                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=data
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Skylight ({name})", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA,
            errors=errors,
            description_placeholders={"url": authorize_url(self._challenge, self._state)},
        )
