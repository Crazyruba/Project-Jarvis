"""Uitbesteden aan OpenClaw en Hermes."""

import subprocess

import pytest

import config
from tools import delegation
from tools.base import ToolRegistry


# --- beschikbaarheid --------------------------------------------------------

def test_openclaw_telt_pas_mee_met_token(monkeypatch):
    monkeypatch.setitem(config.BACKENDS["openclaw"], "api_key", None)
    assert delegation.openclaw_available() is False
    monkeypatch.setitem(config.BACKENDS["openclaw"], "api_key", "geheim")
    assert delegation.openclaw_available() is True


def test_hermes_telt_pas_mee_als_het_commando_bestaat(monkeypatch):
    monkeypatch.setattr(delegation.shutil, "which", lambda naam: None)
    assert delegation.hermes_available() is False
    monkeypatch.setattr(delegation.shutil, "which", lambda naam: "/usr/bin/hermes")
    assert delegation.hermes_available() is True


def test_tools_worden_niet_aangeboden_als_ze_er_niet_zijn(monkeypatch):
    monkeypatch.setitem(config.BACKENDS["openclaw"], "api_key", None)
    monkeypatch.setattr(delegation.shutil, "which", lambda naam: None)

    registry = ToolRegistry()
    assert delegation.register_delegation_tools(registry) == []
    assert registry.names() == []


def test_beide_tools_worden_aangeboden_als_ze_er_wel_zijn(monkeypatch):
    monkeypatch.setitem(config.BACKENDS["openclaw"], "api_key", "geheim")
    monkeypatch.setattr(delegation.shutil, "which", lambda naam: "/usr/bin/hermes")

    registry = ToolRegistry()
    namen = delegation.register_delegation_tools(registry)
    assert set(namen) == {"openclaw_task", "hermes_task"}
    # Uitbesteden kan echt iets doen, dus er hoort eerst gevraagd te worden.
    assert registry.is_sensitive("openclaw_task") is True
    assert registry.is_sensitive("hermes_task") is True


def test_bevestiging_kan_uit(monkeypatch):
    monkeypatch.setattr(config, "DELEGATE_CONFIRM", False)
    monkeypatch.setitem(config.BACKENDS["openclaw"], "api_key", "geheim")
    monkeypatch.setattr(delegation.shutil, "which", lambda naam: None)

    registry = ToolRegistry()
    delegation.register_delegation_tools(registry)
    assert registry.is_sensitive("openclaw_task") is False


# --- OpenClaw ---------------------------------------------------------------

def test_openclaw_zonder_token_legt_uit_wat_er_moet_gebeuren(monkeypatch):
    monkeypatch.setitem(config.BACKENDS["openclaw"], "api_key", None)
    uitkomst = delegation.openclaw_task("doe iets")
    assert "OPENCLAW_GATEWAY_TOKEN" in uitkomst
    assert "chatCompletions" in uitkomst


def test_openclaw_geeft_het_antwoord_terug(monkeypatch):
    monkeypatch.setitem(config.BACKENDS["openclaw"], "api_key", "geheim")
    monkeypatch.setattr("core.providers.OpenAICompatLLM.complete",
                        lambda self, messages: "  Gedaan.  ")
    assert delegation.openclaw_task("doe iets") == "Gedaan."


def test_openclaw_fout_wordt_een_nette_melding(monkeypatch):
    from core.providers import BackendError
    monkeypatch.setitem(config.BACKENDS["openclaw"], "api_key", "geheim")

    def kapot(self, messages):
        raise BackendError("gateway draait niet")

    monkeypatch.setattr("core.providers.OpenAICompatLLM.complete", kapot)
    uitkomst = delegation.openclaw_task("doe iets")
    assert "gateway draait niet" in uitkomst


def test_leeg_antwoord_van_openclaw(monkeypatch):
    monkeypatch.setitem(config.BACKENDS["openclaw"], "api_key", "geheim")
    monkeypatch.setattr("core.providers.OpenAICompatLLM.complete",
                        lambda self, messages: "   ")
    assert "geen antwoord" in delegation.openclaw_task("doe iets")


# --- Hermes -----------------------------------------------------------------

def _hermes(monkeypatch, *, stdout="", stderr="", code=0, exc=None, vangop=None):
    monkeypatch.setattr(delegation.shutil, "which", lambda naam: "/usr/bin/hermes")

    def nep_run(args, **kwargs):
        if vangop is not None:
            vangop.extend(args)
        if exc is not None:
            raise exc
        return subprocess.CompletedProcess(args, code, stdout, stderr)

    monkeypatch.setattr(delegation.subprocess, "run", nep_run)


def test_hermes_zonder_installatie_legt_uit_hoe(monkeypatch):
    monkeypatch.setattr(delegation.shutil, "which", lambda naam: None)
    assert "install.sh" in delegation.hermes_task("zoek uit")


def test_hermes_geeft_de_uitvoer_terug(monkeypatch):
    _hermes(monkeypatch, stdout="Klaar, ik heb het onthouden.\n")
    assert delegation.hermes_task("zoek uit") == "Klaar, ik heb het onthouden."


def test_hermes_krijgt_de_opdracht_mee(monkeypatch):
    args = []
    _hermes(monkeypatch, stdout="ok", vangop=args)
    delegation.hermes_task("zoek het weer op")
    assert args[1] == "-z"
    assert args[2] == "zoek het weer op"


def test_hermes_model_wordt_meegegeven(monkeypatch):
    args = []
    monkeypatch.setattr(config, "HERMES_MODEL", "anthropic/claude-sonnet-4.6")
    _hermes(monkeypatch, stdout="ok", vangop=args)
    delegation.hermes_task("x")
    assert "--model" in args and "anthropic/claude-sonnet-4.6" in args


def test_hermes_foutcode_wordt_gemeld(monkeypatch):
    _hermes(monkeypatch, stderr="geen provider ingesteld", code=1)
    assert "geen provider ingesteld" in delegation.hermes_task("x")


def test_hermes_dat_te_lang_duurt(monkeypatch):
    _hermes(monkeypatch, exc=subprocess.TimeoutExpired("hermes", 1))
    uitkomst = delegation.hermes_task("x")
    assert "nog bezig" in uitkomst and "~/.hermes/logs" in uitkomst


def test_hermes_dat_niet_start(monkeypatch):
    _hermes(monkeypatch, exc=OSError("permissie geweigerd"))
    assert "kon niet starten" in delegation.hermes_task("x")


def test_lange_uitvoer_wordt_ingekort(monkeypatch):
    _hermes(monkeypatch, stdout="x" * 5000)
    uitkomst = delegation.hermes_task("x")
    assert uitkomst.endswith("…[ingekort]") and len(uitkomst) < 2100
