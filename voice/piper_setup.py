"""
Haalt de Nederlandse Piper-stem op.

    python -m voice.piper_setup                 # stem uit config
    python -m voice.piper_setup nl_BE-nathalie-medium
    python -m voice.piper_setup --list          # welke stemmen staan er al

De modellen komen van Hugging Face (rhasspy/piper-voices) en komen in
data/piper/ te staan, die map wordt niet meegecommit.
"""

import argparse
import sys
from pathlib import Path

import config

# Een paar Nederlandse stemmen die bij Piper beschikbaar zijn.
SUGGESTIES = [
    "nl_NL-pim-medium",
    "nl_NL-mls-medium",
    "nl_BE-nathalie-medium",
    "nl_BE-rdh-medium",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Piper-stem ophalen")
    parser.add_argument("voice", nargs="?", default=config.PIPER_VOICE,
                        help=f"stemnaam (standaard: {config.PIPER_VOICE})")
    parser.add_argument("--dir", default=config.PIPER_VOICE_DIR)
    parser.add_argument("--list", action="store_true",
                        help="toon de stemmen die al binnen zijn")
    args = parser.parse_args()

    doelmap = Path(args.dir)

    if args.list:
        doelmap.mkdir(parents=True, exist_ok=True)
        aanwezig = sorted(p.stem for p in doelmap.glob("*.onnx"))
        if aanwezig:
            print("Aanwezige stemmen:")
            for naam in aanwezig:
                merk = "  ← in gebruik" if naam == config.PIPER_VOICE else ""
                print(f"  - {naam}{merk}")
        else:
            print(f"Nog geen stemmen in {doelmap}.")
        print("\nSuggesties voor Nederlands:")
        for naam in SUGGESTIES:
            print(f"  - {naam}")
        return 0

    try:
        from piper.download_voices import download_voice
    except ImportError:
        print("piper-tts ontbreekt. Draai eerst: pip install -r requirements.txt")
        return 1

    doelmap.mkdir(parents=True, exist_ok=True)
    model = doelmap / f"{args.voice}.onnx"
    if model.exists():
        print(f"✅ {args.voice} staat al in {doelmap}.")
        return 0

    print(f"⬇️  {args.voice} ophalen naar {doelmap} …")
    try:
        download_voice(args.voice, doelmap)
    except Exception as e:
        print(f"❌ Ophalen mislukt: {e}")
        print("\nControleer de stemnaam. Suggesties voor Nederlands:")
        for naam in SUGGESTIES:
            print(f"  - {naam}")
        print("\nAlle stemmen: https://huggingface.co/rhasspy/piper-voices")
        return 1

    print(f"✅ Klaar. Zet TTS_ENGINE=piper en PIPER_VOICE={args.voice} in je .env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
