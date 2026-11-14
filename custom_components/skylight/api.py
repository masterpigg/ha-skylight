"""Minimal read-only client for Skylight's (unofficial) cloud API.

Only GET requests are made against Skylight data. The only POST is to
/oauth/token, to trade a sign-in code or refresh token for access tokens.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp

from .const import (
    API_VERSION,
    BASE_URL,
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    OAUTH_CLIENT_ID,
    OAUTH_REDIRECT_URI,
    OAUTH_SCOPE,
)

TIMEOUT = aiohttp.ClientTimeout(total=30)
EXPIRY_SKEW = 120


class SkylightError(Exception):
    """Any Skylight API problem."""


class SkylightAuthError(SkylightError):
    """The tokens were rejected; the user has to sign in again."""


class SkylightVersionError(SkylightError):
    """Skylight retired the API version this integration sends."""


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def create_pkce() -> tuple[str, str, str]:
    """Return (verifier, challenge, state) for a new sign-in."""
    verifier = _b64u(secrets.token_bytes(64))
    challenge = _b64u(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge, _b64u(secrets.token_bytes(16))


def authorize_url(challenge: str, state: str) -> str:
    """Address of Skylight's own sign-in page."""
    return f"{BASE_URL}/oauth/authorize?" + urlencode(
        {
            "response_type": "code",
            "client_id": OAUTH_CLIENT_ID,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "scope": OAUTH_SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )


def parse_redirect(value: str, expected_state: str) -> str:
    """Get the one-time code from a pasted welcome address (or a bare code)."""
    value = value.strip()
    if "code=" not in value:
        return value
    query = parse_qs(urlparse(value).query or value.split("?", 1)[-1])
    if query.get("state", [expected_state])[0] != expected_state:
        raise SkylightAuthError("That address is from a different sign-in attempt")
    return query["code"][0]


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json", "Skylight-Api-Version": API_VERSION}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _check_version(status: int, text: str) -> None:
    if status == 401 and "no longer supported" in text:
        raise SkylightVersionError(
            f"Skylight retired API version {API_VERSION}; update API_VERSION in const.py"
        )


async def _token_request(
    session: aiohttp.ClientSession, form: dict[str, str], fallback_refresh: str | None = None
) -> dict[str, Any]:
    """POST to /oauth/token and return tokens in config-entry form."""
    async with session.post(
        f"{BASE_URL}/oauth/token",
        data={"client_id": OAUTH_CLIENT_ID, **form},
        headers=_headers(),
        timeout=TIMEOUT,
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            _check_version(resp.status, text)
            if resp.status in (400, 401):
                raise SkylightAuthError(f"Skylight rejected the sign-in (HTTP {resp.status})")
            raise SkylightError(f"Skylight token request failed (HTTP {resp.status})")
        body = await resp.json()
    refresh = body.get("refresh_token") or fallback_refresh
    if not refresh:
        raise SkylightAuthError("Skylight did not return a refresh token")
    return {
        CONF_ACCESS_TOKEN: body["access_token"],
        CONF_REFRESH_TOKEN: refresh,
        CONF_EXPIRES_AT: int(body.get("created_at") or time.time()) + int(body.get("expires_in", 0)),
    }


async def exchange_code(session: aiohttp.ClientSession, code: str, verifier: str) -> dict[str, Any]:
    """Trade a one-time sign-in code for tokens."""
    return await _token_request(
        session,
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "scope": OAUTH_SCOPE,
        },
    )


async def refresh_tokens(session: aiohttp.ClientSession, refresh_token: str) -> dict[str, Any]:
    """Trade a refresh token for new tokens (Skylight rotates the refresh token)."""
    return await _token_request(
        session, {"grant_type": "refresh_token", "refresh_token": refresh_token}, refresh_token
    )


class SkylightClient:
    """Read-only Skylight client that keeps its tokens fresh."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        tokens: dict[str, Any],
        on_tokens: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._session = session
        self._tokens = {
            key: tokens[key] for key in (CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, CONF_EXPIRES_AT)
        }
        self._on_tokens = on_tokens
        self._lock = asyncio.Lock()

    async def _access_token(self, rejected: str | None = None) -> str:
        async with self._lock:
            current = self._tokens[CONF_ACCESS_TOKEN]
            expired = time.time() > self._tokens[CONF_EXPIRES_AT] - EXPIRY_SKEW
            if expired or current == rejected:
                self._tokens = await refresh_tokens(self._session, self._tokens[CONF_REFRESH_TOKEN])
                if self._on_tokens:
                    self._on_tokens(dict(self._tokens))
            return self._tokens[CONF_ACCESS_TOKEN]

    async def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """GET a Skylight API path and return the decoded JSON."""
        rejected: str | None = None
        for attempt in range(2):
            token = await self._access_token(rejected)
            async with self._session.get(
                f"{BASE_URL}{path}", params=params, headers=_headers(token), timeout=TIMEOUT
            ) as resp:
                if resp.status == 401:
                    _check_version(401, await resp.text())
                    if attempt == 0:
                        rejected = token
                        continue
                    raise SkylightAuthError("Skylight rejected the access token")
                if resp.status != 200:
                    raise SkylightError(f"GET {path} failed (HTTP {resp.status})")
                return await resp.json()
        raise SkylightError(f"GET {path} failed")

    async def frames(self) -> list[dict[str, Any]]:
        return (await self.get("/api/frames"))["data"]
