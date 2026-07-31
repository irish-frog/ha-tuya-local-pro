"""Switch platform for Tuya Local Pro."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DPS_MAPPINGS,
    DOMAIN,
    ENTITY_TYPE_SWITCH,
)
from .entity import TuyaLocalSwitchEntity
from .helpers import (
    get_device_id,
    load_device_profiles,
    find_matching_profile,
    profile_to_entity_configs,
)

_LOGGER = logging.getLogger(__name__)

# Default switch DPS mappings (fallback when no custom mappings)
DEFAULT_SWITCH_DPS_MAP = {
    "1": {
        "name": "Switch",
        "on_value": True,
        "off_value": False,
    },
    "7": {
        "name": "Child Lock",
        "on_value": True,
        "off_value": False,
        "icon": "mdi:lock",
    },
    "102": {
        "name": "Overcharge Switch",
        "on_value": True,
        "off_value": False,
        "icon": "mdi:flash-alert",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from a config entry."""
    config = {**config_entry.data, **config_entry.options}
    device_id = get_device_id(config)

    device_data = hass.data[DOMAIN].get(device_id)
    if device_data is None:
        _LOGGER.error("No device data found for %s", device_id)
        return

    device = device_data["device"]
    cached = device.get_cached_state()

    # Check for custom DPS mappings
    custom_mappings = config_entry.options.get(CONF_DPS_MAPPINGS, [])
    entities = []

    if custom_mappings:
        # Use custom DPS mappings
        for mapping in custom_mappings:
            if mapping.get("entity_type") != ENTITY_TYPE_SWITCH:
                continue

            dps_id = mapping.get("dps_id")
            if dps_id not in cached:
                continue

            # Check if value is boolean or integer (0/1)
            value = cached[dps_id]
            if not isinstance(value, (bool, int)):
                continue

            entities.append(
                TuyaLocalProSwitch(
                    device,
                    {
                        "name": mapping.get("name", f"Switch {dps_id}"),
                        "entity_id_suffix": f"switch_{dps_id}",
                        "switch_dps": int(dps_id),
                        "on_value": mapping.get("on_value", True),
                        "off_value": mapping.get("off_value", False),
                        "icon": mapping.get("icon"),
                    },
                )
            )
    else:
        # Try to load device profiles from YAML files
        profiles = load_device_profiles(hass)
        match_result = find_matching_profile(profiles, cached)
        
        if match_result:
            profile_name, profile = match_result
            profile_entities = profile_to_entity_configs(profile)
            _LOGGER.info("Using device profile '%s' for switches", profile_name)
            
            # Use device profile entities
            for entity_config in profile_entities:
                if entity_config.get("entity_type") != "switch":
                    continue
                
                dps_id = entity_config.get("dps_id")
                if dps_id not in cached:
                    continue
                
                # Check if value is boolean or integer (0/1)
                value = cached[dps_id]
                if not isinstance(value, (bool, int)):
                    continue
                
                entities.append(
                    TuyaLocalProSwitch(
                        device,
                        {
                            "name": entity_config.get("name", f"Switch {dps_id}"),
                            "entity_id_suffix": f"switch_{dps_id}",
                            "switch_dps": int(dps_id),
                            "on_value": entity_config.get("on_value", True),
                            "off_value": entity_config.get("off_value", False),
                            "icon": entity_config.get("icon"),
                        },
                    )
                )
        else:
            # Use default switch mappings (auto-detect from cached state)
            for dps_id, switch_config in DEFAULT_SWITCH_DPS_MAP.items():
                if dps_id in cached:
                    value = cached[dps_id]
                    if isinstance(value, (bool, int)):
                        entities.append(
                            TuyaLocalProSwitch(
                                device,
                                {
                                    "name": switch_config["name"],
                                    "entity_id_suffix": f"switch_{dps_id}",
                                    "switch_dps": int(dps_id),
                                    "on_value": switch_config["on_value"],
                                    "off_value": switch_config["off_value"],
                                    "icon": switch_config.get("icon"),
                                },
                            )
                        )

    if entities:
        async_add_entities(entities, True)

        # Register update callbacks
        for entity in entities:
            device.register_update_callback(entity.on_receive)


class TuyaLocalProSwitch(TuyaLocalSwitchEntity, SwitchEntity):
    """Representation of a Tuya Local Pro Switch."""

    def __init__(self, device, config):
        """Initialize the switch."""
        super().__init__(device, config)
