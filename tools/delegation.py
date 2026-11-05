"""
Uitbesteden aan OpenClaw en Hermes Agent.

De router (het pratende brein) beantwoordt zelf wat hij weet, en zet deze twee
in wanneer er iets te *doen* valt:

  • OpenClaw  — handen op deze computer: bestanden, programma's, agenda,
                WhatsApp en Telegram. Bereikbaar via zijn OpenAI-endpoint,
                dus gewoon één chat-aanroep.
  • Hermes    — lange, meerstaps- of lerende klussen. Houdt eigen geheugen en
                skills bij in ~/.hermes/ en draait als los commando.

Beide worden alleen aangeboden als ze ook echt bereikbaar zijn; anders zou het
model een tool kiezen die gegarandeerd faalt.
"""

from __future__ import annotations

import shutil
import subprocess

import config


# ---------------------------------------------------------------------------
# OpenClaw
# ---------------------------------------------------------------------------
def openclaw_available() -> bool:
    return bool(config.BACKENDS.get("openclaw", {}).get("api_key"))


def openclaw_task(opdracht: str) -> str:
    """Geef een opdracht door aan de OpenClaw Gateway."""
    from core.providers import BackendError, OpenAICompatLLM

    if not openclaw_available():
        return ("OpenClaw is niet ingesteld. Zet OPENCLAW_GATEWAY_TOKEN in je .env "
                "en zet in openclaw.json gateway.http.endpoints.chatCompletions.enabled "
                "op true.")

    llm = OpenAICompatLLM("openclaw")
    try:
        antwoord = llm.complete([{"role": "user", "content": opdracht}]).strip()
    except BackendError as e:
        return f"OpenClaw kon de opdracht niet uitvoeren: {e}"

    return antwoord or "OpenClaw gaf geen antwoord terug."


# ---------------------------------------------------------------------------
# Hermes Agent
# ---------------------------------------------------------------------------
def hermes_available() -> bool:
    return shutil.which(config.HERMES_BIN) is not None


def hermes_task(opdracht: str) -> str:
    """Zet Hermes op een klus en geef terug wat hij ervan maakte."""
    if not hermes_available():
        return (f"Hermes is niet gevonden ({config.HERMES_BIN}). Installeren: "
                "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash")

    argumenten = [config.HERMES_BIN, "-z", opdracht]
    if config.HERMES_MODEL:
        argumenten += ["--model", config.HERMES_MODEL]

    try:
        klaar = subprocess.run(
            argumenten,
            capture_output=True,
            text=True,
            timeout=config.HERMES_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return (f"Hermes was na {config.HERMES_TIMEOUT} seconden nog bezig. "
                "De klus loopt mogelijk door; kijk in ~/.hermes/logs/.")
    except OSError as e:
        return f"Hermes kon niet starten: {e}"

    uitvoer = (klaar.stdout or "").strip()
    if klaar.returncode != 0:
        fout = (klaar.stderr or "").strip() or f"afsluitcode {klaar.returncode}"
        return f"Hermes gaf een fout: {_kort(fout)}"

    if not uitvoer:
        return "Hermes gaf niets terug."

    # Antwoorden worden voorgelezen; een muur tekst helpt niemand.
    return _kort(uitvoer, 2000)


def _kort(tekst: str, limiet: int = 500) -> str:
    tekst = tekst.strip()
    return tekst if len(tekst) <= limiet else tekst[:limiet] + "…[ingekort]"


# ---------------------------------------------------------------------------
# Registratie
# ---------------------------------------------------------------------------
def register_delegation_tools(registry) -> list[str]:
    """Bied alleen aan wat bereikbaar is. Geeft terug wat er geregistreerd is."""
    geregistreerd = []

    if openclaw_available():
        registry.register(
            name="openclaw_task",
            func=openclaw_task,
            description=(
                "Laat OpenClaw iets doen op deze computer: bestanden beheren, "
                "programma's bedienen, agenda-afspraken, of een bericht sturen via "
                "WhatsApp of Telegram. Gebruik dit voor handelingen, niet voor vragen. "
                "Beschrijf de opdracht in één duidelijke zin."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "opdracht": {
                        "type": "string",
                        "description": "Wat er moet gebeuren, in gewone taal.",
                    }
                },
                "required": ["opdracht"],
            },
            sensitive=config.DELEGATE_CONFIRM,
        )
        geregistreerd.append("openclaw_task")

    if hermes_available():
        registry.register(
            name="hermes_task",
            func=hermes_task,
            description=(
                "Zet Hermes Agent op een langere klus die meerdere stappen kost, "
                "uitgezocht moet worden, of die hij moet onthouden voor later. "
                "Hermes heeft zijn eigen geheugen en skills. Dit duurt even, dus "
                "gebruik het niet voor iets wat je zelf kunt beantwoorden."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "opdracht": {
                        "type": "string",
                        "description": "De klus, met genoeg context om zelfstandig te werken.",
                    }
                },
                "required": ["opdracht"],
            },
            sensitive=config.DELEGATE_CONFIRM,
        )
        geregistreerd.append("hermes_task")

    return geregistreerd
