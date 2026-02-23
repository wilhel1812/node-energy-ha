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
- Install `Node Energy`
- Restart Home Assistant

## 3) Install ApexCharts Card
- HACS -> Frontend -> search `ApexCharts Card`
- Install and reload UI

## 4) Add integration + chart
- Settings -> Devices & Services -> Add Integration -> `Node Energy`
- Configure battery/weather/start hour etc.
- Add an ApexCharts card in Dashboard and use:
  - `entity.attributes.apex_series`
  - Example YAML from `README.md`
