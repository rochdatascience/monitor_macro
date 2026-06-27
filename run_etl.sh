#!/usr/bin/env bash
# Execução do pipeline macroeconômico (Linux/servidor com cron).
set -euo pipefail

cd "$(dirname "$0")"

# Ative o virtualenv se existir
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python3 src/orquestrador.py
