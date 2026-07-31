"""Config flow for Tuya Local Pro integration."""

import asyncio
import logging
from collections import OrderedDict
from typing import Any

import tinytuya
import voluptuous as vol
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_PUSH,
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    API_PROTOCOL_VERSIONS,
    CONF_DEVICE_CID,
    CONF_DEVICE_ID,
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
    DOMAIN,
)
from .tuya_device import TuyaLocalDevice

_LOGGER = logging.getLogger(__name__)


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya Local Pro."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH
    device = None
    data = {}

    def __init__(self) -> None:
        """Initialize the config flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if self.hass.data.get(DOMAIN) is None:
            self.hass.data[DOMAIN] = {}

        if user_input is not None:
            mode = user_input.get("setup_mode")
            if mode == "manual":
                return await self.async_step_local()

        # Build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Required("setup_mode")] = SelectSelector(
            SelectSelectorConfig(
                options=["manual"],
                mode=SelectSelectorMode.LIST,
                translation_key="setup_mode",
            )
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(fields),
            errors=errors or {},
            last_step=False,
        )

    async def async_step_local(self, user_input=None):
        """Handle manual device setup."""
        errors = {}
        devid_opts = {}
        host_opts = {"default": ""}
        key_opts = {}
        proto_opts = {"default": "auto"}

        if user_input is not None:
            proto = user_input.get(CONF_PROTOCOL_VERSION)
            if proto != "auto":
                user_input[CONF_PROTOCOL_VERSION] = float(proto)
            else:
                user_input[CONF_PROTOCOL_VERSION] = "auto"

            # Test the connection
            self.device = await _async_test_connection(user_input, self.hass)
            if self.device:
                self.data = user_input
                await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured()
                return await self.async_step_name()
            else:
                errors["base"] = "connection"
                devid_opts["default"] = user_input[CONF_DEVICE_ID]
                host_opts["default"] = user_input[CONF_HOST]
                key_opts["default"] = user_input[CONF_LOCAL_KEY]
                proto_opts["default"] = str(user_input[CONF_PROTOCOL_VERSION])

        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID, **devid_opts): str,
                    vol.Required(CONF_HOST, **host_opts): str,
                    vol.Required(CONF_LOCAL_KEY, **key_opts): str,
                    vol.Required(
                        CONF_PROTOCOL_VERSION,
                        **proto_opts,
                    ): vol.In(
                        ["auto"] + [str(v) for v in API_PROTOCOL_VERSIONS]
                    ),
                    vol.Optional(CONF_DEVICE_CID, default=""): str,
                }
            ),
            description_placeholders={},
            errors=errors,
        )

    async def async_step_name(self, user_input=None):
        """Step to set the device name."""
        if user_input is not None:
            title = user_input[CONF_NAME]
            del user_input[CONF_NAME]
            return self.async_create_entry(
                title=title, data={**self.data, **user_input}
            )

        default_name = self.data.get(CONF_DEVICE_ID, "Tuya Device")
        schema = {vol.Required(CONF_NAME, default=default_name): str}

        return self.async_show_form(
            step_id="name",
            data_schema=vol.Schema(schema),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle options for Tuya Local Pro."""

    def __init__(self):
        """Initialize options flow."""
        pass

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Manage the options."""
        errors = {}
        config = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            proto = user_input.get(CONF_PROTOCOL_VERSION)
            if proto != "auto":
                user_input[CONF_PROTOCOL_VERSION] = float(proto)
            else:
                user_input[CONF_PROTOCOL_VERSION] = "auto"

            config = {**config, **user_input}
            device = await _async_test_connection(config, self.hass)
            if device:
                return self.async_create_entry(title="", data=user_input)
            else:
                errors["base"] = "connection"

        schema = {
            vol.Required(
                CONF_LOCAL_KEY,
                default=config.get(CONF_LOCAL_KEY, ""),
            ): str,
            vol.Required(CONF_HOST, default=config.get(CONF_HOST, "")): str,
            vol.Required(
                CONF_PROTOCOL_VERSION,
                default=str(config.get(CONF_PROTOCOL_VERSION, "auto")),
            ): vol.In(["auto"] + [str(v) for v in API_PROTOCOL_VERSIONS]),
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors,
        )


def _create_test_device(hass: HomeAssistant, config: dict):
    """Set up a test Tuya device based on passed in config."""
    subdevice_id = config.get(CONF_DEVICE_CID)
    device = TuyaLocalDevice(
        "Test",
        config[CONF_DEVICE_ID],
        config[CONF_HOST],
        config[CONF_LOCAL_KEY],
        config[CONF_PROTOCOL_VERSION],
        subdevice_id,
        hass,
        True,
    )
    return device


async def _async_test_connection(config: dict, hass: HomeAssistant):
    """Test the connection to a Tuya device."""
    if config.get(CONF_PROTOCOL_VERSION) == "auto":
        # Test each protocol
        for proto in API_PROTOCOL_VERSIONS:
            proto_config = {**config, CONF_PROTOCOL_VERSION: proto}
            device = None
            try:
                device = await hass.async_add_executor_job(
                    _create_test_device, hass, proto_config
                )
                await device.async_refresh()
                if device.has_returned_state:
                    return device
            except Exception as e:
                _LOGGER.debug("Protocol %s test failed with %s %s", proto, type(e), e)
            if device is not None:
                device._api.set_socketPersistent(False)
                if device._api.parent:
                    device._api.parent.set_socketPersistent(False)
    else:
        try:
            device = await hass.async_add_executor_job(
                _create_test_device, hass, config
            )
            await device.async_refresh()
            return device if device.has_returned_state else None
        except Exception as e:
            _LOGGER.warning("Connection test failed with %s %s", type(e), e)

    return None
