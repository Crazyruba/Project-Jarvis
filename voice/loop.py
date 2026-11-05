"""
De spraaklus.

Draait in een eigen thread, want de microfoon, Whisper en het wake word
blokkeren allemaal. Alles wat hij doet gaat als gebeurtenis naar de eventbus,
zodat de lampjes en het hologram in de HUD de echte toestand tonen.

    😴 wake word  →  🎙️ opnemen  →  🔐 is het de eigenaar?
       →  🧠 transcriberen  →  💭 antwoord  →  🔊 spreken
       →  🗣️ nog even wachten op een vervolgvraag  →  😴

De zware modellen worden pas in de thread geladen, zodat de HUD meteen
bruikbaar is terwijl Whisper nog binnenkomt.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Callable

import config
from hud.events import HudState


def is_silence(text: str) -> bool:
    """True als een transcriptie leeg is of alleen leestekens/ruis bevat."""
    if not text:
        return True
    return len(re.sub(r"[^0-9A-Za-zÀ-ÿ]", "", text)) == 0


EXIT_COMMANDS = {
    "stop", "stoppen", "afsluiten", "tot ziens", "doei",
    "goodbye jarvis", "shut down", "quit", "exit",
}


class VoiceLoop:
    """Wake word, opnemen, sprekercontrole, antwoorden en spreken."""

    def __init__(self, bus, respond: Callable[[str], str]):
        self.bus = bus
        self.respond = respond

        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ptt = threading.Event()
        self._ready = threading.Event()

        self.stt = None
        self.tts = None
        self.mic = None
        self.wake = None
        self.store = None
        self.encoder = None
        self.error: str | None = None

    # -- besturing ---------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="voice", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._ptt.set()           # maak het wachten los

    def request_listen(self) -> None:
        """Push-to-talk vanuit de HUD: luister nu, zonder wake word."""
        self._ptt.set()

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    # -- niveaus naar het hologram ----------------------------------------
    def _level(self, value: float) -> None:
        self.bus.publish_from_thread("level", {"value": value})

    def _state(self, state: HudState) -> None:
        self.bus.set_state_from_thread(state)

    def _say(self, text: str) -> None:
        self._state(HudState.SPEAKING)
        self.bus.publish_from_thread("message", {"role": "jarvis", "text": text})
        self.tts.speak(text, on_level=self._level)

    # -- opstarten ---------------------------------------------------------
    def _load(self) -> bool:
        from voice.encoder import get_encoder
        from voice.listener import Microfoon, WakeWord
        from voice.stt import SpeechToText
        from voice.tts import TextToSpeech
        from voice.voiceprint import VoiceprintStore

        try:
            self.tts = TextToSpeech()
            self.stt = SpeechToText()
            self.mic = Microfoon()

            store = VoiceprintStore()
            if not store.is_ingesproken():
                self.error = (
                    "Je stem is nog niet ingesproken. Draai eenmalig "
                    "`python -m voice.enroll` en start daarna opnieuw."
                )
                self.bus.publish_from_thread("error", {"text": self.error})
                print(f"⚠️  {self.error}")
                return False

            self.store = store
            self.encoder = get_encoder()
            self.wake = WakeWord()
        except Exception as e:
            self.error = f"Spraak kon niet starten: {e}"
            self.bus.publish_from_thread("error", {"text": self.error})
            print(f"❌ {self.error}")
            return False

        self._ready.set()
        self.bus.publish_from_thread("voice", {"ready": True, "engine": self.tts.name})
        print(f"✅ Spraak klaar (stem: {self.tts.name}).")
        return True

    # -- de lus ------------------------------------------------------------
    def _run(self) -> None:
        if not self._load():
            return

        self._state(HudState.IDLE)

        while not self._stop.is_set():
            # Wachten op "Hey Jarvis", of op push-to-talk uit de HUD.
            via_ptt = self._ptt.is_set()
            if not via_ptt:
                gehoord = self.wake.wacht(
                    should_stop=lambda: self._ptt.is_set() or self._stop.is_set()
                )
                if self._stop.is_set():
                    break
                via_ptt = self._ptt.is_set()
                if not gehoord and not via_ptt:
                    continue

            self._ptt.clear()
            if not via_ptt:
                self._say("Ja?")

            try:
                self._conversation()
            except Exception as e:
                print(f"❌ Fout in de spraaklus: {e}")
                self.bus.publish_from_thread("error", {"text": f"Spraakfout: {e}"})
            finally:
                self._state(HudState.IDLE)
                self._level(0.0)

    def _conversation(self) -> None:
        """Eén gesprek: de eerste beurt, daarna vervolgvragen zonder wake word."""
        eerste = True

        while not self._stop.is_set():
            if not eerste:
                time.sleep(0.4)          # laat de luidspreker uitklinken

            self._state(HudState.LISTENING)
            opname = self.mic.neem_op(on_level=self._level)
            self._level(0.0)

            if not opname.had_spraak:
                print("   🤫 (niets gehoord — terug naar slapen)")
                return

            oordeel = self.store.vergelijk(self.encoder.embed(opname.audio))
            print(f"   🔐 Sprekercontrole: {oordeel}")
            if not oordeel.is_eigenaar:
                if eerste:
                    self._say(f"Sorry, ik neem alleen opdrachten aan van "
                              f"{config.OWNER_NAME}.")
                return

            if eerste:
                from voice.greeting import groet_eenmaal_per_dag
                groet_eenmaal_per_dag(self._say)
            eerste = False

            self._state(HudState.THINKING)
            tekst = self.stt.transcribe(opname.audio)

            if is_silence(tekst):
                print("   🤫 (stilte — terug naar slapen)")
                return

            print(f"Jij: {tekst}")
            self.bus.publish_from_thread("message", {"role": "user", "text": tekst})

            if tekst.lower().strip(" .!?") in EXIT_COMMANDS:
                self._say(f"Tot ziens, {config.OWNER_NAME}!")
                self.stop()
                return

            antwoord = self.respond(tekst)
            if antwoord:
                self._say(antwoord)

            if not config.FOLLOWUP_ENABLED:
                return
