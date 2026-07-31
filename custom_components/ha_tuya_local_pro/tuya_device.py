"""
Tuya Local Device API wrapper.

This module provides a local-first interface for communicating with Tuya WiFi
devices using the tinytuya library. It handles protocol negotiation, persistent
connections, state caching, and retry logic.
"""

import asyncio
import logging
from threading import Lock
from time import time

import tinytuya
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    API_PROTOCOL_VERSIONS,
    CONF_DEVICE_CID,
    CONF_DEVICE_ID,
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Extra context for tinytuya error codes
_ERROR_HINTS = {
    "914": "  If previously running OK, likely the device needs to be power cycled.",
}


class TuyaLocalDevice:
    """Represents a Tuya-based device with local communication."""

    def __init__(
        self,
        name: str,
        dev_id: str,
        address: str,
        local_key: str,
        protocol_version,
        dev_cid: str | None,
        hass: HomeAssistant,
        poll_only: bool = False,
    ):
        """
        Initialize a TuyaLocalDevice.

        Args:
            name: Friendly name for the device.
            dev_id: The Tuya device ID.
            address: The IP address of the device.
            local_key: The local encryption key for the device.
            protocol_version: Protocol version (float or "auto").
            dev_cid: Sub-device CID for Zigbee devices.
            hass: The Home Assistant instance.
            poll_only: If True, only poll for updates (no persistent connection).
        """
        self._name = name
        self._running = False
        self._shutdown_listener = None
        self._startup_listener = None
        self._api_protocol_version_index = None
        self._api_protocol_working = False
        self._api_working_protocol_failures = 0
        self.dev_cid = dev_cid

        # Set up the tinytuya API connection
        try:
            if dev_cid:
                # Sub-device (Zigbee gateway child)
                if hass.data.get(DOMAIN, {}).get(dev_id) and name != "Test":
                    parent = hass.data[DOMAIN][dev_id]["tuyadevice"]
                    parent_lock = hass.data[DOMAIN][dev_id].get(
                        "tuyadevicelock", asyncio.Lock()
                    )
                else:
                    parent = tinytuya.Device(dev_id, address, local_key)
                    parent_lock = asyncio.Lock()
                    if name != "Test":
                        hass.data.setdefault(DOMAIN, {})[dev_id] = {
                            "tuyadevice": parent,
                            "tuyadevicelock": parent_lock,
                        }
                self._api = tinytuya.Device(dev_cid, cid=dev_cid, parent=parent)
                self._api_lock = parent_lock
            else:
                # Direct WiFi device
                if hass.data.get(DOMAIN, {}).get(dev_id) and name != "Test":
                    self._api = hass.data[DOMAIN][dev_id]["tuyadevice"]
                    self._api_lock = hass.data[DOMAIN][dev_id].get(
                        "tuyadevicelock", asyncio.Lock()
                    )
                else:
                    self._api = tinytuya.Device(dev_id, address, local_key)
                    self._api_lock = asyncio.Lock()
                    if name != "Test":
                        hass.data.setdefault(DOMAIN, {})[dev_id] = {
                            "tuyadevice": self._api,
                            "tuyadevicelock": self._api_lock,
                        }
        except Exception as e:
            _LOGGER.error(
                "%s: %s while initialising device %s",
                type(e).__name__,
                e,
                dev_id,
            )
            raise

        # Limit retries at this level so we can rotate protocol versions
        self._api.set_socketRetryLimit(1)
        if self._api.parent:
            self._api.parent.set_socketRetryLimit(1)

        self._refresh_task = None
        self._protocol_configured = protocol_version
        self._poll_only = poll_only
        self._temporary_poll = False
        self._reset_cached_state()

        self._hass = hass

        # Timeout constants
        self._FAKE_IT_TIMEOUT = 5
        self._CACHE_TIMEOUT = 30
        self._HEARTBEAT_INTERVAL = 5
        self._AUTO_CONNECTION_ATTEMPTS = len(API_PROTOCOL_VERSIONS) * 2 + 1
        self._SINGLE_PROTO_CONNECTION_ATTEMPTS = 3
        self._AUTO_FAILURE_RESET_COUNT = 10
        self._lock = Lock()

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id for this device (the dev_id or dev_cid)."""
        return self.dev_cid or self._api.id

    @property
    def device_info(self):
        """Return the device information for this device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Tuya",
        }

    @property
    def has_returned_state(self):
        """Return True if the device has returned some state."""
        cached = self._get_cached_state()
        return len(cached) > 1 or cached.get("updated_at", 0) > 0

    @callback
    def actually_start(self, event=None):
        """Start the monitoring loop."""
        _LOGGER.debug("Starting monitor loop for %s", self.name)
        self._running = True
        self._shutdown_listener = self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.async_stop
        )
        if not self._refresh_task:
            self._refresh_task = self._hass.async_create_task(self.receive_loop())

    def start(self):
        """Start the device communication."""
        if self._hass.is_stopping:
            return
        elif self._hass.is_running:
            if self._startup_listener:
                self._startup_listener()
                self._startup_listener = None
            self.actually_start()
        else:
            self._startup_listener = self._hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self.actually_start
            )

    async def async_stop(self, event=None):
        """Stop the monitoring loop."""
        _LOGGER.debug("Stopping monitor loop for %s", self.name)
        self._running = False
        if self._refresh_task:
            self._api.set_socketPersistent(False)
            if self._api.parent:
                self._api.parent.set_socketPersistent(False)
            await self._refresh_task
        _LOGGER.debug("Monitor loop for %s stopped", self.name)
        self._refresh_task = None

    @property
    def should_poll(self):
        """Return True if the device should be polled instead of push."""
        return self._poll_only or self._temporary_poll or not self.has_returned_state

    async def async_refresh(self):
        """Refresh the device state."""
        _LOGGER.debug("Refreshing device state for %s", self.name)
        if not self._running:
            await self._retry_on_failed_connection(
                lambda: self._refresh_cached_state(),
                f"Failed to refresh device state for {self.name}.",
            )

    def get_property(self, dps_id):
        """Get a cached property value by DPS ID."""
        cached_state = self._get_cached_state()
        return cached_state.get(dps_id)

    def get_cached_state(self):
        """Get the cached state exposed to entities and diagnostics."""
        return self._get_cached_state().copy()

    async def async_set_property(self, dps_id, value):
        """Set a single DPS property."""
        await self.async_set_properties({dps_id: value})

    async def async_set_properties(self, properties):
        """Set multiple DPS properties."""
        if not properties:
            return
        self._add_properties_to_pending_updates(properties)
        await self._debounce_sending_updates()

    def _reset_cached_state(self):
        """Reset all cached state."""
        self._cached_state = {"updated_at": 0}
        self._pending_updates = {}
        self._last_connection = 0
        self._last_full_poll = 0

    def _get_cached_state(self):
        """Get cached state with pending updates overlaid."""
        cached_state = self._cached_state.copy()
        return {**cached_state, **self._get_pending_properties()}

    def _refresh_cached_state(self):
        """Synchronously refresh the device state from the device."""
        new_state = self._api.status()
        if new_state:
            if "Err" not in new_state:
                self._cached_state = self._cached_state | new_state.get("dps", {})
                self._cached_state["updated_at"] = time()
            elif self._api_working_protocol_failures == 1:
                _LOGGER.warning(
                    "%s protocol error %s: %s",
                    self.name,
                    new_state.get("Err"),
                    new_state.get("Error", "message not provided"),
                )
            else:
                _LOGGER.debug(
                    "%s protocol error %s: %s",
                    self.name,
                    new_state.get("Err"),
                    new_state.get("Error", "message not provided"),
                )
        return new_state

    async def receive_loop(self):
        """Coroutine wrapper for async_receive generator."""
        try:
            async for poll in self.async_receive():
                if isinstance(poll, dict):
                    _LOGGER.debug("%s received %s", self.name, poll)
                    full_poll = poll.pop("full_poll", False)
                    self._cached_state = self._cached_state | poll
                    self._cached_state["updated_at"] = time()

                    # Dispatch updates to listening entities
                    for callback_fn in getattr(self, "_update_callbacks", []):
                        try:
                            callback_fn(poll, full_poll)
                        except Exception as e:
                            _LOGGER.exception(
                                "%s callback error: %s", self.name, e
                            )
            _LOGGER.warning("%s receive loop has terminated", self.name)
        except Exception as t:
            _LOGGER.exception(
                "%s receive loop terminated by exception %s", self.name, t
            )
            self._api.set_socketPersistent(False)
            if self._api.parent:
                self._api.parent.set_socketPersistent(False)

    async def async_receive(self):
        """Receive messages from a persistent connection asynchronously."""
        persist = not self.should_poll
        dps_updated = False

        self._api.set_socketPersistent(persist)
        if self._api.parent:
            self._api.parent.set_socketPersistent(persist)

        last_heartbeat = self._cached_state.get("updated_at", 0)
        self._update_callbacks = []

        while self._running:
            error_count = self._api_working_protocol_failures
            force_backoff = False
            try:
                await self._api_lock.acquire()
                last_cache = self._cached_state.get("updated_at", 0)
                now = time()
                full_poll = False

                if persist == self.should_poll:
                    persist = not self.should_poll
                    self._api.set_socketPersistent(persist)
                    if self._api.parent:
                        self._api.parent.set_socketPersistent(persist)
                    self._last_full_poll = 0

                needs_full_poll = now - self._last_full_poll > self._CACHE_TIMEOUT
                if now - last_cache > self._CACHE_TIMEOUT or (
                    persist and needs_full_poll
                ):
                    poll = await self._retry_on_failed_connection(
                        lambda: self._api.status(),
                        f"Failed to fetch device status for {self.name}",
                    )
                    dps_updated = False
                    full_poll = True
                    self._last_full_poll = now
                    last_heartbeat = now
                elif persist:
                    if now - last_heartbeat > self._HEARTBEAT_INTERVAL:
                        await self._hass.async_add_executor_job(
                            self._api.heartbeat, True
                        )
                        last_heartbeat = now
                    poll = await self._hass.async_add_executor_job(
                        self._api.receive
                    )
                    if poll and "Err" in poll and poll["Err"] == "904":
                        poll = None
                else:
                    force_backoff = True
                    poll = None

                if poll:
                    if "Error" in poll:
                        if error_count == self._api_working_protocol_failures:
                            self._api_working_protocol_failures += 1
                        if self._api_working_protocol_failures == 1:
                            _LOGGER.warning(
                                "%s error reading: %s", self.name, poll["Error"]
                            )
                    else:
                        if "dps" in poll:
                            poll = poll["dps"]
                        if isinstance(poll, dict):
                            poll["full_poll"] = full_poll
                            yield poll

            except asyncio.CancelledError:
                self._running = False
                persist = False
                self._api.set_socketPersistent(False)
                if self._api.parent:
                    self._api.parent.set_socketPersistent(False)
                raise
            except Exception as t:
                _LOGGER.exception(
                    "%s receive loop error %s:%s",
                    self.name,
                    type(t).__name__,
                    t,
                )
                persist = False
                self._api.set_socketPersistent(False)
                if self._api.parent:
                    self._api.parent.set_socketPersistent(False)
                force_backoff = True
            finally:
                if self._api_lock.locked():
                    self._api_lock.release()

            if not self.has_returned_state:
                force_backoff = True
            await asyncio.sleep(5 if force_backoff else 0.1)

        self._api.set_socketPersistent(False)
        if self._api.parent:
            self._api.parent.set_socketPersistent(False)

    async def _retry_on_failed_connection(self, func, error_message):
        """Retry a function call with protocol rotation on failure."""
        if self._api_protocol_version_index is None:
            await self._rotate_api_protocol_version()

        auto = (self._protocol_configured == "auto") and (
            not self._api_protocol_working
        )
        connections = (
            self._AUTO_CONNECTION_ATTEMPTS
            if auto
            else self._SINGLE_PROTO_CONNECTION_ATTEMPTS
        )

        last_err_code = None
        last_err_msg = None
        for i in range(connections):
            try:
                if not self._hass.is_stopping:
                    retval = await self._hass.async_add_executor_job(func)
                    if isinstance(retval, dict) and "Error" in retval:
                        last_err_code = retval.get("Err")
                        last_err_msg = retval.get("Error")
                        if last_err_code == "900":
                            self._cached_state["updated_at"] = time()
                            retval = None
                        else:
                            raise AttributeError(retval["Error"])
                    self._api_protocol_working = True
                    self._api_working_protocol_failures = 0
                    return retval
            except Exception as e:
                _LOGGER.debug(
                    "Retrying after exception %s %s (%d/%d)",
                    type(e).__name__,
                    e,
                    i,
                    connections,
                )
                self._api.set_socketPersistent(False)
                if self._api.parent:
                    self._api.parent.set_socketPersistent(False)

                if i + 1 == connections:
                    self._reset_cached_state()
                    self._api_working_protocol_failures += 1
                    if (
                        self._api_working_protocol_failures
                        > self._AUTO_FAILURE_RESET_COUNT
                    ):
                        self._api_protocol_working = False

                    if last_err_code:
                        log_format = "%s Device reported error %s: %s%s"
                        log_args = (
                            error_message,
                            last_err_code,
                            last_err_msg,
                            _ERROR_HINTS.get(last_err_code, ""),
                        )
                    else:
                        log_format = "%s"
                        log_args = (error_message,)

                    if self._api_working_protocol_failures == 1:
                        _LOGGER.error(log_format, *log_args)
                    else:
                        _LOGGER.debug(log_format, *log_args)

                if not self._api_protocol_working:
                    await self._rotate_api_protocol_version()

    async def _rotate_api_protocol_version(self):
        """Rotate through protocol versions on failure."""
        if self._api_protocol_version_index is None:
            try:
                self._api_protocol_version_index = API_PROTOCOL_VERSIONS.index(
                    self._protocol_configured
                )
            except ValueError:
                self._api_protocol_version_index = 0
        elif self._protocol_configured == "auto":
            self._api_protocol_version_index += 1

        if self._api_protocol_version_index >= len(API_PROTOCOL_VERSIONS):
            self._api_protocol_version_index = 0

        new_version = API_PROTOCOL_VERSIONS[self._api_protocol_version_index]
        _LOGGER.debug(
            "Setting protocol version for %s to %s",
            self.name,
            new_version,
        )

        # Handle device22 protocol variants
        if new_version in (3.22, 3.42, 3.52):
            new_version = {3.22: 3.3, 3.42: 3.4, 3.52: 3.5}[new_version]
            self._api.disabledetect = False
        else:
            self._api.disabledetect = True

        await self._hass.async_add_executor_job(self._api.set_version, new_version)
        if self._api.parent:
            await self._hass.async_add_executor_job(
                self._api.parent.set_version, new_version
            )

    def _add_properties_to_pending_updates(self, properties):
        """Add properties to the pending updates queue."""
        now = time()
        for key, value in properties.items():
            self._pending_updates[key] = {
                "value": value,
                "updated_at": now,
                "sent": False,
            }

    def _get_pending_properties(self):
        """Get pending property values."""
        return {key: prop["value"] for key, prop in self._pending_updates.items()}

    def _get_unsent_properties(self):
        """Get properties that haven't been sent yet."""
        return {
            key: info["value"]
            for key, info in self._pending_updates.items()
            if not info["sent"]
        }

    async def _debounce_sending_updates(self):
        """Debounce sending updates to avoid flooding the device."""
        now = time()
        since = now - self._last_connection
        self._last_connection = now
        waittime = 1 if since < 1.1 and self.should_poll else 0.001
        await asyncio.sleep(waittime)
        await self._send_pending_updates()

    async def _send_pending_updates(self):
        """Send pending updates to the device."""
        pending_properties = self._get_unsent_properties()
        if pending_properties:
            await self._retry_on_failed_connection(
                lambda: self._set_values(pending_properties),
                "Failed to update device state.",
            )

    def _set_values(self, properties):
        """Synchronously set multiple DPS values."""
        try:
            self._lock.acquire()
            self._api.set_multiple_values(properties, nowait=True)
            now = time()
            self._last_connection = now
            for key in properties.keys():
                if key in self._pending_updates:
                    self._pending_updates[key]["updated_at"] = now
                    self._pending_updates[key]["sent"] = True
        finally:
            self._lock.release()

    def register_update_callback(self, callback_fn):
        """Register a callback for state updates."""
        if not hasattr(self, "_update_callbacks"):
            self._update_callbacks = []
        self._update_callbacks.append(callback_fn)

    def unregister_update_callback(self, callback_fn):
        """Unregister a state update callback."""
        if hasattr(self, "_update_callbacks"):
            self._update_callbacks = [
                cb for cb in self._update_callbacks if cb != callback_fn
            ]


