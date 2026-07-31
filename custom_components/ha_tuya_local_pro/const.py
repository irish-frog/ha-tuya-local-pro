"""Constants for ha_tuya_local_pro integration."""

DOMAIN = "ha_tuya_local_pro"

# Configuration keys
CONF_DEVICE_ID = "device_id"
CONF_LOCAL_KEY = "local_key"
CONF_HOST = "host"
CONF_PROTOCOL_VERSION = "protocol_version"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_POLL_ONLY = "poll_only"
CONF_DEVICE_CID = "device_cid"
CONF_DEVICE_NAME = "device_name"

# DPS mapping configuration keys (MVP 2)
CONF_DPS_MAPPINGS = "dps_mappings"
CONF_DPS_ID = "dps_id"
CONF_DPS_TYPE = "dps_type"
CONF_DPS_NAME = "dps_name"
CONF_DPS_ENTITY_TYPE = "dps_entity_type"
CONF_DPS_SCALE = "dps_scale"
CONF_DPS_OFFSET = "dps_offset"
CONF_DPS_UNIT = "dps_unit"
CONF_DPS_DEVICE_CLASS = "dps_device_class"
CONF_DPS_STATE_CLASS = "dps_state_class"
CONF_DPS_ICON = "dps_icon"
CONF_DPS_MIN_VALUE = "dps_min_value"
CONF_DPS_MAX_VALUE = "dps_max_value"

# API protocol versions supported
API_PROTOCOL_VERSIONS = [3.1, 3.2, 3.3, 3.4, 3.5, 3.22, 3.42, 3.52]

# Default protocol version
DEFAULT_PROTOCOL_VERSION = "auto"

# Platform list
PLATFORMS = [
    "binary_sensor",
    "sensor",
    "switch",
]

# DPS types
DPS_TYPE_BOOLEAN = "boolean"
DPS_TYPE_INTEGER = "integer"
DPS_TYPE_STRING = "string"
DPS_TYPE_BASE64 = "base64"
DPS_TYPE_JSON = "json"

# Entity types for DPS mapping
ENTITY_TYPE_SENSOR = "sensor"
ENTITY_TYPE_SWITCH = "switch"
ENTITY_TYPE_BINARY_SENSOR = "binary_sensor"
ENTITY_TYPES = [
    ENTITY_TYPE_SENSOR,
    ENTITY_TYPE_SWITCH,
    ENTITY_TYPE_BINARY_SENSOR,
]

# Device classes for sensors
SENSOR_DEVICE_CLASS_POWER = "power"
SENSOR_DEVICE_CLASS_ENERGY = "energy"
SENSOR_DEVICE_CLASS_CURRENT = "current"
SENSOR_DEVICE_CLASS_VOLTAGE = "voltage"
SENSOR_DEVICE_CLASS_TEMPERATURE = "temperature"
SENSOR_DEVICE_CLASS_HUMIDITY = "humidity"

# State classes for sensors
STATE_CLASS_MEASUREMENT = "measurement"
STATE_CLASS_TOTAL_INCREASING = "total_increasing"

# Data store key
DATA_STORE = "store"

# Cloud authentication
TUYA_CLIENT_ID = "HA_3y9q4ak7g4ephrvke"
TUYA_SCHEMA = "haauthorize"

# Response codes
TUYA_RESPONSE_CODE = "code"
TUYA_RESPONSE_MSG = "msg"
TUYA_RESPONSE_QR_CODE = "qrcode"
TUYA_RESPONSE_RESULT = "result"
TUYA_RESPONSE_SUCCESS = "success"

# WebSocket API endpoints
WS_API_DPS_STREAM = "ha_tuya_local_pro/dps_stream"
WS_API_DPS_MAPPING_SAVE = "ha_tuya_local_pro/dps_mapping_save"
WS_API_DPS_MAPPING_LOAD = "ha_tuya_local_pro/dps_mapping_load"
WS_API_PROFILE_EXPORT = "ha_tuya_local_pro/profile_export"
WS_API_PROFILE_IMPORT = "ha_tuya_local_pro/profile_import"
