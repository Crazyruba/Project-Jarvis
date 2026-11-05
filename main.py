#!/usr/bin/env python3
"""
JARVIS in de terminal — zonder browser, zonder microfoon.

Handig om de agent en zijn tools te testen. De holografische interface start
je met `python run_hud.py`.

    python main.py
    python main.py --backend nvidia
    python main.py --eenmalig "wat weet je over mij?"
"""

import argparse
import sys

import config
from core.assembly import build_brain
from core.providers import BackendError

STOPWOORDEN = {"stop", "stoppen", "afsluiten", "tot ziens", "doei", "quit", "exit"}


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS in de terminal")
    parser.add_argument("--backend", default=None,
                        help=f"welk brein (standaard: {config.PRIMARY_BACKEND})")
    parser.add_argument("--eenmalig", metavar="VRAAG",
                        help="stel één vraag en stop daarna")
    args = parser.parse_args()

    ingesteld = [n for n, c in config.BACKENDS.items() if c.get("api_key")]
    if not ingesteld:
        print("⚠️  Geen enkele backend heeft een API-sleutel.")
        print("   Zet NOUS_API_KEY of NVIDIA_API_KEY in je .env.")
        return 1

    brain, memory, registry = build_brain(backend=args.backend)
    tools = len(registry.names()) if registry else 0

    print("=" * 58)
    print(f"  🦾 JARVIS — terminal  ({brain.label}, {tools} tools)")
    print("=" * 58)

    try:
        if args.eenmalig:
            return 0 if _beurt(brain, args.eenmalig) else 1

        print("Typ je vraag. 'stop' om af te sluiten.\n")
        while True:
            try:
                vraag = input(f"{config.OWNER_NAME}: ").strip()
            except EOFError:
                break
            if not vraag:
                continue
            if vraag.lower() in STOPWOORDEN:
                break
            _beurt(brain, vraag)
    except KeyboardInterrupt:
        print()
    finally:
        memory.close()
        print("💾 Geheugen bewaard. JARVIS offline.")
    return 0


def _beurt(brain, vraag: str) -> bool:
    """Eén vraag-antwoord. Geeft False als het misging."""
    print("JARVIS: ", end="", flush=True)
    gelukt = True
    try:
        for kind, value in brain.stream_events(vraag):
            if kind == "token":
                print(value, end="", flush=True)
            elif kind == "tool":
                print(f"\n   🔧 {value['name']}({value['args']})\n", end="", flush=True)
            elif kind == "error":
                print(f"\n❌ {value}")
                gelukt = False
    except BackendError as e:
        print(f"\n❌ {e}")
        gelukt = False
    print()
    return gelukt


if __name__ == "__main__":
    sys.exit(main())
