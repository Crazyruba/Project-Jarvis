"""HUD-server: REST-routes en de volledige WebSocket-stroom."""

import pytest
from fastapi.testclient import TestClient

import config
from hud import server


@pytest.fixture
def client():
    server.history.clear()
    # Binnen `with` draait de lifespan, zodat de eventbus de lus van de server
    # kent. Zonder dat kan een thread er niets op publiceren.
    with TestClient(server.app) as c:
        yield c


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
        yield "token", "Dag "
        yield "token", "Ruben."

    monkeypatch.setattr(server.brain, "stream_events", nep_stream)

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
    def kapot(text, history=None, memory_context=""):
        yield "error", "Nous Portal: geen verbinding"

    monkeypatch.setattr(server.brain, "stream_events", kapot)

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


def test_toolgebruik_is_zichtbaar_in_de_hud(client, monkeypatch):
    def met_tool(text, history=None, memory_context=""):
        yield "tool", {"name": "get_time", "args": {}}
        yield "tool_result", {"name": "get_time", "result": "Het is drie uur."}
        yield "token", "Het is drie uur."

    monkeypatch.setattr(server.brain, "stream_events", met_tool)

    with client.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"type": "text", "content": "hoe laat is het"})

        soorten = []
        for _ in range(12):
            msg = ws.receive_json()
            soorten.append(msg["type"])
            if msg["type"] == "tool":
                assert msg["name"] == "get_time"
            if msg["type"] == "reply_end":
                break

        assert "tool" in soorten
        assert "tool_result" in soorten
        assert soorten.index("tool") < soorten.index("token")


def test_bevestiging_vanuit_de_hud(client):
    """Een gevoelige tool vraagt toestemming; de knop in beeld beslist."""
    import asyncio
    import threading

    uitkomst = {}

    with client.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()

        # Doe alsof de agent (in een thread) om toestemming vraagt.
        def vraag():
            uitkomst["toegestaan"] = server._confirm_in_hud(
                "write_file", {"path": "test.txt"})

        t = threading.Thread(target=vraag)
        t.start()

        melding = ws.receive_json()
        assert melding["type"] == "confirm"
        assert melding["tool"] == "write_file"

        ws.send_json({"type": "confirm", "id": melding["id"], "allow": True})
        klaar = ws.receive_json()
        assert klaar["type"] == "confirm_done" and klaar["allowed"] is True

        t.join(timeout=10)

    assert uitkomst["toegestaan"] is True


def test_weigeren_blokkeert_de_actie(client):
    import threading

    uitkomst = {}
    with client.websocket_connect("/ws") as ws:
        ws.receive_json(); ws.receive_json()

        t = threading.Thread(
            target=lambda: uitkomst.update(
                toegestaan=server._confirm_in_hud("lock_screen", {})))
        t.start()

        melding = ws.receive_json()
        ws.send_json({"type": "confirm", "id": melding["id"], "allow": False})
        ws.receive_json()
        t.join(timeout=10)

    assert uitkomst["toegestaan"] is False
