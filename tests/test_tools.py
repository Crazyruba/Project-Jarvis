"""Toolregistry: schema's uit de functie, uitvoering, permissies."""

from typing import Literal

import pytest

from core.permissions import PermissionManager
from tools.registry import ToolError, ToolRegistry, build_schema, tool


# --- schema's afleiden ------------------------------------------------------

def test_schema_komt_uit_de_functie():
    @tool
    def tijd() -> str:
        """Geef de huidige tijd."""

    schema = build_schema(tijd)
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "tijd"
    assert schema["function"]["description"] == "Geef de huidige tijd."
    assert schema["function"]["parameters"] == {"type": "object", "properties": {}}


def test_parameters_en_uitleg_uit_de_docstring():
    @tool
    def lees(pad: str, regels: int = 10) -> str:
        """Lees een bestand.

        pad: Pad naar het bestand.
        regels: Hoeveel regels je wil.
        """

    velden = build_schema(lees)["function"]["parameters"]
    assert velden["properties"]["pad"] == {
        "type": "string", "description": "Pad naar het bestand."}
    assert velden["properties"]["regels"]["type"] == "integer"
    # Alleen wat geen standaardwaarde heeft is verplicht.
    assert velden["required"] == ["pad"]


def test_doorlopende_uitleg_over_meerdere_regels():
    @tool
    def iets(x: str) -> str:
        """Doe iets.

        x: Een uitleg die doorloopt
           op de volgende regel.
        """

    uitleg = build_schema(iets)["function"]["parameters"]["properties"]["x"]
    assert uitleg["description"] == "Een uitleg die doorloopt op de volgende regel."


def test_literal_wordt_een_enum():
    @tool
    def zet(richting: Literal["omhoog", "omlaag"]) -> str:
        """Zet iets.

        richting: Welke kant op.
        """

    veld = build_schema(zet)["function"]["parameters"]["properties"]["richting"]
    assert veld == {"type": "string", "enum": ["omhoog", "omlaag"],
                    "description": "Welke kant op."}


def test_ontbrekend_type_is_een_fout():
    @tool
    def slecht(x) -> str:
        """Doet iets."""

    with pytest.raises(ToolError, match="type-annotatie"):
        build_schema(slecht)


def test_ontbrekende_beschrijving_is_een_fout():
    @tool
    def stil() -> str:
        pass

    with pytest.raises(ToolError, match="geen beschrijving"):
        build_schema(stil)


def test_onvertaalbaar_type_is_een_fout():
    @tool
    def raar(x: complex) -> str:
        """Doet iets.

        x: Een getal.
        """

    with pytest.raises(ToolError, match="JSON Schema"):
        build_schema(raar)


def test_zonder_decorator_geen_schema():
    def kaal(x: str) -> str:
        """Doet iets."""

    with pytest.raises(ToolError, match="niet met @tool"):
        build_schema(kaal)


# --- registry ---------------------------------------------------------------

@pytest.fixture
def registry():
    return ToolRegistry()


def test_toevoegen_en_uitvoeren(registry):
    @tool
    def tel_op(a: int, b: int) -> str:
        """Tel twee getallen op.

        a: Eerste getal.
        b: Tweede getal.
        """
        return str(a + b)

    registry.add(tel_op)
    assert registry.names() == ["tel_op"]
    assert registry.execute("tel_op", {"a": 2, "b": 3}) == "5"


def test_dubbele_naam_wordt_geweigerd(registry):
    @tool(name="zelfde")
    def een() -> str:
        """Een."""

    @tool(name="zelfde")
    def twee() -> str:
        """Twee."""

    registry.add(een)
    with pytest.raises(ToolError, match="al een tool"):
        registry.add(twee)


def test_onbekende_tool(registry):
    assert "onbekende tool" in registry.execute("bestaat_niet")


def test_verkeerde_argumenten_zijn_herstelbaar(registry):
    @tool
    def lees(pad: str) -> str:
        """Lees iets.

        pad: Het pad.
        """
        return pad

    registry.add(lees)
    assert "verkeerde argumenten" in registry.execute("lees", {"fout": 1})


def test_fout_in_de_tool_blijft_binnen(registry):
    @tool
    def kapot() -> str:
        """Gaat stuk."""
        raise RuntimeError("schijf vol")

    registry.add(kapot)
    assert "schijf vol" in registry.execute("kapot")


def test_module_in_een_keer_opnemen(registry):
    from tools import builtin

    namen = registry.add_module(builtin)
    assert "huidige_tijd" in namen
    assert "schrijf_bestand" in namen
    # Schrijven en vergrendelen horen achter een bevestiging te zitten.
    assert registry.is_sensitive("schrijf_bestand") is True
    assert registry.is_sensitive("vergrendel_scherm") is True
    assert registry.is_sensitive("lees_bestand") is False


def test_elk_ingebouwd_schema_is_geldig():
    """Een fout schema merk je anders pas als het model het probeert."""
    from tools import builtin

    registry = ToolRegistry()
    registry.add_module(builtin)
    for schema in registry.get_schemas():
        functie = schema["function"]
        assert functie["name"] and functie["description"]
        assert functie["parameters"]["type"] == "object"


# --- permissies -------------------------------------------------------------

