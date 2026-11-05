"""
Providerlaag — één OpenAI-compatibele client voor alle backends.

Nous Portal, NVIDIA NIM en de OpenClaw Gateway spreken alle drie het
OpenAI chat-completions protocol. Het enige verschil is de base_url en
de sleutel, dus één klasse volstaat.

    llm = OpenAICompatLLM("nous")
    for stuk in llm.stream([{"role": "user", "content": "Hoi"}]):
        print(stuk, end="")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import config


class BackendError(RuntimeError):
    """De backend was niet bruikbaar (geen sleutel, netwerk, API-fout)."""


class BackendNotConfigured(BackendError):
    """Er staat geen API-sleutel ingesteld voor deze backend."""


@dataclass(frozen=True)
class BackendInfo:
    name: str
    label: str
    base_url: str
    model: str
    configured: bool


def list_backends() -> list[BackendInfo]:
    """Alle bekende backends met hun instelbaarheid — voert geen netwerkverkeer uit."""
    out = []
    for name, cfg in config.BACKENDS.items():
        out.append(
            BackendInfo(
                name=name,
                label=cfg["label"],
                base_url=cfg["base_url"],
                model=cfg["model"],
                configured=bool(cfg.get("api_key")),
            )
        )
    return out


class OpenAICompatLLM:
    """Praat met één backend. Streamt standaard, want de HUD toont tokens."""

    def __init__(self, backend: str, model: str | None = None):
        if backend not in config.BACKENDS:
            raise BackendError(f"Onbekende backend: {backend!r}")

        cfg = config.BACKENDS[backend]
        self.backend = backend
        self.label = cfg["label"]
        self.model = model or cfg["model"]
        self.base_url = cfg["base_url"]
        self._api_key = cfg.get("api_key")
        self._client = None

    # -- intern ------------------------------------------------------------
    def _ensure_client(self):
        if self._client is not None:
            return self._client

        if not self._api_key:
            raise BackendNotConfigured(
                f"Geen API-sleutel voor {self.label}. "
                f"Zet de bijbehorende sleutel in je .env."
            )

        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover - afhankelijkheid ontbreekt
            raise BackendError(
                "De 'openai'-package ontbreekt. Draai: pip install -r requirements.txt"
            ) from e

        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self._api_key,
            timeout=config.LLM_TIMEOUT,
            max_retries=1,
        )
        return self._client

    # -- publiek -----------------------------------------------------------
    def stream(self, messages: list[dict]) -> Iterator[str]:
        """Geef het antwoord stuk voor stuk terug, zodat de ondertitel meeloopt."""
        client = self._ensure_client()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=config.LLM_TEMPERATURE,
                max_tokens=config.LLM_MAX_TOKENS,
                stream=True,
            )
            for chunk in response:
                if not chunk.choices:
                    continue
                piece = chunk.choices[0].delta.content
                if piece:
                    yield piece
        except BackendError:
            raise
        except Exception as e:
            raise BackendError(f"{self.label}: {_kort(e)}") from e

    def stream_with_tools(self, messages: list[dict], tools: list[dict] | None = None):
        """
        Zoals stream(), maar met tools erbij.

        Levert ("token", tekst) zolang het model gewoon praat, en aan het eind
        eenmalig ("tool_calls", [...]) als het tools wil aanroepen. De argumenten
        komen in stukjes binnen, dus die worden hier per index samengevoegd.
        """
        if not tools:
            for piece in self.stream(messages):
                yield "token", piece
            return

        client = self._ensure_client()
        partial: dict[int, dict] = {}

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                temperature=config.LLM_TEMPERATURE,
                max_tokens=config.LLM_MAX_TOKENS,
                stream=True,
            )
            for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if getattr(delta, "content", None):
                    yield "token", delta.content

                for call in (getattr(delta, "tool_calls", None) or []):
                    slot = partial.setdefault(
                        call.index, {"id": "", "name": "", "arguments": ""})
                    if call.id:
                        slot["id"] = call.id
                    fn = getattr(call, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            slot["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            slot["arguments"] += fn.arguments
        except BackendError:
            raise
        except Exception as e:
            raise BackendError(f"{self.label}: {_kort(e)}") from e

        if partial:
            yield "tool_calls", [partial[i] for i in sorted(partial)]

    def complete(self, messages: list[dict]) -> str:
        """Alles in één keer — handig voor tests en de router."""
        return "".join(self.stream(messages))

    def health(self) -> dict:
        """Korte controle: staat de sleutel ingesteld en antwoordt de backend?"""
        if not self._api_key:
            return {
                "backend": self.backend,
                "label": self.label,
                "ok": False,
                "reason": "geen API-sleutel ingesteld",
            }
        try:
            client = self._ensure_client()
            client.models.list()
            return {"backend": self.backend, "label": self.label, "ok": True}
        except Exception as e:
            return {
                "backend": self.backend,
                "label": self.label,
                "ok": False,
                "reason": _kort(e),
            }


def _kort(e: Exception, limit: int = 180) -> str:
    """Houd foutmeldingen leesbaar in de HUD."""
    text = str(e).strip() or e.__class__.__name__
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
