"""Toolregistry: schema's, uitvoering en de permissielaag."""

import pytest

from core.permissions import PermissionManager
from tools.base import ToolRegistry


@pytest.fixture
def registry():
    return ToolRegistry()


def test_schema_heeft_het_openai_formaat(registry):
    registry.register("get_time", lambda: "drie uur", "Geef de tijd.")
    schema = registry.get_schemas()[0]

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "get_time"
    assert schema["function"]["description"] == "Geef de tijd."
    # Zonder parameters hoort er een leeg object te staan, geen None.
    assert schema["function"]["parameters"] == {"type": "object", "properties": {}}


def test_parameters_worden_doorgegeven(registry):
    params = {"type": "object",
              "properties": {"pad": {"type": "string"}},
              "required": ["pad"]}
    registry.register("lees", lambda pad: pad, "Lees.", parameters=params)
    assert registry.get_schemas()[0]["function"]["parameters"] == params


def test_uitvoeren_geeft_het_resultaat(registry):
    registry.register("tel_op", lambda a, b: a + b, "Tel op.")
    assert registry.execute("tel_op", {"a": 2, "b": 3}) == 5


def test_onbekende_tool(registry):
    assert "onbekende tool" in registry.execute("bestaat_niet")


def test_verkeerde_argumenten_zijn_herstelbaar(registry):
    registry.register("lees", lambda pad: pad, "Lees.")
    uitkomst = registry.execute("lees", {"verkeerd": 1})
    assert "verkeerde argumenten" in uitkomst


def test_fout_in_de_tool_blijft_binnen(registry):
    def kapot():
        raise RuntimeError("schijf vol")

    registry.register("kapot", kapot, "Gaat stuk.")
    assert "schijf vol" in registry.execute("kapot")


def test_gevoelige_tool_vraagt_toestemming():
    gevraagd = []

    def sta_toe(naam, args):
        gevraagd.append((naam, args))
        return True

    reg = ToolRegistry(permission_manager=PermissionManager(sta_toe))
    reg.register("schrijf", lambda pad: f"ok {pad}", "Schrijf.", sensitive=True)

    assert reg.execute("schrijf", {"pad": "a.txt"}) == "ok a.txt"
    assert gevraagd == [("schrijf", {"pad": "a.txt"})]


def test_weigeren_voert_de_tool_niet_uit():
    gedraaid = []
    reg = ToolRegistry(permission_manager=PermissionManager(lambda n, a: False))
    reg.register("schrijf", lambda: gedraaid.append(1), "Schrijf.", sensitive=True)

    assert "geannuleerd" in reg.execute("schrijf")
    assert gedraaid == []


def test_gewone_tool_vraagt_niets():
    reg = ToolRegistry(permission_manager=PermissionManager(
        lambda n, a: pytest.fail("had niets mogen vragen")))
    reg.register("tijd", lambda: "drie uur", "Tijd.")
    assert reg.execute("tijd") == "drie uur"


def test_mislukte_toestemmingsvraag_weigert():
    def stuk(naam, args):
        raise OSError("geen terminal")

    pm = PermissionManager(stuk)
    assert pm.request("schrijf", {}) is False


def test_is_sensitive(registry):
    registry.register("a", lambda: 1, "A.")
    registry.register("b", lambda: 1, "B.", sensitive=True)
    assert registry.is_sensitive("a") is False
    assert registry.is_sensitive("b") is True
    assert registry.is_sensitive("bestaat niet") is False


def test_echte_tools_laden_zonder_scherm():
    """system_tools importeert pyautogui lui; zonder scherm mag dat niet breken."""
    from core.assembly import build_registry

    class NepGeheugen:
        def remember_fact(self, t, c): return "ok"
        def summary(self): return "niets"

    reg = build_registry(NepGeheugen())
    namen = reg.names()
    assert {"get_time", "read_file", "write_file", "save_memory"} <= set(namen)
    # Schrijven en vergrendelen horen achter een bevestiging te zitten.
    assert reg.is_sensitive("write_file") is True
    assert reg.is_sensitive("lock_screen") is True
    assert reg.is_sensitive("read_file") is False
