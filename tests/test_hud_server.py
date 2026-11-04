"""HUD-server: REST-routes en de volledige WebSocket-stroom."""

import pytest
from fastapi.testclient import TestClient

import config
from hud import server


@pytest.fixture
def client():
    server.history.clear()
    return TestClient(server.app)


def test_pagina_wordt_geserveerd(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "OPENCLAW HOLO-INTERFACE" in res.text


def test_backends_route(client):
    data = client.get("/api/backends").json()
    assert {b["name"] for b in data["backends"]} == set(config.BACKENDS)
    assert data["owner"] == config.OWNER_NAME


def test_onbekende_toestand_wordt_geweigerd(client):
    assert client.post("/api/state", json={"value": "zweven"}).status_code == 400


def test_toestand_zetten_werkt(client):
    res = client.post("/api/state", json={"value": "listening"})
    assert res.json() == {"ok": True, "state": "listening"}
    client.post("/api/state", json={"value": "idle"})


def test_websocket_begroet_en_streamt(client, monkeypatch):
    def nep_stream(text, history=None, memory_context=""):
        yield "Dag "
        yield "Ruben."

    monkeypatch.setattr(server.brain, "stream", nep_stream)

    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "state"
        assert ws.receive_json()["type"] == "hello"

        ws.send_json({"type": "text", "content": "hoi"})

        tokens, states, eind = [], [], None
        for _ in range(12):
            msg = ws.receive_json()
            if msg["type"] == "token":
                tokens.append(msg["text"])
            elif msg["type"] == "state":
                states.append(msg["value"])
            elif msg["type"] == "reply_end":
                eind = msg["text"]
                break

        assert "".join(tokens) == "Dag Ruben."
        assert eind == "Dag Ruben."
        # DENKT gaat vooraf aan SPREEKT.
        assert states.index("thinking") < states.index("speaking")

    assert server.history[-1] == {"role": "assistant", "content": "Dag Ruben."}


def test_backendfout_komt_als_nette_melding(client, monkeypatch):
    from core.providers import BackendError

    def kapot(text, history=None, memory_context=""):
        raise BackendError("Nous Portal: geen verbinding")
        yield  # pragma: no cover

    monkeypatch.setattr(server.brain, "stream", kapot)

    with client.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"type": "text", "content": "hoi"})

        for _ in range(8):
            msg = ws.receive_json()
            if msg["type"] == "error":
                assert "geen verbinding" in msg["text"]
                return
        pytest.fail("geen foutmelding ontvangen")


def test_lege_invoer_doet_niets(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"type": "text", "content": "   "})
        ws.send_json({"type": "backend", "name": "nvidia"})
        msg = ws.receive_json()
        assert msg["type"] == "backend"      # geen antwoord op lege invoer
    server.brain.use(config.PRIMARY_BACKEND)


def test_ptt_zonder_spraak_meldt_dat_netjes(client):
    assert server.voice is None
    with client.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"type": "ptt_start"})
        msg = ws.receive_json()
        assert msg["type"] == "error" and "--no-voice" in msg["text"]


def test_ptt_met_spraak_vraagt_de_lus_te_luisteren(client, monkeypatch):
    class NepLus:
        ready = True
        error = None
        tts = None
        def __init__(self): self.gevraagd = False
        def request_listen(self): self.gevraagd = True

    lus = NepLus()
    monkeypatch.setattr(server, "voice", lus)

    with client.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"type": "ptt_start"})
        ws.send_json({"type": "backend", "name": "nvidia"})
        assert ws.receive_json()["type"] == "backend"   # geen foutmelding ertussen
    assert lus.gevraagd is True
    server.brain.use(config.PRIMARY_BACKEND)


def test_spraakstatus_staat_in_backends(client, monkeypatch):
    assert client.get("/api/backends").json()["voice"]["enabled"] is False

    class NepLus:
        ready = True
        error = None
        class tts: name = "piper"
    monkeypatch.setattr(server, "voice", NepLus())

    stem = client.get("/api/backends").json()["voice"]
    assert stem == {"enabled": True, "ready": True, "engine": "piper", "error": None}
