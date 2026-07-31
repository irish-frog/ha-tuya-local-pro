"""Base entity class for Tuya Local Pro devices."""

import logging
from typing import Any

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN
from .tuya_device import TuyaLocalDevice

_LOGGER = logging.getLogger(__name__)


class TuyaLocalEntity(Entity):
    """Base class for all Tuya Local Pro entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: TuyaLocalDevice, config: dict):
        """Initialize the entity.

        Args:
            device: The TuyaLocalDevice instance.
            config: Entity configuration dictionary.
        """
        self._device = device
        self._config = config
        self._dps_map = {}

        # Set up entity ID and name from config
        self._attr_name = config.get("name", None)
        self._attr_unique_id = f"{device.unique_id}_{config.get('entity_id_suffix', 'entity')}"

        # Set up device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer="Tuya",
        )

        # Set up icon if specified
        if "icon" in config:
            self._attr_icon = config["icon"]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device.has_returned_state

    def on_receive(self, poll: dict, full_poll: bool = False):
        """Handle state updates from the device.

        Args:
            poll: Dictionary of DPS updates.
            full_poll: True if this is a full status poll.
        """
        pass

    def schedule_update_ha_state(self):
        """Schedule an update of the HA state."""
        self.async_schedule_update_ha_state()

    def _get_dps_value(self, dps_id: int) -> Any:
        """Get a value from the device by DPS ID."""
        return self._device.get_property(str(dps_id))

    async def _set_dps_value(self, dps_id: int, value: Any):
        """Set a value on the device by DPS ID."""
        await self._device.async_set_property(str(dps_id), value)

    def _apply_scale(self, value: Any, scale: float = 1.0, offset: float = 0.0) -> Any:
        """Apply scale and offset to a value."""
        if value is None:
            return None
        try:
            return (float(value) * scale) + offset
        except (TypeError, ValueError):
            return value


class TuyaLocalSensorEntity(TuyaLocalEntity):
    """Base class for Tuya sensor entities."""

    def __init__(self, device: TuyaLocalDevice, config: dict):
        """Initialize the sensor entity."""
        super().__init__(device, config)
        self._sensor_dps = config.get("sensor_dps")
        self._unit = config.get("unit", None)
        self._device_class = config.get("device_class", None)
        self._state_class = config.get("state_class", None)
        self._scale = config.get("scale", 1.0)
        self._offset = config.get("offset", 0.0)
        self._precision = config.get("precision", None)
        self._values = config.get("values", None)

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        if self._sensor_dps is None:
            return None
        value = self._get_dps_value(self._sensor_dps)
        if value is not None:
            value = self._apply_scale(value, self._scale, self._offset)
            if self._precision is not None:
                try:
                    value = round(float(value), self._precision)
                except (TypeError, ValueError):
                    pass
        return value

    @property
    def native_unit_of_measurement(self):
        """Return the unit for the sensor."""
        return self._unit

    @property
    def device_class(self):
        """Return the class of this device."""
        return self._device_class

    @property
    def state_class(self):
        """Return the state class of this entity."""
        return self._state_class

    @property
    def options(self):
        """Return a set of possible options."""
        if self._values:
            return list(self._values.values())
        return None

    def on_receive(self, poll: dict, full_poll: bool = False):
        """Handle state updates from the device."""
        if self._sensor_dps and str(self._sensor_dps) in poll:
            self.schedule_update_ha_state()


class TuyaLocalSwitchEntity(TuyaLocalEntity):
    """Base class for Tuya switch entities."""

    def __init__(self, device: TuyaLocalDevice, config: dict):
        """Initialize the switch entity."""
        super().__init__(device, config)
        self._switch_dps = config.get("switch_dps")
        self._on_value = config.get("on_value", True)
        self._off_value = config.get("off_value", False)

    @property
    def is_on(self):
        """Return True if the switch is on."""
        if self._switch_dps is None:
            return None
        value = self._get_dps_value(self._switch_dps)
        return value == self._on_value

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._switch_dps is not None:
            await self._set_dps_value(self._switch_dps, self._on_value)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._switch_dps is not None:
            await self._set_dps_value(self._switch_dps, self._off_value)

    def on_receive(self, poll: dict, full_poll: bool = False):
        """Handle state updates from the device."""
        if self._switch_dps and str(self._switch_dps) in poll:
            self.schedule_update_ha_state()
