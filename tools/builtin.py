"""
De ingebouwde tools.

Elke tool is een gewone functie; het schema volgt uit de signatuur en de
docstring (zie tools/registry.py). Antwoorden zijn kort en in het Nederlands,
want ze worden voorgelezen.
"""

from __future__ import annotations

import datetime as dt
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Literal

import config
from tools.registry import tool

MAX_LEESGROOTTE = 200_000          # bytes; grotere bestanden zijn geen spraakantwoord
MAX_ANTWOORD = 3_000               # tekens die we teruggeven aan het model

DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag",
         "zaterdag", "zondag"]
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]


# ---------------------------------------------------------------------------
# Hulpjes
# ---------------------------------------------------------------------------
def _wortels() -> list[Path]:
    """De mappen waar de bestandstools mogen komen."""
    return [Path(p).expanduser().resolve() for p in config.FILE_ROOTS]


def _veilig_pad(pad: str) -> Path:
    """
    Los een pad op en controleer dat het binnen de toegestane mappen valt.

    Een assistent die op zinnen van een taalmodel afgaat moet niet in /etc
    kunnen schrijven omdat iemand dat in een webpagina had gezet. Welke mappen
    wel mogen staat in config.FILE_ROOTS: standaard je thuismap en de projectmap.
    """
    opgelost = Path(pad).expanduser()
    if not opgelost.is_absolute():
        opgelost = Path.cwd() / opgelost
    opgelost = opgelost.resolve()

    for wortel in _wortels():
        if opgelost == wortel or wortel in opgelost.parents:
            return opgelost

    toegestaan = ", ".join(str(w) for w in _wortels())
    raise PermissionError(
        f"'{pad}' valt buiten de mappen waar ik mag komen ({toegestaan})."
    )


def _kort(tekst: str, limiet: int | None = None) -> str:
    # De grens pas hier opzoeken: als standaardargument wordt hij bij het
    # importeren vastgelegd en is hij daarna niet meer aan te passen.
    limiet = MAX_ANTWOORD if limiet is None else limiet
    tekst = tekst.strip()
    if len(tekst) <= limiet:
        return tekst
    return tekst[:limiet] + f"\n…[ingekort, {len(tekst)} tekens in totaal]"


# ---------------------------------------------------------------------------
# Tijd
# ---------------------------------------------------------------------------
@tool
def huidige_tijd() -> str:
    """Geef de huidige datum en tijd."""
    nu = dt.datetime.now()
    return (f"Het is {DAGEN[nu.weekday()]} {nu.day} {MAANDEN[nu.month - 1]} "
            f"{nu.year}, {nu.hour:02d}:{nu.minute:02d} uur.")


