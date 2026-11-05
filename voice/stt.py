"""
Spraak naar tekst met faster-whisper, lokaal op de CPU.

De taal komt uit config.LANG. Nederlands is lastiger dan Engels, dus het
standaardmodel is `small`; `medium` is merkbaar beter maar ook trager.
"""

from __future__ import annotations

import numpy as np

import config

# Whisper verzint graag beleefdheden in een stilte. Dit zijn de uitkomsten
# die we als "niets gezegd" behandelen in plaats van als opdracht.
VERZINSELS = {
    "ondertiteling door de amara.org gemeenschap",
    "ondertitels ingediend door de amara.org gemeenschap",
    "abonneer je op mijn kanaal",
    "bedankt voor het kijken",
    "dankjewel",
    "thank you",
    "thanks for watching",
    "you",
}


class SpeechToText:
    """Zet opgenomen audio lokaal om naar tekst."""

    def __init__(self, model: str | None = None, taal: str | None = None):
        from faster_whisper import WhisperModel

        self.taal = taal or config.LANG
        naam = model or config.WHISPER_MODEL
        print(f"🎤 Whisper laden ({naam}, taal={self.taal}) — eerste keer duurt even…")
        # int8 houdt het behapbaar op een CPU zonder GPU.
        self.model = WhisperModel(naam, device="cpu", compute_type="int8")
        print("✅ Whisper klaar.")

    def transcribe(self, audio: np.ndarray) -> str:
        golf = np.asarray(audio, dtype="float32").ravel()
        if golf.size < config.SAMPLE_RATE // 4:      # korter dan 0,25 s
            return ""

        segmenten, _ = self.model.transcribe(
            golf,
            language=self.taal,
            # Zonder dit plakt Whisper eerdere tekst aan een stille opname vast.
            condition_on_previous_text=False,
        )
        tekst = " ".join(segment.text for segment in segmenten).strip()

        if tekst.strip(" .,!?").lower() in VERZINSELS:
            return ""
        return tekst
