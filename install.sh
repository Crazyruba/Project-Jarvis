#!/usr/bin/env bash
#
# JARVIS installeren.
#
#   ./install.sh              alles
#   ./install.sh --no-voice   alleen de HUD (geen microfoon nodig)
#
# Waarom een script en niet één pip-commando: openwakeword eist op Linux
# tflite-runtime, waarvan geen wheels bestaan voor recente Python-versies.
# JARVIS draait het wake word-model via ONNX en gebruikt tflite nergens voor,
# dus het wordt met --no-deps geïnstalleerd. Dat is niet uit te drukken in een
# requirements.txt, want --no-deps geldt daar voor het hele bestand.

set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT"

MET_SPRAAK=1
[[ "${1:-}" == "--no-voice" ]] && MET_SPRAAK=0

PIP="pip"
if [[ -x "venv/bin/pip" ]]; then
  PIP="venv/bin/pip"
  echo "📦 venv gevonden: venv/"
elif [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "⚠️  Je zit niet in een virtuele omgeving."
  echo "   Aanbevolen:  python3 -m venv venv && source venv/bin/activate"
  read -r -p "   Toch doorgaan? (j/N) " antwoord
  [[ "$antwoord" =~ ^[jJyY]$ ]] || exit 1
fi

echo "📦 Afhankelijkheden installeren…"
$PIP install --upgrade pip --quiet
$PIP install -r requirements.txt

if (( MET_SPRAAK )); then
  echo
  echo "📦 openwakeword installeren (zonder tflite-runtime)…"
  $PIP install --no-deps openwakeword

  echo
  echo "⬇️  Wake word-model ophalen…"
  $PIP show openwakeword >/dev/null && \
    $(dirname "$PIP")/python -c "
import openwakeword.utils as u
u.download_models(['hey_jarvis'])
print('✅ Wake word-model binnen.')
" || echo "⚠️  Model ophalen mislukte; de eerste start probeert het opnieuw."

  echo
  echo "⬇️  Nederlandse stem ophalen…"
  $(dirname "$PIP")/python -m voice.piper_setup || \
    echo "⚠️  Stem ophalen mislukte; JARVIS valt terug op pyttsx3."
fi

echo
echo "✅ Klaar."
echo
echo "   1. cp .env.example .env     en zet je API-sleutel erin"
if (( MET_SPRAAK )); then
  echo "   2. python -m voice.enroll   je stem eenmalig inspreken"
  echo "   3. python run_hud.py        starten"
else
  echo "   2. python run_hud.py --no-voice"
fi
