#!/usr/bin/env bash
# Reinicia el web server de BORJA (uvicorn en 127.0.0.1:4151) para cargar cambios de código.
# Correr desde el entorno donde efectivamente corre el server (no la consola sandboxeada).
set -euo pipefail
cd /opt/BORJA

echo "→ matando uvicorn en 4151…"
pkill -f "uvicorn backend.main:app" 2>/dev/null || echo "  (no había uno corriendo)"
sleep 2

echo "→ relanzando…"
nohup .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 4151 --log-level info \
  > /tmp/borja_web.log 2>&1 &
sleep 3

if curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:4151/ | grep -qE "200|303"; then
  echo "✓ arriba en http://127.0.0.1:4151  → /hoja (sidebar: Hoja de evidencia)"
else
  echo "✗ no respondió — revisá /tmp/borja_web.log"
fi
