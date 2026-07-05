"""Binary sensors for ESPN College GameDay."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import GameDayCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: GameDayCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [NewAnnouncementSensor(coordinator), FlairWeekSensor(coordinator)]
    )


class GameDayBinaryEntity(CoordinatorEntity[GameDayCoordinator], BinarySensorEntity):
    def __init__(self, coordinator: GameDayCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self.entity_id = f"binary_sensor.gameday_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "espn_gameday")},
            name="ESPN College GameDay",
            manufacturer="ESPN (unofficial)",
        )

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data or {}


class NewAnnouncementSensor(GameDayBinaryEntity):
    _attr_icon = "mdi:bullhorn"

    def __init__(self, coordinator: GameDayCoordinator) -> None:
        super().__init__(coordinator, "new_announcement", "GameDay New Announcement")

    @property
    def is_on(self) -> bool:
        fresh_until = self._data.get("fresh_until")
        if not fresh_until:
            return False
        parsed = dt_util.parse_datetime(fresh_until)
        return bool(parsed and dt_util.utcnow() < parsed)


class FlairWeekSensor(GameDayBinaryEntity):
    _attr_icon = "mdi:party-popper"

    def __init__(self, coordinator: GameDayCoordinator) -> None:
        super().__init__(coordinator, "flair_week", "GameDay Flair Week")

    @property
    def is_on(self) -> bool:
        return bool(self._data.get("flair_team"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"flair_team": self._data.get("flair_team")}