def setup_device(hass: HomeAssistant, config: dict):
    """Set up a Tuya device based on passed in config."""
    from .helpers import get_device_id

    device_id = get_device_id(config)
    _LOGGER.info("Creating device: %s", device_id)
    hass.data.setdefault(DOMAIN, {})

    device = TuyaLocalDevice(
        config[CONF_NAME],
        config[CONF_DEVICE_ID],
        config[CONF_HOST],
        config[CONF_LOCAL_KEY],
        config[CONF_PROTOCOL_VERSION],
        config.get(CONF_DEVICE_CID),
        hass,
        config.get("poll_only", False),
    )
    hass.data[DOMAIN][device_id] = {
        "device": device,
        "tuyadevice": device._api,
        "tuyadevicelock": device._api_lock,
    }

    return device


async def async_delete_device(hass: HomeAssistant, config: dict):
    """Delete a device and clean up resources."""
    from .helpers import get_device_id

    device_id = get_device_id(config)
    _LOGGER.info("Deleting device: %s", device_id)
    domain_data = hass.data.get(DOMAIN, {})
    device_entry = domain_data.get(device_id)
    if device_entry is None:
        return

    device = device_entry.get("device")
    if device is not None:
        await device.async_stop()
        device_entry.pop("device", None)
    device_entry.pop("tuyadevice", None)
    device_entry.pop("tuyadevicelock", None)
    if not device_entry:
        domain_data.pop(device_id, None)
