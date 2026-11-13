"""
ECAPA-TDNN-encoder: audio in, stemafdruk uit.

Het model komt van SpeechBrain en wordt één keer geladen; dat duurt een paar
seconden en kost zo'n 700 MB, dus een tweede exemplaar wil je niet.
"""

from __future__ import annotations

import numpy as np

import config

_encoder: "Encoder | None" = None


class Encoder:
    """Zet mono 16 kHz-audio om in een stemafdruk van 192 getallen."""

    def __init__(self, map_: str | None = None):
        from speechbrain.inference.speaker import EncoderClassifier
        from speechbrain.utils.fetching import LocalStrategy

        print("🔊 ECAPA-model laden…")
        self.model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=map_ or config.ECAPA_MODEL_DIR,
            run_opts={"device": "cpu"},
            # Kopiëren in plaats van symlinken: symlinks vragen op Windows
            # om extra rechten en breken de cache stilletjes.
            local_strategy=LocalStrategy.COPY,
        )
        print("✅ ECAPA klaar.")

    def embed(self, audio) -> np.ndarray:
        import torch

        golf = np.asarray(audio, dtype="float32").ravel()
        if golf.size == 0:
            raise ValueError("Lege opname; daar valt geen stemafdruk uit te halen.")

        with torch.no_grad():
            uitkomst = self.model.encode_batch(torch.from_numpy(golf).unsqueeze(0))
        return uitkomst.squeeze().detach().cpu().numpy().astype("float32")


def get_encoder() -> Encoder:
    """Het gedeelde exemplaar; laadt bij de eerste aanroep."""
    global _encoder
    if _encoder is None:
        _encoder = Encoder()
    return _encoder
