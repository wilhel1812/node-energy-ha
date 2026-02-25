from __future__ import annotations

from homeassistant.util import dt as dt_util
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_APEX_SERIES,
    ATTR_CHARGE_POWER_NOW_W,
    ATTR_DISCHARGE_POWER_NOW_W,
    ATTR_ENERGY_CHARGED_KWH_TOTAL,
    ATTR_ENERGY_DISCHARGED_KWH_TOTAL,
    ATTR_FORECAST,
    ATTR_FULL_CHARGE_AT,
    ATTR_FULL_CHARGE_ETA_HOURS,
    ATTR_HISTORY_SOC,
    ATTR_HISTORY_VOLTAGE,
    ATTR_HISTORY_WEATHER,
    ATTR_INTERVALS,
    ATTR_META,
    ATTR_MODEL,
    ATTR_NET_POWER_AVG_24H_W,
    ATTR_NET_POWER_NOW_W,
    ATTR_NO_SUN_RUNTIME_DAYS,
    DOMAIN,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NodeEnergySensor(coordinator, entry),
            NodeEnergyNoSunRuntimeSensor(coordinator, entry),
            NodeEnergyMetricSensor(
                coordinator, entry, "net_power_now", "Net power now", ATTR_NET_POWER_NOW_W, "W",
                icon="mdi:flash", state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.POWER,
            ),
            NodeEnergyMetricSensor(
                coordinator, entry, "net_power_avg_24h", "Net power avg 24h", ATTR_NET_POWER_AVG_24H_W, "W",
                icon="mdi:chart-timeline-variant", state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.POWER,
            ),
            NodeEnergyMetricSensor(
                coordinator, entry, "charge_power_now", "Charge power now", ATTR_CHARGE_POWER_NOW_W, "W",
                icon="mdi:battery-arrow-up", state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.POWER,
            ),
            NodeEnergyMetricSensor(
                coordinator, entry, "discharge_power_now", "Discharge power now", ATTR_DISCHARGE_POWER_NOW_W, "W",
                icon="mdi:battery-arrow-down", state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.POWER,
            ),
            NodeEnergyMetricSensor(
                coordinator, entry, "energy_charged_total", "Energy charged total", ATTR_ENERGY_CHARGED_KWH_TOTAL, "kWh",
                icon="mdi:battery-plus", state_class=SensorStateClass.TOTAL_INCREASING, device_class=SensorDeviceClass.ENERGY,
            ),
            NodeEnergyMetricSensor(
                coordinator, entry, "energy_discharged_total", "Energy discharged total", ATTR_ENERGY_DISCHARGED_KWH_TOTAL, "kWh",
                icon="mdi:battery-minus", state_class=SensorStateClass.TOTAL_INCREASING, device_class=SensorDeviceClass.ENERGY,
            ),
            NodeEnergyMetricSensor(
                coordinator, entry, "full_charge_eta_hours", "Full charge ETA", ATTR_FULL_CHARGE_ETA_HOURS, "h",
                icon="mdi:battery-charging-high", state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.DURATION,
            ),
            NodeEnergyTimestampSensor(
                coordinator, entry, "full_charge_at", "Full charge at", ATTR_FULL_CHARGE_AT, icon="mdi:clock-check-outline",
            ),
        ],
        True,
    )


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


class NodeEnergyNoSunRuntimeSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "d"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_no_sun_runtime_days"
        self._attr_name = f"{entry.title} No-sun runtime"
        self._attr_icon = "mdi:weather-night"

    @property
    def native_value(self):
        v = (self.coordinator.data or {}).get(ATTR_NO_SUN_RUNTIME_DAYS)
        return round(float(v), 2) if v is not None else None


class NodeEnergyMetricSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        unique_suffix: str,
        label: str,
        data_key: str,
        unit: str,
        *,
        icon: str,
        state_class: SensorStateClass,
        device_class: SensorDeviceClass,
    ) -> None:
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_name = f"{entry.title} {label}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = state_class
        self._attr_device_class = device_class

    @property
    def native_value(self):
        v = (self.coordinator.data or {}).get(self._data_key)
        return round(float(v), 5) if v is not None else None


class NodeEnergyTimestampSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        unique_suffix: str,
        label: str,
        data_key: str,
        *,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_name = f"{entry.title} {label}"
        self._attr_icon = icon

    @property
    def native_value(self):
        raw = (self.coordinator.data or {}).get(self._data_key)
        if not raw:
            return None
        return dt_util.parse_datetime(str(raw))
