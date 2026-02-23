# Quickstart

## 1) Publish integration repo
```bash
cd /Users/wilhelmfrancke/Applications/CodexSandboxGeneric/ha-node-energy
git init
git add -A
git commit -m "Initial release"
git branch -M main
git remote add origin <YOUR_NODE_ENERGY_HA_REPO_URL>
./scripts/publish.sh
```

## 2) Install from HACS (UI)
- HACS -> 3 dots -> Custom repositories
- Add integration repo URL as category `Integration`
- Install `Battery Telemetry Forecast`
- Restart Home Assistant

## 3) Install ApexCharts Card
- HACS -> Frontend -> search `ApexCharts Card`
- Install and reload UI

## 4) Install setup helper card (recommended)
- HACS -> Custom repositories -> add `https://github.com/wilhel1812/node-energy-card` as `Dashboard`
- Install `Battery Telemetry Card`
- Add card type `custom:battery-telemetry-card`
- Pick entity in UI editor and save

## 5) Add integration + chart
- Settings -> Devices & Services -> Add Integration -> `Battery Telemetry Forecast`
- Configure battery/weather/start hour etc.
- Install `ApexCharts Card` from HACS Frontend.
- Add `custom:battery-telemetry-card` in dashboard and save.
