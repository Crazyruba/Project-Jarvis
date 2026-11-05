import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Eigenaar & taal
# ---------------------------------------------------------------------------
OWNER_NAME = os.getenv("OWNER_NAME", "Ruben")
LANG = os.getenv("JARVIS_LANG", "nl")          # Whisper-taalcode: nl | en


# ---------------------------------------------------------------------------
# API-sleutels
# ---------------------------------------------------------------------------
NOUS_API_KEY = os.getenv("NOUS_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
OPENCLAW_GATEWAY_TOKEN = os.getenv("OPENCLAW_GATEWAY_TOKEN")

# Google Search (optioneel, voor de web_search-tool)
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")


# ---------------------------------------------------------------------------
# Backends — alle drie OpenAI-compatibel, alleen een andere base_url
# ---------------------------------------------------------------------------
BACKENDS = {
    "nous": {
        "label": "Nous Portal",
        "base_url": os.getenv("NOUS_BASE_URL", "https://inference-api.nousresearch.com/v1"),
        "api_key": NOUS_API_KEY,
        "model": os.getenv("NOUS_MODEL", "NousResearch/Hermes-4-70B"),
    },
    "nvidia": {
        "label": "NVIDIA NIM",
        "base_url": os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        "api_key": NVIDIA_API_KEY,
        "model": os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct"),
    },
    "openclaw": {
        "label": "OpenClaw",
        "base_url": os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18789/v1"),
        "api_key": OPENCLAW_GATEWAY_TOKEN,
        "model": os.getenv("OPENCLAW_MODEL", "openclaw/default"),
    },
}

# Welke backend standaard praat, en waarop teruggevallen wordt als die faalt.
PRIMARY_BACKEND = os.getenv("PRIMARY_BACKEND", "nous")
FALLBACK_BACKEND = os.getenv("FALLBACK_BACKEND", "nvidia")

LLM_TIMEOUT = 60        # seconden per aanvraag
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 1024


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------
HUD_HOST = os.getenv("HUD_HOST", "127.0.0.1")   # loopback: niet naar buiten openzetten
HUD_PORT = int(os.getenv("HUD_PORT", "7332"))
HUD_TITLE = "J.A.R.V.I.S"
HUD_SUBTITLE = "OPENCLAW HOLO-INTERFACE"
HUD_HISTORY_LIMIT = 20      # aantal beurten dat de HUD meestuurt als context
CONFIRM_TIMEOUT = 60        # seconden wachten op goedkeuring in de HUD


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
TOOLS_ENABLED = os.getenv("TOOLS_ENABLED", "1") not in {"0", "false", "False"}
MAX_STEPS = 5               # tool-rondes per vraag


# ---------------------------------------------------------------------------
# Spraak naar tekst
# ---------------------------------------------------------------------------
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")   # tiny|base|small|medium
SAMPLE_RATE = 16000        # Whisper verwacht 16 kHz
RECORD_SECONDS = 7


# ---------------------------------------------------------------------------
# Tekst naar spraak
# ---------------------------------------------------------------------------
TTS_ENGINE = os.getenv("TTS_ENGINE", "pyttsx3")       # fase 2: "piper"
PIPER_VOICE = os.getenv("PIPER_VOICE", "nl_NL-pim-medium")
PIPER_VOICE_DIR = os.getenv("PIPER_VOICE_DIR", "data/piper")
TTS_RATE = 175
TTS_VOICE_INDEX = 0


# ---------------------------------------------------------------------------
# Wake word + sprekerherkenning
# ---------------------------------------------------------------------------
CHROMA_DB_PATH = "data/chroma_voiceprints"
WAKE_WORD_MODEL = "hey_jarvis"
WAKE_THRESHOLD = 0.80
VOICEPRINT_PATH = "data/voiceprint.npy"
SPEAKER_THRESHOLD = 0.55
ENROLL_SECONDS = 6
GREETING_STATE_PATH = "data/last_greeting.txt"
VOICEPRINT_COLLECTION = "owner_voiceprint"
ECAPA_MODEL_DIR = "data/ecapa_model"
CONFIRM_LISTEN = 3
ENROLL_SAMPLES = 5


# ---------------------------------------------------------------------------
# Gespreksmodus
# ---------------------------------------------------------------------------
FOLLOWUP_ENABLED = True
FOLLOWUP_WINDOW = 10
FOLLOWUP_LISTEN = 7


# ---------------------------------------------------------------------------
# Systeemprompt — {memory_context} wordt elke beurt opnieuw gevuld
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Je bent JARVIS, de persoonlijke assistent van {owner}.
Je bent beleefd, warm en efficiënt. Je antwoordt in het Nederlands.

Je antwoorden worden hardop voorgelezen, dus houd ze kort en spreektalig:
geen opsommingstekens, geen markdown, geen lange inleidingen. Eén tot drie
zinnen, tenzij er expliciet om meer gevraagd wordt.

Gebruik de beschikbare tools om dingen voor elkaar te krijgen. Denk stap voor stap.
Wanneer {owner} iets blijvends over zichzelf deelt (feiten, voorkeuren, projecten,
doelen), sla dat op met de save_memory-tool. Vraagt hij wat je over hem weet,
gebruik dan recall_memory of het geheugen hieronder.

--- GEHEUGEN ---
{memory_context}
--- EINDE GEHEUGEN ---
"""
