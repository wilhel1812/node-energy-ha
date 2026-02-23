# Node Energy (Home Assistant Integration)

Node-generic Home Assistant integration for battery/solar modeling and forecast.

## What this package contains
- `custom_components/node_energy`: integration (config flow + options flow + sensor + service)
- `www/node-energy-card.js`: local copy of the card for manual install/testing

For UI-managed updates of both backend and card, publish as **two HACS repos**:
1. Integration repo (this package)
2. Dashboard plugin repo (`ha-node-energy-card` package)

## HACS Install (Integration)
1. Push this folder as its own GitHub repository.
2. In HACS: 3 dots -> Custom repositories.
3. Add repo URL, Category = `Integration`.
4. Install `Node Energy` from HACS.
5. Restart Home Assistant.
6. Add integration: Settings -> Devices & Services -> Add Integration -> `Node Energy`.

## UI Config (per entry)
- `battery_entity` (required): battery percentage sensor for the node
- `voltage_entity` (optional)
- `weather_entity` (optional)
- `start_hour` (0-23): analysis start hour (yesterday at this hour)
- `cells_current`, `cell_mah`, `cell_v`, `horizon_days`

Create multiple entries for multiple nodes.

## Service
`node_energy.refresh`
- Optional `entry_id` field (refresh one entry)
- Without `entry_id`, refreshes all entries

## Release / Update Process
1. Update code.
2. Bump integration version:
   ```bash
   ./scripts/bump_version.sh 0.1.2
   ```
3. Commit and tag:
   ```bash
   git commit -am "Release v0.1.2"
   git tag v0.1.2
   git push && git push --tags
   ```
4. In Home Assistant, open HACS and click `Update`.

## Local manual install (fallback)
1. Copy `custom_components/node_energy` -> `<HA config>/custom_components/node_energy`
2. Restart Home Assistant
