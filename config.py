import os
from pathlib import Path

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

# Waar de bestandstools mogen komen. Standaard je thuismap plus de projectmap
# zelf — die laatste is nodig voor schermafbeeldingen en het geheugen, en valt
# niet altijd onder je thuismap. Meerdere paden scheiden met een dubbele punt.
FILE_ROOTS = [
    p for p in (
        os.getenv("FILE_ROOTS", "").split(os.pathsep)
        or []
    ) if p
] or [str(Path.home()), str(Path(__file__).resolve().parent)]
MAX_STEPS = 5               # tool-rondes per vraag


# ---------------------------------------------------------------------------
# Uitbesteden: OpenClaw doet dingen op deze pc, Hermes leert en werkt lang door
# ---------------------------------------------------------------------------
# OpenClaw gebruikt de backend-instellingen hierboven. Zet in openclaw.json:
#   gateway: { http: { endpoints: { chatCompletions: { enabled: true } } } }
OPENCLAW_TIMEOUT = int(os.getenv("OPENCLAW_TIMEOUT", "300"))

HERMES_BIN = os.getenv("HERMES_BIN", "hermes")
HERMES_TIMEOUT = int(os.getenv("HERMES_TIMEOUT", "900"))
HERMES_MODEL = os.getenv("HERMES_MODEL")       # leeg = wat Hermes zelf ingesteld heeft

# Uitbesteden kan echte dingen doen, dus standaard eerst even vragen.
DELEGATE_CONFIRM = os.getenv("DELEGATE_CONFIRM", "1") not in {"0", "false", "False"}


# ---------------------------------------------------------------------------
# Spraak naar tekst
# ---------------------------------------------------------------------------
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")   # tiny|base|small|medium
SAMPLE_RATE = 16000        # Whisper verwacht 16 kHz

# Opnemen stopt op stilte, niet op een vaste duur.
MAX_OPNAME = float(os.getenv("MAX_OPNAME", "20"))        # harde bovengrens
STILTE_NA = float(os.getenv("STILTE_NA", "0.9"))         # stilte die een zin afsluit
WACHT_OP_SPRAAK = float(os.getenv("WACHT_OP_SPRAAK", "3"))  # geduld voor het eerste woord


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
WAKE_WORD_MODEL = os.getenv("WAKE_WORD_MODEL", "hey_jarvis")
WAKE_THRESHOLD = float(os.getenv("WAKE_THRESHOLD", "0.80"))

VOICEPRINT_PATH = os.getenv("VOICEPRINT_PATH", "data/voiceprint.npz")
SPEAKER_THRESHOLD = float(os.getenv("SPEAKER_THRESHOLD", "0.55"))
ECAPA_MODEL_DIR = os.getenv("ECAPA_MODEL_DIR", "data/ecapa_model")
ENROLL_SAMPLES = int(os.getenv("ENROLL_SAMPLES", "5"))

GREETING_STATE_PATH = "data/laatste_groet.txt"


# ---------------------------------------------------------------------------
# Gespreksmodus
# ---------------------------------------------------------------------------
FOLLOWUP_ENABLED = os.getenv("FOLLOWUP_ENABLED", "1") not in {"0", "false", "False"}


# ---------------------------------------------------------------------------
# Systeemprompt — {memory_context} wordt elke beurt opnieuw gevuld
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Je bent JARVIS, de persoonlijke assistent van {owner}.
Je bent beleefd, warm en efficiënt. Je antwoordt in het Nederlands.

Je antwoorden worden hardop voorgelezen, dus houd ze kort en spreektalig:
geen opsommingstekens, geen markdown, geen lange inleidingen. Eén tot drie
zinnen, tenzij er expliciet om meer gevraagd wordt.

Denk stap voor stap en kies bewust wat je zelf doet en wat je uitbesteedt:

- Vragen, uitleg en gesprek: zelf beantwoorden.
- Iets opzoeken, lezen, schrijven of op deze pc bedienen: je eigen tools.
- Een handeling op de computer die verder gaat dan je eigen tools, of een
  bericht via WhatsApp of Telegram: gebruik openclaw_task, als die er is.
- Een langere klus die uitgezocht moet worden, meerdere stappen kost, of die
  onthouden moet blijven voor later: gebruik hermes_task, als die er is.
  Dat duurt even, dus niet voor iets wat je zelf kunt beantwoorden.

Besteed nooit iets uit wat je in één zin kunt beantwoorden.

Wanneer {owner} iets blijvends over zichzelf deelt (feiten, voorkeuren,
projecten, doelen), sla dat op met de save_memory-tool. Vraagt hij wat je over
hem weet, gebruik dan recall_memory of het geheugen hieronder.

--- GEHEUGEN ---
{memory_context}
--- EINDE GEHEUGEN ---
"""
