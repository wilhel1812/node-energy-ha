#!/usr/bin/env bash
set -euo pipefail
if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Set remote first: git remote add origin <repo-url>"
  exit 1
fi
VER=$(python - <<'PY'
import json
from pathlib import Path
m=json.loads(Path('custom_components/node_energy/manifest.json').read_text())
print(m['version'])
PY
)

git add -A
git commit -m "Release v${VER}" || true
git tag -f "v${VER}"
git push origin HEAD
git push origin "v${VER}" --force

echo "Published integration release v${VER}"
