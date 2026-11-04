"""
Tekst naar spraak.

Piper is de voorkeur: een lokaal neuraal model met een goede Nederlandse stem,
zonder internet en zonder kosten. pyttsx3 blijft als terugval, want dat is
altijd aanwezig — het klinkt alleen een stuk robotachtiger.

Tijdens het spreken gaat de RMS van elk audiostukje naar een callback, zodat
het hologram op de stem meebeweegt.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Callable, Iterable

import config

LevelCallback = Callable[[float], None]


def _rms(samples) -> float:
    """Geluidsniveau van int16-audio, geschaald naar 0..1 voor het hologram."""
    import numpy as np

    arr = np.asarray(samples, dtype="float32")
    if arr.size == 0:
        return 0.0
    value = float(np.sqrt(np.mean((arr / 32768.0) ** 2)))
    # Spraak zit meestal rond 0,05-0,25 RMS; log-schaal oogt natuurlijker.
    if value <= 0:
        return 0.0
    scaled = (math.log10(value * 1000 + 1) / 3.0)
    return max(0.0, min(1.0, scaled))


class BaseTTS:
    name = "basis"

    def speak(self, text: str, on_level: LevelCallback | None = None) -> None:
        raise NotImplementedError

    def available(self) -> bool:
        return True


class PiperTTS(BaseTTS):
    """Lokale neurale stem. Geeft per audiostukje het niveau door."""

    name = "piper"

    def __init__(self, voice: str | None = None, voice_dir: str | None = None):
        self.voice = voice or config.PIPER_VOICE
        self.voice_dir = Path(voice_dir or config.PIPER_VOICE_DIR)
        self.model_path = self.voice_dir / f"{self.voice}.onnx"
        self._voice = None

    def available(self) -> bool:
        return self.model_path.exists()

    def _load(self):
        if self._voice is not None:
            return self._voice
        if not self.available():
            raise FileNotFoundError(
                f"Piper-stem niet gevonden: {self.model_path}. "
                f"Haal hem op met: python -m voice.piper_setup"
            )
        from piper import PiperVoice

        self._voice = PiperVoice.load(self.model_path)
        return self._voice

    def speak(self, text: str, on_level: LevelCallback | None = None) -> None:
        import sounddevice as sd

        voice = self._load()
        stream = None
        try:
            for chunk in voice.synthesize(text):
                samples = chunk.audio_int16_array
                if stream is None:
                    stream = sd.OutputStream(
                        samplerate=chunk.sample_rate,
                        channels=chunk.sample_channels,
                        dtype="int16",
                    )
                    stream.start()
                if on_level:
                    on_level(_rms(samples))
                stream.write(samples)
        finally:
            if stream is not None:
                stream.stop()
                stream.close()
            if on_level:
                on_level(0.0)


class Pyttsx3TTS(BaseTTS):
    """Terugval. Altijd aanwezig, maar klinkt robotachtig en kent geen niveau."""

    name = "pyttsx3"

    def speak(self, text: str, on_level: LevelCallback | None = None) -> None:
        import pyttsx3

        engine = pyttsx3.init()                 # vers exemplaar per zin
        engine.setProperty("rate", config.TTS_RATE)

        voices = engine.getProperty("voices") or []
        # Zoek een Nederlandse stem; val anders terug op de ingestelde index.
        gekozen = None
        for v in voices:
            blob = f"{getattr(v, 'id', '')} {getattr(v, 'name', '')}".lower()
            languages = [
                lang.decode() if isinstance(lang, bytes) else str(lang)
                for lang in (getattr(v, "languages", None) or [])
            ]
            blob += " " + " ".join(languages).lower()
            if "nl" in blob or "dutch" in blob or "nederland" in blob:
                gekozen = v.id
                break
        if gekozen:
            engine.setProperty("voice", gekozen)
        elif voices and config.TTS_VOICE_INDEX < len(voices):
            engine.setProperty("voice", voices[config.TTS_VOICE_INDEX].id)

        # Geen echte amplitude beschikbaar; geef een vast niveau zodat het
        # hologram tenminste beweegt terwijl er geluid is.
        if on_level:
            on_level(0.45)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
        if on_level:
            on_level(0.0)


class TextToSpeech:
    """Kiest de motor en houdt het aanroeppunt gelijk voor de rest van de code."""

    def __init__(self, engine: str | None = None, on_level: LevelCallback | None = None):
        self.on_level = on_level
        self.engine = self._pick(engine or config.TTS_ENGINE)

    @staticmethod
    def _pick(wanted: str) -> BaseTTS:
        if wanted == "piper":
            piper = PiperTTS()
            if piper.available():
                return piper
            print(
                f"⚠️  Piper-stem '{piper.voice}' ontbreekt in {piper.voice_dir} — "
                "ik gebruik pyttsx3.\n"
                "   Ophalen met: python -m voice.piper_setup"
            )
        return Pyttsx3TTS()

    @property
    def name(self) -> str:
        return self.engine.name

    def speak(self, text: str, on_level: LevelCallback | None = None) -> None:
        if not text:
            return
        print(f"🔊 JARVIS: {text}")
        callback = on_level or self.on_level
        try:
            self.engine.speak(text, callback)
        except Exception as e:
            print(f"   ❌ [TTS-fout ({self.engine.name}): {e}]")
            if callback:
                callback(0.0)
