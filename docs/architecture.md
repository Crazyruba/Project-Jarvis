# Architectuur — J.A.R.V.I.S. Holo-Interface

> Levend document. Bijwerken zodra de werkelijkheid afwijkt van wat hier staat.

## Doel

Een holografische J.A.R.V.I.S.-interface op een Lenovo T580 (i7, 16 GB, Linux), die
samenwerkt met OpenClaw, Hermes Agent en Claude Code, met build.nvidia.com en de
Nous Research Portal als inference-backends.

## Het inzicht dat de architectuur draagt

Alle vier de "breinen" spreken hetzelfde protocol:

| Backend | base_url | Auth |
|---|---|---|
| Nous Portal | `https://inference-api.nousresearch.com/v1` | `NOUS_API_KEY` (`sk-nous-…`) |
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` |
| OpenClaw Gateway | `http://127.0.0.1:18789/v1` | `OPENCLAW_GATEWAY_TOKEN` |
| Hermes Agent | subprocess `hermes -z` | `~/.hermes/.env` |

De eerste drie zijn OpenAI-compatibel. Daarom is er **één client met een andere
`base_url`** in plaats van drie integraties. OpenClaw's chat-endpoint moet je wel
expliciet aanzetten:

```json5
{ gateway: { http: { endpoints: { chatCompletions: { enabled: true } } } } }
```

Dat endpoint is bewust gekozen boven de WebSocket-control-plane: die vereist een
Ed25519 device-identiteit, challenge-signing en pairing-goedkeuring, en de
protocolversie loopt mee met OpenClaw's release-trein. Het HTTP-endpoint is stabiel
en kost één `POST`.

## Overzicht

```
        ┌──────────────── browser op localhost:7332 ────────────────┐
        │   HOLO-HUD   Three.js hologram · status · ondertitels     │
        │              invoerveld · spatie = push-to-talk           │
        └───────────────────────────▲───────────────────────────────┘
                                    │  WebSocket /ws
                                    │  (state · token · message · level · tool)
        ┌───────────────────────────┴───────────────────────────────┐
        │  JARVIS-CORE  (Python, 127.0.0.1:7332)                     │
        │                                                            │
        │   voice/       wake word → Whisper(nl) → ECAPA → Piper(nl) │
        │   core/brain   ROUTER: waar gaat deze vraag heen?          │
        │   memory/      werk · kort · lang (SQLite)                 │
        └───┬──────────────┬──────────────┬─────────────────┬────────┘
            │              │              │                 │
      praten/weten    doe iets op     leer / complexe    (bouwfase)
            │          deze pc         meerstaps-taak        │
            ▼              ▼              ▼                 ▼
    ┌───────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐
    │ Nous      │  │  OpenClaw    │  │ Hermes Agent │  │  Claude   │
    │ Portal    │  │  Gateway     │  │ skills +     │  │  Code     │
    │ + NVIDIA  │  │  :18789      │  │ geheugen     │  │ bouwt de  │
    │ NIM       │  │  /v1/chat    │  │ hermes -z    │  │ repo      │
    └───────────┘  └──────────────┘  └──────────────┘  └───────────┘
         cloud        lokaal, handen    lokaal, leert    niet runtime
```

## Rolverdeling

| Component | Rol | Hoe aangesproken |
|---|---|---|
| **Jarvis-core** | Gezicht, stem, geheugen, router | deze repo |
| **Nous Portal / NVIDIA NIM** | Pratend brein: antwoorden, redeneren | OpenAI-client, cloud |
| **OpenClaw** | Handen: bestanden, apps, WhatsApp/Telegram, agenda | `POST /v1/chat/completions` |
| **Hermes Agent** | Lange taken, zelflerende skills, eigen geheugen | `hermes -z "<opdracht>"` |
| **Claude Code** | Bouwt en onderhoudt deze repo | niet in de runtime |

Hermes ondersteunt beide gevraagde API's native: provider `nvidia` (`NVIDIA_API_KEY`
in `~/.hermes/.env`) en Nous Portal via OAuth (`hermes model`).

## Mappenindeling

```
run_hud.py              entrypoint: HUD + optioneel de voice-loop
hud/
  events.py             EventBus + HudState (IDLE/LISTENING/THINKING/SPEAKING)
  server.py             FastAPI + WebSocket + REST
  static/               index.html, css/, js/ (app.js, holo.js), vendor/, assets/
core/
  providers.py          OpenAICompatLLM — één client, meerdere base_urls
  brain.py              router: chat · openclaw · hermes
  agent.py              bestaande ReAct-loop (fase 3: naar OpenAI tool-calling)
  llm.py                Gemini-wrapper (vervalt in fase 3)
  permissions.py        bevestiging voor gevoelige acties
memory/                 werk- · kort- · langetermijngeheugen (SQLite)
tools/                  toolregistry + tools
voice/                  wake word, STT, TTS, ECAPA-sprekerverificatie
```

## HUD-protocol (WebSocket `/ws`)

Client → server: `text`, `ptt_start`, `ptt_stop`, `cancel`
Server → client: `state`, `token`, `message`, `level`, `tool`, `error`

`state` kent vier waarden, één per lampje in de interface:

| Intern | In beeld |
|---|---|
| `idle` | ONLINE |
| `listening` | LUISTERT |
| `thinking` | DENKT |
| `speaking` | SPREEKT |

`level` draagt de RMS van de audio, zodat het hologram meebeweegt op de stem.

## Resourcebudget (16 GB)

| Proces | RAM | Opmerking |
|---|---|---|
| Whisper `small` int8 | ~1,0 GB | alleen tijdens transcriberen |
| openWakeWord (ONNX) | ~150 MB | continu |
| ECAPA + ChromaDB | ~700 MB | continu |
| Piper nl medium | ~100 MB | per zin |
| OpenClaw Gateway (Node) | ~400–800 MB | continu |
| Hermes (Python) | ~500 MB | per sessie |
| Browser met de HUD | ~400 MB | |

Ruim binnen 16 GB. De krapte zit in **CPU, niet in geheugen**: het wake word luistert
continu en Whisper piekt op alle cores. Daarom staan de zware modellen in de cloud.

## Veiligheid

- HUD en OpenClaw-gateway binden op loopback. De Gateway-token geldt als volledige
  operator-toegang — niet naar buiten openzetten.
- Sprekerverificatie is een drempel, geen slot.
- `auth/token.json` hoort niet in git: Google schrijft daar een echt OAuth-token in.
