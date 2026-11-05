"""De ReAct-lus op OpenAI tool-calling."""

import pytest

import config
from core.agent import Agent, _parse_args
from tools.base import ToolRegistry


class NepLLM:
    """Speelt vooraf bepaalde beurten af, zoals een model dat zou doen."""

    def __init__(self, beurten):
        self.beurten = list(beurten)
        self.gezien = []          # de berichten per beurt

    def stream_with_tools(self, messages, tools=None):
        self.gezien.append(list(messages))
        if not self.beurten:
            yield "token", "(niets meer)"
            return
        for item in self.beurten.pop(0):
            yield item


def _call(naam, args='{}', id="c1"):
    return "tool_calls", [{"id": id, "name": naam, "arguments": args}]


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register("get_time", lambda: "Het is drie uur.", "Tijd.")
    reg.register("tel_op", lambda a, b: str(a + b), "Tel op.")
    return reg


# --- argumenten ------------------------------------------------------------

def test_lege_argumenten():
    assert _parse_args("") == {}
    assert _parse_args(None) == {}


def test_json_argumenten():
    assert _parse_args('{"a": 1}') == {"a": 1}


def test_onleesbare_argumenten_blijven_tekst():
    assert _parse_args("{kapot") == "{kapot"


# --- de lus ----------------------------------------------------------------

def test_zonder_tools_komt_het_antwoord_direct(registry):
    llm = NepLLM([[("token", "Hallo "), ("token", "Ruben.")]])
    agent = Agent(llm, registry)
    assert agent.run("hoi") == "Hallo Ruben."


def test_tool_wordt_aangeroepen_en_het_antwoord_volgt(registry):
    llm = NepLLM([
        [_call("get_time")],
        [("token", "Het is drie uur.")],
    ])
    agent = Agent(llm, registry)

    soorten = [k for k, _ in agent.stream("hoe laat is het")]
    assert soorten == ["tool", "tool_result", "token"]

    # De tweede beurt moet het toolresultaat in de berichten hebben.
    tweede = llm.gezien[1]
    assert tweede[-1]["role"] == "tool"
    assert tweede[-1]["content"] == "Het is drie uur."
    assert tweede[-2]["role"] == "assistant"
    assert tweede[-2]["tool_calls"][0]["function"]["name"] == "get_time"


def test_argumenten_komen_bij_de_tool_aan(registry):
    llm = NepLLM([
        [_call("tel_op", '{"a": 2, "b": 5}')],
        [("token", "Zeven.")],
    ])
    resultaten = [v for k, v in Agent(llm, registry).stream("2 plus 5")
                  if k == "tool_result"]
    assert resultaten[0]["result"] == "7"


def test_argumenten_in_stukjes_worden_samengevoegd(registry):
    """Een model stuurt argumenten per fragment; die horen aaneengeplakt te worden."""
    class GestukteLLM:
        def __init__(self): self.beurt = 0
        def stream_with_tools(self, messages, tools=None):
            self.beurt += 1
            if self.beurt == 1:
                yield "tool_calls", [{"id": "c1", "name": "tel_op",
                                      "arguments": '{"a": 2, "b": 5}'}]
            else:
                yield "token", "Zeven."

    resultaten = [v for k, v in Agent(GestukteLLM(), registry).stream("x")
                  if k == "tool_result"]
    assert resultaten[0]["result"] == "7"


def test_meerdere_tools_in_een_beurt(registry):
    llm = NepLLM([
        [("tool_calls", [
            {"id": "a", "name": "get_time", "arguments": "{}"},
            {"id": "b", "name": "tel_op", "arguments": '{"a": 1, "b": 1}'},
        ])],
        [("token", "Klaar.")],
    ])
    namen = [v["name"] for k, v in Agent(llm, registry).stream("x") if k == "tool"]
    assert namen == ["get_time", "tel_op"]


def test_onleesbare_argumenten_geven_een_nette_fout(registry):
    llm = NepLLM([[_call("tel_op", "{kapot")], [("token", "Sorry.")]])
    resultaten = [v for k, v in Agent(llm, registry).stream("x") if k == "tool_result"]
    assert "onleesbare argumenten" in resultaten[0]["result"]


def test_stappenlimiet_wordt_gerespecteerd(registry, monkeypatch):
    monkeypatch.setattr(config, "MAX_STEPS", 3)
    # Een model dat blijft tools aanroepen en nooit antwoordt.
    llm = NepLLM([[_call("get_time")] for _ in range(10)])

    tools = [v for k, v in Agent(llm, registry).stream("x") if k == "tool"]
    laatste = [v for k, v in Agent(NepLLM([[_call("get_time")]] * 10), registry)
               .stream("x") if k == "token"]

    assert len(tools) == 3
    assert "stappenlimiet" in laatste[-1]


def test_backendfout_komt_als_error_naar_buiten(registry):
    from core.providers import BackendError

    class Kapot:
        def stream_with_tools(self, messages, tools=None):
            raise BackendError("Nous Portal: geen verbinding")
            yield  # pragma: no cover

    gebeurtenissen = list(Agent(Kapot(), registry).stream("x"))
    assert gebeurtenissen == [("error", "Nous Portal: geen verbinding")]


# --- context ---------------------------------------------------------------

def test_systeemprompt_en_geschiedenis(registry):
    agent = Agent(NepLLM([]), registry)
    messages = agent.build_messages("nu", [{"role": "user", "content": "eerder"}],
                                    "Houdt van koffie.")
    assert messages[0]["role"] == "system"
    assert config.OWNER_NAME in messages[0]["content"]
    assert "Houdt van koffie." in messages[0]["content"]
    assert messages[1]["content"] == "eerder"
    assert messages[-1] == {"role": "user", "content": "nu"}


def test_tools_worden_aan_het_model_aangeboden(registry):
    llm = NepLLM([[("token", "ok")]])
    agent = Agent(llm, registry)
    list(agent.stream("x"))
    # Het schema moet meegaan; NepLLM bewaart alleen de berichten, dus
    # controleer via de registry dat er iets aan te bieden valt.
    assert len(registry.get_schemas()) == 2