# ---------------------------------------------------------------------------
# Bestanden
# ---------------------------------------------------------------------------
@tool
def lees_bestand(pad: str) -> str:
    """Lees de inhoud van een tekstbestand.

    pad: Pad naar het bestand, binnen de thuismap.
    """
    try:
        doel = _veilig_pad(pad)
    except PermissionError as e:
        return str(e)

    if not doel.is_file():
        return f"Bestand niet gevonden: {pad}"
    if doel.stat().st_size > MAX_LEESGROOTTE:
        return f"{pad} is te groot om voor te lezen ({doel.stat().st_size} bytes)."

    try:
        return _kort(doel.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        return f"Ik kon het bestand niet lezen: {e}"


@tool(sensitive=True)
def schrijf_bestand(pad: str, inhoud: str) -> str:
    """Schrijf tekst naar een bestand; bestaande inhoud wordt vervangen.

    pad: Pad naar het bestand, binnen de thuismap.
    inhoud: De tekst die weggeschreven wordt.
    """
    try:
        doel = _veilig_pad(pad)
    except PermissionError as e:
        return str(e)

    bestond = doel.is_file()
    try:
        doel.parent.mkdir(parents=True, exist_ok=True)
        doel.write_text(inhoud, encoding="utf-8")
    except OSError as e:
        return f"Ik kon niet schrijven: {e}"

    return f"{'Vervangen' if bestond else 'Opgeslagen'}: {doel}"


@tool
def zoek_bestanden(map: str, woord: str, maximum: int = 20) -> str:
    """Zoek in een map naar bestanden met een woord in de naam.

    map: De map waarin gezocht wordt.
    woord: Woord dat in de bestandsnaam moet voorkomen.
    maximum: Hoeveel resultaten je hoogstens terugkrijgt.
    """
    try:
        wortel = _veilig_pad(map)
    except PermissionError as e:
        return str(e)

    if not wortel.is_dir():
        return f"Map niet gevonden: {map}"

    woord = woord.lower()
    gevonden: list[str] = []
    for pad in wortel.rglob("*"):
        # Verborgen mappen overslaan: .git en .cache leveren alleen ruis.
        if any(deel.startswith(".") for deel in pad.relative_to(wortel).parts):
            continue
        if pad.is_file() and woord in pad.name.lower():
            gevonden.append(str(pad))
            if len(gevonden) >= maximum:
                break

    if not gevonden:
        return f"Geen bestanden met '{woord}' in {map}."
    return f"{len(gevonden)} gevonden:\n" + "\n".join(gevonden)


# ---------------------------------------------------------------------------
# Systeem
# ---------------------------------------------------------------------------
@tool
def open_programma(naam: str) -> str:
    """Open een programma op deze computer.

    naam: Naam van het programma, bijvoorbeeld firefox of code.
    """
    systeem = platform.system()
    if systeem == "Darwin":
        commando = ["open", "-a", naam]
    elif systeem == "Windows":
        commando = ["cmd", "/c", "start", "", naam]
    else:
        # Op Linux eerst kijken of het bestaat; anders krijg je een
        # nietszeggende FileNotFoundError uit Popen.
        if shutil.which(naam) is None:
            return f"Ik kan '{naam}' niet vinden op dit systeem."
        commando = [naam]

    try:
        subprocess.Popen(commando, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        return f"Ik kon {naam} niet openen: {e}"
    return f"Ik open {naam}."


@tool
def schermafbeelding() -> str:
    """Maak een schermafbeelding en sla die op."""
    try:
        import pyautogui              # pas hier laden: vereist een scherm
    except Exception as e:
        return f"Schermafbeeldingen kunnen hier niet: {e}"

    map_ = Path("data/screenshots")
    map_.mkdir(parents=True, exist_ok=True)
    doel = map_ / f"scherm_{dt.datetime.now():%Y%m%d_%H%M%S}.png"

    try:
        pyautogui.screenshot().save(doel)
    except Exception as e:
        return f"Ik kon geen schermafbeelding maken: {e}"
    return f"Opgeslagen in {doel}."


@tool
def volume(richting: Literal["omhoog", "omlaag", "dempen"], stappen: int = 5) -> str:
    """Pas het volume van het systeem aan.

    richting: omhoog, omlaag of dempen.
    stappen: Hoeveel stappen omhoog of omlaag.
    """
    try:
        import pyautogui
    except Exception as e:
        return f"Het volume aanpassen kan hier niet: {e}"

    toetsen = {"omhoog": "volumeup", "omlaag": "volumedown", "dempen": "volumemute"}
    toets = toetsen.get(richting)
    if toets is None:
        return "Gebruik omhoog, omlaag of dempen."

    try:
        for _ in range(1 if richting == "dempen" else max(1, min(stappen, 20))):
            pyautogui.press(toets)
    except Exception as e:
        return f"Ik kon het volume niet aanpassen: {e}"

    return {"omhoog": "Volume omhoog.", "omlaag": "Volume omlaag.",
            "dempen": "Geluid gedempt of hersteld."}[richting]


@tool(sensitive=True)
def vergrendel_scherm() -> str:
    """Vergrendel het scherm van deze computer."""
    systeem = platform.system()
    try:
        if systeem == "Windows":
            import ctypes
            ctypes.windll.user32.LockWorkStation()          # type: ignore[attr-defined]
        elif systeem == "Darwin":
            subprocess.run(["pmset", "displaysleepnow"], check=True)
        else:
            # loginctl werkt op alles met systemd; xdg-screensaver als terugval.
            for commando in (["loginctl", "lock-session"],
                             ["xdg-screensaver", "lock"]):
                if shutil.which(commando[0]) and \
                        subprocess.run(commando).returncode == 0:
                    break
            else:
                return "Ik kon geen manier vinden om het scherm te vergrendelen."
    except Exception as e:
        return f"Ik kon het scherm niet vergrendelen: {e}"
    return "Scherm vergrendeld."


# ---------------------------------------------------------------------------
# Web
# ---------------------------------------------------------------------------
@tool
def zoek_op_het_web(zoekopdracht: str, aantal: int = 3) -> str:
    """Zoek actuele informatie op het web.

    zoekopdracht: Waar je naar zoekt.
    aantal: Hoeveel resultaten je wil, hoogstens tien.
    """
    if not (config.GOOGLE_SEARCH_API_KEY and config.GOOGLE_SEARCH_ENGINE_ID):
        return ("Zoeken op het web is niet ingesteld. Zet GOOGLE_SEARCH_API_KEY "
                "en GOOGLE_SEARCH_ENGINE_ID in je .env.")

    import requests

    try:
        antwoord = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": config.GOOGLE_SEARCH_API_KEY,
                "cx": config.GOOGLE_SEARCH_ENGINE_ID,
                "q": zoekopdracht,
                "num": max(1, min(aantal, 10)),
            },
            timeout=10,
        )
        antwoord.raise_for_status()
        treffers = antwoord.json().get("items", [])
    except Exception as e:
        return f"Zoeken mislukte: {e}"

    if not treffers:
        return f"Geen resultaten voor '{zoekopdracht}'."

    regels = [f"• {t.get('title', '')}\n  {t.get('snippet', '')}\n  {t.get('link', '')}"
              for t in treffers]
    return _kort("\n\n".join(regels))
