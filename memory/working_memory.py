"""
Werkgeheugen: het gesprek van deze sessie, in RAM.

Berichten staan in de vorm die de modellen verwachten
({"role": "user"|"assistant", "content": "…"}), zodat ze zo naar de backend
kunnen. Voorheen stonden hier Gemini-objecten.
"""

from __future__ import annotations


class WorkingMemory:
    """Het lopende gesprek, afgekapt zodat het niet eindeloos groeit."""

    def __init__(self, max_turns: int = 20):
        self.history: list[dict] = []
        self.max_turns = max_turns

    # -- schrijven ---------------------------------------------------------
    def add(self, role: str, content: str) -> None:
        if not content:
            return
        self.history.append({"role": role, "content": content})
        self._trim()

    def add_user(self, text: str) -> None:
        self.add("user", text)

    def add_assistant(self, text: str) -> None:
        self.add("assistant", text)

    # Oude naam, toen het antwoord nog "model" heette.
    add_model = add_assistant

    # -- lezen -------------------------------------------------------------
    def get(self) -> list[dict]:
        return self.history

    def recent(self, limit: int) -> list[dict]:
        return self.history[-limit:] if limit else list(self.history)

    # -- onderhoud ---------------------------------------------------------
    def _trim(self) -> None:
        maximum = self.max_turns * 2        # vraag + antwoord per beurt
        if len(self.history) > maximum:
            self.history = self.history[-maximum:]

    def clear(self) -> None:
        self.history.clear()

    # -- gedraagt zich als een lijst ---------------------------------------
    def __len__(self) -> int:
        return len(self.history)

    def __iter__(self):
        return iter(self.history)

    def __getitem__(self, index):
        return self.history[index]

    def append(self, message: dict) -> None:
        self.history.append(message)
        self._trim()
