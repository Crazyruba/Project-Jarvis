# 🦾 JARVIS — Holografische persoonlijke assistent

[![tests](https://github.com/Crazyruba/Project-Jarvis/actions/workflows/tests.yml/badge.svg)](https://github.com/Crazyruba/Project-Jarvis/actions/workflows/tests.yml)

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

### 3. Stem ophalen en inspreken (eenmalig)

```bash
python -m voice.piper_setup     # Nederlandse stem ophalen
python -m voice.enroll          # je eigen stem inspreken
```

### 4. Starten

```bash
python run_hud.py               # met spraak
python run_hud.py --no-voice    # alleen typen
python main.py                  # in de terminal, zonder browser
```

Open daarna **http://127.0.0.1:7332**. Zeg *"Hey Jarvis"*, houd **spatie**
ingedrukt, of typ gewoon.

### 5. Altijd aan (optioneel)

```bash
./deploy/install.sh --all
```

Zet JARVIS als gebruikersdienst op, samen met OpenClaw en Hermes als die er
zijn. Logboek: `journalctl --user -u jarvis-hud -f`.

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
main.py             dezelfde agent, in de terminal
hud/                server, eventbus en de holografische interface
core/               providers, router, agent, permissies, assemblage
memory/             store.py (blijvend, SQLite + FTS5) · working_memory.py
tools/              registry.py (schema's uit de functie) · builtin · delegation
voice/              listener · voiceprint · encoder · stt · tts · loop
deploy/             systemd-units en installatiescript
docs/               architectuur en roadmap
```

---

## 🗺️ Roadmap

- ✅ **Fase 1** — holografische HUD + providerlaag (Nous / NVIDIA / OpenClaw)
- ✅ **Fase 2** — Nederlandse spraak: Whisper `nl` + Piper-stem
- ✅ **Fase 3** — tools op OpenAI tool-calling, Gemini-pad eruit
- ✅ **Fase 4** — OpenClaw als handen
- ✅ **Fase 5** — Hermes Agent als lerend geheugen
- ✅ **Fase 6** — systemd-units, altijd aan

Alles staat er; wat nog mist is draaien op de echte machine — zie
*Nog te testen* onderaan.

Details in [`docs/roadmap.md`](docs/roadmap.md).

---

## 🧪 Tests draaien

```bash
pip install -r requirements-dev.txt
pytest
```

`pytest.ini` zet de projectwortel op het pad en geeft elke test 60 seconden,
zodat `pytest` vanuit elke map hetzelfde doet.

Bewust een aparte lijst: de volledige `requirements.txt` trekt torch, chromadb
en faster-whisper binnen — ruim een gigabyte die geen enkele test aanraakt. De
zware modules worden pas in de spraaklus geladen.

GitHub Actions draait dit bij elke push op Python 3.11 en 3.13, plus een
syntaxcontrole op de HUD-scripts.

---

## 🤝 OpenClaw en Hermes aansluiten

Beide worden alleen aangeboden als ze bereikbaar zijn, zodat JARVIS nooit een
tool kiest die gegarandeerd faalt.

**OpenClaw** — zet in `~/.openclaw/openclaw.json`:

```json5
{ gateway: { http: { endpoints: { chatCompletions: { enabled: true } } } } }
```

en `OPENCLAW_GATEWAY_TOKEN` in je `.env`. JARVIS stuurt dan handelingen
("zet het licht uit", "stuur dit via WhatsApp") naar `openclaw_task`.

**Hermes** — installeren, dan je sleutels erin:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
echo 'NVIDIA_API_KEY=nvapi-...' >> ~/.hermes/.env   # provider: nvidia
hermes model                                        # of Nous Portal via OAuth
```

Langere of lerende klussen gaan dan naar `hermes_task`.

Beide vragen eerst om bevestiging in de HUD. Dat uitzetten kan met
`DELEGATE_CONFIRM=0`.

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
| Stem klinkt robotachtig | Piper-stem ontbreekt; draai `python -m voice.piper_setup` |
| Nederlands wordt slecht verstaan | `WHISPER_MODEL=medium` (trager, ~2,5 GB) |
| Spraak start niet | Eerst `python -m voice.enroll` |

> Opnieuw inspreken: verwijder `data/chroma_voiceprints/` en start opnieuw.

---

## 🧪 Nog te testen op echte hardware

Deze is eerlijk: het volgende is **niet** end-to-end gedraaid, omdat de
ontwikkelomgeving geen microfoon had en Hugging Face er geblokkeerd was.

- Piper-synthese en Whisper-herkenning zelf (de logica eromheen wél)
- Het wake word en de sprekerverificatie met echte audio
- De systemd-units onder een draaiende systemd
- OpenClaw en Hermes tegen de échte programma's — wel tegen nagebootste

Wat wél end-to-end draaide: de HUD in een echte browser, tool-calling met
bevestiging (weigeren maakt geen bestand, toestaan wel), de OpenClaw-brug tegen
een nagebootste gateway, en Hermes tegen een echt uitvoerbaar bestand.

---

## ⚠️ Let op

De stemverificatie is een **vriendelijke drempel, geen slot**. En houd de HUD en
de OpenClaw Gateway op loopback: een gateway-token geldt als volledige
operator-toegang.

---

## 📜 Licentie

MIT — zie [`LICENSE`](LICENSE).
