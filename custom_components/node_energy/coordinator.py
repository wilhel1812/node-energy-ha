from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import math
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_APEX_SERIES,
    ATTR_CHARGE_POWER_NOW_W,
    ATTR_DISCHARGE_POWER_NOW_W,
    ATTR_ENERGY_CHARGED_KWH_TOTAL,
    ATTR_ENERGY_DISCHARGED_KWH_TOTAL,
    ATTR_FORECAST,
    ATTR_HISTORY_SOC,
    ATTR_HISTORY_VOLTAGE,
    ATTR_HISTORY_WEATHER,
    ATTR_INTERVALS,
    ATTR_META,
    ATTR_MODEL,
    ATTR_NET_POWER_AVG_24H_W,
    ATTR_NET_POWER_NOW_W,
    ATTR_NO_SUN_RUNTIME_DAYS,
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
    DEFAULT_START_HOUR,
    DOMAIN,
    UPDATE_INTERVAL_MINUTES,
)


@dataclass
class Sample:
    ts: datetime
    value: float


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _parse_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _quantile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(float(v) for v in xs)
    if len(ys) == 1:
        return ys[0]
    q = max(0.0, min(1.0, float(q)))
    pos = q * (len(ys) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ys[lo]
    k = pos - lo
    return ys[lo] * (1.0 - k) + ys[hi] * k


def _fit_load_and_solar(intervals: list[dict[str, Any]], cap_wh: float) -> tuple[float, float]:
    if not intervals or cap_wh <= 0:
        return 0.0, 0.0

    x: list[float] = []
    y: list[float] = []
    for it in intervals:
        dt_h = float(it.get("dt_h", 0.0))
        dsoc = float(it.get("dsoc", 0.0))
        if dt_h <= 0:
            continue
        sx = float(it.get("sun_proxy", 0.0)) * float(it.get("weather_factor_hist", 1.0))
        p_obs = cap_wh * (dsoc / 100.0) / dt_h
        x.append(sx)
        y.append(p_obs)

    if not y:
        return 0.0, 0.0

    night_obs = [p for p, sx in zip(y, x, strict=False) if sx <= 0.01]
    if night_obs:
        load_w = max(0.0, -_mean(night_obs))
    else:
        load_w = max(0.0, -_mean(y))

    day_xy = [(sx, p + load_w) for p, sx in zip(y, x, strict=False) if sx > 0.01]
    if day_xy:
        num = sum(sx * yp for sx, yp in day_xy)
        den = sum(sx * sx for sx, _ in day_xy)
        solar_peak_w = max(0.0, num / den) if den > 0 else 0.0
    else:
        solar_peak_w = max(0.0, _mean(y) + load_w)
    return load_w, solar_peak_w


def _build_weather_climatology_by_hour(
    intervals: list[dict[str, Any]],
    load_w: float,
    solar_peak_w_raw: float,
    q: float = 0.35,
) -> tuple[list[float], float]:
    buckets: list[list[float]] = [[] for _ in range(24)]
    all_vals: list[float] = []

    for it in intervals:
        sproxy = float(it.get("sun_proxy", 0.0))
        if sproxy <= 0.01:
            continue
        tm = dt_util.parse_datetime(str(it.get("tm", "")))
        if tm is None:
            continue
        dt_h = float(it.get("dt_h", 0.0))
        dsoc = float(it.get("dsoc", 0.0))
        if dt_h <= 0:
            continue
        p_obs = float(it.get("net_power_obs_w", 0.0))
        if not math.isfinite(p_obs):
            p_obs = 0.0
        obs_prod = max(0.0, p_obs + load_w)
        clear_prod = max(1e-6, solar_peak_w_raw * sproxy)
        wf_emp = max(0.05, min(1.0, obs_prod / clear_prod))
        h = tm.astimezone(dt_util.DEFAULT_TIME_ZONE).hour
        buckets[h].append(wf_emp)
        all_vals.append(wf_emp)

    # Fallback to historic weather factors if production-derived values are too sparse.
    if len(all_vals) < 6:
        for it in intervals:
            sproxy = float(it.get("sun_proxy", 0.0))
            if sproxy <= 0.01:
                continue
            tm = dt_util.parse_datetime(str(it.get("tm", "")))
            if tm is None:
                continue
            wf = float(it.get("weather_factor_hist", 1.0))
            wf = max(0.05, min(1.0, wf))
            h = tm.astimezone(dt_util.DEFAULT_TIME_ZONE).hour
            buckets[h].append(wf)
            all_vals.append(wf)

    global_q = max(0.05, min(1.0, _quantile(all_vals, q))) if all_vals else 0.60
    hourly = [global_q for _ in range(24)]
    for h in range(24):
        if buckets[h]:
            hourly[h] = max(0.05, min(1.0, _quantile(buckets[h], q)))
    return hourly, global_q


def _compute_backtest_24h(intervals: list[dict[str, Any]], cap_wh: float) -> dict[str, float | int] | None:
    if len(intervals) < 10 or cap_wh <= 0:
        return None

    def _tm(it: dict[str, Any]) -> datetime | None:
        return dt_util.parse_datetime(str(it.get("tm", "")))

    enriched: list[dict[str, Any]] = []
    for it in intervals:
        tm = _tm(it)
        if tm is None:
            continue
        e = dict(it)
        e["_tm"] = tm
        enriched.append(e)
    if len(enriched) < 10:
        return None
    enriched.sort(key=lambda it: it["_tm"])

    latest_tm = enriched[-1]["_tm"]
    anchor = latest_tm - timedelta(hours=24)
    train = [it for it in enriched if it["_tm"] <= anchor]
    test = [it for it in enriched if it["_tm"] > anchor]
    if len(train) < 6 or len(test) < 4:
        return None

    load_train, solar_train = _fit_load_and_solar(train, cap_wh)
    soc = float(test[0].get("soc0", 0.0))
    errs: list[float] = []
    obs_day_e = 0.0
    pred_day_e = 0.0
    day_count = 0

    for it in test:
        dt_h = float(it.get("dt_h", 0.0))
        if dt_h <= 0:
            continue
        sx = float(it.get("sun_proxy", 0.0)) * float(it.get("weather_factor_hist", 1.0))
        p_net_pred = -load_train + solar_train * sx
        soc += (p_net_pred * dt_h / cap_wh) * 100.0
        soc = max(0.0, min(100.0, soc))
        actual = float(it.get("soc1", soc))
        errs.append(soc - actual)

        if float(it.get("sun_proxy", 0.0)) > 0.01:
            dsoc = float(it.get("dsoc", 0.0))
            p_obs = cap_wh * (dsoc / 100.0) / dt_h
            obs_prod = max(0.0, p_obs + load_train)
            pred_prod = max(0.0, solar_train * sx)
            obs_day_e += obs_prod * dt_h
            pred_day_e += pred_prod * dt_h
            day_count += 1

    if not errs:
        return None
    mae = sum(abs(e) for e in errs) / len(errs)
    bias = sum(errs) / len(errs)
    rmse = math.sqrt(sum(e * e for e in errs) / len(errs))
    solar_scale_raw = (obs_day_e / pred_day_e) if pred_day_e > 1e-6 else 1.0
    return {
        "samples_train": len(train),
        "samples_test": len(test),
        "mae_soc": mae,
        "bias_soc": bias,
        "rmse_soc": rmse,
        "horizon_error_soc": errs[-1],
        "solar_scale_raw": solar_scale_raw,
        "daylight_samples_test": day_count,
    }


# NOAA-style approximation; same model as the standalone script.
def _solar_position_utc(ts_utc: datetime, lat_deg: float, lon_deg: float) -> tuple[float, float]:
    ts_utc = ts_utc.astimezone(UTC)
    y = ts_utc.year
    m = ts_utc.month
    d = ts_utc.day
    hr = ts_utc.hour + ts_utc.minute / 60.0 + ts_utc.second / 3600.0

    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    jd = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5 + hr / 24.0
    t = (jd - 2451545.0) / 36525.0

    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    m_sun = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    m_rad = math.radians(m_sun % 360.0)
    c = (
        math.sin(m_rad) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * m_rad) * (0.019993 - 0.000101 * t)
        + math.sin(3 * m_rad) * 0.000289
    )
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    lam = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23.0 + (26.0 + ((21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0)) / 60.0
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))

    lam_r = math.radians(lam)
    eps_r = math.radians(eps)
    decl = math.asin(math.sin(eps_r) * math.sin(lam_r))
    ra = math.atan2(math.cos(eps_r) * math.sin(lam_r), math.cos(lam_r))

    gmst = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * t * t
        - (t * t * t) / 38710000.0
    ) % 360.0
    lst = math.radians((gmst + lon_deg) % 360.0)
    ha = (lst - ra + math.pi) % (2 * math.pi) - math.pi

    lat_r = math.radians(lat_deg)
    elev = math.asin(math.sin(lat_r) * math.sin(decl) + math.cos(lat_r) * math.cos(decl) * math.cos(ha))
    az = math.atan2(
        math.sin(ha),
        math.cos(ha) * math.sin(lat_r) - math.tan(decl) * math.cos(lat_r),
    )
    return math.degrees(elev), (math.degrees(az) + 180.0) % 360.0


