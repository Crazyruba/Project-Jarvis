"""
Toolregistry met schema's afgeleid uit de functie zelf.

Een tool is een gewone Python-functie. Het JSON-schema dat de modellen nodig
hebben wordt afgeleid uit de signatuur en de docstring, zodat er niets dubbel
onderhouden hoeft te worden:

    @tool(sensitive=True)
    def write_file(path: str, content: str) -> str:
        '''Schrijf tekst naar een bestand.

        path: Volledig pad naar het bestand.
        content: De tekst die weggeschreven wordt.
        '''

Daaruit volgt naam, beschrijving, parametertypes, welke verplicht zijn, en
per parameter een omschrijving. Een verkeerd schema kan dus niet meer uit de
pas lopen met de code eronder.
"""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable, Literal, get_args, get_origin, get_type_hints

# Python-type naar JSON Schema.
_JSON_TYPES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


class ToolError(Exception):
    """Een tool is verkeerd gedefinieerd."""


def tool(_func: Callable | None = None, *, name: str | None = None,
         sensitive: bool = False):
    """Markeer een functie als tool. `sensitive` vraagt eerst om toestemming."""

    def wrap(func: Callable) -> Callable:
        func._tool = {                      # type: ignore[attr-defined]
            "name": name or func.__name__,
            "sensitive": sensitive,
        }
        return func

    return wrap(_func) if _func is not None else wrap


def _split_docstring(doc: str) -> tuple[str, dict[str, str]]:
    """Scheidt de beschrijving van de regels `parameter: uitleg`."""
    beschrijving: list[str] = []
    parameters: dict[str, str] = {}
    huidige: str | None = None

    for regel in inspect.cleandoc(doc or "").splitlines():
        gestript = regel.strip()
        match = re.match(r"^([a-z_][a-z0-9_]*)\s*:\s*(.+)$", gestript)
        if match:
            huidige = match.group(1)
            parameters[huidige] = match.group(2).strip()
        elif huidige and gestript:
            parameters[huidige] += " " + gestript       # doorlopende regel
        elif not parameters:
            beschrijving.append(gestript)
        else:
            huidige = None

    return " ".join(b for b in beschrijving if b).strip(), parameters


def _json_type(annotatie: Any, naam: str, tool_naam: str) -> dict:
    """Vertaal één annotatie naar een JSON Schema-fragment."""
    if annotatie is inspect.Parameter.empty:
        raise ToolError(
            f"Tool '{tool_naam}': parameter '{naam}' heeft geen type-annotatie. "
            "Zonder type kan er geen schema van gemaakt worden."
        )

    # Literal["up", "down"] wordt een enum: dat scheelt uitleg in de prompt.
    if get_origin(annotatie) is Literal:
        keuzes = list(get_args(annotatie))
        soort = _JSON_TYPES.get(type(keuzes[0]), "string") if keuzes else "string"
        return {"type": soort, "enum": keuzes}

    basis = get_origin(annotatie) or annotatie
    if basis not in _JSON_TYPES:
        raise ToolError(
            f"Tool '{tool_naam}': type {annotatie!r} van '{naam}' kan niet "
            "naar JSON Schema vertaald worden."
        )
    return {"type": _JSON_TYPES[basis]}


def build_schema(func: Callable) -> dict:
    """Leid het OpenAI-toolschema af uit een functie."""
    meta = getattr(func, "_tool", None)
    if meta is None:
        raise ToolError(f"{func.__name__} is niet met @tool gemarkeerd.")

    tool_naam = meta["name"]
    beschrijving, parameter_uitleg = _split_docstring(func.__doc__ or "")
    if not beschrijving:
        raise ToolError(f"Tool '{tool_naam}' heeft geen beschrijving in de docstring.")

    handtekening = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:                       # pragma: no cover - exotische annotaties
        hints = {}

    eigenschappen: dict[str, dict] = {}
    verplicht: list[str] = []

    for naam, parameter in handtekening.parameters.items():
        if naam == "self" or parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD
        ):
            continue

        annotatie = hints.get(naam, parameter.annotation)
        veld = _json_type(annotatie, naam, tool_naam)
        if naam in parameter_uitleg:
            veld["description"] = parameter_uitleg[naam]
        eigenschappen[naam] = veld

        if parameter.default is inspect.Parameter.empty:
            verplicht.append(naam)

    parameters: dict[str, Any] = {"type": "object", "properties": eigenschappen}
    if verplicht:
        parameters["required"] = verplicht

    return {
        "type": "function",
        "function": {
            "name": tool_naam,
            "description": beschrijving,
            "parameters": parameters,
        },
    }


class ToolRegistry:
    """Verzamelt tools, levert hun schema's en bewaakt de gevoelige."""

    def __init__(self, permission_manager=None):
        self._tools: dict[str, dict] = {}
        self.permissions = permission_manager

    # -- vullen ------------------------------------------------------------
    def add(self, func: Callable, sensitive: bool | None = None) -> Callable:
        """
        Neem één met @tool gemarkeerde functie op.

        `sensitive` overschrijft wat bij de decorator stond, voor tools waarvan
        pas bij het opstarten bekend is of ze om bevestiging moeten vragen.
        """
        meta = getattr(func, "_tool", None)
        if meta is None:
            raise ToolError(f"{func.__name__} is niet met @tool gemarkeerd.")

        naam = meta["name"]
        if naam in self._tools:
            raise ToolError(f"Er is al een tool met de naam '{naam}'.")

        self._tools[naam] = {
            "func": func,
            "sensitive": meta["sensitive"] if sensitive is None else sensitive,
            "schema": build_schema(func),
        }
        return func

    def add_module(self, module) -> list[str]:
        """Neem alles op wat in een module met @tool is gemarkeerd."""
        toegevoegd = []
        for _, object_ in inspect.getmembers(module, callable):
            if getattr(object_, "_tool", None) is not None:
                # Een module kan iets importeren dat elders al geregistreerd is.
                if object_._tool["name"] in self._tools:
                    continue
                self.add(object_)
                toegevoegd.append(object_._tool["name"])
        return sorted(toegevoegd)

    # -- lezen -------------------------------------------------------------
    def get_schemas(self) -> list[dict]:
        return [t["schema"] for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def is_sensitive(self, naam: str) -> bool:
        tool_ = self._tools.get(naam)
        return bool(tool_ and tool_["sensitive"])

    # -- uitvoeren ---------------------------------------------------------
    def execute(self, naam: str, args: dict | None = None) -> str:
        if naam not in self._tools:
            return f"Fout: onbekende tool '{naam}'"

        args = args or {}
        tool_ = self._tools[naam]

        if tool_["sensitive"] and self.permissions:
            if not self.permissions.request(naam, args):
                return f"Actie '{naam}' is geannuleerd."

        try:
            return str(tool_["func"](**args))
        except TypeError as e:
            # Verkeerde of ontbrekende argumenten: het model mag het herstellen.
            return f"Tool '{naam}' kreeg verkeerde argumenten: {e}"
        except Exception as e:
            print(f"Toolfout in '{naam}': {e}")
            return f"Tool '{naam}' gaf een fout: {e}"
