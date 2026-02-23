# Quickstart

## 1) Create GitHub repos
Create two empty GitHub repositories:
- `node-energy-ha` (integration)
- `node-energy-card` (dashboard card)

## 2) Publish integration repo
```bash
cd /Users/wilhelmfrancke/Applications/CodexSandboxGeneric/ha-node-energy
git init
git add -A
git commit -m "Initial release"
git branch -M main
git remote add origin <YOUR_NODE_ENERGY_HA_REPO_URL>
./scripts/publish.sh
```

## 3) Publish card repo
```bash
cd /Users/wilhelmfrancke/Applications/CodexSandboxGeneric/ha-node-energy-card
git init
git add -A
git commit -m "Initial release"
git branch -M main
git remote add origin <YOUR_NODE_ENERGY_CARD_REPO_URL>
./publish.sh 0.1.0
```

## 4) Install from HACS (UI)
- HACS -> 3 dots -> Custom repositories
- Add integration repo URL as category `Integration`
- Add card repo URL as category `Dashboard`
- Install both
- Restart Home Assistant

## 5) Add card resource
If HACS plugin install does not auto-add resource:
- URL: `/hacsfiles/node-energy-card.js`
- Type: `module`

## 6) Add integration + card
- Settings -> Devices & Services -> Add Integration -> `Node Energy`
- Configure battery/weather/start hour etc.

Card YAML:
```yaml
type: custom:node-energy-card
entity: sensor.node_energy
cells: 2
days: 7
```
