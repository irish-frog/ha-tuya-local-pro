"""WebSocket API for Tuya Local Pro integration."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.websocket_api import (
    ActiveConnection,
    websocket_api,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    WS_API_DPS_MAPPING_LOAD,
    WS_API_DPS_MAPPING_SAVE,
    WS_API_DPS_STREAM,
    WS_API_DPS_TOGGLE,
    WS_API_PROFILE_EXPORT,
    WS_API_PROFILE_IMPORT,
)
from .helpers import (
    export_device_profile,
    get_device_id,
    import_device_profile,
    validate_profile,
)

_LOGGER = logging.getLogger(__name__)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_API_DPS_STREAM,
        vol.Required("device_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def handle_dps_stream(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Stream live DPS data from a device."""
    device_id = msg.get("device_id")
    if not device_id:
        connection.send_error(msg["id"], "invalid_device_id", "No device_id provided")
        return

    device_data = hass.data.get(DOMAIN, {}).get(device_id)
    if not device_data:
        connection.send_error(msg["id"], "device_not_found", f"Device {device_id} not found")
        return

    device = device_data.get("device")
    if not device:
        connection.send_error(msg["id"], "device_not_found", f"Device object not found for {device_id}")
        return

    # Send initial state
    cached_state = device._get_cached_state()
    # Filter out internal keys
    dps_data = {k: v for k, v in cached_state.items() if k not in ("updated_at",)}
    connection.send_result(msg["id"], {"dps": dps_data})

    # Register callback for live updates
    @callback
    def on_dps_update(poll: dict, full_poll: bool = False):
        """Handle DPS update from device."""
        # Filter out internal keys
        filtered_poll = {k: v for k, v in poll.items() if k not in ("full_poll", "updated_at")}
        if filtered_poll:
            connection.send_message(
                websocket_api.event_message(msg["id"], {"dps": filtered_poll, "full_poll": full_poll})
            )

    device.register_update_callback(on_dps_update)

    # Store the callback reference so we can unregister later
    if not hasattr(connection, "_tuya_dps_callbacks"):
        connection._tuya_dps_callbacks = {}
    connection._tuya_dps_callbacks[device_id] = on_dps_update

    # Clean up when connection closes
    @callback
    def on_connection_close():
        """Clean up when websocket connection closes."""
        if hasattr(connection, "_tuya_dps_callbacks") and device_id in connection._tuya_dps_callbacks:
            device.unregister_update_callback(connection._tuya_dps_callbacks.pop(device_id))

    connection.subscriptions[msg["id"]] = on_connection_close


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_API_DPS_TOGGLE,
        vol.Required("device_id"): str,
        vol.Required("dps_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def handle_dps_toggle(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Toggle a boolean-like DPS value on a device."""
    device_id = msg.get("device_id")
    dps_id = msg.get("dps_id")

    if not device_id or dps_id is None:
        connection.send_error(msg["id"], "invalid_request", "device_id and dps_id are required")
        return

    device_data = hass.data.get(DOMAIN, {}).get(device_id)
    if not device_data:
        connection.send_error(msg["id"], "device_not_found", f"Device {device_id} not found")
        return

    device = device_data.get("device")
    if not device:
        connection.send_error(msg["id"], "device_not_found", f"Device object not found for {device_id}")
        return

    cached_state = device.get_cached_state()
    current_value = cached_state.get(str(dps_id))
    if isinstance(current_value, bool):
        new_value = not current_value
    elif isinstance(current_value, int) and current_value in (0, 1):
        new_value = 0 if current_value == 1 else 1
    else:
        connection.send_error(
            msg["id"],
            "unsupported_dps_value",
            f"DPS {dps_id} is not toggleable",
        )
        return

    try:
        await device.async_set_property(str(dps_id), new_value)
    except Exception as err:
        connection.send_error(msg["id"], "toggle_failed", f"Failed to toggle DPS {dps_id}: {err}")
        return

    connection.send_result(msg["id"], {"success": True, "dps_id": str(dps_id), "value": new_value})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_API_DPS_MAPPING_SAVE,
        vol.Required("device_id"): str,
        vol.Optional("mappings", default=[]): list,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def handle_dps_mapping_save(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Save DPS mappings for a device."""
    device_id = msg.get("device_id")
    mappings = msg.get("mappings", [])

    if not device_id:
        connection.send_error(msg["id"], "invalid_device_id", "No device_id provided")
        return

    # Find the config entry for this device
    config_entry = None
    for entry in hass.config_entries.async_entries(DOMAIN):
        entry_device_id = get_device_id(entry.data)
        if entry_device_id == device_id:
            config_entry = entry
            break

    if not config_entry:
        connection.send_error(msg["id"], "config_entry_not_found", f"No config entry found for device {device_id}")
        return

    # Validate mappings
    validated_mappings = []
    for mapping in mappings:
        validated = {
            "dps_id": str(mapping.get("dps_id", "")),
            "dps_type": mapping.get("dps_type", "integer"),
            "name": mapping.get("name", f"DPS {mapping.get('dps_id', '?')}"),
            "entity_type": mapping.get("entity_type", "sensor"),
            "scale": float(mapping.get("scale", 1.0)),
            "offset": float(mapping.get("offset", 0.0)),
            "unit": mapping.get("unit", None),
            "device_class": mapping.get("device_class", None),
            "state_class": mapping.get("state_class", None),
            "icon": mapping.get("icon", None),
            "on_value": mapping.get("on_value", True),
            "off_value": mapping.get("off_value", False),
        }
        validated_mappings.append(validated)

    # Update the config entry options
    new_options = {**config_entry.options, "dps_mappings": validated_mappings}
    hass.config_entries.async_update_entry(config_entry, options=new_options)

    connection.send_result(msg["id"], {"success": True, "mappings": validated_mappings})
    _LOGGER.info("Saved %d DPS mappings for device %s", len(validated_mappings), device_id)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_API_DPS_MAPPING_LOAD,
        vol.Required("device_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def handle_dps_mapping_load(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Load DPS mappings for a device."""
    device_id = msg.get("device_id")

    if not device_id:
        connection.send_error(msg["id"], "invalid_device_id", "No device_id provided")
        return

    # Find the config entry for this device
    config_entry = None
    for entry in hass.config_entries.async_entries(DOMAIN):
        entry_device_id = get_device_id(entry.data)
        if entry_device_id == device_id:
            config_entry = entry
            break

    if not config_entry:
        connection.send_error(msg["id"], "config_entry_not_found", f"No config entry found for device {device_id}")
        return

    mappings = config_entry.options.get("dps_mappings", [])
    connection.send_result(msg["id"], {"mappings": mappings})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_API_PROFILE_EXPORT,
        vol.Required("device_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def handle_profile_export(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Export device profile to a portable format."""
    device_id = msg.get("device_id")

    if not device_id:
        connection.send_error(msg["id"], "invalid_device_id", "No device_id provided")
        return

    # Find the config entry for this device
    config_entry = None
    for entry in hass.config_entries.async_entries(DOMAIN):
        entry_device_id = get_device_id(entry.data)
        if entry_device_id == device_id:
            config_entry = entry
            break

    if not config_entry:
        connection.send_error(msg["id"], "config_entry_not_found", f"No config entry found for device {device_id}")
        return

    # Get device data
    device_data = hass.data.get(DOMAIN, {}).get(device_id)
    device_name = config_entry.title
    dps_mappings = config_entry.options.get("dps_mappings", [])
    
    # Get device info if available
    device_info = None
    if device_data and "device" in device_data:
        device = device_data["device"]
        device_info = {
            "manufacturer": "Tuya",
            "model": "Unknown",
        }

    # Export the profile
    profile = export_device_profile(
        device_id=device_id,
        device_name=device_name,
        dps_mappings=dps_mappings,
        device_info=device_info,
    )

    connection.send_result(msg["id"], {"profile": profile})
    _LOGGER.info("Exported profile for device %s with %d entities", device_id, len(dps_mappings))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_API_PROFILE_IMPORT,
        vol.Required("device_id"): str,
        vol.Required("profile"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def handle_profile_import(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Import device profile from a portable format."""
    device_id = msg.get("device_id")
    profile = msg.get("profile", {})

    if not device_id:
        connection.send_error(msg["id"], "invalid_device_id", "No device_id provided")
        return

    if not profile:
        connection.send_error(msg["id"], "invalid_profile", "No profile provided")
        return

    # Validate the profile
    is_valid, error_message = validate_profile(profile)
    if not is_valid:
        connection.send_error(msg["id"], "invalid_profile", f"Invalid profile: {error_message}")
        return

    # Find the config entry for this device
    config_entry = None
    for entry in hass.config_entries.async_entries(DOMAIN):
        entry_device_id = get_device_id(entry.data)
        if entry_device_id == device_id:
            config_entry = entry
            break

    if not config_entry:
        connection.send_error(msg["id"], "config_entry_not_found", f"No config entry found for device {device_id}")
        return

    # Import the profile
    try:
        mappings = import_device_profile(profile)
        
        # Update the config entry options
        new_options = {**config_entry.options, "dps_mappings": mappings}
        hass.config_entries.async_update_entry(config_entry, options=new_options)
        
        connection.send_result(msg["id"], {
            "success": True,
            "mappings": mappings,
            "message": f"Imported {len(mappings)} entity mappings from profile",
        })
        _LOGGER.info("Imported profile for device %s with %d mappings", device_id, len(mappings))
    except Exception as e:
        connection.send_error(msg["id"], "import_error", f"Failed to import profile: {str(e)}")
        _LOGGER.error("Failed to import profile for device %s: %s", device_id, e)


async def async_register_websocket_apis(hass: HomeAssistant) -> None:
    """Register WebSocket APIs."""
    websocket_api.async_register_command(hass, handle_dps_stream)
    websocket_api.async_register_command(hass, handle_dps_toggle)
    websocket_api.async_register_command(hass, handle_dps_mapping_save)
    websocket_api.async_register_command(hass, handle_dps_mapping_load)
    websocket_api.async_register_command(hass, handle_profile_export)
    websocket_api.async_register_command(hass, handle_profile_import)
    _LOGGER.debug("Registered Tuya Local Pro WebSocket APIs")
