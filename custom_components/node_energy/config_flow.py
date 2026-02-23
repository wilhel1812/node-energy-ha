from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_ENTITY,
    CONF_CELL_MAH,
    CONF_CELL_V,
    CONF_CELLS_CURRENT,
    CONF_HORIZON_DAYS,
    CONF_NAME,
    CONF_START_DATE,
    CONF_START_HOUR,
    CONF_VOLTAGE_ENTITY,
    CONF_WEATHER_ENTITY,
    DEFAULT_CELL_MAH,
    DEFAULT_CELL_V,
    DEFAULT_CELLS_CURRENT,
    DEFAULT_HORIZON_DAYS,
    DEFAULT_NAME,
    DEFAULT_START_HOUR,
    DOMAIN,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(
                CONF_BATTERY_ENTITY,
                default=defaults.get(CONF_BATTERY_ENTITY, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"])
            ),
            vol.Optional(
                CONF_VOLTAGE_ENTITY,
                default=defaults.get(CONF_VOLTAGE_ENTITY, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"])
            ),
            vol.Optional(
                CONF_WEATHER_ENTITY,
                default=defaults.get(CONF_WEATHER_ENTITY, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["weather"])
            ),
            vol.Required(
                CONF_START_HOUR,
                default=defaults.get(CONF_START_HOUR, DEFAULT_START_HOUR),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_START_DATE,
                default=defaults.get(CONF_START_DATE),
            ): selector.DateSelector(),
            vol.Required(
                CONF_CELLS_CURRENT,
                default=defaults.get(CONF_CELLS_CURRENT, DEFAULT_CELLS_CURRENT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=12, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_CELL_MAH,
                default=defaults.get(CONF_CELL_MAH, DEFAULT_CELL_MAH),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=200, max=10000, step=50, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_CELL_V,
                default=defaults.get(CONF_CELL_V, DEFAULT_CELL_V),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=2.5, max=4.2, step=0.05, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_HORIZON_DAYS,
                default=defaults.get(CONF_HORIZON_DAYS, DEFAULT_HORIZON_DAYS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=14, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
        }
    )


class NodeEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_BATTERY_ENTITY]}::{user_input.get(CONF_NAME, DEFAULT_NAME)}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema({}), errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return NodeEnergyOptionsFlow(config_entry)


class NodeEnergyOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self._entry.data, **self._entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(defaults), errors={})
