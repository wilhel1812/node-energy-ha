# Battery Telemetry Forecast (Home Assistant Integration)

Home Assistant integration for battery/solar modeling and forecast.

## Pivot: ApexCharts-first
This integration now exposes precomputed chart series in `sensor.<your_node_energy_sensor>.attributes.apex_series` so you can use **ApexCharts Card** as the primary UI.

## Install (HACS)
1. Add this repo as custom repository in HACS, category `Integration`.
2. Install `Battery Telemetry Forecast`.
3. Restart Home Assistant.
4. Add integration: Settings -> Devices & Services -> Add Integration -> `Battery Telemetry Forecast`.
5. Install `ApexCharts Card` from HACS Frontend.
6. Optional (recommended for setup UX): install `Battery Telemetry Setup Card` dashboard plugin:
   - https://github.com/wilhel1812/node-energy-card

## UI Config per entry
- `battery_entity` (required)
- `voltage_entity` (optional)
- `weather_entity` (optional)
- `start_hour` (0-23)
- `start_date` (optional; use this to cut off bad pre-solar data)
- `cells_current`, `cell_mah`, `cell_v`, `horizon_days`

You can create multiple entries for multiple nodes.

## ApexCharts setup
Install [ApexCharts Card](https://github.com/RomRider/apexcharts-card) from HACS (Dashboard).

## Fast setup
1. Add `custom:battery-telemetry-setup-card` to any dashboard.
2. Pick your Battery Telemetry sensor from the dropdown.
3. Click `Copy Dashboard Config`.
4. Paste into Dashboard -> Edit -> Raw configuration editor.

Then add a single chart card (example):

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Battery Telemetry
graph_span: 72h
now:
  show: true
  label: Now
apex_config:
  chart:
    height: 680
    toolbar:
      show: true
  legend:
    show: true
  xaxis:
    type: datetime
    labels:
      datetimeUTC: false
      format: dd MMM HH:mm
  stroke:
    width: [3, 3, 2, 2, 2, 2, 2, 2]
  yaxis:
    - id: soc
      min: 0
      max: 100
      decimalsInFloat: 1
      title: { text: "SOC %" }
    - id: power
      opposite: true
      title: { text: "Power W" }
    - id: sun
      opposite: true
      min: -90
      max: 90
      title: { text: "Sun elev °" }
series:
  - entity: sensor.wam6
    name: SOC (history)
    yaxis_id: soc
    data_generator: return (entity.attributes.apex_series?.soc_actual || []).map(p => [new Date(p.x).getTime(), p.y]);
  - entity: sensor.wam6
    name: SOC (projection weather)
    yaxis_id: soc
    data_generator: return (entity.attributes.apex_series?.soc_projection_weather || []).map(p => [new Date(p.x).getTime(), p.y]);
  - entity: sensor.wam6
    name: SOC (projection clear sky)
    yaxis_id: soc
    data_generator: return (entity.attributes.apex_series?.soc_projection_clear || []).map(p => [new Date(p.x).getTime(), p.y]);
    stroke_dash: 6
  - entity: sensor.wam6
    name: Observed net W
    yaxis_id: power
    data_generator: return (entity.attributes.apex_series?.power_observed || []).map(p => [new Date(p.x).getTime(), p.y]);
  - entity: sensor.wam6
    name: Modeled net W
    yaxis_id: power
    data_generator: return (entity.attributes.apex_series?.power_modeled || []).map(p => [new Date(p.x).getTime(), p.y]);
  - entity: sensor.wam6
    name: Production W (weather)
    yaxis_id: power
    data_generator: return (entity.attributes.apex_series?.power_production_weather || []).map(p => [new Date(p.x).getTime(), p.y]);
  - entity: sensor.wam6
    name: Production W (clear sky)
    yaxis_id: power
    stroke_dash: 6
    data_generator: return (entity.attributes.apex_series?.power_production_clear || []).map(p => [new Date(p.x).getTime(), p.y]);
  - entity: sensor.wam6
    name: Consumption W
    yaxis_id: power
    data_generator: return (entity.attributes.apex_series?.power_consumption || []).map(p => [new Date(p.x).getTime(), p.y]);
  - entity: sensor.wam6
    name: Sun elevation (history)
    yaxis_id: sun
    data_generator: return (entity.attributes.apex_series?.sun_history || []).map(p => [new Date(p.x).getTime(), p.y]);
  - entity: sensor.wam6
    name: Sun elevation (forecast)
    yaxis_id: sun
    stroke_dash: 6
    data_generator: return (entity.attributes.apex_series?.sun_forecast || []).map(p => [new Date(p.x).getTime(), p.y]);
```

Replace `sensor.wam6` with your Battery Telemetry sensor.

## Service
`node_energy.refresh`
- Optional `entry_id` to refresh one entry.
- Without `entry_id`, refreshes all entries.

## Notes
- Card updates live as HA state updates arrive.
- ApexCharts handles tooltip/cursor/highlighting natively.
- This integration is ApexCharts-first; legacy custom card artifacts are removed.
- This project is independent and not affiliated with Meshtastic.

## Maintainer release flow (both repos)
Run from integration repo:

```bash
./scripts/release_both.sh 0.3.0
```

This publishes matching tags for the integration and setup-card repos.
