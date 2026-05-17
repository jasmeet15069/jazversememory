#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/jazversememory"
DATA_DIR="/var/lib/jazversememory"

apt-get update
apt-get install -y python3 python3-venv python3-pip rsync

mkdir -p "$APP_DIR" "$DATA_DIR"
cd "$APP_DIR"

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .

cat >/etc/jazversememory.env <<'ENV'
JAZVERSE_MEMORY_DB=/var/lib/jazversememory/jazversememory.sqlite3
JAZVERSE_MEMORY_HOST=0.0.0.0
JAZVERSE_MEMORY_PORT=8787
ENV

cp deploy/jazversememory.service /etc/systemd/system/jazversememory.service
systemctl daemon-reload
systemctl enable jazversememory
systemctl restart jazversememory
systemctl status jazversememory --no-pager
