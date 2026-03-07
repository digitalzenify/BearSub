#!/usr/bin/env bash
set -euo pipefail

cd /opt/SubsDump/backend
uvicorn app:APP --host 127.0.0.1 --port 9010 --reload
