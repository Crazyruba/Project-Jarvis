import config
from voice.ecapa_encoder import get_encoder
from voice.voiceprint_store import VoiceprintStore


class SpeakerVerifier:
    """Vergelijkt een stemfragment met de opgeslagen stemafdruk van de eigenaar."""

    def __init__(self, store: VoiceprintStore):
        self.encoder = get_encoder()      # gedeeld ECAPA-model
        self.store = store

    def verify(self, audio):
        """
        Geeft (is_eigenaar, gelijkenis) terug.

        De opslag bevat alleen stemafdrukken van de eigenaar, dus de gelijkenis
        bepaalt het oordeel. Vroeger stond hier een vaste naam; die stond een
        andere OWNER_NAME in de weg.
        """
        try:
            embedding = self.encoder.embed(audio)
            gelijkenis, _ = self.store.verify(embedding)
            return gelijkenis >= config.SPEAKER_THRESHOLD, gelijkenis
        except Exception as e:
            print(f"   ❌ [Sprekercontrole mislukt: {e}]")
            return False, 0.0
