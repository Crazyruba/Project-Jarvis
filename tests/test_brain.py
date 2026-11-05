"""Router: opbouw van de context en terugvallen op de reservebackend."""

import pytest

import config
from core.brain import Brain
from core.providers import BackendError


def test_systeemprompt_bevat_eigenaar_en_geheugen():
    brain = Brain("nous")
    messages = brain.build_messages("hoi", [], "Houdt van koffie.")
    system = messages[0]["content"]
    assert messages[0]["role"] == "system"
    assert config.OWNER_NAME in system
    assert "Houdt van koffie." in system


def test_geschiedenis_wordt_afgekapt():
    brain = Brain("nous")
    lang = [{"role": "user", "content": str(i)} for i in range(100)]
    messages = brain.build_messages("nu", lang)
    # systeemprompt + afgekapte geschiedenis + de nieuwe vraag
    assert len(messages) == config.HUD_HISTORY_LIMIT + 2
    assert messages[-1]["content"] == "nu"


def test_lege_herinneringen_leveren_nette_tekst():
    system = Brain("nous").build_messages("hoi", [])[0]["content"]
    assert "Nog geen opgeslagen herinneringen." in system


def test_valt_terug_op_reservebackend(monkeypatch):
    brain = Brain("nous")

    def kapot(self, messages):
        raise BackendError("primair ligt eruit")
        yield  # pragma: no cover

    def werkt(self, messages):
        yield "reserve "
        yield "antwoord"

    import core.providers as providers
    # De primaire instantie faalt, de reserve wordt vers aangemaakt.
    monkeypatch.setattr(brain._llm, "stream", lambda m: kapot(None, m))
    monkeypatch.setattr(providers.OpenAICompatLLM, "stream", werkt)

    assert "".join(brain.stream("hoi")) == "reserve antwoord"
    assert brain.last_backend_used == config.FALLBACK_BACKEND


def test_zonder_bruikbare_reserve_komt_de_oorspronkelijke_fout_terug(monkeypatch):
    brain = Brain("nous")

    def kapot(messages):
        raise BackendError("primair ligt eruit")
        yield  # pragma: no cover

    import core.providers as providers
    monkeypatch.setattr(brain._llm, "stream", kapot)
    monkeypatch.setattr(providers.OpenAICompatLLM, "stream",
                        lambda self, m: (_ for _ in ()).throw(BackendError("reserve ook")))

    with pytest.raises(BackendError) as excinfo:
        list(brain.stream("hoi"))
    assert "primair ligt eruit" in str(excinfo.value)


def test_van_backend_wisselen():
    brain = Brain("nous")
    brain.use("nvidia")
    assert brain.backend_name == "nvidia"
    assert brain.label == config.BACKENDS["nvidia"]["label"]
