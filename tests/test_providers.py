"""Providerlaag: backends, ontbrekende sleutels, foutafhandeling."""

import pytest

import config
from core.providers import (
    BackendError, BackendNotConfigured, OpenAICompatLLM, list_backends,
)


def test_alle_backends_staan_in_de_lijst():
    namen = {b.name for b in list_backends()}
    assert namen == set(config.BACKENDS)


def test_backend_zonder_sleutel_geldt_als_niet_ingesteld(monkeypatch):
    monkeypatch.setitem(config.BACKENDS["nous"], "api_key", None)
    nous = next(b for b in list_backends() if b.name == "nous")
    assert nous.configured is False


def test_onbekende_backend_wordt_geweigerd():
    with pytest.raises(BackendError):
        OpenAICompatLLM("bestaat-niet")


def test_stream_zonder_sleutel_geeft_duidelijke_fout(monkeypatch):
    monkeypatch.setitem(config.BACKENDS["nvidia"], "api_key", None)
    llm = OpenAICompatLLM("nvidia")
    with pytest.raises(BackendNotConfigured) as excinfo:
        list(llm.stream([{"role": "user", "content": "hoi"}]))
    assert "sleutel" in str(excinfo.value).lower()


def test_health_meldt_reden_zonder_sleutel(monkeypatch):
    monkeypatch.setitem(config.BACKENDS["nvidia"], "api_key", None)
    result = OpenAICompatLLM("nvidia").health()
    assert result["ok"] is False
    assert result["reason"]


def test_lange_foutmelding_wordt_ingekort():
    from core.providers import _kort
    assert len(_kort(RuntimeError("x" * 500))) <= 180
    assert _kort(RuntimeError("")) == "RuntimeError"
