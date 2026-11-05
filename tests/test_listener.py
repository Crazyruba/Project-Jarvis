"""Opnemen met stiltedetectie, en de groet."""

from datetime import date

import numpy as np
import pytest

import config
from voice.listener import Microfoon, Opname, rms


# --- niveaumeting -----------------------------------------------------------

def test_rms_van_stilte():
    assert rms(np.zeros(100, dtype="float32")) == 0.0


def test_rms_van_leeg_blok():
    assert rms(np.array([], dtype="float32")) == 0.0


def test_luider_geeft_hogere_rms():
    zacht = np.full(100, 0.01, dtype="float32")
    luid = np.full(100, 0.5, dtype="float32")
    assert rms(zacht) < rms(luid)


# --- opnemen met een nagebootste microfoon ---------------------------------

class NepStroom:
    """Speelt een reeks blokken af alsof het de microfoon is."""

    def __init__(self, niveaus, blokgrootte):
        self.niveaus = list(niveaus)
        self.blokgrootte = blokgrootte
        self.gelezen = 0

    def read(self, _frames):
        niveau = self.niveaus[self.gelezen] if self.gelezen < len(self.niveaus) else 0.0
        self.gelezen += 1
        blok = np.full((self.blokgrootte, 1), niveau, dtype="float32")
        return blok, False

    def __enter__(self): return self
    def __exit__(self, *a): return False


def _neem_op(monkeypatch, niveaus, **kwargs):
    mic = Microfoon()
    stroom = NepStroom(niveaus, mic.blokgrootte)

    import sys, types
    nep_sd = types.SimpleNamespace(InputStream=lambda **kw: stroom)
    monkeypatch.setitem(sys.modules, "sounddevice", nep_sd)
    return mic.neem_op(**kwargs), stroom


def test_stopt_na_stilte(monkeypatch):
    # 8 blokken ruismeting, dan spraak, dan stilte.
    niveaus = [0.001] * 8 + [0.3] * 20 + [0.0] * 200
    opname, stroom = _neem_op(monkeypatch, niveaus, stilte_na=0.2, max_seconden=10)

    assert opname.had_spraak is True
    # Lang niet alle 200 stille blokken: hij kapt af zodra het stil blijft.
    assert stroom.gelezen < 60
    assert opname.seconden < 3


def test_stopt_als_er_niets_gezegd_wordt(monkeypatch):
    niveaus = [0.001] * 500
    opname, stroom = _neem_op(monkeypatch, niveaus,
                              wacht_op_spraak=0.3, max_seconden=10)

    assert opname.had_spraak is False
    assert opname.seconden < 2          # niet de volle tien seconden


def test_harde_bovengrens(monkeypatch):
    """Iemand die blijft praten wordt uiteindelijk toch afgekapt."""
    niveaus = [0.001] * 8 + [0.4] * 10_000
    opname, _ = _neem_op(monkeypatch, niveaus, max_seconden=1.0, stilte_na=5)

    assert opname.had_spraak is True
    assert opname.seconden <= 1.5


def test_luide_kamer_verhoogt_de_drempel(monkeypatch):
    """
    In een rumoerige ruimte mag achtergrondruis niet als spraak tellen.

    De ruisvloer wordt bij het begin gemeten; blijft het daarna op datzelfde
    niveau, dan is er niets gezegd.
    """
    niveaus = [0.05] * 8 + [0.05] * 300
    opname, _ = _neem_op(monkeypatch, niveaus,
                         wacht_op_spraak=0.3, max_seconden=5)
    assert opname.had_spraak is False


def test_niveaus_gaan_naar_de_callback(monkeypatch):
    gezien = []
    niveaus = [0.001] * 8 + [0.3] * 10 + [0.0] * 50
    _neem_op(monkeypatch, niveaus, stilte_na=0.2, on_level=gezien.append)

    assert gezien                       # er is gemeten
    assert gezien[-1] == 0.0            # en netjes op nul afgesloten
    assert all(0.0 <= n <= 1.0 for n in gezien)


# --- groet ------------------------------------------------------------------

