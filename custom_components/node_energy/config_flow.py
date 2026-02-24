from __future__ import annotations

from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ANALYSIS_START,
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
    DOMAIN,
)


def _default_analysis_start(defaults: dict[str, Any]) -> str | None:
    if defaults.get(CONF_ANALYSIS_START):
        return defaults.get(CONF_ANALYSIS_START)

    start_date = defaults.get(CONF_START_DATE)
    start_hour = defaults.get(CONF_START_HOUR)
    if start_date:
        d = dt_util.parse_date(str(start_date))
        if d is not None:
            h = int(start_hour) if start_hour is not None else 0
            h = max(0, min(23, h))
            dt_local = datetime(d.year, d.month, d.day, h, 0, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
            return dt_local.isoformat()
    return None


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    analysis_start_default = _default_analysis_start(defaults) or ""
    fields: dict[Any, Any] = {}
    fields[vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME))] = str

    battery_default = defaults.get(CONF_BATTERY_ENTITY)
    if isinstance(battery_default, str) and battery_default:
        battery_key = vol.Required(CONF_BATTERY_ENTITY, default=battery_default)
    else:
        battery_key = vol.Required(CONF_BATTERY_ENTITY)
    fields[battery_key] = selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"]))

    voltage_default = defaults.get(CONF_VOLTAGE_ENTITY)
    if isinstance(voltage_default, str) and voltage_default:
        voltage_key = vol.Optional(CONF_VOLTAGE_ENTITY, default=voltage_default)
    else:
        voltage_key = vol.Optional(CONF_VOLTAGE_ENTITY)
    fields[voltage_key] = selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"]))

    weather_default = defaults.get(CONF_WEATHER_ENTITY)
    if isinstance(weather_default, str) and weather_default:
        weather_key = vol.Optional(CONF_WEATHER_ENTITY, default=weather_default)
    else:
        weather_key = vol.Optional(CONF_WEATHER_ENTITY)
    fields[weather_key] = selector.EntitySelector(selector.EntitySelectorConfig(domain=["weather"]))

    fields[vol.Optional(CONF_ANALYSIS_START, default=analysis_start_default)] = str
    fields[vol.Required(CONF_CELLS_CURRENT, default=defaults.get(CONF_CELLS_CURRENT, DEFAULT_CELLS_CURRENT))] = selector.NumberSelector(
        selector.NumberSelectorConfig(min=1, max=12, step=1, mode=selector.NumberSelectorMode.BOX)
    )
    fields[vol.Required(CONF_CELL_MAH, default=defaults.get(CONF_CELL_MAH, DEFAULT_CELL_MAH))] = selector.NumberSelector(
        selector.NumberSelectorConfig(min=200, max=10000, step=50, mode=selector.NumberSelectorMode.BOX)
    )
    fields[vol.Required(CONF_CELL_V, default=defaults.get(CONF_CELL_V, DEFAULT_CELL_V))] = selector.NumberSelector(
        selector.NumberSelectorConfig(min=2.5, max=4.2, step=0.05, mode=selector.NumberSelectorMode.BOX)
    )
    fields[vol.Required(CONF_HORIZON_DAYS, default=defaults.get(CONF_HORIZON_DAYS, DEFAULT_HORIZON_DAYS))] = selector.NumberSelector(
        selector.NumberSelectorConfig(min=1, max=14, step=1, mode=selector.NumberSelectorMode.BOX)
    )
    return vol.Schema(fields)


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
