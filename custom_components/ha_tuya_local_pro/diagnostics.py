"""Diagnostics support for Tuya Local Pro."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .helpers import get_device_id

# Keys to redact from diagnostics output
REDACT_KEYS = {"local_key"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry with sensitive data redacted."""
    device_id = get_device_id(entry.data)

    return {
        "config_entry_data": async_redact_data(dict(entry.data), REDACT_KEYS),
        "config_entry_options": async_redact_data(dict(entry.options), REDACT_KEYS),
        "device_id": device_id,
        "title": entry.title,
    }