@pytest.mark.parametrize("uur,verwacht", [
    (3, "Goedenacht"), (9, "Goedemorgen"), (14, "Goedemiddag"), (21, "Goedenavond"),
])
def test_dagdeel(uur, verwacht):
    from voice.greeting import _dagdeel
    assert _dagdeel(uur) == verwacht


def test_groet_hooguit_een_keer_per_dag(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GREETING_STATE_PATH", str(tmp_path / "groet.txt"))
    from voice import greeting

    gezegd = []
    assert greeting.groet_eenmaal_per_dag(gezegd.append) is True
    assert greeting.groet_eenmaal_per_dag(gezegd.append) is False
    assert len(gezegd) == 1
    assert config.OWNER_NAME in gezegd[0]


def test_groet_werkt_ook_als_opslaan_mislukt(tmp_path, monkeypatch):
    # Een pad dat niet te schrijven is mag de groet niet tegenhouden.
    monkeypatch.setattr(config, "GREETING_STATE_PATH", "/proc/kanniet/groet.txt")
    from voice import greeting

    gezegd = []
    assert greeting.groet_eenmaal_per_dag(gezegd.append) is True
    assert len(gezegd) == 1


# --- ontbrekend wake word ---------------------------------------------------
# openwakeword eist op Linux tflite-runtime, waarvan geen wheels bestaan voor
# recente Python-versies. Zonder dat pakket moet alles behalve "Hey Jarvis"
# gewoon blijven werken.

def test_beschikbaarheid_wordt_gedetecteerd(monkeypatch):
    import importlib.util

    from voice.listener import WakeWord

    monkeypatch.setattr(importlib.util, "find_spec", lambda naam: None)
    assert WakeWord.beschikbaar() is False

    monkeypatch.setattr(importlib.util, "find_spec", lambda naam: object())
    assert WakeWord.beschikbaar() is True


def test_ontbrekend_pakket_geeft_bruikbare_uitleg(monkeypatch):
    import builtins

    from voice.listener import WakeWord, WakeWordNietBeschikbaar

    echte_import = builtins.__import__

    def zonder_oww(naam, *args, **kwargs):
        if naam.startswith("openwakeword"):
            raise ImportError("No module named 'openwakeword'")
        return echte_import(naam, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", zonder_oww)

    with pytest.raises(WakeWordNietBeschikbaar) as excinfo:
        WakeWord()

    melding = str(excinfo.value)
    assert "--no-deps openwakeword" in melding      # het commando dat helpt
    assert "tflite" in melding                      # en waarom het nodig is


def test_spraaklus_valt_terug_op_push_to_talk(monkeypatch):
    """Zonder wake word moet de lus blijven draaien op push-to-talk alleen."""
    from hud.events import EventBus
    from voice.listener import WakeWordNietBeschikbaar
    from voice.loop import VoiceLoop

    bus = EventBus()
    gemeld = []
    bus.publish_from_thread = lambda kind, payload=None: gemeld.append(
        {"type": kind, **(payload or {})})
    bus.set_state_from_thread = lambda state: None

    lus = VoiceLoop(bus=bus, respond=lambda t: "antwoord")

    # Doe alsof alles laadt behalve het wake word.
    class NepStore:
        def is_ingesproken(self): return True

    class NepTTS:
        name = "nep"

    monkeypatch.setattr("voice.tts.TextToSpeech", lambda *a, **k: NepTTS())
    monkeypatch.setattr("voice.stt.SpeechToText", lambda *a, **k: object())
    monkeypatch.setattr("voice.listener.Microfoon", lambda *a, **k: object())
    monkeypatch.setattr("voice.voiceprint.VoiceprintStore", lambda *a, **k: NepStore())
    monkeypatch.setattr("voice.encoder.get_encoder", lambda: object())
    monkeypatch.setattr("voice.listener.WakeWord",
                        lambda *a, **k: (_ for _ in ()).throw(
                            WakeWordNietBeschikbaar("openwakeword ontbreekt")))

    assert lus._load() is True          # laden slaagt alsnog
    assert lus.wake is None
    assert lus.ready is True

    fouten = [g for g in gemeld if g["type"] == "error"]
    assert any("spatiebalk" in f["text"] for f in fouten)

    klaar = [g for g in gemeld if g["type"] == "voice"]
    assert klaar[0]["wake_word"] is False
