"""
Stemafdrukken: opslaan en vergelijken.

Een stemafdruk is een ECAPA-TDNN-embedding van 192 getallen. Daar zijn er een
stuk of vijf van, dus een vectordatabase is hier zwaar gereedschap voor een
klein klusje: cosinusgelijkenis over een numpy-array is een paar regels en
scheelt een forse afhankelijkheid.

De afdrukken staan in één .npz naast een klein JSON-bestand met wie en wanneer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import config

AFDRUK_LENGTE = 192          # ECAPA-TDNN


@dataclass(frozen=True)
class Oordeel:
    """Uitkomst van een vergelijking."""

    is_eigenaar: bool
    gelijkenis: float
    gebruikt: int            # over hoeveel opgeslagen afdrukken gemiddeld is

    def __str__(self) -> str:
        wie = "eigenaar" if self.is_eigenaar else "afgewezen"
        return f"{wie} ({self.gelijkenis:.2f} over {self.gebruikt})"


def cosinus(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Cosinusgelijkenis van één vector tegen een rij vectoren.

    Genormaliseerd met een ondergrens op de lengte, zodat een stille opname
    (vector van nul) geen deling door nul geeft maar gewoon 0 scoort.
    """
    a = np.asarray(a, dtype="float32").ravel()
    b = np.atleast_2d(np.asarray(b, dtype="float32"))

    a_norm = a / max(float(np.linalg.norm(a)), 1e-9)
    b_norm = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-9)
    return b_norm @ a_norm


class VoiceprintStore:
    """De opgeslagen stemafdrukken van de eigenaar."""

    def __init__(self, pad: str | None = None):
        self.pad = Path(pad or config.VOICEPRINT_PATH)
        self.meta_pad = self.pad.with_suffix(".json")
        self._afdrukken: np.ndarray | None = None
        self._meta: dict = {}
        self._laad()

    # -- opslag ------------------------------------------------------------
    def _laad(self) -> None:
        if self.pad.exists():
            try:
                with np.load(self.pad) as bestand:
                    self._afdrukken = bestand["afdrukken"]
            except Exception as e:
                print(f"⚠️  Stemafdrukken onleesbaar ({e}); opnieuw inspreken nodig.")
                self._afdrukken = None
        if self.meta_pad.exists():
            try:
                self._meta = json.loads(self.meta_pad.read_text("utf-8"))
            except Exception:
                self._meta = {}

    def _bewaar(self) -> None:
        self.pad.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(self.pad, afdrukken=self._afdrukken)
        self.meta_pad.write_text(
            json.dumps(self._meta, ensure_ascii=False, indent=2), "utf-8")

    # -- staat -------------------------------------------------------------
    @property
    def aantal(self) -> int:
        return 0 if self._afdrukken is None else int(self._afdrukken.shape[0])

    def is_ingesproken(self) -> bool:
        return self.aantal > 0

    @property
    def eigenaar(self) -> str:
        return self._meta.get("eigenaar", config.OWNER_NAME)

    # -- vullen ------------------------------------------------------------
    def voeg_toe(self, afdruk) -> None:
        """Neem één stemafdruk op."""
        vector = np.asarray(afdruk, dtype="float32").ravel()
        if vector.size != AFDRUK_LENGTE:
            raise ValueError(
                f"Een stemafdruk hoort {AFDRUK_LENGTE} getallen te hebben, "
                f"kreeg er {vector.size}."
            )

        self._afdrukken = (vector[None, :] if self._afdrukken is None
                           else np.vstack([self._afdrukken, vector[None, :]]))
        self._meta["eigenaar"] = config.OWNER_NAME
        self._meta["aantal"] = self.aantal
        self._bewaar()

    def wis(self) -> None:
        """Alles weggooien, om opnieuw in te spreken."""
        self._afdrukken = None
        self._meta = {}
        for bestand in (self.pad, self.meta_pad):
            bestand.unlink(missing_ok=True)

    # -- vergelijken -------------------------------------------------------
    def vergelijk(self, afdruk, drempel: float | None = None,
                  top_k: int = 3) -> Oordeel:
        """
        Vergelijk een stemfragment met wat is opgeslagen.

        Het gemiddelde over de dichtstbijzijnde paar afdrukken is stabieler dan
        één enkele match: één ongelukkige opname tijdens het inspreken trekt het
        oordeel dan niet scheef.
        """
        drempel = config.SPEAKER_THRESHOLD if drempel is None else drempel

        if not self.is_ingesproken():
            return Oordeel(False, 0.0, 0)

        scores = cosinus(afdruk, self._afdrukken)
        hoeveel = max(1, min(top_k, scores.size))
        beste = np.sort(scores)[-hoeveel:]
        gemiddelde = float(beste.mean())

        return Oordeel(gemiddelde >= drempel, gemiddelde, hoeveel)
