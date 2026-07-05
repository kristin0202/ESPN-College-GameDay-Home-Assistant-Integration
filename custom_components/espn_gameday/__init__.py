"""ESPN College GameDay integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_CLEAR_OVERRIDES,
    SERVICE_SET_LOCATION,
    SERVICE_SET_PICKER,
    SERVICE_SET_PICKS,
)
from .coordinator import GameDayCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SET_LOCATION_SCHEMA = vol.Schema(
    {
        vol.Required("school"): cv.string,
        vol.Optional("source_url", default=""): cv.string,
    }
)
SET_PICKER_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Optional("source_url", default=""): cv.string,
    }
)
SET_PICKS_SCHEMA = vol.Schema(
    {
        vol.Required("picks"): {cv.string: cv.string},
        vol.Optional("source_url", default=""): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = GameDayCoordinator(hass, entry)
    await coordinator.async_load_store()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok


def _coordinator(hass: HomeAssistant) -> GameDayCoordinator:
    return next(iter(hass.data[DOMAIN].values()))


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SET_LOCATION):
        return

    async def set_location(call: ServiceCall) -> None:
        await _coordinator(hass).async_set_override(
            "location",
            {"school": call.data["school"], "source_url": call.data["source_url"]},
        )

    async def set_picker(call: ServiceCall) -> None:
        await _coordinator(hass).async_set_override(
            "picker",
            {"name": call.data["name"], "source_url": call.data["source_url"]},
        )

    async def set_picks(call: ServiceCall) -> None:
        await _coordinator(hass).async_set_override(
            "picks",
            {"picks": call.data["picks"], "source_url": call.data["source_url"]},
        )

    async def clear_overrides(call: ServiceCall) -> None:
        await _coordinator(hass).async_clear_overrides()

    hass.services.async_register(
        DOMAIN, SERVICE_SET_LOCATION, set_location, schema=SET_LOCATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PICKER, set_picker, schema=SET_PICKER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PICKS, set_picks, schema=SET_PICKS_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_OVERRIDES, clear_overrides)