def _condition_weight(condition: str) -> float:
    c = (condition or "").lower()
    table = {
        "sunny": 1.00,
        "clear-night": 0.95,
        "partlycloudy": 0.82,
        "cloudy": 0.62,
        "fog": 0.58,
        "rainy": 0.50,
        "pouring": 0.42,
        "snowy": 0.48,
        "snowy-rainy": 0.44,
        "hail": 0.35,
        "lightning": 0.32,
        "lightning-rainy": 0.28,
        "windy": 0.78,
        "windy-variant": 0.72,
    }
    return table.get(c, 0.70)


def _weather_factor(condition: str, cloud_coverage: float | None, precip_probability: float | None) -> float:
    if cloud_coverage is None:
        cloud_factor = _condition_weight(condition)
    else:
        cloud_frac = max(0.0, min(1.0, cloud_coverage / 100.0))
        cloud_factor = 1.0 - 0.75 * cloud_frac
    if precip_probability is None:
        precip_factor = 1.0
    else:
        precip_factor = 1.0 - 0.25 * max(0.0, min(100.0, precip_probability)) / 100.0
    return max(0.05, min(1.0, cloud_factor * _condition_weight(condition) * precip_factor))


def _weather_factor_at(points: list[dict[str, Any]], ts: datetime) -> tuple[float, str]:
    if not points:
        return 1.0, ""

    def by_hour_fallback(target_ts: datetime) -> tuple[float, str]:
        buckets: dict[int, list[dict[str, Any]]] = {}
        for p in points:
            h = p["ts"].astimezone(target_ts.tzinfo or UTC).hour
            buckets.setdefault(h, []).append(p)
        h = target_ts.astimezone(target_ts.tzinfo or UTC).hour
        if h in buckets and buckets[h]:
            vals = buckets[h]
            return _mean([float(v["factor"]) for v in vals]), vals[-1].get("condition", "")
        return _mean([float(p["factor"]) for p in points]), points[-1].get("condition", "")

    if ts <= points[0]["ts"] or ts >= points[-1]["ts"]:
        return by_hour_fallback(ts)

    for i in range(1, len(points)):
        a = points[i - 1]
        b = points[i]
        if a["ts"] <= ts <= b["ts"]:
            span = (b["ts"] - a["ts"]).total_seconds()
            if span <= 0:
                return float(a["factor"]), a.get("condition", "")
            k = (ts - a["ts"]).total_seconds() / span
            fac = float(a["factor"]) + (float(b["factor"]) - float(a["factor"])) * k
            return fac, (a.get("condition", "") if k < 0.5 else b.get("condition", ""))

    return by_hour_fallback(ts)


class NodeEnergyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry.entry_id}",
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )

    @property
    def cfg(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    async def _async_fetch_history(self, entity_id: str, start_utc: datetime) -> list[Sample]:
        if not entity_id:
            return []

        def _query() -> list[Sample]:
            # recorder helper API varies by HA versions; keep fallback-safe.
            from homeassistant.components.recorder.history import get_significant_states

            res = get_significant_states(
                self.hass,
                start_utc,
                None,
                [entity_id],
                include_start_time_state=True,
                significant_changes_only=False,
                minimal_response=False,
                no_attributes=False,
            )
            items = res.get(entity_id, []) if isinstance(res, dict) else []
            out: list[Sample] = []
            for st in items:
                v = _parse_float(getattr(st, "state", None))
                if v is None:
                    continue
                t = getattr(st, "last_updated", None) or getattr(st, "last_changed", None)
                if t is None:
                    continue
                out.append(Sample(ts=t, value=v))
            out.sort(key=lambda x: x.ts)
            return out

        try:
            return await self.hass.async_add_executor_job(_query)
        except Exception:
            return []

    async def _async_fetch_weather_history(self, entity_id: str, start_utc: datetime) -> list[dict[str, Any]]:
        if not entity_id:
            return []

        def _query() -> list[dict[str, Any]]:
            from homeassistant.components.recorder.history import get_significant_states

            res = get_significant_states(
                self.hass,
                start_utc,
                None,
                [entity_id],
                include_start_time_state=True,
                significant_changes_only=False,
                minimal_response=False,
                no_attributes=False,
            )
            items = res.get(entity_id, []) if isinstance(res, dict) else []
            out: list[dict[str, Any]] = []
            for st in items:
                t = getattr(st, "last_updated", None) or getattr(st, "last_changed", None)
                if t is None:
                    continue
                attrs = getattr(st, "attributes", {}) or {}
                cond = (getattr(st, "state", "") or "").lower()
                cloud = _parse_float(attrs.get("cloud_coverage"))
                prob = _parse_float(attrs.get("precipitation_probability"))
                out.append(
                    {
                        "ts": t,
                        "condition": cond,
                        "cloud_coverage": cloud,
                        "precipitation_probability": prob,
                        "factor": _weather_factor(cond, cloud, prob),
                    }
                )
            out.sort(key=lambda x: x["ts"])
            return out

        try:
            return await self.hass.async_add_executor_job(_query)
        except Exception:
            return []

    async def _async_weather_forecast_hourly(self, weather_entity: str) -> list[dict[str, Any]]:
        if not weather_entity:
            return []
        try:
            resp = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "hourly", "entity_id": weather_entity},
                blocking=True,
                return_response=True,
            )
        except Exception:
            return []

        payload = resp or {}
        # HA return shape differs by version:
        # - {"service_response": {"weather.x": {"forecast": [...]}}}
        # - {"weather.x": {"forecast": [...]}}
        root = payload.get("service_response", payload)
        fc = (root.get(weather_entity, {}) or {}).get("forecast", [])
        rows: list[dict[str, Any]] = []
        for p in fc:
            ts = dt_util.parse_datetime(p.get("datetime"))
            if not ts:
                continue
            cloud = _parse_float(p.get("cloud_coverage"))
            prob = _parse_float(p.get("precipitation_probability"))
            cond = (p.get("condition") or "").lower()
            rows.append(
                {
                    "ts": ts,
                    "condition": cond,
                    "cloud_coverage": cloud,
                    "precipitation_probability": prob,
                    "factor": _weather_factor(cond, cloud, prob),
                }
            )
        rows.sort(key=lambda r: r["ts"])
        return rows

    async def _async_update_data(self) -> dict[str, Any]:
        cfg = self.cfg

        battery_entity = cfg.get(CONF_BATTERY_ENTITY)
        voltage_entity = cfg.get(CONF_VOLTAGE_ENTITY)
        weather_entity = cfg.get(CONF_WEATHER_ENTITY)

        if not battery_entity:
            raise UpdateFailed("Battery entity is required")

        start_hour = int(cfg.get(CONF_START_HOUR, DEFAULT_START_HOUR))
        start_date = cfg.get(CONF_START_DATE)
        cells_current = int(cfg.get(CONF_CELLS_CURRENT, DEFAULT_CELLS_CURRENT))
        cell_mah = float(cfg.get(CONF_CELL_MAH, DEFAULT_CELL_MAH))
        cell_v = float(cfg.get(CONF_CELL_V, DEFAULT_CELL_V))
        horizon_days = int(cfg.get(CONF_HORIZON_DAYS, DEFAULT_HORIZON_DAYS))

        now_local = dt_util.now()
        start_local: datetime
        analysis_start = cfg.get(CONF_ANALYSIS_START)
        if analysis_start:
            parsed_dt = dt_util.parse_datetime(str(analysis_start))
            if parsed_dt is not None:
                if parsed_dt.tzinfo is None:
                    start_local = parsed_dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
                else:
                    start_local = parsed_dt.astimezone(dt_util.DEFAULT_TIME_ZONE)
            else:
                start_local = (now_local - timedelta(days=1)).replace(hour=start_hour, minute=0, second=0, microsecond=0)
        elif start_date:
            parsed_date = dt_util.parse_date(str(start_date))
            if parsed_date:
                start_local = datetime(parsed_date.year, parsed_date.month, parsed_date.day, start_hour, 0, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
            else:
                start_local = (now_local - timedelta(days=1)).replace(hour=start_hour, minute=0, second=0, microsecond=0)
        else:
            start_local = (now_local - timedelta(days=1)).replace(hour=start_hour, minute=0, second=0, microsecond=0)
        start_utc = start_local.astimezone(UTC)

        batt_rows = await self._async_fetch_history(battery_entity, start_utc)
        volt_rows = await self._async_fetch_history(voltage_entity, start_utc) if voltage_entity else []

        if len(batt_rows) < 2:
            raise UpdateFailed("Not enough battery history yet")

        weather_hist_points = await self._async_fetch_weather_history(weather_entity, start_utc) if weather_entity else []

        weather_forecast_points = await self._async_weather_forecast_hourly(weather_entity) if weather_entity else []

        lat = float(self.hass.config.latitude)
        lon = float(self.hass.config.longitude)

        def nearest(samples: list[Sample], ts: datetime) -> float | None:
            if not samples:
                return None
            return min(samples, key=lambda s: abs((s.ts - ts).total_seconds())).value

        cap_wh_current = cells_current * (cell_mah / 1000.0) * cell_v
        intervals: list[dict[str, Any]] = []

        for i in range(1, len(batt_rows)):
            p = batt_rows[i - 1]
            c = batt_rows[i]
            dt_h = (c.ts - p.ts).total_seconds() / 3600.0
            if dt_h <= 0:
                continue
            mid = p.ts + (c.ts - p.ts) / 2
            elev, az = _solar_position_utc(mid, lat, lon)
            sun_proxy = max(0.0, math.sin(math.radians(max(elev, 0.0))))
            w_hist, w_cond = _weather_factor_at(weather_hist_points, mid)
            dsoc = c.value - p.value
            net_obs = cap_wh_current * (dsoc / 100.0) / dt_h
            intervals.append(
                {
                    "tm": mid.isoformat(),
                    "dt_h": dt_h,
                    "soc0": p.value,
                    "soc1": c.value,
                    "dsoc": dsoc,
                    "sun_elev_deg": elev,
                    "sun_az_deg": az,
                    "sun_proxy": sun_proxy,
                    "weather_factor_hist": w_hist,
                    "weather_condition_hist": w_cond,
                    "voltage": nearest(volt_rows, mid),
                    "net_power_obs_w": net_obs,
                }
            )

        if not intervals:
            raise UpdateFailed("No valid intervals")

        load_w, solar_peak_w_raw = _fit_load_and_solar(intervals, cap_wh_current)
        backtest_24h = _compute_backtest_24h(intervals, cap_wh_current)
        solar_scale_24h = 1.0
        if backtest_24h and int(backtest_24h.get("daylight_samples_test", 0)) >= 3:
            solar_scale_24h = max(0.25, min(1.25, float(backtest_24h.get("solar_scale_raw", 1.0))))
        solar_peak_w = solar_peak_w_raw * solar_scale_24h
        fallback_quantile = 0.35
        wf_climatology_hourly, wf_climatology_global = _build_weather_climatology_by_hour(
            intervals,
            load_w,
            solar_peak_w_raw,
            fallback_quantile,
        )

        for it in intervals:
            p_clear = solar_peak_w * it["sun_proxy"]
            p_prod = p_clear * it["weather_factor_hist"]
            it["production_clear_w"] = p_clear
            it["production_w"] = p_prod
            it["consumption_w"] = load_w
            it["net_power_model_w"] = -load_w + p_prod

        latest_soc = batt_rows[-1].value
        latest_ts = batt_rows[-1].ts
        now_utc = dt_util.utcnow().astimezone(UTC)

        step_min = 10
        step_delta = timedelta(minutes=step_min)
        steps = int((max(1, min(14, horizon_days)) * 24 * 60) / step_min)

        weather_all = sorted(
            [*weather_hist_points, *weather_forecast_points],
            key=lambda p: p.get("ts") or datetime.min.replace(tzinfo=UTC),
        )
        provider_forecast_end = weather_forecast_points[-1]["ts"] if weather_forecast_points else None

        def _weather_factor_for_future(ts: datetime) -> float:
            fac_provider, _ = _weather_factor_at(weather_all, ts)
            fac_provider = max(0.05, min(1.0, float(fac_provider)))
            if provider_forecast_end and ts > provider_forecast_end:
                h = ts.astimezone(dt_util.DEFAULT_TIME_ZONE).hour
                fac_clim = wf_climatology_hourly[h] if 0 <= h < 24 else wf_climatology_global
                hrs = (ts - provider_forecast_end).total_seconds() / 3600.0
                # Smooth transition from provider profile to conservative climatology.
                alpha = math.exp(-max(0.0, hrs) / 12.0)
                return max(0.05, min(1.0, alpha * fac_provider + (1.0 - alpha) * fac_clim))
            return fac_provider

        def _simulate_soc_between(start_ts: datetime, end_ts: datetime, start_soc: float, use_weather: bool) -> float:
            if end_ts <= start_ts:
                return start_soc
            cap_wh = cells_current * (cell_mah / 1000.0) * cell_v
            soc = float(start_soc)
            t = start_ts
            while t < end_ts:
                t_next = min(t + step_delta, end_ts)
                dt_h = (t_next - t).total_seconds() / 3600.0
                mid = t + (t_next - t) / 2
                elev, _ = _solar_position_utc(mid, lat, lon)
                sproxy = max(0.0, math.sin(math.radians(max(elev, 0.0))))
                wf = _weather_factor_for_future(mid)
                p_prod = solar_peak_w * sproxy * (wf if use_weather else 1.0)
                p_net = -load_w + p_prod
                soc += (p_net * dt_h / cap_wh) * 100.0
                soc = max(0.0, min(100.0, soc))
                t = t_next
            return soc

        soc_now = _simulate_soc_between(latest_ts, now_utc, latest_soc, True)

        times: list[str] = []
        solar_proxy: list[float] = []
        solar_elev: list[float] = []
        weather_factor: list[float] = []

        for i in range(steps + 1):
            t = now_utc + timedelta(minutes=i * step_min)
            elev, _ = _solar_position_utc(t, lat, lon)
            sproxy = max(0.0, math.sin(math.radians(max(elev, 0.0))))
            wf = _weather_factor_for_future(t)
            times.append(t.isoformat())
            solar_proxy.append(sproxy)
            solar_elev.append(elev)
            weather_factor.append(wf)

        def simulate(cells: int, use_weather: bool) -> list[float]:
            cap_wh = cells * (cell_mah / 1000.0) * cell_v
            soc = float(soc_now)
            out = [soc]
            dt_h = step_min / 60.0
            for i in range(1, len(times)):
                wf = weather_factor[i] if use_weather else 1.0
                p_prod = solar_peak_w * solar_proxy[i] * wf
                p_net = -load_w + p_prod
                soc += (p_net * dt_h / cap_wh) * 100.0
                soc = max(0.0, min(100.0, soc))
                out.append(soc)
            return out

        scenario_cells = sorted({cells_current, *range(1, 13)})

        forecast = {
            "times": times,
            "solar_proxy": solar_proxy,
            "solar_elev": solar_elev,
            "weather_factor": weather_factor,
            "latest_soc": latest_soc,
            "scenarios": {str(c): simulate(c, True) for c in scenario_cells},
            "scenarios_clear": {str(c): simulate(c, False) for c in scenario_cells},
        }

        soc_actual = [{"x": s.ts.isoformat(), "y": s.value} for s in batt_rows]
        soc_projection_weather = [{"x": t, "y": v} for t, v in zip(times, forecast["scenarios"].get(str(cells_current), []), strict=False)]
        soc_projection_clear = [{"x": t, "y": v} for t, v in zip(times, forecast["scenarios_clear"].get(str(cells_current), []), strict=False)]
        cap_wh_runtime = cells_current * (cell_mah / 1000.0) * cell_v
        soc_projection_no_sun: list[dict[str, Any]] = []
        soc_no_sun = float(soc_now)
        dt_h_step = step_min / 60.0
        for t in times:
            soc_projection_no_sun.append({"x": t, "y": soc_no_sun})
            if cap_wh_runtime > 0:
                soc_no_sun += ((-load_w) * dt_h_step / cap_wh_runtime) * 100.0
                soc_no_sun = max(0.0, min(100.0, soc_no_sun))

        remain_wh_no_sun = max(0.0, min(100.0, soc_now)) / 100.0 * cap_wh_runtime
        no_sun_runtime_days = (remain_wh_no_sun / load_w / 24.0) if load_w > 0 else None

        charged_wh_total = cap_wh_current * sum(max(0.0, float(it.get("dsoc", 0.0))) / 100.0 for it in intervals)
        discharged_wh_total = cap_wh_current * sum(max(0.0, -float(it.get("dsoc", 0.0))) / 100.0 for it in intervals)

        now_window_start = now_utc - timedelta(hours=24)
        energy_24h_wh = 0.0
        dur_24h_h = 0.0
        for it in intervals:
            tm = dt_util.parse_datetime(it.get("tm", ""))
            if tm is None or tm < now_window_start:
                continue
            dt_h = float(it.get("dt_h", 0.0))
            p_w = float(it.get("net_power_obs_w", 0.0))
            energy_24h_wh += p_w * dt_h
            dur_24h_h += dt_h
        net_power_avg_24h_w = (energy_24h_wh / dur_24h_h) if dur_24h_h > 0 else None

        now_solar_proxy = solar_proxy[0] if solar_proxy else 0.0
        now_weather_factor = weather_factor[0] if weather_factor else 1.0
        current_prod_weather_w = solar_peak_w * now_solar_proxy * now_weather_factor
        net_power_now_w = -load_w + current_prod_weather_w
        charge_power_now_w = max(0.0, net_power_now_w)
        discharge_power_now_w = max(0.0, -net_power_now_w)
        sun_history: list[dict[str, Any]] = []
        for it in intervals:
            tm = dt_util.parse_datetime(it["tm"])
            if tm and tm < now_utc:
                sun_history.append({"x": it["tm"], "y": it["sun_elev_deg"]})

        last_sun_hist_ts = dt_util.parse_datetime(sun_history[-1]["x"]) if sun_history else None
        if last_sun_hist_ts is None or last_sun_hist_ts < now_utc:
            t_hist = (latest_ts if latest_ts > start_utc else start_utc)
            while t_hist < now_utc:
                elev, _ = _solar_position_utc(t_hist, lat, lon)
                sun_history.append({"x": t_hist.isoformat(), "y": elev})
                t_hist += step_delta
        sun_forecast = [{"x": t, "y": e} for t, e in zip(times, solar_elev, strict=False)]
        power_observed = [{"x": it["tm"], "y": it["net_power_obs_w"]} for it in intervals]
        power_modeled = [{"x": it["tm"], "y": it["net_power_model_w"]} for it in intervals]
        power_prod_weather = [{"x": it["tm"], "y": it["production_w"]} for it in intervals]
        power_prod_clear = [{"x": it["tm"], "y": it["production_clear_w"]} for it in intervals]
        power_consumption = [{"x": it["tm"], "y": it["consumption_w"]} for it in intervals]

        apex_series = {
            "now": now_utc.isoformat(),
            "soc_actual": soc_actual,
            "soc_projection_weather": soc_projection_weather,
            "soc_projection_clear": soc_projection_clear,
            "soc_projection_no_sun": soc_projection_no_sun,
            "sun_history": sun_history,
            "sun_forecast": sun_forecast,
            "power_observed": power_observed,
            "power_modeled": power_modeled,
            "power_production_weather": power_prod_weather,
            "power_production_clear": power_prod_clear,
            "power_consumption": power_consumption,
        }

        return {
            ATTR_META: {
                "name": cfg.get(CONF_NAME),
                "battery_entity": battery_entity,
                "voltage_entity": voltage_entity,
                "weather_entity": weather_entity,
                "start_hour": start_hour,
                "start_date": start_local.date().isoformat(),
                "cells_current": cells_current,
                "cell_mah": cell_mah,
                "cell_v": cell_v,
                "horizon_days": horizon_days,
                "latest_local": latest_ts.astimezone(dt_util.DEFAULT_TIME_ZONE).isoformat(),
                "now_local": now_utc.astimezone(dt_util.DEFAULT_TIME_ZONE).isoformat(),
            },
            ATTR_MODEL: {
                "load_w": load_w,
                "solar_peak_w": solar_peak_w,
                "solar_peak_w_raw": solar_peak_w_raw,
                "avg_net_w_observed": _mean([float(it.get("net_power_obs_w", 0.0)) for it in intervals]),
                "current_production_weather_w": current_prod_weather_w,
                "solar_scale_24h": solar_scale_24h,
                "weather_fallback_method": "climatology_p35_blend12h",
                "weather_fallback_quantile": fallback_quantile,
                "weather_provider_horizon_hours": (
                    round((provider_forecast_end - now_utc).total_seconds() / 3600.0, 2)
                    if provider_forecast_end
                    else None
                ),
                "backtest_24h_mae_soc": (round(float(backtest_24h["mae_soc"]), 3) if backtest_24h else None),
                "backtest_24h_bias_soc": (round(float(backtest_24h["bias_soc"]), 3) if backtest_24h else None),
                "backtest_24h_rmse_soc": (round(float(backtest_24h["rmse_soc"]), 3) if backtest_24h else None),
                "backtest_24h_horizon_error_soc": (round(float(backtest_24h["horizon_error_soc"]), 3) if backtest_24h else None),
                "backtest_24h_samples_train": (int(backtest_24h["samples_train"]) if backtest_24h else None),
                "backtest_24h_samples_test": (int(backtest_24h["samples_test"]) if backtest_24h else None),
            },
            ATTR_HISTORY_SOC: [{"t": s.ts.isoformat(), "v": s.value} for s in batt_rows],
            ATTR_HISTORY_VOLTAGE: [{"t": s.ts.isoformat(), "v": s.value} for s in volt_rows],
            ATTR_HISTORY_WEATHER: [
                {
                    "t": p["ts"].isoformat(),
                    "condition": p.get("condition", ""),
                    "cloud_coverage": p.get("cloud_coverage"),
                    "factor": p.get("factor", 1.0),
                }
                for p in weather_hist_points
            ],
            ATTR_INTERVALS: intervals,
            ATTR_FORECAST: forecast,
            ATTR_APEX_SERIES: apex_series,
            ATTR_NO_SUN_RUNTIME_DAYS: round(no_sun_runtime_days, 3) if no_sun_runtime_days is not None else None,
            ATTR_NET_POWER_NOW_W: round(net_power_now_w, 3),
            ATTR_NET_POWER_AVG_24H_W: round(net_power_avg_24h_w, 3) if net_power_avg_24h_w is not None else None,
            ATTR_CHARGE_POWER_NOW_W: round(charge_power_now_w, 3),
            ATTR_DISCHARGE_POWER_NOW_W: round(discharge_power_now_w, 3),
            ATTR_ENERGY_CHARGED_KWH_TOTAL: round(charged_wh_total / 1000.0, 5),
            ATTR_ENERGY_DISCHARGED_KWH_TOTAL: round(discharged_wh_total / 1000.0, 5),
            "native_value": round(latest_soc, 2),
        }


import logging

_LOGGER = logging.getLogger(__name__)
