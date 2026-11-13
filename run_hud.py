#!/usr/bin/env python3
"""
Entrypoint voor de holografische interface.

    python run_hud.py --no-voice      alleen de HUD (geen microfoon nodig)
    python run_hud.py                 idem; de voice-loop komt in fase 2
"""

import argparse
import sys

import config


def main():
    parser = argparse.ArgumentParser(description="JARVIS Holo-Interface")
    parser.add_argument("--host", default=config.HUD_HOST)
    parser.add_argument("--port", type=int, default=config.HUD_PORT)
    parser.add_argument("--no-voice", action="store_true",
                        help="start zonder microfoon: alleen typen")
    parser.add_argument("--reload", action="store_true", help="herlaad bij codewijziging")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("uvicorn ontbreekt. Draai eerst: pip install -r requirements.txt")
        sys.exit(1)

    # uvicorn zonder websocket-ondersteuning geeft een stille 404 op /ws.
    try:
        import websockets  # noqa: F401
    except ImportError:
        try:
            import wsproto  # noqa: F401
        except ImportError:
            print("⚠️  Geen WebSocket-bibliotheek gevonden — de HUD laadt wel, maar")
            print("   blijft op 'verbinding verbroken' staan.")
            print("   Oplossing: pip install 'uvicorn[standard]'")
            sys.exit(1)

    if args.reload and not args.no_voice:
        print("ℹ️  --reload start een subproces, waar de spraakthread niet bij kan.")
        print("   Spraak wordt uitgezet; gebruik --reload alleen om de HUD te bouwen.")
        args.no_voice = True

    if args.no_voice:
        print("🔇 Spraak staat uit: alleen typen.")
    else:
        # De modellen laden in de achtergrondthread, zodat de HUD meteen opent.
        from hud import server as hud_server
        from hud.events import bus
        from voice.loop import VoiceLoop

        stem = VoiceLoop(bus=bus, respond=hud_server.respond_from_voice)
        hud_server.attach_voice(stem)
        stem.start()
        print("🎙️  Spraak start op de achtergrond — zeg 'Hey Jarvis' zodra hij klaar is.")

    configured = [name for name, cfg in config.BACKENDS.items() if cfg.get("api_key")]
    if not configured:
        print("⚠️  Geen enkele backend heeft een API-sleutel. Zet NOUS_API_KEY of")
        print("   NVIDIA_API_KEY in je .env — de HUD start wel, maar kan niet antwoorden.")
    else:
        print(f"🧠 Backends gereed: {', '.join(configured)}  (primair: {config.PRIMARY_BACKEND})")

    print("=" * 58)
    print(f"  🦾 {config.HUD_TITLE} — {config.HUD_SUBTITLE}")
    print(f"  → http://{args.host}:{args.port}")
    print("=" * 58)

    uvicorn.run(
        "hud.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
