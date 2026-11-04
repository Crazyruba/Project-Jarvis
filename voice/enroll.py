"""
Eenmalig je stem inspreken.

    python -m voice.enroll              # inspreken
    python -m voice.enroll --reset      # eerst wissen, dan opnieuw
    python -m voice.enroll --status     # staat er al iets?
"""

import argparse
import sys

import config


def main() -> int:
    parser = argparse.ArgumentParser(description="Stemafdruk inspreken")
    parser.add_argument("--reset", action="store_true",
                        help="bestaande stemafdrukken wissen en opnieuw beginnen")
    parser.add_argument("--status", action="store_true",
                        help="alleen tonen wat er is opgeslagen")
    args = parser.parse_args()

    from voice.voiceprint_store import VoiceprintStore

    store = VoiceprintStore()

    if args.status:
        aantal = store.count()
        if aantal:
            print(f"✅ {aantal} stemafdruk(ken) opgeslagen voor {config.OWNER_NAME}.")
        else:
            print("Nog niets ingesproken. Draai: python -m voice.enroll")
        return 0

    if args.reset and store.is_enrolled():
        print("🗑️  Bestaande stemafdrukken wissen…")
        store.reset()

    if store.is_enrolled():
        print(f"✅ Er staan al {store.count()} stemafdrukken.")
        print("   Opnieuw inspreken: python -m voice.enroll --reset")
        return 0

    from voice.enrollment import VoiceEnrollment
    from voice.tts import TextToSpeech

    tts = TextToSpeech()
    print(f"🔊 Stem: {tts.name}")
    VoiceEnrollment(store).enroll(tts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
