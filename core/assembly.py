"""
Eén plek waar het brein in elkaar wordt gezet.

Zowel de HUD als de terminal gebruiken dit, zodat ze gegarandeerd dezelfde
tools, hetzelfde geheugen en dezelfde instellingen hebben.
"""

from __future__ import annotations

import config
from core.brain import Brain
from core.permissions import PermissionManager
from memory.manager import MemoryManager
from tools.base import ToolRegistry
from tools.basic_tools import register_basic_tools
from tools.file_tools import register_file_tools
from tools.memory_tools import register_memory_tools
from tools.system_tools import register_system_tools
from tools.web_tools import register_web_tools


def build_registry(memory, confirm_func=None) -> ToolRegistry:
    """Alle tools, met een permissielaag voor de gevoelige."""
    registry = ToolRegistry(permission_manager=PermissionManager(confirm_func))
    register_basic_tools(registry)
    register_memory_tools(registry, memory)
    register_file_tools(registry)
    register_web_tools(registry)
    register_system_tools(registry)
    # Fase 4 en 5 hangen OpenClaw en Hermes hier als extra tools aan.
    return registry


def build_brain(confirm_func=None, backend: str | None = None):
    """
    Zet geheugen, tools en router in elkaar.

    Geeft (brain, memory, registry) terug. `confirm_func(tool, args) -> bool`
    bepaalt hoe er om toestemming wordt gevraagd; standaard is dat de terminal.
    """
    memory = MemoryManager()
    registry = build_registry(memory, confirm_func) if config.TOOLS_ENABLED else None
    brain = Brain(backend=backend, tools=registry, memory=memory)
    return brain, memory, registry
