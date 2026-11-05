"""
Spraaklus en TTS-keuze.

Microfoon, Whisper en Piper zijn hier niet beschikbaar, dus alles draait met
nagebootste onderdelen. Wat hier getest wordt is de logica eromheen: welke
motor gekozen wordt, hoe het niveau geschaald wordt, en of de lus de juiste
toestanden doorgeeft.
"""

import sys
import types

import pytest

import config
from hud.events import EventBus, HudState


# --- niveau-omrekening ------------------------------------------------------

def test_rms_van_stilte_is_nul():
    np = pytest.importorskip("numpy")
    from voice.tts import _rms
    assert _rms(np.zeros(1000, dtype="int16")) == 0.0


def test_rms_blijft_binnen_nul_en_een():
    np = pytest.importorskip("numpy")
    from voice.tts import _rms
    luid = np.full(1000, 32000, dtype="int16")
    zacht = np.full(1000, 300, dtype="int16")
    assert 0.0 <= _rms(zacht) <= _rms(luid) <= 1.0


def test_rms_van_leeg_fragment():
    np = pytest.importorskip("numpy")
    from voice.tts import _rms
    assert _rms(np.array([], dtype="int16")) == 0.0


# --- motorkeuze -------------------------------------------------------------

def test_piper_zonder_model_valt_terug_op_pyttsx3(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "PIPER_VOICE_DIR", str(tmp_path))
    from voice.tts import TextToSpeech

    tts = TextToSpeech(engine="piper")
    assert tts.name == "pyttsx3"
    assert "ontbreekt" in capsys.readouterr().out


def test_piper_met_model_wordt_gekozen(monkeypatch, tmp_path):
    (tmp_path / f"{config.PIPER_VOICE}.onnx").write_bytes(b"nep")
    monkeypatch.setattr(config, "PIPER_VOICE_DIR", str(tmp_path))
    from voice.tts import TextToSpeech

    assert TextToSpeech(engine="piper").name == "piper"


