#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <version> (e.g. 0.2.0)"
  exit 1
fi

VER="$1"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CARD_DIR="${ROOT_DIR}/../ha-node-energy-card"

if [[ ! -d "${CARD_DIR}/.git" ]]; then
  echo "Expected sibling card repo at: ${CARD_DIR}"
  exit 1
fi

echo "==> Releasing integration ${VER}"
cd "${ROOT_DIR}"
"${ROOT_DIR}/scripts/bump_version.sh" "${VER}"
git add custom_components/node_energy/manifest.json || true
git commit -m "Release v${VER}" || true
git tag -f "v${VER}"
git push origin HEAD
git push origin "v${VER}" --force

echo "==> Releasing setup card ${VER}"
cd "${CARD_DIR}"
git add -A
git commit -m "Release v${VER}" || true
git tag -f "v${VER}"
git push origin HEAD
git push origin "v${VER}" --force

echo "Done. Released integration + card as v${VER}"
