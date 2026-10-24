"""Ouman EH-800 USB integration.

The experimental restore service is available only with explicit YAML opt-in.
Normal sensor/number YAML integrations are unchanged.
"""
from __future__ import annotations

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .restore import async_setup_restore

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Required("port"): cv.string,
        vol.Optional("enable_manual_restore", default=False): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config) -> bool:
    """Only register the destructive restore service when explicitly enabled."""
    settings = config.get(DOMAIN) or {}
    if settings.get("enable_manual_restore", False):
        await async_setup_restore(hass, settings["port"])
    return True