def test_piper_zonder_model_geeft_duidelijke_fout(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PIPER_VOICE_DIR", str(tmp_path))
    from voice.tts import PiperTTS

    with pytest.raises(FileNotFoundError) as excinfo:
        PiperTTS()._load()
    assert "piper_setup" in str(excinfo.value)


def test_lege_tekst_wordt_niet_uitgesproken(monkeypatch):
    from voice.tts import BaseTTS, TextToSpeech

    class Teller(BaseTTS):
        name = "teller"
        def __init__(self): self.keer = 0
        def speak(self, text, on_level=None): self.keer += 1

    tts = TextToSpeech.__new__(TextToSpeech)
    tts.engine = Teller()
    tts.on_level = None
    tts.speak("")
    assert tts.engine.keer == 0


def test_tts_fout_blijft_binnen_en_zet_niveau_terug():
    from voice.tts import BaseTTS, TextToSpeech

    class Kapot(BaseTTS):
        name = "kapot"
        def speak(self, text, on_level=None): raise RuntimeError("geen geluidskaart")

    niveaus = []
    tts = TextToSpeech.__new__(TextToSpeech)
    tts.engine = Kapot()
    tts.on_level = niveaus.append
    tts.speak("hallo")          # mag de lus niet onderuit halen
    assert niveaus[-1] == 0.0


# --- stiltedetectie ---------------------------------------------------------

@pytest.mark.parametrize("tekst", ["", "   ", "...", "?!", None])
def test_stilte_wordt_herkend(tekst):
    from voice.loop import is_silence
    assert is_silence(tekst) is True


@pytest.mark.parametrize("tekst", ["hoi", "Wat is het weer?", "één", "café"])
def test_echte_spraak_is_geen_stilte(tekst):
    from voice.loop import is_silence
    assert is_silence(tekst) is False


# --- de lus -----------------------------------------------------------------

class NepTTS:
    name = "nep"
    def __init__(self): self.gezegd = []
    def speak(self, text, on_level=None):
        self.gezegd.append(text)
        if on_level: on_level(0.5); on_level(0.0)


class NepSTT:
    def __init__(self, teksten): self.teksten = list(teksten)
    def transcribe(self, audio):
        return self.teksten.pop(0) if self.teksten else ""


class NepMicrofoon:
    """Geeft net zoveel opnames terug als er teksten zijn, daarna stilte."""

    def __init__(self, aantal, had_spraak=True):
        self.over = aantal
        self.had_spraak = had_spraak

    def neem_op(self, on_level=None, **kwargs):
        from voice.listener import Opname
        if on_level: on_level(0.3); on_level(0.0)
        spraak = self.had_spraak and self.over > 0
        self.over -= 1
        return Opname(audio=object(), seconden=1.5, had_spraak=spraak)


class NepStore:
    def __init__(self, ok=True): self.ok = ok
    def vergelijk(self, afdruk):
        from voice.voiceprint import Oordeel
        return Oordeel(self.ok, 0.91 if self.ok else 0.12, 3)


class NepEncoder:
    def embed(self, audio): return object()


def _lus(bus, teksten, respond=lambda t: "antwoord", eigenaar=True,
         had_spraak=True):
    from voice.loop import VoiceLoop
    lus = VoiceLoop(bus=bus, respond=respond)
    lus.stt = NepSTT(teksten)
    lus.tts = NepTTS()
    lus.mic = NepMicrofoon(len(teksten) or 1, had_spraak)
    lus.store = NepStore(eigenaar)
    lus.encoder = NepEncoder()
    return lus


def _events(bus):
    """Verzamel alles wat de lus publiceert, zonder draaiende server."""
    verzameld = []
    bus.publish_from_thread = lambda kind, payload=None: verzameld.append(
        {"type": kind, **(payload or {})})
    bus.set_state_from_thread = lambda state: verzameld.append(
        {"type": "state", "value": state.value})
    return verzameld


def test_gesprek_doorloopt_de_toestanden(monkeypatch):
    monkeypatch.setattr(config, "FOLLOWUP_ENABLED", False)
    monkeypatch.setattr("voice.greeting.groet_eenmaal_per_dag", lambda zeg: False)

    bus = EventBus()
    events = _events(bus)
    lus = _lus(bus, ["hoe laat is het"], respond=lambda t: "Het is drie uur.")
    lus._conversation()

    toestanden = [e["value"] for e in events if e["type"] == "state"]
    assert toestanden == ["listening", "thinking", "speaking"]
    assert lus.tts.gezegd == ["Het is drie uur."]

    berichten = [e for e in events if e["type"] == "message"]
    assert berichten[0] == {"type": "message", "role": "user", "text": "hoe laat is het"}


def test_vreemde_stem_wordt_geweigerd(monkeypatch):
    monkeypatch.setattr("voice.greeting.groet_eenmaal_per_dag", lambda zeg: False)

    bus = EventBus()
    _events(bus)
    lus = _lus(bus, ["doe de deur open"], eigenaar=False)
    lus._conversation()

    assert len(lus.tts.gezegd) == 1
    assert config.OWNER_NAME in lus.tts.gezegd[0]


def test_stilte_beeindigt_het_gesprek(monkeypatch):
    monkeypatch.setattr("voice.greeting.groet_eenmaal_per_dag", lambda zeg: False)

    bus = EventBus()
    _events(bus)
    lus = _lus(bus, ["   "], respond=lambda t: pytest.fail("mag niet aangeroepen"))
    lus._conversation()
    assert lus.tts.gezegd == []


def test_niets_gehoord_beeindigt_het_gesprek_meteen(monkeypatch):
    """Zonder spraak hoeft er niet getranscribeerd of geverifieerd te worden."""
    monkeypatch.setattr("voice.greeting.groet_eenmaal_per_dag", lambda zeg: False)

    bus = EventBus()
    _events(bus)
    lus = _lus(bus, ["iets"], respond=lambda t: pytest.fail("mag niet aangeroepen"),
               had_spraak=False)
    lus._conversation()
    assert lus.tts.gezegd == []


def test_afsluitcommando_stopt_de_lus(monkeypatch):
    monkeypatch.setattr("voice.greeting.groet_eenmaal_per_dag", lambda zeg: False)

    bus = EventBus()
    _events(bus)
    lus = _lus(bus, ["tot ziens"], respond=lambda t: pytest.fail("mag niet aangeroepen"))
    lus._conversation()

    assert lus._stop.is_set()
    assert config.OWNER_NAME in lus.tts.gezegd[0]


def test_vervolgvraag_zonder_wake_word(monkeypatch):
    monkeypatch.setattr(config, "FOLLOWUP_ENABLED", True)
    monkeypatch.setattr("voice.greeting.groet_eenmaal_per_dag", lambda zeg: False)
    monkeypatch.setattr("time.sleep", lambda s: None)

    bus = EventBus()
    _events(bus)
    # Eerste vraag, dan een vervolgvraag, dan stilte.
    lus = _lus(bus, ["eerste vraag", "tweede vraag", ""])
    lus._conversation()

    assert lus.tts.gezegd == ["antwoord", "antwoord"]


def test_push_to_talk_zet_de_vlag():
    bus = EventBus()
    lus = _lus(bus, [])
    assert lus._ptt.is_set() is False
    lus.request_listen()
    assert lus._ptt.is_set() is True


def test_stoppen_maakt_het_wachten_los():
    bus = EventBus()
    lus = _lus(bus, [])
    lus.stop()
    assert lus._stop.is_set() and lus._ptt.is_set()
