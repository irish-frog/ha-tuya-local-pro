"""Sensor platform for Tuya Local Pro."""

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .calculated_energy import CalculatedEnergySensor
from .const import (
    DOMAIN,
    ENTITY_TYPE_SENSOR,
)
from .entity import TuyaLocalSensorEntity
from .helpers import (
    get_device_id,
    load_device_profiles,
    find_matching_profile,
    profile_to_entity_configs,
)

_LOGGER = logging.getLogger(__name__)

# Default DPS mappings for DIN Rail energy monitors (fallback when no custom mappings)
DEFAULT_SENSOR_DPS_MAP = {
    "18": {
        "name": "Current",
        "unit": UnitOfElectricCurrent.AMPERE,
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "scale": 0.001,
        "precision": 2,
    },
    "19": {
        "name": "Power",
        "unit": "W",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "scale": 0.1,
        "precision": 1,
    },
    "20": {
        "name": "Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "scale": 0.1,
        "precision": 1,
    },
    "1": {
        "name": "Total Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
        "precision": 2,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    config = {**config_entry.data, **config_entry.options}
    device_id = get_device_id(config)

    device_data = hass.data[DOMAIN].get(device_id)
    if device_data is None:
        _LOGGER.error("No device data found for %s", device_id)
        return

    device = device_data["device"]
    cached = device.get_cached_state()

    # Check for custom DPS mappings
    custom_mappings = config_entry.options.get("dps_mappings", [])
    entities = []

    # Track power sensors for calculated energy creation
    # Store: (unique_id_suffix, sensor_name, dps_id)
    power_sensors_info = []

    if custom_mappings:
        # Use custom DPS mappings
        for mapping in custom_mappings:
            if mapping.get("entity_type") != ENTITY_TYPE_SENSOR:
                continue

            dps_id = mapping.get("dps_id")
            if dps_id not in cached:
                continue

            # Check if value is numeric
            value = cached[dps_id]
            if not isinstance(value, (int, float)):
                continue

            # Map device_class string to SensorDeviceClass enum
            device_class = None
            if mapping.get("device_class"):
                try:
                    device_class = SensorDeviceClass(mapping["device_class"])
                except ValueError:
                    pass

            # Map state_class string to SensorStateClass enum
            state_class = None
            if mapping.get("state_class"):
                try:
                    state_class = SensorStateClass(mapping["state_class"])
                except ValueError:
                    pass

            unique_id_suffix = f"sensor_{dps_id}"
            sensor_entity = TuyaLocalProSensor(
                device,
                {
                    "name": mapping.get("name", f"Sensor {dps_id}"),
                    "entity_id_suffix": unique_id_suffix,
                    "sensor_dps": int(dps_id),
                    "unit": mapping.get("unit"),
                    "device_class": device_class,
                    "state_class": state_class,
                    "scale": float(mapping.get("scale", 1.0)),
                    "offset": float(mapping.get("offset", 0.0)),
                    "precision": 2,
                    "icon": mapping.get("icon"),
                },
            )
            entities.append(sensor_entity)

            # Track power sensors for calculated energy creation
            if device_class == SensorDeviceClass.POWER:
                power_sensors_info.append((unique_id_suffix, mapping.get("name", f"Power {dps_id}"), dps_id))
    else:
        # Try to load device profiles from YAML files
        profiles = load_device_profiles(hass)
        match_result = find_matching_profile(profiles, cached)
        
        if match_result:
            profile_name, profile = match_result
            profile_entities = profile_to_entity_configs(profile)
            _LOGGER.info("Using device profile '%s' for sensors", profile_name)
            
            # Use device profile entities
            for entity_config in profile_entities:
                if entity_config.get("entity_type") != "sensor":
                    continue
                
                dps_id = entity_config.get("dps_id")
                if dps_id not in cached:
                    continue
                
                # Check if value is numeric
                value = cached[dps_id]
                if not isinstance(value, (int, float)):
                    continue
                
                # Map device_class string to SensorDeviceClass enum
                device_class = None
                if entity_config.get("device_class"):
                    try:
                        device_class = SensorDeviceClass(entity_config["device_class"])
                    except ValueError:
                        pass
                
                # Map state_class string to SensorStateClass enum
                state_class = None
                if entity_config.get("state_class"):
                    try:
                        state_class = SensorStateClass(entity_config["state_class"])
                    except ValueError:
                        pass
                
                unique_id_suffix = f"sensor_{dps_id}"
                sensor_entity = TuyaLocalProSensor(
                    device,
                    {
                        "name": entity_config.get("name", f"Sensor {dps_id}"),
                        "entity_id_suffix": unique_id_suffix,
                        "sensor_dps": int(dps_id),
                        "unit": entity_config.get("unit"),
                        "device_class": device_class,
                        "state_class": state_class,
                        "scale": float(entity_config.get("scale", 1.0)),
                        "offset": float(entity_config.get("offset", 0.0)),
                        "precision": 2,
                        "icon": entity_config.get("icon"),
                    },
                )
                entities.append(sensor_entity)
                
                # Track power sensors for calculated energy creation
                if device_class == SensorDeviceClass.POWER:
                    power_sensors_info.append((unique_id_suffix, entity_config.get("name", f"Power {dps_id}"), dps_id))
        else:
            # Use default DPS mappings (auto-detect from cached state)
            for dps_id, sensor_config in DEFAULT_SENSOR_DPS_MAP.items():
                if dps_id in cached:
                    value = cached[dps_id]
                    if isinstance(value, (int, float)):
                        unique_id_suffix = f"sensor_{dps_id}"
                        sensor_entity = TuyaLocalProSensor(
                            device,
                            {
                                "name": sensor_config["name"],
                                "entity_id_suffix": unique_id_suffix,
                                "sensor_dps": int(dps_id),
                                "unit": sensor_config["unit"],
                                "device_class": sensor_config["device_class"],
                                "state_class": sensor_config["state_class"],
                                "scale": sensor_config["scale"],
                                "precision": sensor_config["precision"],
                            },
                        )
                        entities.append(sensor_entity)

                        # Track power sensors for calculated energy creation
                        if sensor_config.get("device_class") == SensorDeviceClass.POWER:
                            power_sensors_info.append((unique_id_suffix, sensor_config["name"], dps_id))

    if entities:
        async_add_entities(entities, True)
        for entity in entities:
            if hasattr(entity, 'on_receive'):
                device.register_update_callback(entity.on_receive)

    # Schedule calculated energy sensor creation after power sensors are registered
    # This ensures the source entity IDs exist in HA's entity registry
    if power_sensors_info:
        async def create_calculated_energy_sensors(_now):
            """Create calculated energy sensors after power sensors are registered."""
            calculated_entities = []
            
            # Get entity registry
            entity_reg = er.async_get(hass)
            
            for unique_id_suffix, sensor_name, dps_id in power_sensors_info:
                # Find the actual entity_id from the entity registry using unique_id
                full_unique_id = f"{device.unique_id}_{unique_id_suffix}"
                source_entity_id = entity_reg.async_get_entity_id(
                    "sensor", DOMAIN, full_unique_id
                )
                
                if source_entity_id:
                    # Create unique suffix for each calculated energy sensor
                    sensor_suffix = f"calculated_energy_{dps_id}"
                    
                    calculated_energy = CalculatedEnergySensor(
                        hass=hass,
                        source_entity_id=source_entity_id,
                        device_unique_id=device.unique_id,
                        device_name=device.name,
                        name=sensor_name,
                        precision=3,
                        method="left",  # Left Riemann sum is recommended for HA
                        sensor_suffix=sensor_suffix,
                    )
                    calculated_entities.append(calculated_energy)
                    _LOGGER.info(
                        "Created calculated energy sensor for power sensor %s (source: %s)",
                        sensor_name,
                        source_entity_id,
                    )
                else:
                    _LOGGER.warning(
                        "Could not find entity_id for power sensor %s with unique_id %s",
                        sensor_name,
                        full_unique_id,
                    )
            
            if calculated_entities:
                async_add_entities(calculated_entities, True)
        
        # Delay creation by 2 seconds to ensure power sensors are registered
        async_call_later(hass, 2.0, create_calculated_energy_sensors)


class TuyaLocalProSensor(TuyaLocalSensorEntity, SensorEntity):
    """Representation of a Tuya Local Pro Sensor."""

    def __init__(self, device, config):
        """Initialize the sensor."""
        super().__init__(device, config)
