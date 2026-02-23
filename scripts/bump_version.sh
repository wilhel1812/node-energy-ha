#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "usage: $0 <new-version> (e.g. 0.1.2)"
  exit 1
fi
VER="$1"
python - <<PY
import json, pathlib
for p in [
  pathlib.Path('custom_components/node_energy/manifest.json'),
]:
    data=json.loads(p.read_text())
    data['version']='$VER'
    p.write_text(json.dumps(data, indent=2)+"\n")
print('updated version to', '$VER')
PY
