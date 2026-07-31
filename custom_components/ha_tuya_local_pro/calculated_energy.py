"""Calculated Energy Sensor using Riemann sum integration.

This module provides a calculated energy sensor that derives kWh from a power sensor
using Riemann sum integration. It's designed for Energy Dashboard compatibility with
persistent storage across Home Assistant restarts.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Storage version and key
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = "calculated_energy"


class CalculatedEnergySensor(RestoreEntity, SensorEntity):
    """Calculated energy sensor using Riemann sum integration.
    
    This sensor calculates cumulative energy (kWh) from a power sensor (W)
    using the left Riemann sum method. It persists its state across restarts
    and is compatible with the Home Assistant Energy Dashboard.
    
    Attributes:
        _attr_device_class: SensorDeviceClass.ENERGY
        _attr_state_class: SensorStateClass.TOTAL_INCREASING
        _attr_native_unit_of_measurement: UnitOfEnergy.KILO_WATT_HOUR
    """
    
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_has_entity_name = False
    _attr_should_poll = False
    
    def __init__(
        self,
        hass: HomeAssistant,
        source_entity_id: str,
        device_unique_id: str,
        device_name: str,
        sensor_name: str = "Calculated Energy",
        precision: int = 3,
        method: str = "left",
        sensor_suffix: str = "calculated_energy",
    ) -> None:
        """Initialize the calculated energy sensor.
        
        Args:
            hass: Home Assistant instance.
            source_entity_id: Entity ID of the source power sensor.
            device_unique_id: Unique ID of the parent Tuya device.
            device_name: Name of the parent Tuya device.
            sensor_name: Friendly name for this sensor.
            precision: Number of decimal places for the result.
            method: Riemann sum method ('left', 'trapezoidal', or 'right').
            sensor_suffix: Suffix for unique ID to avoid collisions.
        """
        super().__init__()
        
        self._hass = hass
        self._source_entity_id = source_entity_id
        self._device_unique_id = device_unique_id
        self._device_name = device_name
        self._precision = precision
        self._method = method
        
        # Set entity attributes
        self._attr_name = sensor_name
        self._attr_unique_id = f"{device_unique_id}_{sensor_suffix}"
        self._attr_icon = "mdi:lightning-bolt"
        
        # Set up device info - share with parent device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            name=device_name,
            manufacturer="Tuya",
        )
        
        # Riemann sum state
        self._accumulated_kwh: float = 0.0
        self._last_sample_time: Optional[datetime] = None
        self._last_sample_value: Optional[float] = None
        self._initialized = False
        
        # Storage - use sensor_suffix to avoid key collisions
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}_{device_unique_id}_{sensor_suffix}"
        )
        self._unsub_state_listener = None
    
    @property
    def native_value(self) -> Optional[float]:
        """Return the current accumulated energy value."""
        if not self._initialized:
            return None
        return round(self._accumulated_kwh, self._precision)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "source_entity": self._source_entity_id,
            "integration_method": self._method,
            "last_sample_time": self._last_sample_time.isoformat() if self._last_sample_time else None,
            "last_sample_value": self._last_sample_value,
        }
    
    @property
    def available(self) -> bool:
        """Return True if the source entity is available."""
        state = self._hass.states.get(self._source_entity_id)
        return state is not None and state.state not in ("unavailable", "unknown")
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
        # Restore previous state from HA's restore state
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unavailable", "unknown", "none"):
            try:
                self._accumulated_kwh = float(last_state.state)
                self._initialized = True
                _LOGGER.debug(
                    "Restored accumulated energy: %s kWh for %s",
                    self._accumulated_kwh,
                    self._source_entity_id,
                )
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Could not restore energy state for %s, starting from 0",
                    self._source_entity_id,
                )
        
        # Also try to restore from our custom storage
        stored_data = await self._store.async_load()
        if stored_data and "accumulated_kwh" in stored_data:
            self._accumulated_kwh = stored_data["accumulated_kwh"]
            self._initialized = True
            if "last_sample_time" in stored_data:
                self._last_sample_time = datetime.fromisoformat(stored_data["last_sample_time"])
            if "last_sample_value" in stored_data:
                self._last_sample_value = stored_data["last_sample_value"]
        
        # Listen for source entity state changes
        self._unsub_state_listener = async_track_state_change_event(
            self._hass,
            self._source_entity_id,
            self._async_source_state_changed,
        )
        
        # Process current source state
        source_state = self._hass.states.get(self._source_entity_id)
        if source_state and source_state.state not in ("unavailable", "unknown"):
            self._process_power_value(source_state)
    
    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from hass."""
        await super().async_will_remove_from_hass()
        
        # Unsubscribe from state changes
        if self._unsub_state_listener:
            self._unsub_state_listener()
            self._unsub_state_listener = None
        
        # Persist current state
        await self._persist_state()
    
    @callback
    def _async_source_state_changed(self, event) -> None:
        """Handle source entity state change."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        
        if new_state.state in ("unavailable", "unknown"):
            return
        
        self._process_power_value(new_state)
        self.async_write_ha_state()
    
    def _process_power_value(self, state: State) -> None:
        """Process a power value and calculate energy using Riemann sum.
        
        Uses the left Riemann sum method:
        energy = power × time_interval
        
        The power is converted from W to kW by dividing by 1000.
        """
        try:
            power_watts = float(state.state)
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid power value: %s", state.state)
            return
        
        # Use last_updated for more accurate time tracking
        current_time = state.last_updated or datetime.now()
        
        if self._last_sample_time is not None and self._last_sample_value is not None:
            # Calculate time interval in hours
            time_delta = current_time - self._last_sample_time
            hours = time_delta.total_seconds() / 3600.0
            
            if hours <= 0:
                return
            
            # Calculate energy using the selected method
            if self._method == "left":
                # Left Riemann sum: use the previous sample value
                energy_wh = self._last_sample_value * hours
            elif self._method == "trapezoidal":
                # Trapezoidal rule: average of current and previous
                energy_wh = ((self._last_sample_value + power_watts) / 2.0) * hours
            elif self._method == "right":
                # Right Riemann sum: use the current sample value
                energy_wh = power_watts * hours
            else:
                energy_wh = self._last_sample_value * hours
            
            # Convert Wh to kWh
            energy_kwh = energy_wh / 1000.0
            
            # Only add positive energy (avoid counting negative power from solar export, etc.)
            if energy_kwh > 0:
                self._accumulated_kwh += energy_kwh
                self._initialized = True
                _LOGGER.debug(
                    "Calculated energy: %.6f kWh (power=%.1fW, time=%.4fh, method=%s)",
                    energy_kwh,
                    power_watts,
                    hours,
                    self._method,
                )
        
        # Update sample tracking
        self._last_sample_time = current_time
        self._last_sample_value = power_watts
    
    async def _persist_state(self) -> None:
        """Persist the accumulated energy state to storage."""
        data = {
            "accumulated_kwh": self._accumulated_kwh,
            "last_sample_time": self._last_sample_time.isoformat() if self._last_sample_time else None,
            "last_sample_value": self._last_sample_value,
        }
        await self._store.async_save(data)
        _LOGGER.debug(
            "Persisted calculated energy: %s kWh for %s",
            self._accumulated_kwh,
            self._source_entity_id,
        )
    
    async def async_reset(self, energy: float = 0.0) -> None:
        """Reset the accumulated energy value.
        
        Args:
            energy: New accumulated energy value (default 0).
        """
        self._accumulated_kwh = energy
        self._initialized = True
        self.async_write_ha_state()
        await self._persist_state()
        _LOGGER.info(
            "Reset calculated energy to %s kWh for %s",
            energy,
            self._source_entity_id,
        )
