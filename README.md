# 🦾 JARVIS — A Personal Voice Assistant Built From Scratch

> A hands-free, voice-controlled AI agent that lives on your laptop — with long-term memory, tool-calling capabilities, and **biometric voice verification** so it responds only to its owner.

JARVIS is a **from-scratch agent framework** (no LangChain, no AutoGen) built to learn and demonstrate the core engineering behind modern AI assistants: the ReAct reasoning loop, tool orchestration, layered memory, a local voice pipeline, and speaker recognition.

---

## ✨ Features

- 🧠 **Custom Agent Framework** — a hand-built ReAct loop (Reason → Act → Observe) with an extensible tool registry
- 💾 **3-Layer Memory** — working (session), short-term (recent), and long-term (persistent facts) memory
- 🎙️ **Fully Hands-Free** — wake on *"Hey Jarvis"*, then talk naturally
- 🔐 **Voice Biometrics** — ECAPA-TDNN speaker verification ensures **only the owner** can issue commands
- 🗣️ **Conversation Mode** — ask follow-ups without repeating the wake word
- 🔊 **Local Voice Pipeline** — offline speech-to-text (Whisper) and text-to-speech
- 🛡️ **Human-in-the-Loop Safety** — asks for spoken confirmation before sensitive actions (writing files, etc.)
- 🔧 **Real Capabilities** — file operations, web search, and system control (screenshots, volume, lock)

---

## 🖥️ Jarvis HUD for OpenClaw

The `hud/` folder holds a holographic 3D front-end (Vite + TypeScript + three.js) that
connects to an [OpenClaw](https://github.com/openclaw/openclaw) Gateway over WebSocket,
with browser voice input and output. See [`hud/README.md`](hud/README.md) (Dutch).

![Jarvis HUD](docs/hud-screenshot.png)

---

## 🏗️ Architecture

```
                        JARVIS
                          🧠
                      Agent Core
                  (ReAct + Gemini)
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
     Memory             Tools             Voice
        │                 │                 │
   SQLite +          Files / Web       Whisper (STT)
   ChromaDB          System Ctrl       TTS Engine
                                       Wake Word
                                       ECAPA Speaker ID
```

**Interaction flow:**

```
😴 Idle  →  "Hey Jarvis"  →  🔔 "Yes?"  →  🎙️ Record
   →  🔐 Verify it's the owner  →  🧠 Agent reasons + uses tools
   →  🔊 Speaks reply  →  🗣️ Waits for follow-up  →  😴 (silence → sleep)
```

---

## 🧰 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.11+ |
| **Reasoning (LLM)** | Google Gemini API (function-calling) |
| **Wake Word** | openWakeWord (ONNX) |
| **Speech-to-Text** | faster-whisper (offline) |
| **Text-to-Speech** | pyttsx3 / edge-tts |
| **Speaker Verification** | SpeechBrain ECAPA-TDNN |
| **Vector Store** | ChromaDB (cosine similarity) |
| **Short/Long Memory** | SQLite + ChromaDB |
| **Audio I/O** | sounddevice |

---

## 📁 Project Structure

```
Project-Jarvis/
├── main.py                 # Entry point + conversation loop
├── config.py               # All settings
├── requirements.txt
├── .env                    # API keys (not committed)
│
├── core/                   # The brain
│   ├── llm.py              # Gemini wrapper
│   ├── agent.py            # ReAct loop
│   └── permissions.py      # Confirm-before-sensitive-actions
│
├── memory/                 # Memory system
│   ├── manager.py
│   ├── working_memory.py
│   ├── short_term_memory.py
│   └── long_term_memory.py
│
├── tools/                  # Capabilities
│   ├── base.py             # Tool registry
│   ├── basic_tools.py      # time, open app
│   ├── file_tools.py       # read/write/search files
│   ├── web_tools.py        # web search
│   ├── system_tools.py     # screenshot, volume, lock
│   └── memory_tools.py     # save/recall memory
│
├── voice/                  # Voice pipeline
│   ├── stt.py              # speech → text
│   ├── tts.py              # text → speech
│   ├── wake_word.py        # "Hey Jarvis" listener
│   ├── ecapa_encoder.py    # ECAPA voiceprint engine
│   ├── voiceprint_store.py # ChromaDB voiceprint store
│   ├── enrollment.py       # one-time voice setup
│   ├── speaker_id.py       # "is this the owner?" check
│   └── greeting.py         # once-a-day greeting
│
└── data/                   # Auto-generated (memory, voiceprints, screenshots)
```

---

## 🚀 Getting Started

### 1. Clone & set up environment

```bash
git clone <your-repo-url>
cd Project-Jarvis
python -m venv venv
venv/Scripts/activate.ps1      # Windows
# source venv/bin/activate   # macOS/Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Download voice models (one-time)

```bash
python -c "import openwakeword.utils; openwakeword.utils.download_models()"
```

### 4. Add your API key

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_SEARCH_API_KEY=your_search_api_key      # optional (web search)
GOOGLE_SEARCH_ENGINE_ID=your_cx_id             # optional (web search)
```

> Get a free Gemini key at https://aistudio.google.com/apikey.

### 5. Run

```bash
python main.py
```

On first launch, JARVIS will guide you through a **one-time voice enrollment** (reads a few sentences to build your voiceprint). After that, just say **"Hey Jarvis"**! 🎙️

---

## 💬 Example Commands

```
"Hey Jarvis"  →  "What time is it?"
              →  "Take a screenshot"
              →  "Search the web for CrewAI"
              →  "Remember that I'm building Project Jarvis"
              →  "What do you know about me?"
              →  "Write a hello world script to test.py"   (asks to confirm)
```

---

## 🗺️ Development Roadmap

The project was built in independent, working phases:

- ✅ **Phase 1** — Agent framework (ReAct loop + tool registry)
- ✅ **Phase 2** — 3-layer memory system
- ✅ **Phase 3** — Tools + permission layer
- ⏳ **Phase 4** — Gmail + Calendar (planned)
- ✅ **Phase 5** — Voice pipeline (STT + TTS)
- ✅ **Phase 6** — Wake word + speaker verification
- 🔨 **Phase 7** — Polish: conversation mode, logging, auto-start

**Future ideas:** semantic memory recall (RAG), voice-activity detection (VAD), acoustic echo cancellation, and autonomous multi-step task planning.

---

## 🎓 What This Project Demonstrates

- Building an **agent framework** from first principles
- **Function-calling / tool orchestration** with an LLM
- **Vector databases** and cosine-similarity search (for both memory *and* voice biometrics)
- A complete **local voice AI pipeline**
- **Speaker verification** using production-grade embeddings (ECAPA-TDNN)
- Clean, modular **software architecture** designed to scale

---

## 🛠️ Troubleshooting

| Issue | Fix |
|-------|-----|
| `429 RESOURCE_EXHAUSTED` | Gemini quota — check usage / wait |
| Wake word won't trigger | Lower `WAKE_THRESHOLD` in `config.py` |
| Rejects your voice | Lower `SPEAKER_THRESHOLD`; re-enroll in a quiet room |
| SpeechBrain symlink error (Windows) | Use `LocalStrategy.COPY` or enable Developer Mode |
| Auto-triggers after speaking | Use headphones (avoids mic feedback) |

> **Re-enroll your voice:** delete the `data/chroma_voiceprints/` folder and restart.

---

## ⚠️ Disclaimer

JARVIS is a **personal learning project**. The voice verification is a friendly access gate, **not** fortress-grade security. Use responsibly.

---

## 📜 License

MIT License — free to use, learn from, and build upon.

---

*Built with curiosity and a lot of debugging. 🚀*