"""Eén keer per dag een groet, passend bij het tijdstip."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import config


def _dagdeel(uur: int) -> str:
    if uur < 6:
        return "Goedenacht"
    if uur < 12:
        return "Goedemorgen"
    if uur < 18:
        return "Goedemiddag"
    return "Goedenavond"


def al_gegroet(vandaag: date | None = None) -> bool:
    bestand = Path(config.GREETING_STATE_PATH)
    if not bestand.exists():
        return False
    try:
        return bestand.read_text("utf-8").strip() == (vandaag or date.today()).isoformat()
    except OSError:
        return False


def groet_eenmaal_per_dag(zeg) -> bool:
    """Groet als dat vandaag nog niet gebeurd is. Geeft terug of er gegroet is."""
    if al_gegroet():
        return False

    nu = datetime.now()
    zeg(f"{_dagdeel(nu.hour)}, {config.OWNER_NAME}. Ik ben online.")

    bestand = Path(config.GREETING_STATE_PATH)
    try:
        bestand.parent.mkdir(parents=True, exist_ok=True)
        bestand.write_text(date.today().isoformat(), "utf-8")
    except OSError:
        pass            # niet kunnen onthouden is geen reden om te stoppen
    return True
