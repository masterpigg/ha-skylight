"""Constants for the (unofficial, read-only) Skylight Calendar integration."""

import logging

DOMAIN = "skylight"
LOGGER = logging.getLogger(__package__)

BASE_URL = "https://app.ourskylight.com"

# Skylight rejects requests whose version header names a retired app version
# ("This version of Skylight is no longer supported"). When that happens,
# update this value to the one the current Skylight app sends.
API_VERSION = "2026-10-15"

# OAuth client the Skylight apps use (authorization code + PKCE)
OAUTH_CLIENT_ID = "skylight-mobile"
OAUTH_REDIRECT_URI = "https://ourskylight.com/welcome"
OAUTH_SCOPE = "everything"

CONF_FRAME_ID = "frame_id"
CONF_FRAME_NAME = "frame_name"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"

UPDATE_INTERVAL_MINUTES = 5
CALENDAR_LOOKAHEAD_DAYS = 14
