"""
Eén plek waar het brein in elkaar wordt gezet.

De HUD en de terminal gebruiken dit allebei, zodat ze gegarandeerd dezelfde
tools, hetzelfde geheugen en dezelfde instellingen hebben.
"""

from __future__ import annotations

import config
from core.brain import Brain
from core.permissions import PermissionManager
from memory.store import Memory
from tools import builtin
from tools.delegation import register_delegation_tools
from tools.memory_tools import maak_geheugentools
from tools.registry import ToolRegistry


def build_registry(memory, confirm_func=None) -> ToolRegistry:
    """Alle tools, met een permissielaag voor de gevoelige."""
    registry = ToolRegistry(permission_manager=PermissionManager(confirm_func))

    registry.add_module(builtin)
    for tool_ in maak_geheugentools(memory):
        registry.add(tool_)

    # OpenClaw en Hermes komen er alleen bij als ze bereikbaar zijn.
    uitbesteed = register_delegation_tools(registry)
    if uitbesteed:
        print(f"🤝 Uitbesteden kan via: {', '.join(uitbesteed)}")

    return registry


def build_brain(confirm_func=None, backend: str | None = None):
    """
    Zet geheugen, tools en router in elkaar.

    Geeft (brain, memory, registry) terug. `confirm_func(tool, args) -> bool`
    bepaalt hoe er om toestemming wordt gevraagd; standaard is dat de terminal.
    """
    memory = Memory()
    registry = build_registry(memory, confirm_func) if config.TOOLS_ENABLED else None
    brain = Brain(backend=backend, tools=registry, memory=memory)
    return brain, memory, registry
