"""
Je stem inspreken, eenmalig.

    python -m voice.enroll            inspreken
    python -m voice.enroll --reset    wissen en opnieuw
    python -m voice.enroll --status   wat staat er al
    python -m voice.enroll --check    test of je herkend wordt
"""

from __future__ import annotations

import argparse
import sys

import config

ZINNEN = [
    "Mijn naam is {owner} en dit is mijn assistent.",
    "Hey Jarvis, je spreekt met {owner}.",
    "Onthoud alsjeblieft hoe mijn stem klinkt.",
    "Ik ben degene die deze assistent opdrachten geeft.",
    "Dit is {owner}, ik bevestig wie ik ben.",
    "De zon ging onder achter de oude houten schuur.",
    "Zeven vrolijke musici speelden tot diep in de nacht.",
]


def spreek_in(store, zeg, luister, encoder, aantal: int) -> int:
    """Neem een aantal zinnen op. Geeft terug hoeveel er bruikbaar waren."""
    zeg(f"We gaan mijn stemherkenning instellen, {config.OWNER_NAME}. "
        f"Ik vraag je {aantal} zinnen voor te lezen. Spreek rustig en duidelijk.")

    gelukt = 0
    for nummer in range(aantal):
        zin = ZINNEN[nummer % len(ZINNEN)].format(owner=config.OWNER_NAME)
        zeg(f"Zin {nummer + 1}. Zeg: {zin}")
        print(f"🎙️  Opname {nummer + 1}/{aantal} — zeg: {zin}")

        opname = luister()
        if not opname.had_spraak or opname.seconden < 1.0:
            print("   ⚠️  Niets of te kort opgenomen; deze slaan we over.")
            zeg("Ik hoorde niets. We proberen de volgende.")
            continue

        try:
            store.voeg_toe(encoder.embed(opname.audio))
        except Exception as e:
            print(f"   ⚠️  Deze opname kon niet verwerkt worden: {e}")
            continue

        gelukt += 1
        print(f"   ✅ Opgeslagen ({opname.seconden:.1f}s)")

    return gelukt


def main() -> int:
    parser = argparse.ArgumentParser(description="Stemafdruk inspreken")
    parser.add_argument("--reset", action="store_true", help="wissen en opnieuw")
    parser.add_argument("--status", action="store_true", help="wat staat er al")
    parser.add_argument("--check", action="store_true", help="test de herkenning")
    parser.add_argument("--aantal", type=int, default=config.ENROLL_SAMPLES)
    args = parser.parse_args()

    from voice.voiceprint import VoiceprintStore

    store = VoiceprintStore()

    if args.status:
        if store.is_ingesproken():
            print(f"✅ {store.aantal} stemafdruk(ken) opgeslagen voor {store.eigenaar}.")
            print(f"   Bestand: {store.pad}")
        else:
            print("Nog niets ingesproken. Draai: python -m voice.enroll")
        return 0

    from voice.encoder import get_encoder
    from voice.listener import Microfoon
    from voice.tts import TextToSpeech

    tts = TextToSpeech()
    microfoon = Microfoon()

    if args.check:
        if not store.is_ingesproken():
            print("Er is nog niets ingesproken.")
            return 1
        tts.speak("Zeg iets, dan kijk ik of ik je herken.")
        opname = microfoon.neem_op()
        if not opname.had_spraak:
            print("Ik hoorde niets.")
            return 1
        oordeel = store.vergelijk(get_encoder().embed(opname.audio))
        print(f"Uitkomst: {oordeel}")
        tts.speak("Ik herken je." if oordeel.is_eigenaar
                  else "Ik herken je niet; de drempel staat misschien te hoog.")
        return 0 if oordeel.is_eigenaar else 1

    if args.reset and store.is_ingesproken():
        print("🗑️  Bestaande stemafdrukken wissen…")
        store.wis()

    if store.is_ingesproken():
        print(f"✅ Er staan al {store.aantal} stemafdrukken.")
        print("   Opnieuw inspreken: python -m voice.enroll --reset")
        return 0

    print(f"🔊 Stem: {tts.name}")
    gelukt = spreek_in(store, tts.speak, microfoon.neem_op, get_encoder(), args.aantal)

    if gelukt == 0:
        tts.speak("Er is niets opgenomen. Controleer je microfoon.")
        return 1
    if gelukt < max(2, args.aantal // 2):
        tts.speak(f"Maar {gelukt} opnames gelukt. Dat werkt, maar de herkenning "
                  "wordt beter als je het nog eens doet.")
    else:
        tts.speak("Gelukt. Je stemafdruk is opgeslagen; ik herken je voortaan.")

    print(f"✅ Klaar — {gelukt} stemafdrukken in {store.pad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
