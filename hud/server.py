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

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from core.brain import Brain
from core.providers import BackendError, OpenAICompatLLM, list_backends
from hud.events import HudState, bus

STATIC_DIR = Path(__file__).parent / "static"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # De spraakthread publiceert op deze lus.
    bus.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="JARVIS Holo-Interface", docs_url=None, redoc_url=None,
              lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

brain = Brain()
history: list[dict] = []
_current_task: asyncio.Task | None = None

# De spraaklus draait in een eigen thread en wordt door run_hud.py gezet.
voice = None



def attach_voice(loop) -> None:
    """Koppel een VoiceLoop, zodat push-to-talk in de HUD werkt."""
    global voice
    voice = loop


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
        "voice": {
            "enabled": voice is not None,
            "ready": bool(voice and voice.ready),
            "engine": getattr(getattr(voice, "tts", None), "name", None),
            "error": getattr(voice, "error", None),
        },
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
        "voice": {
            "enabled": voice is not None,
            "ready": bool(voice and voice.ready),
            "engine": getattr(getattr(voice, "tts", None), "name", None),
            "error": getattr(voice, "error", None),
        },
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

    elif kind == "ptt_start":
        if voice is None:
            await bus.publish("error", {
                "text": "Spraak staat uit. Start met `python run_hud.py` (zonder --no-voice)."
            })
        elif not voice.ready:
            await bus.publish("error", {
                "text": voice.error or "Spraak is nog aan het opstarten…"
            })
        else:
            voice.request_listen()

    elif kind == "ptt_stop":
        # De opname loopt een vaste tijd door; loslaten hoeft niets te doen.
        pass


async def generate_reply(text: str) -> str:
    """
    Laat het brein antwoorden en stream het woord voor woord naar de HUD.

    Zet zelf geen toestanden en meldt de vraag niet: dat doet de aanroeper,
    omdat de spraaklus die al beheert. Geeft het hele antwoord terug.
    """
    queue: asyncio.Queue = asyncio.Queue()
    pieces: list[str] = []

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
    eerste = True

    while True:
        kind, value = await queue.get()
        if kind == "done":
            break
        if kind == "error":
            await bus.publish("error", {"text": value})
            await worker
            return ""
        if eerste:
            await bus.set_state(HudState.SPEAKING)
            await bus.publish("reply_start", {"backend": brain.last_backend_used})
            eerste = False
        pieces.append(value)
        await bus.publish("token", {"text": value})

    await worker

    reply = "".join(pieces).strip()
    if reply:
        await bus.publish("reply_end", {"text": reply})
    return reply


async def _answer(text: str):
    """Tekstinvoer uit de HUD: vraag tonen, antwoorden, terug naar rust."""
    await bus.publish("message", {"role": "user", "text": text})
    history.append({"role": "user", "content": text})

    await bus.set_state(HudState.THINKING)
    try:
        reply = await generate_reply(text)
        if reply:
            history.append({"role": "assistant", "content": reply})
    except asyncio.CancelledError:
        await bus.publish("error", {"text": "Afgebroken."})
        raise
    finally:
        await bus.set_state(HudState.IDLE)


def respond_from_voice(text: str) -> str:
    """
    Aanroeppunt voor de spraakthread.

    De spraaklus beheert zijn eigen toestanden en heeft het gesprokene al
    gemeld, dus hier alleen het antwoord. Blokkeert tot het antwoord klaar is,
    want de lus moet het daarna uitspreken.
    """
    loop = bus._loop
    if loop is None or loop.is_closed():
        return ""

    history.append({"role": "user", "content": text})
    future = asyncio.run_coroutine_threadsafe(generate_reply(text), loop)
    try:
        reply = future.result(timeout=config.LLM_TIMEOUT + 30)
    except Exception as e:
        asyncio.run_coroutine_threadsafe(
            bus.publish("error", {"text": f"Geen antwoord: {e}"}), loop)
        return ""
    if reply:
        history.append({"role": "assistant", "content": reply})
    return reply
