import numpy as np
import sounddevice as sd
import config
from voice.voiceprint_store import VoiceprintStore
from voice.ecapa_encoder import get_encoder


class VoiceEnrollment:
    """Eenmalig inspreken — slaat de ECAPA-stemvectoren van de eigenaar op."""

    def __init__(self, store: VoiceprintStore):
        self.encoder = get_encoder()      # shared ECAPA model
        self.store = store

    def is_enrolled(self) -> bool:
        return self.store.is_enrolled()

    def _record_sample(self) -> np.ndarray:
        audio = sd.rec(
            int(config.ENROLL_SECONDS * config.SAMPLE_RATE),
            samplerate=config.SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        return audio.flatten()

    def enroll(self, tts):
        """Record several samples and store their ECAPA embeddings in Chroma."""
        tts.speak(
            f"We gaan mijn stemherkenning instellen, {config.OWNER_NAME}. "
            f"Ik vraag je {config.ENROLL_SAMPLES} zinnen voor te lezen. "
            "Spreek rustig en duidelijk."
        )

        zinnen = [
            f"Mijn naam is {config.OWNER_NAME} en JARVIS is mijn assistent.",
            f"Hey JARVIS, je spreekt met {config.OWNER_NAME}.",
            "JARVIS, onthoud hoe mijn stem klinkt.",
            "Ik ben de enige die JARVIS opdrachten mag geven.",
            f"Dit is {config.OWNER_NAME}, ik bevestig mijn identiteit.",
        ]

        for i in range(config.ENROLL_SAMPLES):
            zin = zinnen[i % len(zinnen)]
            tts.speak(f"Opname {i + 1}. Zeg: {zin}")
            print(f"🎙️  Opname {i + 1}/{config.ENROLL_SAMPLES}…")

            audio = self._record_sample()
            embedding = self.encoder.embed(audio)
            self.store.add_voiceprint(embedding, sample_id=f"{config.OWNER_NAME.lower()}_{i}")
            print(f"   ✅ Opname {i + 1} opgeslagen.")

        tts.speak("Gelukt. Je stemafdruk is opgeslagen; ik herken je voortaan.")
        print(f"✅ Klaar — {config.ENROLL_SAMPLES} stemvectoren opgeslagen.")