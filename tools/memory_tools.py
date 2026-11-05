"""
Geheugentools.

Deze hebben de opslag nodig, dus ze worden per sessie gemaakt in plaats van
als losse functies gedefinieerd zoals de rest.
"""

from __future__ import annotations

from typing import Literal

from tools.registry import tool


def maak_geheugentools(memory):
    """Geef de tools terug die op dit geheugen werken."""

    @tool
    def onthoud(soort: Literal["feit", "voorkeur", "project", "doel"],
                inhoud: str) -> str:
        """Onthoud iets blijvends over de eigenaar. Gebruik dit zodra hij iets
        deelt dat later nog van pas komt.

        soort: feit, voorkeur, project of doel.
        inhoud: Wat onthouden moet worden, in één duidelijke zin.
        """
        return memory.onthoud(soort, inhoud)

    @tool
    def herinner_je(onderwerp: str = "") -> str:
        """Haal op wat je over de eigenaar weet. Zonder onderwerp krijg je alles.

        onderwerp: Waarover je iets wil weten; leeg laten geeft het hele overzicht.
        """
        if not onderwerp.strip():
            return memory.samenvatting()

        treffers = memory.zoek(onderwerp, limiet=8)
        if not treffers:
            return f"Ik weet niets over '{onderwerp}'."
        return "\n".join(f"- {f.inhoud}" for f in treffers)

    @tool(sensitive=True)
    def vergeet(onderwerp: str) -> str:
        """Verwijder wat je over een onderwerp hebt onthouden.

        onderwerp: Waarover de herinneringen weg mogen.
        """
        return memory.vergeet(onderwerp)

    return [onthoud, herinner_je, vergeet]
