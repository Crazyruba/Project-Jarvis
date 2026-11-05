"""
Toestemming vragen voor gevoelige acties.

De manier van vragen is inwisselbaar: in de terminal via input(), en in de HUD
via een knop in beeld. De rest van de code merkt daar niets van.
"""

from __future__ import annotations

from typing import Callable

import config

JA = {"ja", "jawel", "doe maar", "ok", "oke", "oké", "prima", "yes", "y", "j"}


def terminal_confirm(tool_name: str, args: dict) -> bool:
    """Standaard: vragen in de terminal."""
    details = ", ".join(f"{k}={v}" for k, v in args.items())
    antwoord = input(
        f"\n⚠️  JARVIS wil '{tool_name}' uitvoeren ({details}). Toestaan? (ja/nee): "
    ).strip().lower()
    return antwoord in JA


class PermissionManager:
    """Vraagt om goedkeuring voordat een gevoelige tool draait."""

    def __init__(self, confirm_func: Callable[[str, dict], bool] | None = None):
        self.confirm_func = confirm_func or terminal_confirm

    def request(self, tool_name: str, args: dict | None = None) -> bool:
        try:
            return bool(self.confirm_func(tool_name, args or {}))
        except Exception as e:
            # Lukt het vragen niet, dan is het antwoord nee.
            print(f"   ⚠️  Toestemming vragen mislukte ({e}) — actie geweigerd.")
            return False

    def describe(self, tool_name: str, args: dict | None = None) -> str:
        details = ", ".join(f"{k}={v}" for k, v in (args or {}).items())
        return f"JARVIS wil '{tool_name}' uitvoeren ({details})." if details \
            else f"JARVIS wil '{tool_name}' uitvoeren."
