"""
De ReAct-lus: Redeneren → Handelen → Waarnemen.

Werkt op het OpenAI tool-calling formaat, dus op elke backend die dat spreekt
(Nous Portal, NVIDIA NIM, OpenClaw). Het antwoord komt als gebeurtenissen naar
buiten, zodat de HUD tokens kan tonen terwijl ze binnenkomen en kan laten zien
welke tool draait:

    ("token", "tekst")                     stukje antwoord
    ("tool", {"name": …, "args": {…}})     tool gaat draaien
    ("tool_result", {"name": …, …})        tool is klaar
    ("error", "melding")                   het ging mis
"""

from __future__ import annotations

import json
from typing import Iterator

import config
from core.providers import BackendError


class Agent:
    """Voert tools uit tot het model een echt antwoord geeft."""

    def __init__(self, llm, tools, memory=None):
        self.llm = llm
        self.tools = tools
        self.memory = memory

    # -- context -----------------------------------------------------------
    def build_messages(self, user_input: str, history: list[dict] | None = None,
                       memory_context: str | None = None) -> list[dict]:
        if memory_context is None and self.memory is not None:
            # Alleen wat bij déze vraag past, niet het hele geheugen.
            memory_context = self.memory.context_for(user_input)

        system = config.SYSTEM_PROMPT.format(
            owner=config.OWNER_NAME,
            memory_context=memory_context or "Nog geen opgeslagen herinneringen.",
        )
        messages = [{"role": "system", "content": system}]
        messages.extend((history or [])[-config.HUD_HISTORY_LIMIT:])
        messages.append({"role": "user", "content": user_input})
        return messages

    # -- de lus ------------------------------------------------------------
    def stream(self, user_input: str, history: list[dict] | None = None,
               memory_context: str | None = None) -> Iterator[tuple[str, object]]:
        messages = self.build_messages(user_input, history, memory_context)
        schemas = self.tools.get_schemas() if self.tools else []

        for _ in range(config.MAX_STEPS):
            tekst: list[str] = []
            calls: list[dict] = []

            try:
                for kind, value in self.llm.stream_with_tools(messages, schemas):
                    if kind == "token":
                        tekst.append(value)
                        yield "token", value
                    elif kind == "tool_calls":
                        calls = value
            except BackendError as e:
                yield "error", str(e)
                return

            if not calls:
                return                      # klaar: dit was het antwoord

            # Wat het model zei plus de tools die het wil draaien.
            messages.append({
                "role": "assistant",
                "content": "".join(tekst) or None,
                "tool_calls": [
                    {
                        "id": c["id"] or f"call_{i}",
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c["arguments"] or "{}"},
                    }
                    for i, c in enumerate(calls)
                ],
            })

            for i, call in enumerate(calls):
                naam = call["name"]
                args = _parse_args(call["arguments"])

                yield "tool", {"name": naam, "args": args}
                print(f"   🔧 [tool: {naam}({args})]")

                if isinstance(args, dict):
                    resultaat = self.tools.execute(naam, args)
                else:
                    resultaat = (f"Tool '{naam}' kreeg onleesbare argumenten: "
                                 f"{call['arguments']!r}")

                yield "tool_result", {"name": naam, "result": str(resultaat)}
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"] or f"call_{i}",
                    "content": str(resultaat),
                })

        yield "token", (f" Ik liep tegen mijn stappenlimiet aan, "
                        f"{config.OWNER_NAME}. Zal ik doorgaan?")

    # -- gemakshalve -------------------------------------------------------
    def run(self, user_input: str, history: list[dict] | None = None) -> str:
        """Hele antwoord in één keer; handig voor tests en scripts."""
        stukken = []
        for kind, value in self.stream(user_input, history):
            if kind == "token":
                stukken.append(value)
            elif kind == "error":
                return str(value)
        antwoord = "".join(stukken).strip()

        if self.memory is not None:
            self.memory.log("user", user_input)
            if antwoord:
                self.memory.log("jarvis", antwoord)
        return antwoord


def _parse_args(raw: str):
    """Argumenten komen als JSON-tekst binnen; lege tekst betekent geen args."""
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw                   # de aanroeper maakt er een nette fout van
    return parsed if isinstance(parsed, dict) else raw
