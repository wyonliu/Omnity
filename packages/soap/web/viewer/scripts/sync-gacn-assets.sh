#!/usr/bin/env bash
# 从 GenerativeAgentsCN 同步 village 素材与示例 movement.json（不入库，见 .gitignore）
set -euo pipefail
VIEWER_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${VIEWER_ROOT}/public/vendor/generative-agents-cn"
ASSETS_SRC="generative_agents/frontend/static/assets"
MOVEMENT_URL="https://raw.githubusercontent.com/x-glacier/GenerativeAgentsCN/main/generative_agents/results/compressed/example/movement.json"
REPO="https://github.com/x-glacier/GenerativeAgentsCN.git"

mkdir -p "${DEST}/assets" "${DEST}/example"
TMP="$(mktemp -d)"
cleanup() { rm -rf "${TMP}"; }
trap cleanup EXIT

echo "Cloning shallow ${REPO} …"
git clone --depth 1 "${REPO}" "${TMP}/gacn"

echo "Rsync assets → ${DEST}/assets/"
rsync -a "${TMP}/gacn/${ASSETS_SRC}/" "${DEST}/assets/"

echo "Downloading example movement.json …"
curl -fsSL -o "${DEST}/example/movement.json" "${MOVEMENT_URL}"

echo "Done. Tilemap: ${DEST}/assets/village/tilemap/tilemap.json"
echo "Replay:    ${DEST}/example/movement.json"
