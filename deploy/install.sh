#!/usr/bin/env bash
#
# Zet JARVIS als gebruikersdienst op, zodat hij meestart met je sessie.
#
#   ./deploy/install.sh              alleen de HUD
#   ./deploy/install.sh --all        ook OpenClaw en Hermes, als die er zijn
#
# Draait bewust als *gebruikers*dienst (--user) en niet systeembreed: de
# assistent heeft je geluidsserver, je sleutels en je bestanden nodig.

set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
ALLES=0
[[ "${1:-}" == "--all" ]] && ALLES=1

if ! command -v systemctl >/dev/null; then
  echo "❌ systemd niet gevonden. Start JARVIS dan handmatig: python run_hud.py"
  exit 1
fi

if [[ ! -x "$PROJECT/venv/bin/python" ]]; then
  echo "⚠️  Geen venv gevonden in $PROJECT/venv"
  echo "   Maak die eerst:  python -m venv venv && venv/bin/pip install -r requirements.txt"
  exit 1
fi

mkdir -p "$UNIT_DIR"

installeer() {
  local naam="$1"
  cp "$PROJECT/deploy/systemd/$naam" "$UNIT_DIR/$naam"
  echo "  ✓ $naam"
}

echo "📦 Diensten plaatsen in $UNIT_DIR"
installeer jarvis-hud.service

if (( ALLES )); then
  command -v openclaw >/dev/null && installeer openclaw-gateway.service \
    || echo "  – openclaw niet gevonden, overgeslagen"
  command -v hermes   >/dev/null && installeer hermes-gateway.service \
    || echo "  – hermes niet gevonden, overgeslagen"
fi

systemctl --user daemon-reload
systemctl --user enable --now jarvis-hud.service

if (( ALLES )); then
  for d in openclaw-gateway hermes-gateway; do
    [[ -f "$UNIT_DIR/$d.service" ]] && systemctl --user enable --now "$d.service" || true
  done
fi

# Zonder lingering stoppen de diensten zodra je uitlogt.
if ! loginctl show-user "$USER" -p Linger --value 2>/dev/null | grep -q yes; then
  echo
  echo "ℹ️  Om JARVIS ook zonder ingelogde sessie te laten draaien:"
  echo "   sudo loginctl enable-linger $USER"
fi

echo
echo "✅ Klaar.  http://127.0.0.1:7332"
echo "   status:  systemctl --user status jarvis-hud"
echo "   logboek: journalctl --user -u jarvis-hud -f"
echo "   stoppen: systemctl --user disable --now jarvis-hud"
