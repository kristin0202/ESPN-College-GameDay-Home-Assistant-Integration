"""Sensors for ESPN College GameDay."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GameDayCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: GameDayCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextShowSensor(coordinator),
            LocationSensor(coordinator),
            GuestPickerSensor(coordinator),
            FeaturedGameSensor(coordinator),
            FinalPicksSensor(coordinator),
            UpcomingSensor(coordinator),
        ]
    )


class GameDayEntity(CoordinatorEntity[GameDayCoordinator]):
    _attr_has_entity_name = False

    def __init__(self, coordinator: GameDayCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self.entity_id = f"sensor.gameday_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "espn_gameday")},
            name="ESPN College GameDay",
            manufacturer="ESPN (unofficial)",
        )

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data or {}


class NextShowSensor(GameDayEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:television-classic"

    def __init__(self, coordinator: GameDayCoordinator) -> None:
        super().__init__(coordinator, "next_show", "GameDay Next Show")

    @property
    def native_value(self) -> datetime | None:
        return self._data.get("next_show")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "phase": self._data.get("phase"),
            "season_year": self._data.get("season_year"),
            "week_number": self._data.get("week_number"),
            "show_end": _iso(self._data.get("show_end")),
            "fresh_until": self._data.get("fresh_until"),
        }


class LocationSensor(GameDayEntity, SensorEntity):
    _attr_icon = "mdi:map-marker-star"

    def __init__(self, coordinator: GameDayCoordinator) -> None:
        super().__init__(coordinator, "location", "GameDay Location")

    @property
    def native_value(self) -> str:
        location = self._data.get("location")
        return location.get("school", "TBA") if location else "TBA"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        location = self._data.get("location") or {}
        game = self._data.get("featured_game") or {}
        return {
            "week": location.get("week"),
            "venue": game.get("venue"),
            "city": game.get("city"),
            "state": game.get("state"),
            "announced_at": location.get("announced_at"),
            "source_url": location.get("source_url"),
            "confidence": location.get("confidence"),
            "method": location.get("method"),
        }


class GuestPickerSensor(GameDayEntity, SensorEntity):
    _attr_icon = "mdi:microphone-variant"

    def __init__(self, coordinator: GameDayCoordinator) -> None:
        super().__init__(coordinator, "guest_picker", "GameDay Guest Picker")

    @property
    def native_value(self) -> str:
        picker = self._data.get("picker")
        return picker.get("name", "TBA") if picker else "TBA"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        picker = self._data.get("picker") or {}
        return {
            "announced_at": picker.get("announced_at"),
            "source_url": picker.get("source_url"),
            "method": picker.get("method"),
        }


class FeaturedGameSensor(GameDayEntity, SensorEntity):
    _attr_icon = "mdi:football"

    def __init__(self, coordinator: GameDayCoordinator) -> None:
        super().__init__(coordinator, "featured_game", "GameDay Featured Game")

    @property
    def native_value(self) -> str:
        game = self._data.get("featured_game")
        return game.get("matchup", "TBA") if game else "TBA"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._data.get("featured_game") or {})


class FinalPicksSensor(GameDayEntity, SensorEntity):
    _attr_icon = "mdi:clipboard-check-multiple"

    def __init__(self, coordinator: GameDayCoordinator) -> None:
        super().__init__(coordinator, "final_picks", "GameDay Final Picks")

    @property
    def native_value(self) -> str:
        picks = self._data.get("picks")
        return "available" if picks and picks.get("picks") else "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        picks = self._data.get("picks") or {}
        return {
            "picks": picks.get("picks"),
            "source_url": picks.get("source_url"),
            "method": picks.get("method"),
            "announced_at": picks.get("announced_at"),
        }


class UpcomingSensor(GameDayEntity, SensorEntity):
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, coordinator: GameDayCoordinator) -> None:
        super().__init__(coordinator, "upcoming", "GameDay Upcoming Sites")

    @property
    def native_value(self) -> str:
        upcoming = self._data.get("upcoming") or []
        return upcoming[0]["school"] if upcoming else "TBA"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"schedule": self._data.get("upcoming") or []}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
