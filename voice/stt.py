"""
Spraak naar tekst met faster-whisper, lokaal op de CPU.

De taal komt uit config.LANG. Nederlands is merkbaar lastiger dan Engels,
dus het standaardmodel is `small` in plaats van `base`.
"""

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

import config


class SpeechToText:
    """Neemt op van de microfoon en zet dat lokaal om naar tekst."""

    def __init__(self, model_name: str | None = None, language: str | None = None):
        self.language = language or config.LANG
        name = model_name or config.WHISPER_MODEL
        print(f"🎤 Whisper laden ({name}, taal={self.language}) — eerste keer duurt dit even…")
        # int8 houdt het licht op een CPU zonder GPU.
        self.model = WhisperModel(name, device="cpu", compute_type="int8")
        print("✅ Whisper klaar.")

    def record(self, seconds: int | None = None, on_level=None) -> np.ndarray:
        """Neem audio op. Met on_level gaat het niveau live naar het hologram."""
        seconds = seconds or config.RECORD_SECONDS
        print(f"🎙️  Luisteren, {seconds}s…")

        if on_level is None:
            audio = sd.rec(
                int(seconds * config.SAMPLE_RATE),
                samplerate=config.SAMPLE_RATE,
                channels=1,
                dtype="float32",
            )
            sd.wait()
            return audio.flatten()

        # Met niveaumeting: blokjes opnemen en per blokje de RMS doorgeven.
        blocks = []
        blocksize = int(config.SAMPLE_RATE * 0.08)      # 80 ms
        with sd.InputStream(
            samplerate=config.SAMPLE_RATE, channels=1,
            dtype="float32", blocksize=blocksize,
        ) as stream:
            needed = int(seconds * config.SAMPLE_RATE)
            gathered = 0
            while gathered < needed:
                block, _ = stream.read(blocksize)
                block = block.flatten()
                blocks.append(block)
                gathered += len(block)
                rms = float(np.sqrt(np.mean(block ** 2))) if block.size else 0.0
                on_level(min(1.0, rms * 8))             # spraak zit rond 0,02-0,12
        on_level(0.0)
        return np.concatenate(blocks)[: int(seconds * config.SAMPLE_RATE)]

    def transcribe(self, audio: np.ndarray) -> str:
        """Zet opgenomen audio om naar tekst."""
        segments, _ = self.model.transcribe(audio, language=self.language)
        return " ".join(seg.text for seg in segments).strip()

    def listen(self, seconds: int | None = None, on_level=None) -> str:
        """Opnemen en transcriberen in één keer."""
        audio = self.record(seconds, on_level=on_level)
        print("🧠 Transcriberen…")
        return self.transcribe(audio)
