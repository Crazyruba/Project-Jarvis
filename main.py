"""
JARVIS - Personal Voice Assistant
Entry point: wires together brain, memory, tools, voice, and speaker ID.

Pipeline:
  😴 Wake word ("Hey Jarvis")  ->  🔔 "Yes?"  ->  🗣️ Conversation mode
  In conversation mode:
    opnemen -> eigenaar verifiëren -> transcriberen -> agent -> spreken
    -> stay awake for follow-ups -> silence returns to sleep
"""

import re
import time

# --- Core (brain, memory, permissions, tools) ---
from core.llm import GeminiLLM
from core.agent import Agent
from core.permissions import PermissionManager
from tools.base import ToolRegistry
from tools.basic_tools import register_basic_tools
from tools.memory_tools import register_memory_tools
from tools.file_tools import register_file_tools
from tools.web_tools import register_web_tools
from tools.system_tools import register_system_tools
from memory.manager import MemoryManager

# --- Voice (STT, TTS, wake word, speaker ID) ---
from voice.stt import SpeechToText
from voice.tts import TextToSpeech
from voice.wake_word import WakeWordListener
from voice.voiceprint_store import VoiceprintStore
from voice.enrollment import VoiceEnrollment
from voice.speaker_id import SpeakerVerifier
from voice.greeting import maybe_greet

import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_silence(text: str) -> bool:
    """True if a transcription is empty or just punctuation/noise (no real words)."""
    if not text:
        return True
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", text)
    return len(cleaned) == 0


def build_jarvis():
    """Construct the agent brain with memory + all tools."""
    memory = MemoryManager()
    permissions = PermissionManager()

    registry = ToolRegistry(permission_manager=permissions)
    register_basic_tools(registry)
    register_memory_tools(registry, memory)
    register_file_tools(registry)
    register_web_tools(registry)
    register_system_tools(registry)
    # NOTE: Gmail + Calendar (Phase 4) intentionally skipped for now.
    # When ready: register_gmail_tools(registry); register_calendar_tools(registry)

    llm = GeminiLLM(tool_schemas=registry.get_schemas())
    agent = Agent(llm=llm, tools=registry, memory=memory)
    return agent, memory


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 55)
    print("  🦾 JARVIS — Personal Voice Assistant")
    print("=" * 55)

    # 1. Brain (agent + memory + tools)
    jarvis, memory = build_jarvis()

    # 2. Voice I/O
    stt = SpeechToText()
    tts = TextToSpeech()

    # 3. Voiceprint store (ChromaDB) + one-time enrollment
    store = VoiceprintStore()
    enrollment = VoiceEnrollment(store)
    if not enrollment.is_enrolled():
        print("👤 First run — let's enroll your voice into ChromaDB.")
        enrollment.enroll(tts)

    # 4. Speaker verifier (shares the SAME store) + wake word
    verifier = SpeakerVerifier(store)
    wake = WakeWordListener()

    tts.speak("JARVIS is online. Zeg 'Hey Jarvis' wanneer je me nodig hebt.")

    # 5. Two-state loop:  😴 wake  <->  🗣️ conversation
    try:
        running = True
        while running:
            # ===== 😴 STATE 1: Wait for the wake word =====
            wake.wait_for_wake()
            tts.speak("Ja?")

            # ===== 🗣️ STATE 2: Conversation mode =====
            in_conversation = True
            first_turn = True

            while in_conversation:
                # Let speaker audio settle before follow-up recordings
                if not first_turn:
                    time.sleep(0.4)

                # --- 🎙️ Record (single audio used for verify + transcribe) ---
                audio = stt.record(config.FOLLOWUP_LISTEN)

                # --- 🔐 Is dit de eigenaar? ---
                is_karan, score = verifier.verify(audio)
                status = f"{config.OWNER_NAME} ✅" if is_karan else "Onbekend ❌"
                print(f"   🔐 Speaker check: {status} (similarity: {score:.2f})")

                if not is_karan:
                    # Reject only on the first turn; on follow-ups, just sleep quietly
                    if first_turn:
                        tts.speak(f"Sorry, ik neem alleen opdrachten aan van {config.OWNER_NAME}.")
                    in_conversation = False
                    break

                # --- 👋 Greet once per day (first verified turn only) ---
                if first_turn:
                    maybe_greet(tts)
                first_turn = False

                # --- 🧠 Transcribe ---
                user_input = stt.transcribe(audio)

                # --- 🤫 Silence -> leave conversation, back to sleep ---
                if is_silence(user_input):
                    print("   🤫 (silence — returning to wake mode)")
                    in_conversation = False
                    break

                print(f"You (said): {user_input}")

                # --- 🛑 Voice exit commands ---
                if user_input.lower().strip() in {
                    "quit", "exit", "goodbye jarvis", "shut down"
                }:
                    tts.speak(f"Tot ziens, {config.OWNER_NAME}!")
                    running = False
                    in_conversation = False
                    break

                # --- 🧠 Run through the agent + speak the reply ---
                reply = jarvis.run(user_input)
                tts.speak(reply)

                # 🔁 Stay awake for the next follow-up (no wake word needed)
                print(f"   💬 (listening for a follow-up — stay silent to sleep)")

    except KeyboardInterrupt:
        print("\n👋 Shutting down (Ctrl+C).")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        try:
            tts.speak(f"Er ging iets mis, {config.OWNER_NAME}. Ik sluit af.")
        except Exception:
            pass
    finally:
        memory.close()
        print("💾 Memory saved. JARVIS offline.")

if __name__ == "__main__":
    main()