def test_gevoelige_tool_vraagt_toestemming():
    gevraagd = []

    @tool(sensitive=True)
    def schrijf(pad: str) -> str:
        """Schrijf iets.

        pad: Het pad.
        """
        return f"ok {pad}"

    registry = ToolRegistry(permission_manager=PermissionManager(
        lambda naam, args: gevraagd.append((naam, args)) or True))
    registry.add(schrijf)

    assert registry.execute("schrijf", {"pad": "a.txt"}) == "ok a.txt"
    assert gevraagd == [("schrijf", {"pad": "a.txt"})]


def test_weigeren_voert_de_tool_niet_uit():
    gedraaid = []

    @tool(sensitive=True)
    def schrijf() -> str:
        """Schrijf iets."""
        gedraaid.append(1)
        return "gedaan"

    registry = ToolRegistry(permission_manager=PermissionManager(lambda n, a: False))
    registry.add(schrijf)

    assert "geannuleerd" in registry.execute("schrijf")
    assert gedraaid == []


def test_mislukte_toestemmingsvraag_weigert():
    def stuk(naam, args):
        raise OSError("geen terminal")

    assert PermissionManager(stuk).request("schrijf", {}) is False


# --- bestandssandbox --------------------------------------------------------
# Deze beveiliging ging eerder stuk doordat hij alleen de thuismap toestond,
# terwijl het project daar niet altijd onder valt.

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "FILE_ROOTS", [str(tmp_path)])
    return tmp_path


def test_schrijven_en_lezen_binnen_de_sandbox(sandbox):
    from tools.builtin import lees_bestand, schrijf_bestand

    assert "Opgeslagen" in schrijf_bestand(str(sandbox / "a.txt"), "hallo")
    assert lees_bestand(str(sandbox / "a.txt")) == "hallo"


def test_bestaand_bestand_vervangen_wordt_gemeld(sandbox):
    from tools.builtin import schrijf_bestand

    pad = str(sandbox / "a.txt")
    schrijf_bestand(pad, "een")
    assert "Vervangen" in schrijf_bestand(pad, "twee")


def test_submappen_worden_aangemaakt(sandbox):
    from tools.builtin import schrijf_bestand

    assert "Opgeslagen" in schrijf_bestand(str(sandbox / "diep/er/a.txt"), "x")
    assert (sandbox / "diep/er/a.txt").read_text() == "x"


@pytest.mark.parametrize("pad", [
    "/etc/passwd",
    "/tmp/ergens-anders.txt",
])
def test_buiten_de_sandbox_wordt_geweigerd(sandbox, pad):
    from tools.builtin import lees_bestand, schrijf_bestand

    assert "valt buiten" in schrijf_bestand(pad, "x")
    assert "valt buiten" in lees_bestand(pad)


def test_ontsnappen_met_puntpunt_wordt_geweigerd(sandbox):
    from tools.builtin import schrijf_bestand

    uitkomst = schrijf_bestand(str(sandbox / "../../../../etc/kwaad.txt"), "x")
    assert "valt buiten" in uitkomst


def test_meerdere_wortels_mogen(tmp_path, monkeypatch):
    import config
    from tools.builtin import schrijf_bestand

    een, twee = tmp_path / "een", tmp_path / "twee"
    een.mkdir(); twee.mkdir()
    monkeypatch.setattr(config, "FILE_ROOTS", [str(een), str(twee)])

    assert "Opgeslagen" in schrijf_bestand(str(een / "a.txt"), "x")
    assert "Opgeslagen" in schrijf_bestand(str(twee / "b.txt"), "x")
    assert "valt buiten" in schrijf_bestand(str(tmp_path / "c.txt"), "x")


def test_ontbrekend_bestand(sandbox):
    from tools.builtin import lees_bestand
    assert "niet gevonden" in lees_bestand(str(sandbox / "bestaat-niet.txt"))


def test_te_groot_bestand_wordt_niet_voorgelezen(sandbox, monkeypatch):
    from tools import builtin

    monkeypatch.setattr(builtin, "MAX_LEESGROOTTE", 10)
    (sandbox / "groot.txt").write_text("x" * 100)
    assert "te groot" in builtin.lees_bestand(str(sandbox / "groot.txt"))


def test_lange_inhoud_wordt_ingekort(sandbox, monkeypatch):
    from tools import builtin

    monkeypatch.setattr(builtin, "MAX_ANTWOORD", 50)
    (sandbox / "lang.txt").write_text("y" * 500)
    assert "ingekort" in builtin.lees_bestand(str(sandbox / "lang.txt"))


def test_zoeken_slaat_verborgen_mappen_over(sandbox):
    from tools.builtin import zoek_bestanden

    (sandbox / ".git").mkdir()
    (sandbox / ".git" / "notitie.txt").write_text("x")
    (sandbox / "notitie.txt").write_text("x")

    uitkomst = zoek_bestanden(str(sandbox), "notitie")
    assert "1 gevonden" in uitkomst
    assert ".git" not in uitkomst


def test_huidige_tijd_is_nederlands():
    from tools.builtin import huidige_tijd
    tekst = huidige_tijd()
    assert tekst.startswith("Het is ")
    assert "uur" in tekst
