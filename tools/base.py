"""
Toolregistry.

Levert de schema's in het OpenAI tool-calling formaat, want alle backends
(Nous Portal, NVIDIA NIM, OpenClaw) spreken dat protocol. Voorheen stond hier
Gemini's FunctionDeclaration.
"""

from __future__ import annotations

from typing import Callable


class ToolRegistry:
    """Houdt de tools bij, levert hun schema's en bewaakt de gevoelige acties."""

    def __init__(self, permission_manager=None):
        self._tools: dict[str, dict] = {}
        self.permissions = permission_manager

    def register(self, name: str, func: Callable, description: str,
                 parameters: dict | None = None, sensitive: bool = False) -> None:
        if parameters is None:
            parameters = {"type": "object", "properties": {}}

        self._tools[name] = {
            "func": func,
            "sensitive": sensitive,
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
        }

    def get_schemas(self) -> list[dict]:
        """De toollijst zoals de modellen die verwachten."""
        return [tool["schema"] for tool in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def is_sensitive(self, name: str) -> bool:
        tool = self._tools.get(name)
        return bool(tool and tool["sensitive"])

    def execute(self, name: str, args: dict | None = None) -> str:
        if name not in self._tools:
            return f"Fout: onbekende tool '{name}'"

        args = args or {}
        tool = self._tools[name]

        if tool["sensitive"] and self.permissions:
            if not self.permissions.request(name, args):
                return f"Actie '{name}' is geannuleerd."

        try:
            return tool["func"](**args)
        except TypeError as e:
            # Verkeerde of ontbrekende argumenten: het model mag het herstellen.
            return f"Tool '{name}' kreeg verkeerde argumenten: {e}"
        except Exception as e:
            print(f"Toolfout in '{name}': {e}")
            return f"Tool '{name}' gaf een fout: {e}"
