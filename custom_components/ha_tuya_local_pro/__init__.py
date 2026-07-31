"""
Tuya Local Pro - A local-first Home Assistant integration for Tuya WiFi devices.

This integration communicates directly with Tuya devices over the local network.
Cloud access is optional and used only for onboarding, not daily operation.
"""

import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .helpers import get_device_id
from .panel import async_register_dps_builder_panel
from .tuya_device import setup_device, async_delete_device
from .websocket_api import async_register_websocket_apis

_LOGGER = logging.getLogger(__name__)


def cleanup_failed_device(hass: HomeAssistant, device_id: str):
    """Drop cached device objects left behind by failed setup."""
    domain_data = hass.data.get(DOMAIN, {})
    stale = domain_data.pop(device_id, None)
    if not stale:
        return

    api = stale.get("tuyadevice")
    if api:
        api.set_socketPersistent(False)
        if api.parent:
            api.parent.set_socketPersistent(False)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Tuya Local Pro component."""
    # Register WebSocket APIs
    await async_register_websocket_apis(hass)
    await async_register_dps_builder_panel(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Tuya Local Pro from a config entry."""
    device_id = get_device_id(entry.data)
    _LOGGER.debug("Setting up entry for device: %s", device_id)

    config = {**entry.data, **entry.options, "name": entry.title}
    try:
        device = await hass.async_add_executor_job(setup_device, hass, config)
        await device.async_refresh()
    except Exception as e:
        cleanup_failed_device(hass, device_id)
        raise ConfigEntryNotReady("Tuya Local Pro device not ready") from e

    if not device.has_returned_state:
        cleanup_failed_device(hass, device_id)
        raise ConfigEntryNotReady("Tuya Local Pro device offline")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.add_update_listener(async_update_entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    device_id = get_device_id(entry.data)
    _LOGGER.debug("Unloading entry for device: %s", device_id)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        await async_delete_device(hass, entry.data)
        hass.data.get(DOMAIN, {}).pop(device_id, None)

    return unload_ok


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug("Updating entry for device: %s", get_device_id(entry.data))
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
