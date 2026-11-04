# 🦾 JARVIS — Holografische persoonlijke assistent

> Een handsfree spraakassistent met een holografische interface, die op je eigen
> laptop draait: langetermijngeheugen, tools, en biometrische stemherkenning
> zodat hij alleen naar zijn eigenaar luistert.

JARVIS is een **zelfgebouwd agent-framework** (geen LangChain, geen AutoGen) om de
techniek achter moderne AI-assistenten van de grond af te leren: de ReAct-lus,
toolorkestratie, gelaagd geheugen, een lokale spraakpijplijn en sprekerherkenning —
met daarbovenop een holografische HUD.

---

## ✨ Wat het doet

- 🪞 **Holografische interface** — procedureel 3D-hologram in de browser, dat
  meebeweegt met de stem en de toestand toont: ONLINE · LUISTERT · DENKT · SPREEKT
- 🧠 **Eigen agent-framework** — handgebouwde ReAct-lus met uitbreidbare toolregistry
- 🔀 **Vier breinen, één protocol** — Nous Portal, NVIDIA NIM, OpenClaw en Hermes
  Agent, allemaal via dezelfde OpenAI-compatibele client
- 💾 **3-laags geheugen** — werk-, korte- en langetermijngeheugen
- 🎙️ **Handsfree** — wakker op *"Hey Jarvis"*, daarna gewoon doorpraten
- 🔐 **Stembiometrie** — ECAPA-TDNN-sprekerverificatie als toegangsdrempel
- 🛡️ **Bevestiging vooraf** — gevoelige acties vragen eerst toestemming

---

## 🏗️ Architectuur

```
        ┌──────────── browser op localhost:7332 ────────────┐
        │  HOLO-HUD   hologram · status · ondertitels        │
        └───────────────────────▲───────────────────────────┘
                                │  WebSocket
        ┌───────────────────────┴───────────────────────────┐
        │  JARVIS-CORE   voice · router · geheugen           │
        └──┬───────────┬────────────┬──────────────┬────────┘
           ▼           ▼            ▼              ▼
     Nous Portal   OpenClaw    Hermes Agent   Claude Code
     + NVIDIA NIM  (handen)    (leert bij)    (bouwt de repo)
```

Het inzicht dat dit draagt: **Nous Portal, NVIDIA NIM en de OpenClaw Gateway
spreken alle drie het OpenAI chat-protocol.** Eén client met een andere
`base_url` volstaat dus. Zie [`docs/architecture.md`](docs/architecture.md).

---

## 🚀 Aan de slag

### 1. Omgeving

```bash
git clone <repo-url>
cd Project-Jarvis
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Sleutels

Maak een `.env` in de projectmap. Eén backend is genoeg om te beginnen:

```env
OWNER_NAME=Ruben

# Nous Research Portal — https://portal.nousresearch.com
NOUS_API_KEY=sk-nous-...

# NVIDIA NIM — https://build.nvidia.com (gratis credits)
NVIDIA_API_KEY=nvapi-...

# OpenClaw Gateway (fase 4, lokaal)
# OPENCLAW_GATEWAY_TOKEN=...
```

### 3. Starten

```bash
python run_hud.py --no-voice
```

Open daarna **http://127.0.0.1:7332**. Typ een bericht; het tandwiel rechtsboven
wisselt van brein en test de backends.

> De spraakpijplijn (wake word, Nederlandse herkenning, Piper-stem) komt in
> fase 2 — zie [`docs/roadmap.md`](docs/roadmap.md).

---

## ⌨️ Sneltoetsen

| Toets | Doet |
|---|---|
| `/` | naar het invoerveld |
| `spatie` (ingedrukt) | praten (fase 2) |
| `Esc` | antwoord afbreken |

---

## 📁 Indeling

```
run_hud.py          entrypoint voor de HUD
hud/                server, eventbus en de interface
core/               providers, router, agent, permissies
memory/             werk- · korte- · langetermijngeheugen
tools/              toolregistry en tools
voice/              wake word, STT, TTS, sprekerherkenning
docs/               architectuur en roadmap
```

---

## 🗺️ Roadmap

- ✅ **Fase 1** — holografische HUD + providerlaag (Nous / NVIDIA / OpenClaw)
- ⏳ **Fase 2** — Nederlandse spraak: Whisper `nl` + Piper-stem
- ⏳ **Fase 3** — tools op OpenAI tool-calling, Gemini-pad eruit
- ⏳ **Fase 4** — OpenClaw als handen
- ⏳ **Fase 5** — Hermes Agent als lerend geheugen
- ⏳ **Fase 6** — systemd-units, altijd aan

Details in [`docs/roadmap.md`](docs/roadmap.md).

---

## 🛠️ Problemen oplossen

| Probleem | Oplossing |
|---|---|
| HUD blijft op "verbinding verbroken" | `pip install 'uvicorn[standard]'` — zonder WebSocket-bibliotheek geeft `/ws` een 404 |
| "geen API-sleutel ingesteld" | Zet `NOUS_API_KEY` of `NVIDIA_API_KEY` in `.env` |
| Hologram ontbreekt | Geen WebGL; de HUD werkt verder gewoon |
| Ventilator draait hard | Zet **lite** aan in het tandwiel |
| Wake word gaat niet af | Verlaag `WAKE_THRESHOLD` in `config.py` |
| Herkent jouw stem niet | Verlaag `SPEAKER_THRESHOLD`; opnieuw inspreken in een stille kamer |

> Opnieuw inspreken: verwijder `data/chroma_voiceprints/` en start opnieuw.

---

## ⚠️ Let op

De stemverificatie is een **vriendelijke drempel, geen slot**. En houd de HUD en
de OpenClaw Gateway op loopback: een gateway-token geldt als volledige
operator-toegang.

---

## 📜 Licentie

MIT.
