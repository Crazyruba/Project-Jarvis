"""Stemafdrukken: opslaan, vergelijken, drempels."""

import numpy as np
import pytest

import config
from voice.voiceprint import AFDRUK_LENGTE, Oordeel, VoiceprintStore, cosinus


def afdruk(seed: int, lengte: int = AFDRUK_LENGTE) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(size=lengte).astype("float32")


@pytest.fixture
def store(tmp_path):
    return VoiceprintStore(str(tmp_path / "stem.npz"))


# --- cosinus ----------------------------------------------------------------

def test_dezelfde_vector_scoort_een():
    v = afdruk(1)
    assert cosinus(v, v[None, :])[0] == pytest.approx(1.0, abs=1e-5)


def test_tegengestelde_vector_scoort_min_een():
    v = afdruk(1)
    assert cosinus(v, -v[None, :])[0] == pytest.approx(-1.0, abs=1e-5)


def test_stilte_geeft_geen_deling_door_nul():
    """Een opname van pure stilte levert een nulvector; dat mag niet knallen."""
    stil = np.zeros(AFDRUK_LENGTE, dtype="float32")
    uitkomst = cosinus(stil, afdruk(2)[None, :])
    assert np.isfinite(uitkomst).all()
    assert uitkomst[0] == pytest.approx(0.0)


def test_cosinus_tegen_meerdere_vectoren():
    assert cosinus(afdruk(1), np.vstack([afdruk(1), afdruk(2), afdruk(3)])).shape == (3,)


# --- opslag -----------------------------------------------------------------

def test_leeg_bij_aanvang(store):
    assert store.is_ingesproken() is False
    assert store.aantal == 0


def test_toevoegen_en_bewaren(store, tmp_path):
    store.voeg_toe(afdruk(1))
    store.voeg_toe(afdruk(2))
    assert store.aantal == 2

    # Opnieuw inlezen moet hetzelfde opleveren.
    opnieuw = VoiceprintStore(str(tmp_path / "stem.npz"))
    assert opnieuw.aantal == 2
    assert opnieuw.is_ingesproken()


def test_verkeerde_lengte_wordt_geweigerd(store):
    with pytest.raises(ValueError, match="192"):
        store.voeg_toe(np.zeros(64, dtype="float32"))


def test_wissen(store):
    store.voeg_toe(afdruk(1))
    store.wis()
    assert store.aantal == 0
    assert not store.pad.exists()


def test_onleesbaar_bestand_blokkeert_het_opstarten_niet(tmp_path, capsys):
    pad = tmp_path / "kapot.npz"
    pad.write_bytes(b"dit is geen npz")
    store = VoiceprintStore(str(pad))
    assert store.aantal == 0
    assert "onleesbaar" in capsys.readouterr().out


# --- vergelijken ------------------------------------------------------------

def test_zonder_afdrukken_altijd_afgewezen(store):
    oordeel = store.vergelijk(afdruk(1))
    assert oordeel == Oordeel(False, 0.0, 0)


def test_eigen_stem_wordt_herkend(store):
    stem = afdruk(7)
    for ruis in range(3):
        # Kleine variatie, zoals verschillende opnames van dezelfde persoon.
        store.voeg_toe(stem + afdruk(100 + ruis) * 0.1)

    oordeel = store.vergelijk(stem)
    assert oordeel.is_eigenaar is True
    assert oordeel.gelijkenis > config.SPEAKER_THRESHOLD


def test_vreemde_stem_wordt_afgewezen(store):
    for n in range(3):
        store.voeg_toe(afdruk(n))
    oordeel = store.vergelijk(afdruk(999))
    assert oordeel.is_eigenaar is False


def test_drempel_is_instelbaar(store):
    stem = afdruk(7)
    store.voeg_toe(stem)
    assert store.vergelijk(stem, drempel=0.99).is_eigenaar is True
    assert store.vergelijk(afdruk(8), drempel=0.99).is_eigenaar is False


def test_gemiddelde_over_meerdere_afdrukken(store):
    """Eén mislukte opname mag het oordeel niet bepalen."""
    stem = afdruk(7)
    store.voeg_toe(stem)
    store.voeg_toe(stem * 0.98)
    store.voeg_toe(afdruk(321))          # uitschieter uit het inspreken

    oordeel = store.vergelijk(stem, top_k=2)
    assert oordeel.gebruikt == 2
    assert oordeel.is_eigenaar is True


def test_oordeel_leest_prettig():
    assert "eigenaar" in str(Oordeel(True, 0.91, 3))
    assert "afgewezen" in str(Oordeel(False, 0.12, 3))
