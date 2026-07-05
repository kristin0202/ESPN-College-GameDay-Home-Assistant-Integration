"""Config flow for ESPN College GameDay."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_FLAIR_TEAMS, DEFAULT_FLAIR_TEAMS, DOMAIN


class GameDayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="ESPN College GameDay", data=user_input
            )

        schema = vol.Schema(
            {vol.Optional(CONF_FLAIR_TEAMS, default=DEFAULT_FLAIR_TEAMS): str}
        )
        return self.async_show_form(step_id="user", data_schema=schema)
