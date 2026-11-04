"""
Eventbus voor de HUD.

Eén bus waarop zowel de webserver als straks de voice-loop publiceren, zodat
de lampjes in beeld altijd de echte toestand tonen. Abonnees krijgen hun eigen
wachtrij; een trage browser kan de rest dus niet ophouden.
"""

from __future__ import annotations

import asyncio
import contextlib
from enum import Enum


class HudState(str, Enum):
    """De vier lampjes linksboven in de interface."""

    IDLE = "idle"            # ONLINE
    LISTENING = "listening"  # LUISTERT
    THINKING = "thinking"    # DENKT
    SPEAKING = "speaking"    # SPREEKT


class EventBus:
    """Publiceert gebeurtenissen naar alle verbonden HUD-clients."""

    MAX_QUEUE = 256

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._state: HudState = HudState.IDLE

    # -- toestand ----------------------------------------------------------
    @property
    def state(self) -> HudState:
        return self._state

    async def set_state(self, state: HudState) -> None:
        """Wissel van toestand en vertel het de HUD. Geen bericht als er niets wijzigt."""
        if state == self._state:
            return
        self._state = state
        await self.publish("state", {"value": state.value})

    @contextlib.asynccontextmanager
    async def during(self, state: HudState):
        """Blijf in deze toestand zolang het blok draait, en val daarna terug op IDLE."""
        previous = self._state
        await self.set_state(state)
        try:
            yield
        finally:
            await self.set_state(previous if previous != state else HudState.IDLE)

    # -- publiceren --------------------------------------------------------
    async def publish(self, kind: str, payload: dict | None = None) -> None:
        message = {"type": kind, **(payload or {})}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Deze client loopt achter; één verloren frame is beter dan
                # de hele bus laten wachten.
                pass

    # -- abonneren ---------------------------------------------------------
    @contextlib.contextmanager
    def subscribe(self):
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.MAX_QUEUE)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    @property
    def listener_count(self) -> int:
        return len(self._subscribers)


bus = EventBus()
