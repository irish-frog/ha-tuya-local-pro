# ha-tuya-local-pro

A **local-first** Home Assistant custom integration for Tuya and Smart Life Wi-Fi devices.

## Philosophy

This integration communicates **directly with your devices over your local network**. Cloud access is optional and used only for onboarding — never for daily operation. Your devices work even when the internet is down.

## Features

- **Local-first communication** — no cloud dependency for control
- **Manual device setup** — enter device ID, IP, local key, and protocol
- **Auto-DPS detection** — sensors and switches are auto-detected from device state
- **Calculated kWh sensors** — reliable energy dashboard-compatible sensors
- **Profile export/import** — share device configurations as JSON
- **Multiple protocol versions** — supports Tuya protocols 3.1 through 3.5
- **Auto protocol detection** — tries all protocol versions automatically

## Must-Not Requirements

This integration must **never**:

1. Require daily Tuya Cloud API calls
2. Require an active Tuya Developer trial after setup
3. Require cloud access for normal control
4. Break if the internet is down
5. Overwrite local mappings without user approval
6. Expose local keys in logs or diagnostics

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Search for "Tuya Local Pro"
4. Click "Download"
5. Restart Home Assistant

### Manual

1. Clone or download this repository
2. Copy the `custom_components/ha_tuya_local_pro` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Setup

### Manual Setup (MVP 1)

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "Tuya Local Pro"
3. Select "Manual Setup"
4. Enter your device details:
   - **Device ID**: Found in the Tuya IoT Platform or via tinytuya scan
   - **IP Address**: The local IP of your device
   - **Local Key**: The encryption key for local communication
   - **Protocol Version**: Select "auto" to auto-detect, or specify your device's version
5. Give your device a friendly name
6. The integration will create switch and sensor entities based on your device's DPS

### Finding Your Device ID and Local Key

#### Option 1: Tuya IoT Platform
1. Log in to [iot.tuya.com](https://iot.tuya.com/)
2. Go to your project → Devices
3. Find your device and note the Device ID and Local Key

#### Option 2: tinytuya CLI
```bash
pip install tinytuya
python -m tinytuya scan
```

## Supported Entities

### Auto-Detected DPS Mappings

| DPS | Entity Type | Description |
|-----|-------------|-------------|
| 1 | switch | Main on/off switch |
| 1 | sensor | Total energy (kWh) |
| 4/6 | binary_sensor | Fault indicator |
| 7 | switch | Child lock |
| 18 | sensor | Current (A) |
| 19 | sensor | Power (W) |
| 20 | sensor | Voltage (V) |
| 102 | switch | Overcharge switch |

## First Target Device

### Generic Tuya DIN Rail Breaker / Energy Monitor

- **Protocol**: 3.5
- **Entities**:
  - Switch (DP 1)
  - Power W (DP 19)
  - Current A (DP 18)
  - Voltage V (DP 20)
  - Total Energy kWh (DP 1)
  - Child Lock (DP 7)
  - Fault (DP 4)
  - Overcharge Switch (DP 102)

## Troubleshooting

### Device Not Connecting

1. Verify the device is on the same network as Home Assistant
2. Check that the local key is correct
3. Try different protocol versions or use "auto"
4. Ensure the device isn't being used by the Tuya app simultaneously

### Error 914

If you see error 914, the device may need to be power cycled. Unplug it for 30 seconds, then plug it back in.

### Error 900

Some devices (IR/RF remotes) never return status data. Error 900 is normal for these devices.

## Development

### Architecture

```
ha_tuya_local_pro/
├── __init__.py          # Integration setup and lifecycle
├── manifest.json        # HA integration metadata
├── const.py            # Constants and configuration keys
├── config_flow.py      # Manual and cloud-assisted setup
├── tuya_device.py      # Local Tuya protocol wrapper
├── entity.py           # Base entity classes
├── switch.py           # Switch platform
├── sensor.py           # Sensor platform
├── devices/            # Device profiles (YAML)
├── helpers/            # Configuration helpers
└── translations/       # UI strings
```

### Adding a New Device Profile

1. Create a YAML file in `devices/` with the device's DPS mappings
2. Define the entity types and their configuration
3. The integration will use these profiles for entity setup

## License

MIT License
