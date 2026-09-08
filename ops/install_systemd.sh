#!/bin/bash
# Instalación del servicio systemd para BORJA.
# Requiere sudo — el usuario lo corre una sola vez.

set -e

SERVICE_FILE="/DATA/I-314/FINANCE/ops/borja.service"
TARGET="/etc/systemd/system/borja.service"
LOG_DIR="/var/log/borja"

if [ "$EUID" -ne 0 ]; then
  echo "Correr con sudo: sudo bash $0"
  exit 1
fi

echo "[1/4] Creando directorio de logs $LOG_DIR"
mkdir -p "$LOG_DIR"
chown i314:i314 "$LOG_DIR"

echo "[2/4] Copiando unit file a $TARGET"
cp "$SERVICE_FILE" "$TARGET"

echo "[3/4] Reload systemd + enable"
systemctl daemon-reload
systemctl enable borja.service

echo "[4/4] Start"
systemctl start borja.service
sleep 2
systemctl status borja.service --no-pager

echo ""
echo "Listo. Comandos útiles:"
echo "  sudo systemctl status borja    # ver estado"
echo "  sudo systemctl restart borja   # reiniciar"
echo "  sudo systemctl stop borja      # detener"
echo "  sudo journalctl -u borja -f    # logs en vivo"
echo "  tail -f /var/log/borja/borja.log  # logs desde archivo"
