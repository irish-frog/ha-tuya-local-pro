"""Binary sensor platform for Tuya Local Pro."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DPS_MAPPINGS,
    DOMAIN,
    ENTITY_TYPE_BINARY_SENSOR,
)
from .entity import TuyaLocalEntity
from .helpers import get_device_id

_LOGGER = logging.getLogger(__name__)

# Default binary sensor DPS mappings (fallback when no custom mappings)
DEFAULT_BINARY_SENSOR_DPS_MAP = {
    "4": {
        "name": "Fault",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
    "6": {
        "name": "Fault (alt)",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities from a config entry."""
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
            if mapping.get("entity_type") != ENTITY_TYPE_BINARY_SENSOR:
                continue

            dps_id = mapping.get("dps_id")
            if dps_id not in cached:
                continue

            # Map device_class string to BinarySensorDeviceClass enum
            device_class = None
            if mapping.get("device_class"):
                try:
                    device_class = BinarySensorDeviceClass(mapping["device_class"])
                except ValueError:
                    pass

            entities.append(
                TuyaLocalProBinarySensor(
                    device,
                    {
                        "name": mapping.get("name", f"Binary Sensor {dps_id}"),
                        "entity_id_suffix": f"binary_sensor_{dps_id}",
                        "sensor_dps": int(dps_id),
                        "device_class": device_class,
                        "icon": mapping.get("icon"),
                    },
                )
            )
    else:
        # Use default binary sensor mappings (auto-detect from cached state)
        for dps_id, bs_config in DEFAULT_BINARY_SENSOR_DPS_MAP.items():
            if dps_id in cached:
                value = cached[dps_id]
                if isinstance(value, (int, str, bool)):
                    entities.append(
                        TuyaLocalProBinarySensor(
                            device,
                            {
                                "name": bs_config["name"],
                                "entity_id_suffix": f"binary_sensor_{dps_id}",
                                "sensor_dps": int(dps_id),
                                "device_class": bs_config["device_class"],
                            },
                        )
                    )

    if entities:
        async_add_entities(entities, True)
        for entity in entities:
            device.register_update_callback(entity.on_receive)


class TuyaLocalProBinarySensor(TuyaLocalEntity, BinarySensorEntity):
    """Representation of a Tuya Local Pro Binary Sensor."""

    def __init__(self, device, config):
        """Initialize the binary sensor."""
        super().__init__(device, config)
        self._sensor_dps = config.get("sensor_dps")
        self._device_class = config.get("device_class")

    @property
    def is_on(self):
        """Return True if the binary sensor is on (fault detected)."""
        if self._sensor_dps is None:
            return None
        value = self._get_dps_value(self._sensor_dps)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.lower() not in ("0", "false", "off", "normal", "ok", "")
        return bool(value)

    @property
    def device_class(self):
        """Return the class of this device."""
        return self._device_class

    def on_receive(self, poll: dict, full_poll: bool = False):
        """Handle state updates from the device."""
        if self._sensor_dps and str(self._sensor_dps) in poll:
            self.schedule_update_ha_state()
