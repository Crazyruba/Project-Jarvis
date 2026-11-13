"""
Luisteren: het wake word en het opnemen zelf.

Opnemen stopt wanneer je uitgesproken bent, niet na een vast aantal seconden.
Dat scheelt wachten na elke korte zin, en Whisper krijgt geen staart stilte
mee waar het soms woorden in verzint.

De stiltedetectie is bewust eenvoudig: de ruisvloer wordt bij het begin van
elke opname gemeten, en alles wat daar ruim boven uitkomt telt als spraak.
Een getraind VAD-model is nauwkeuriger, maar dat is weer een afhankelijkheid
en een model om te laden.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

import config


class WakeWordNietBeschikbaar(RuntimeError):
    """openwakeword ontbreekt; praten kan nog wel met push-to-talk."""


@dataclass
class Opname:
    audio: np.ndarray
    seconden: float
    had_spraak: bool


def rms(blok: np.ndarray) -> float:
    if blok.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(blok, dtype="float64"))))


class Microfoon:
    """Neemt op en stopt zodra het stil blijft."""

    BLOK = 0.032                    # 32 ms; fijn genoeg voor stiltedetectie

    def __init__(self, samplerate: int | None = None):
        self.samplerate = samplerate or config.SAMPLE_RATE
        self.blokgrootte = int(self.samplerate * self.BLOK)

    def neem_op(self, max_seconden: float | None = None,
                stilte_na: float | None = None,
                wacht_op_spraak: float | None = None,
                on_level=None) -> Opname:
        """
        Neem op tot het `stilte_na` seconden stil is, of tot `max_seconden`.

        `wacht_op_spraak` is hoe lang er op het eerste woord gewacht wordt;
        komt er niets, dan stopt het meteen in plaats van de hele tijd vol te
        maken met stilte.
        """
        import sounddevice as sd

        max_seconden = max_seconden or config.MAX_OPNAME
        stilte_na = stilte_na or config.STILTE_NA
        wacht_op_spraak = wacht_op_spraak or config.WACHT_OP_SPRAAK

        blokken: list[np.ndarray] = []
        gesproken = False
        stille_blokken = 0

        # De tijd wordt geteld in opgenomen samples, niet met de wandklok.
        # De geluidskaart bepaalt het tempo; levert die een paar blokken in
        # één keer, dan loopt een klokmeting uit de pas terwijl het aantal
        # samples altijd klopt.
        max_blokken = max(1, int(max_seconden / self.BLOK))
        stilte_blokken = max(1, int(stilte_na / self.BLOK))
        geduld_blokken = max(1, int(wacht_op_spraak / self.BLOK))

        with sd.InputStream(samplerate=self.samplerate, channels=1,
                            dtype="float32", blocksize=self.blokgrootte) as stroom:
            # Eerst even de kamer meten: elke ruimte en microfoon is anders.
            meting = []
            for _ in range(max(1, int(0.25 / self.BLOK))):
                blok, _ = stroom.read(self.blokgrootte)
                meting.append(rms(blok.ravel()))
            ruisvloer = float(np.median(meting))
            # Ruim boven de ruis, met een bodem voor een heel stille microfoon.
            drempel = max(ruisvloer * 3.0, 0.012)

            while len(blokken) < max_blokken:
                blok, _ = stroom.read(self.blokgrootte)
                mono = blok.ravel()
                blokken.append(mono)

                niveau = rms(mono)
                if on_level:
                    on_level(min(1.0, niveau * 8))

                if niveau > drempel:
                    gesproken = True
                    stille_blokken = 0
                    continue

                stille_blokken += 1
                if gesproken:
                    if stille_blokken >= stilte_blokken:
                        break                       # uitgesproken
                elif stille_blokken >= geduld_blokken:
                    break                           # er kwam niets

        if on_level:
            on_level(0.0)

        audio = (np.concatenate(blokken) if blokken
                 else np.zeros(0, dtype="float32"))
        return Opname(audio, len(audio) / self.samplerate, gesproken)


class WakeWord:
    """Wacht op 'Hey Jarvis', en laat zich onderbreken."""

    CHUNK = 1280                    # 80 ms bij 16 kHz, wat openWakeWord wil

    @staticmethod
    def beschikbaar() -> bool:
        """Of openwakeword geïnstalleerd is."""
        import importlib.util

        return importlib.util.find_spec("openwakeword") is not None

    def __init__(self, model: str | None = None, drempel: float | None = None):
        try:
            from openwakeword.model import Model
        except ImportError as e:
            raise WakeWordNietBeschikbaar(
                "openwakeword is niet geïnstalleerd. Installeren met:\n"
                "    pip install --no-deps openwakeword\n"
                "(--no-deps omdat het op Linux tflite-runtime eist, dat JARVIS "
                "niet gebruikt en waarvoor geen wheels bestaan.)"
            ) from e

        self.naam = model or config.WAKE_WORD_MODEL
        self.drempel = config.WAKE_THRESHOLD if drempel is None else drempel
        print("🎙️  Wake word-model laden…")
        self.model = Model(wakeword_models=[self.naam], inference_framework="onnx")
        print(f"✅ Wake word klaar. Zeg '{self.naam.replace('_', ' ')}'.")

    def _leeg_buffer(self) -> None:
        """
        Oude voorspellingen weggooien.

        Zonder dit triggert JARVIS op zijn eigen stem die nog in de buffer zit,
        en gaat hij in een lus met zichzelf praten.
        """
        try:
            self.model.reset()
        except Exception:
            for sleutel in getattr(self.model, "prediction_buffer", {}):
                self.model.prediction_buffer[sleutel].clear()

    def wacht(self, should_stop=None, opwarm_blokken: int = 15) -> bool:
        """True als het wake word klonk, False als `should_stop` ingreep."""
        import sounddevice as sd

        self._leeg_buffer()

        with sd.InputStream(samplerate=config.SAMPLE_RATE, channels=1,
                            dtype="int16", blocksize=self.CHUNK) as stroom:
            # De staart van de vorige zin uit de microfoon laten lopen.
            for _ in range(opwarm_blokken):
                stroom.read(self.CHUNK)
            self._leeg_buffer()

            while True:
                if should_stop is not None and should_stop():
                    return False

                blok, _ = stroom.read(self.CHUNK)
                score = self.model.predict(
                    np.frombuffer(blok, dtype=np.int16)
                ).get(self.naam, 0.0)

                if score >= self.drempel:
                    print(f"   🔔 Wake word gehoord ({score:.2f})")
                    # Even wachten, anders bijt het triggerwoord zelf in de opname.
                    time.sleep(0.25)
                    return True
