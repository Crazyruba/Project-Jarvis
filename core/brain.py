"""
De router: waar gaat deze vraag heen?

Kiest een backend, laat de agent zijn tools gebruiken, en valt bij een storing
terug op de reservebackend — maar alleen zolang er nog niets naar buiten is
gegaan, anders zou een antwoord halverwege van stem wisselen.

Naar buiten komen gebeurtenissen, geen kale tekst, zodat de HUD ook kan tonen
welke tool draait:

    ("token", "tekst") · ("tool", {...}) · ("tool_result", {...}) · ("error", "…")
"""

from __future__ import annotations

from typing import Iterator

import config
from core.agent import Agent
from core.providers import BackendError, OpenAICompatLLM


class Brain:
    """Kiest een backend, bewaakt de context en valt terug bij storing."""

    def __init__(self, backend: str | None = None, model: str | None = None,
                 tools=None, memory=None):
        self.backend_name = backend or config.PRIMARY_BACKEND
        self.model = model
        self.tools = tools
        self.memory = memory
        self._llm = OpenAICompatLLM(self.backend_name, model)
        self.last_backend_used: str | None = None

    # -- instellingen ------------------------------------------------------
    def use(self, backend: str, model: str | None = None) -> None:
        """Wissel van backend (het tandwiel rechtsboven in de HUD)."""
        self._llm = OpenAICompatLLM(backend, model)
        self.backend_name = backend
        self.model = model

    @property
    def label(self) -> str:
        return self._llm.label

    def _agent(self, llm) -> Agent:
        return Agent(llm=llm, tools=self.tools, memory=self.memory)

    # -- context -----------------------------------------------------------
    def build_messages(self, user_input: str, history: list[dict] | None = None,
                       memory_context: str = "") -> list[dict]:
        return self._agent(self._llm).build_messages(
            user_input, history or [], memory_context or None)

    # -- denken ------------------------------------------------------------
    def stream_events(self, user_input: str, history: list[dict] | None = None,
                      memory_context: str = "") -> Iterator[tuple[str, object]]:
        """Gebeurtenissen van de agent, met terugval op de reservebackend."""
        eerste = self._agent(self._llm).stream(
            user_input, history, memory_context or None)

        geleverd = False
        fout: str | None = None

        try:
            for kind, value in eerste:
                if kind == "error" and not geleverd:
                    fout = str(value)       # nog niets getoond: reserve mag het proberen
                    break
                geleverd = True
                yield kind, value
        except BackendError as e:
            if geleverd:
                raise
            fout = str(e)

        if fout is None:
            self.last_backend_used = self.backend_name
            return

        reserve = config.FALLBACK_BACKEND
        if reserve == self.backend_name or reserve not in config.BACKENDS:
            yield "error", fout
            return

        try:
            llm = OpenAICompatLLM(reserve)
            for kind, value in self._agent(llm).stream(
                    user_input, history, memory_context or None):
                if kind == "error" and not geleverd:
                    yield "error", fout     # meld de oorspronkelijke fout
                    return
                geleverd = True
                self.last_backend_used = reserve
                yield kind, value
        except BackendError:
            yield "error", fout

    def stream(self, user_input: str, history: list[dict] | None = None,
               memory_context: str = "") -> Iterator[str]:
        """Alleen de tekst, voor aanroepers die geen tools hoeven te tonen."""
        for kind, value in self.stream_events(user_input, history, memory_context):
            if kind == "token":
                yield value
            elif kind == "error":
                raise BackendError(str(value))

    # -- nog in te vullen --------------------------------------------------
    # Fase 4: taken die iets op deze pc moeten dóén gaan naar de OpenClaw
    #         Gateway — dat is backend "openclaw", hetzelfde protocol.
    # Fase 5: lange of lerende taken gaan via subprocess naar `hermes -z`.
