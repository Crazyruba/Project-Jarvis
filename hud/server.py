"""
HUD-server — FastAPI op loopback.

  GET  /              de interface
  WS   /ws            state · token · message · level · tool · error
  GET  /api/health    status per backend (voor het tandwiel)
  GET  /api/backends  welke backends bestaan en zijn ingesteld
  POST /api/say       laat JARVIS iets zeggen (voice-loop, fase 2)
  POST /api/state     zet de toestand (voice-loop, fase 2)
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from core.brain import Brain
from core.providers import BackendError, OpenAICompatLLM, list_backends
from hud.events import HudState, bus

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="JARVIS Holo-Interface", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

brain = Brain()
history: list[dict] = []
_current_task: asyncio.Task | None = None


# ---------------------------------------------------------------------------
# Pagina
# ---------------------------------------------------------------------------
@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------
@app.get("/api/backends")
async def backends():
    return {
        "backends": [b.__dict__ for b in list_backends()],
        "active": brain.backend_name,
        "primary": config.PRIMARY_BACKEND,
        "fallback": config.FALLBACK_BACKEND,
        "owner": config.OWNER_NAME,
        "title": config.HUD_TITLE,
        "subtitle": config.HUD_SUBTITLE,
    }


@app.get("/api/health")
async def health():
    """Controleert elke backend apart. Doet netwerkverkeer, dus niet in een lus aanroepen."""
    results = await asyncio.gather(
        *(asyncio.to_thread(OpenAICompatLLM(b.name).health) for b in list_backends())
    )
    return {"backends": results, "active": brain.backend_name}


class SayRequest(BaseModel):
    text: str
    role: str = "jarvis"


@app.post("/api/say")
async def say(req: SayRequest):
    await bus.publish("message", {"role": req.role, "text": req.text})
    return {"ok": True}


class StateRequest(BaseModel):
    value: str


@app.post("/api/state")
async def set_state(req: StateRequest):
    try:
        await bus.set_state(HudState(req.value))
    except ValueError:
        return JSONResponse({"ok": False, "error": f"onbekende toestand: {req.value}"},
                            status_code=400)
    return {"ok": True, "state": bus.state.value}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()

    with bus.subscribe() as queue:
        await ws.send_json({"type": "state", "value": bus.state.value})
        await ws.send_json({
            "type": "hello",
            "owner": config.OWNER_NAME,
            "backend": brain.backend_name,
            "label": brain.label,
        })

        pump = asyncio.create_task(_pump(ws, queue))
        try:
            while True:
                data = await ws.receive_json()
                await _handle(data)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            with contextlib.suppress(Exception):
                await ws.send_json({"type": "error", "text": str(e)})
        finally:
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump


async def _pump(ws: WebSocket, queue: asyncio.Queue):
    """Stuurt alles van de bus door naar deze browser."""
    while True:
        message = await queue.get()
        await ws.send_json(message)


async def _handle(data: dict):
    global _current_task

    kind = data.get("type")

    if kind == "text":
        text = (data.get("content") or "").strip()
        if not text:
            return
        if _current_task and not _current_task.done():
            return  # er loopt al een antwoord
        _current_task = asyncio.create_task(_answer(text))

    elif kind == "cancel":
        if _current_task and not _current_task.done():
            _current_task.cancel()
        await bus.set_state(HudState.IDLE)

    elif kind == "backend":
        name = data.get("name")
        if name in config.BACKENDS:
            brain.use(name, data.get("model") or None)
            await bus.publish("backend", {"name": name, "label": brain.label})

    elif kind in ("ptt_start", "ptt_stop"):
        # Fase 2 koppelt hier de microfoon aan.
        await bus.publish("error", {
            "text": "Spraak komt in fase 2 — typ voorlopig je bericht."
        })


async def _answer(text: str):
    """Laat het brein antwoorden en stream het woord voor woord naar de HUD."""
    await bus.publish("message", {"role": "user", "text": text})
    history.append({"role": "user", "content": text})

    await bus.set_state(HudState.THINKING)
    pieces: list[str] = []

    try:
        queue: asyncio.Queue = asyncio.Queue()

        def produce():
            try:
                for piece in brain.stream(text, history[:-1]):
                    queue.put_nowait(("token", piece))
            except BackendError as e:
                queue.put_nowait(("error", str(e)))
            except Exception as e:  # pragma: no cover - onverwacht
                queue.put_nowait(("error", f"Onverwachte fout: {e}"))
            finally:
                queue.put_nowait(("done", None))

        worker = asyncio.create_task(asyncio.to_thread(produce))
        first_token = True

        while True:
            kind, value = await queue.get()
            if kind == "done":
                break
            if kind == "error":
                await bus.publish("error", {"text": value})
                await bus.set_state(HudState.IDLE)
                await worker
                return
            if first_token:
                await bus.set_state(HudState.SPEAKING)
                await bus.publish("reply_start", {"backend": brain.last_backend_used})
                first_token = False
            pieces.append(value)
            await bus.publish("token", {"text": value})

        await worker

        reply = "".join(pieces).strip()
        if reply:
            history.append({"role": "assistant", "content": reply})
            await bus.publish("reply_end", {"text": reply})

    except asyncio.CancelledError:
        await bus.publish("error", {"text": "Afgebroken."})
        raise
    finally:
        await bus.set_state(HudState.IDLE)
