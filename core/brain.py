"""
De router: waar gaat deze vraag heen?

Fase 1 kent één bestemming — een pratend brein (Nous of NVIDIA). De plekken
waar OpenClaw en Hermes aanhaken zijn al benoemd, zodat fase 4 en 5 alleen
nog hoeven in te vullen.
"""

from __future__ import annotations

from typing import Iterator

import config
from core.providers import BackendError, OpenAICompatLLM


class Brain:
    """Kiest een backend, bewaakt de context en valt terug bij storing."""

    def __init__(self, backend: str | None = None, model: str | None = None):
        self.backend_name = backend or config.PRIMARY_BACKEND
        self.model = model
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

    # -- denken ------------------------------------------------------------
    def build_messages(self, user_input: str, history: list[dict],
                       memory_context: str = "") -> list[dict]:
        system = config.SYSTEM_PROMPT.format(
            owner=config.OWNER_NAME,
            memory_context=memory_context or "Nog geen opgeslagen herinneringen.",
        )
        messages = [{"role": "system", "content": system}]
        messages.extend(history[-config.HUD_HISTORY_LIMIT:])
        messages.append({"role": "user", "content": user_input})
        return messages

    def stream(self, user_input: str, history: list[dict] | None = None,
               memory_context: str = "") -> Iterator[str]:
        """Streamt het antwoord; valt bij een storing stil terug op de reservebackend."""
        messages = self.build_messages(user_input, history or [], memory_context)

        try:
            yielded = False
            for piece in self._llm.stream(messages):
                yielded = True
                self.last_backend_used = self.backend_name
                yield piece
            if yielded:
                return
            raise BackendError(f"{self._llm.label} gaf een leeg antwoord.")
        except BackendError as primary_error:
            fallback = config.FALLBACK_BACKEND
            if fallback == self.backend_name or fallback not in config.BACKENDS:
                raise

            # Pas terugvallen als de primaire backend nog niets opleverde,
            # anders zou het antwoord halverwege van stem wisselen.
            try:
                reserve = OpenAICompatLLM(fallback)
                pieces = reserve.stream(messages)
                first = next(pieces, None)
                if first is None:
                    raise primary_error
                self.last_backend_used = fallback
                yield first
                yield from pieces
            except BackendError:
                raise primary_error

    # -- nog in te vullen --------------------------------------------------
    # Fase 4: taken die iets op deze pc moeten dóén gaan naar de OpenClaw
    #         Gateway — dat is backend "openclaw", hetzelfde protocol.
    # Fase 5: lange of lerende taken gaan via subprocess naar `hermes -z`.
