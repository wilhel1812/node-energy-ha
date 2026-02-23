from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_APEX_SERIES, ATTR_FORECAST, ATTR_HISTORY_SOC, ATTR_HISTORY_VOLTAGE, ATTR_HISTORY_WEATHER, ATTR_INTERVALS, ATTR_META, ATTR_MODEL, DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NodeEnergySensor(coordinator, entry)], True)


class NodeEnergySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_soc"
        self._attr_name = entry.title
        self._attr_icon = "mdi:battery-sync"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("native_value")

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data or {}
        return {
            ATTR_META: d.get(ATTR_META),
            ATTR_MODEL: d.get(ATTR_MODEL),
            ATTR_HISTORY_SOC: d.get(ATTR_HISTORY_SOC),
            ATTR_HISTORY_VOLTAGE: d.get(ATTR_HISTORY_VOLTAGE),
            ATTR_HISTORY_WEATHER: d.get(ATTR_HISTORY_WEATHER),
            ATTR_INTERVALS: d.get(ATTR_INTERVALS),
            ATTR_FORECAST: d.get(ATTR_FORECAST),
            ATTR_APEX_SERIES: d.get(ATTR_APEX_SERIES),
        }
