"""Helpers for Tuya Local Pro integration."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def get_device_id(config: dict) -> str:
    """Get the device ID from config."""
    return config.get("device_id", "unknown")


def load_device_profiles(hass: HomeAssistant) -> dict[str, dict]:
    """Load all device profiles from the devices directory.
    
    Returns a dictionary mapping device profile names to their configurations.
    """
    profiles = {}
    
    # Get the directory containing this module
    module_dir = Path(__file__).parent.parent
    devices_dir = module_dir / "devices"
    
    if not devices_dir.exists():
        _LOGGER.debug("Devices directory not found: %s", devices_dir)
        return profiles
    
    try:
        import yaml
    except ImportError:
        _LOGGER.warning("PyYAML not available, cannot load device profiles")
        return profiles
    
    for yaml_file in devices_dir.glob("*.yaml"):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                profile = yaml.safe_load(f)
                if profile and isinstance(profile, dict):
                    profile_name = yaml_file.stem
                    profiles[profile_name] = profile
                    _LOGGER.debug("Loaded device profile: %s", profile_name)
        except Exception as e:
            _LOGGER.warning("Failed to load profile %s: %s", yaml_file.name, e)
    
    _LOGGER.info("Loaded %d device profiles", len(profiles))
    return profiles


def find_matching_profile(
    profiles: dict[str, dict],
    cached_state: dict,
    threshold: float = 0.5,
) -> Optional[tuple[str, dict]]:
    """Find a matching device profile based on cached DPS state.
    
    Args:
        profiles: Dictionary of loaded profiles.
        cached_state: Current cached state from the device.
        threshold: Minimum match ratio (0.0 to 1.0) to consider a profile matching.
    
    Returns:
        Tuple of (profile_name, profile_config) if found, None otherwise.
    """
    for profile_name, profile in profiles.items():
        # Collect all DPS IDs from the profile
        profile_dps_ids = set()
        for entity_def in profile.get("entities", []):
            for dps_def in entity_def.get("dps", []):
                if "id" in dps_def:
                    profile_dps_ids.add(str(dps_def["id"]))
        
        if not profile_dps_ids:
            continue
        
        # Check how many profile DPS IDs are present in cached state
        matching_count = len(profile_dps_ids.intersection(set(cached_state.keys())))
        match_ratio = matching_count / len(profile_dps_ids)
        
        if match_ratio >= threshold:
            _LOGGER.info(
                "Found matching profile '%s' (matched %d/%d DPS, ratio: %.2f)",
                profile_name,
                matching_count,
                len(profile_dps_ids),
                match_ratio,
            )
            return profile_name, profile
    
    return None


def profile_to_entity_configs(profile: dict) -> list[dict]:
    """Convert a device profile to entity configuration list.
    
    Args:
        profile: The device profile configuration.
    
    Returns:
        List of entity configurations suitable for creating HA entities.
    """
    entities = []
    
    for entity_def in profile.get("entities", []):
        entity_config = {
            "entity_type": entity_def.get("entity", "sensor"),
            "name": entity_def.get("name", "Unknown"),
            "icon": entity_def.get("icon"),
            "device_class": entity_def.get("class"),
        }
        
        # Parse DPS configurations
        for dps_def in entity_def.get("dps", []):
            dps_id = dps_def.get("id")
            if dps_id is not None:
                entity_config["dps_id"] = str(dps_id)
                entity_config["dps_type"] = dps_def.get("type", "integer")
                entity_config["scale"] = dps_def.get("scale", 1.0)
                entity_config["offset"] = dps_def.get("offset", 0.0)
                entity_config["unit"] = dps_def.get("unit")
                entity_config["state_class"] = dps_def.get("class")
                
                # Handle range for number entities
                if "range" in dps_def:
                    entity_config["min_value"] = dps_def["range"].get("min", 0)
                    entity_config["max_value"] = dps_def["range"].get("max", 100)
        
        entities.append(entity_config)
    
    return entities


def export_device_profile(
    device_id: str,
    device_name: str,
    dps_mappings: list[dict],
    device_info: Optional[dict] = None,
) -> dict:
    """Export device configuration to a portable profile dictionary.
    
    Args:
        device_id: The unique device ID.
        device_name: Friendly name for the device.
        dps_mappings: List of DPS mapping configurations.
        device_info: Optional device information (manufacturer, model, etc.).
    
    Returns:
        Dictionary containing the device profile in a portable format.
    """
    profile = {
        "profile_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "device": {
            "id": device_id,
            "name": device_name,
            "manufacturer": device_info.get("manufacturer", "Tuya") if device_info else "Tuya",
            "model": device_info.get("model", "Unknown") if device_info else "Unknown",
        },
        "entities": [],
    }
    
    # Convert DPS mappings to profile entity format
    for mapping in dps_mappings:
        entity = {
            "entity": mapping.get("entity_type", "sensor"),
            "name": mapping.get("name", f"DPS {mapping.get('dps_id', '?')}"),
            "icon": mapping.get("icon"),
            "class": mapping.get("device_class"),
            "dps": [],
        }
        
        # Add DPS configuration
        dps_config = {
            "id": int(mapping.get("dps_id", 0)),
            "type": mapping.get("dps_type", "integer"),
        }
        
        # Add optional fields
        if mapping.get("unit"):
            dps_config["unit"] = mapping["unit"]
        if mapping.get("state_class"):
            dps_config["class"] = mapping["state_class"]
        if mapping.get("scale") and mapping["scale"] != 1.0:
            dps_config["scale"] = mapping["scale"]
        if mapping.get("offset") and mapping["offset"] != 0.0:
            dps_config["offset"] = mapping["offset"]
        if mapping.get("on_value") is not None:
            dps_config["on_value"] = mapping["on_value"]
        if mapping.get("off_value") is not None:
            dps_config["off_value"] = mapping["off_value"]
        
        # Handle number entity range
        if mapping.get("entity_type") == "number":
            if "min_value" in mapping:
                dps_config["min_value"] = mapping["min_value"]
            if "max_value" in mapping:
                dps_config["max_value"] = mapping["max_value"]
        
        entity["dps"].append(dps_config)
        profile["entities"].append(entity)
    
    return profile


def import_device_profile(profile: dict) -> list[dict]:
    """Import a device profile and convert to DPS mappings.
    
    Args:
        profile: Device profile dictionary.
    
    Returns:
        List of DPS mapping configurations.
    """
    mappings = []
    
    for entity_def in profile.get("entities", []):
        entity_type = entity_def.get("entity", "sensor")
        
        for dps_def in entity_def.get("dps", []):
            dps_id = dps_def.get("id")
            if dps_id is None:
                continue
            
            mapping = {
                "dps_id": str(dps_id),
                "dps_type": dps_def.get("type", "integer"),
                "name": entity_def.get("name", f"DPS {dps_id}"),
                "entity_type": entity_type,
                "scale": float(dps_def.get("scale", 1.0)),
                "offset": float(dps_def.get("offset", 0.0)),
                "unit": dps_def.get("unit"),
                "device_class": entity_def.get("class"),
                "state_class": dps_def.get("class"),
                "icon": entity_def.get("icon"),
            }
            
            # Add switch-specific fields
            if entity_type == "switch":
                mapping["on_value"] = dps_def.get("on_value", True)
                mapping["off_value"] = dps_def.get("off_value", False)
            
            # Add number entity range fields
            if entity_type == "number":
                mapping["min_value"] = dps_def.get("min_value", 0)
                mapping["max_value"] = dps_def.get("max_value", 100)
            
            mappings.append(mapping)
    
    return mappings


def validate_profile(profile: dict) -> tuple[bool, str]:
    """Validate a device profile structure.
    
    Args:
        profile: Device profile dictionary to validate.
    
    Returns:
        Tuple of (is_valid, error_message).
    """
    if not isinstance(profile, dict):
        return False, "Profile must be a dictionary"
    
    # Check for required fields
    if "entities" not in profile:
        return False, "Profile must contain 'entities' field"
    
    if not isinstance(profile["entities"], list):
        return False, "'entities' must be a list"
    
    # Validate each entity
    for i, entity in enumerate(profile["entities"]):
        if "entity" not in entity:
            return False, f"Entity {i} missing 'entity' field"
        
        if "dps" not in entity:
            return False, f"Entity {i} missing 'dps' field"
        
        if not isinstance(entity["dps"], list):
            return False, f"Entity {i} 'dps' must be a list"
        
        for j, dps in enumerate(entity["dps"]):
            if "id" not in dps:
                return False, f"Entity {i} DPS {j} missing 'id' field"
    
    return True, "Valid"
