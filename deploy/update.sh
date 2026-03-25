#!/usr/bin/env bash
set -euo pipefail

# Quick update: pull latest code, rebuild, restart
# Usage: bash update.sh

echo "[Ome] Pulling latest code..."
cd "$(dirname "$0")/.."
git pull origin main

echo "[Ome] Rebuilding..."
cd deploy

if docker compose version &>/dev/null 2>&1; then
    DC="docker compose"
else
    DC="docker-compose"
fi

$DC build --no-cache ome-server
$DC up -d ome-server

echo "[Ome] ✦ Updated and restarted! ✦"
