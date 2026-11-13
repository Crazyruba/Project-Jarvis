"""Het geheugen: ontdubbelen, relevantie zoeken, context opbouwen."""

import pytest

from memory.store import Memory, _fts_query, _normaliseer
from memory.working_memory import WorkingMemory


@pytest.fixture
def mem(tmp_path):
    m = Memory(str(tmp_path / "test.db"))
    yield m
    m.close()


# --- normaliseren en zoekopdrachten ----------------------------------------

@pytest.mark.parametrize("a,b", [
    ("Koffie zwart", "koffie  zwart"),
    ("Café au lait", "cafe au lait"),
    ("Hij drinkt koffie!", "hij drinkt koffie"),
])
def test_varianten_normaliseren_naar_hetzelfde(a, b):
    assert _normaliseer(a) == _normaliseer(b)


def test_fts_query_laat_leestekens_niet_door():
    """Een aanhalingsteken of streepje in de vraag mag FTS5 niet laten struikelen."""
    query = _fts_query('wat is "dit" -- en of/of?')
    assert '"' in query          # woorden staan tussen quotes
    assert "--" not in query
    assert all(deel.strip() for deel in query.split(" OR "))


def test_korte_woorden_vallen_af():
    assert _fts_query("ik ga op de fiets") == '"fiets"*'


def test_lege_vraag_geeft_lege_query():
    assert _fts_query("?? -- !") == ""


# --- onthouden en ontdubbelen ----------------------------------------------

def test_onthouden_en_terugvinden(mem):
    assert mem.onthoud("voorkeur", "Ruben drinkt koffie zwart") == "Opgeslagen."
    assert [f.inhoud for f in mem.zoek("koffie")] == ["Ruben drinkt koffie zwart"]


def test_dubbel_wordt_niet_nog_eens_opgeslagen(mem):
    mem.onthoud("feit", "Woont in Utrecht")
    assert mem.onthoud("feit", "woont in UTRECHT!") == "Dat weet ik al."
    assert mem.aantallen()["feiten"] == 1


def test_lege_inhoud(mem):
    assert "niets" in mem.onthoud("feit", "   ")
    assert mem.aantallen()["feiten"] == 0


def test_onbekende_soort_wordt_feit(mem):
    mem.onthoud("onzin", "Iets willekeurigs")
    assert mem.alle_feiten()[0].soort == "feit"


def test_vergeten(mem):
    mem.onthoud("feit", "Houdt van drop")
    assert "Vergeten" in mem.vergeet("drop")
    assert mem.zoek("drop") == []


def test_vergeten_van_iets_dat_er_niet_is(mem):
    assert "vond niets" in mem.vergeet("eenhoorns")


# --- relevantie -------------------------------------------------------------

def test_alleen_relevante_feiten_in_de_context(mem):
    mem.onthoud("voorkeur", "Drinkt koffie zwart")
    mem.onthoud("project", "Bouwt een assistent op een Lenovo")
    for n in range(20):
        mem.onthoud("feit", f"Willekeurig feitje nummer {n}")

    context = mem.context_for("zet eens koffie")
    assert "koffie zwart" in context
    # Niet alles komt mee: dat was juist het probleem.
    assert context.count("Willekeurig feitje") < 10


def test_veelgebruikte_feiten_komen_altijd_mee(mem):
    mem.onthoud("feit", "Heet Ruben")
    for _ in range(3):
        mem.zoek("Ruben")                       # telt als treffer

    mem.onthoud("feit", "Iets over tuinieren")
    context = mem.context_for("vertel over tuinieren")
    assert "Heet Ruben" in context              # via de kern
    assert "tuinieren" in context               # via de zoekopdracht


def test_context_zonder_herinneringen(mem):
    assert "Nog geen" in mem.context_for("wat dan ook")


def test_context_zonder_vraag_valt_terug_op_recent(mem):
    mem.onthoud("feit", "Iets recents")
    assert "Iets recents" in mem.context_for("")


# --- gesprekslogboek --------------------------------------------------------

def test_beurten_worden_bewaard(mem):
    mem.log("user", "hoi")
    mem.log("jarvis", "Dag Ruben.")
    beurten = mem.recente_beurten()
    assert [b["inhoud"] for b in beurten] == ["hoi", "Dag Ruben."]


def test_lege_beurt_wordt_overgeslagen(mem):
    mem.log("user", "   ")
    assert mem.aantallen()["beurten"] == 0


def test_logboek_wordt_gesnoeid(mem):
    for n in range(40):
        mem.log("user", f"bericht {n}")
    assert mem.snoei_beurten(bewaar=10) == 30
    assert mem.aantallen()["beurten"] == 10


def test_samenvatting(mem):
    assert "weet nog niets" in mem.samenvatting()
    mem.onthoud("feit", "Houdt van zeilen")
    assert "zeilen" in mem.samenvatting()


# --- werkgeheugen -----------------------------------------------------------

def test_werkgeheugen_houdt_de_beurten_bij():
    w = WorkingMemory(max_turns=2)
    w.add_user("een"); w.add_assistant("twee")
    w.add_user("drie"); w.add_assistant("vier")
    w.add_user("vijf")
    # Hoogstens max_turns * 2 berichten.
    assert len(w) == 4
    assert w[-1] == {"role": "user", "content": "vijf"}


def test_werkgeheugen_slaat_leeg_over():
    w = WorkingMemory()
    w.add_user("")
    assert len(w) == 0
