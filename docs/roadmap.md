# Roadmap

Zie `docs/architecture.md` voor het waarom. Dit is de volgorde van bouwen.

## Fase 1 — De HUD ✅ in uitvoering

Doel: `http://127.0.0.1:7332` opent de interface, je typt Nederlands en krijgt
antwoord van Nous Portal of NVIDIA NIM. Geen microfoon nodig — zo los te testen.

- [x] `docs/` vullen, opruimwerk (naam, taal, `.gitignore`, requirements)
- [x] `core/providers.py` — één OpenAI-compatibele client, meerdere backends
- [x] `hud/events.py` — eventbus + vier toestanden
- [x] `hud/server.py` — FastAPI, WebSocket, `/api/health`
- [x] `hud/static/` — hologram, statuspaneel, ondertitels, invoerveld
- [ ] Draaien op de T580, bijschaven

**Verificatie:** `python run_hud.py --no-voice`, dan in de browser:
HUD laadt · `/api/health` meldt per backend · typ "Hoi Jarvis, wie ben je?" →
`DENKT` licht op, ondertitel loopt streamend mee → terug naar `ONLINE` ·
backend wisselen werkt · netwerk eruit geeft nette fout, geen crash ·
`lite`-modus zet bloom uit.

## Fase 2 — Nederlandse stem en oren

- [ ] `voice/stt.py`: `language` uit `config.LANG` (`nl`), Whisper naar `small`
- [ ] `voice/tts.py`: pyttsx3 → **Piper** met `nl_NL-pim-medium`
- [ ] RMS tijdens spreken naar de eventbus → hologram beweegt mee
- [ ] Wake word en ECAPA publiceren hun status op de bus
- [ ] Push-to-talk neemt serverzijdig op via het bestaande `stt.record()`

**Verificatie:** "Hey Jarvis" → `LUISTERT`, Nederlandse zin correct getranscribeerd,
Piper antwoordt in het Nederlands, hologram beweegt mee. Vreemde stem wordt geweigerd.

## Fase 3 — Tools op het nieuwe brein

- [ ] `tools/base.py` van Gemini `FunctionDeclaration` → OpenAI JSON-schema
- [ ] `core/agent.py` van `function_call` → `tool_calls`
- [ ] Gemini-pad (`core/llm.py`) eruit
- [ ] Tool-aanroepen als `tool`-event in beeld
- [ ] `core/permissions.py`: bevestigen in de HUD in plaats van `input()`

**Verificatie:** *"maak een bestand test.txt"* vraagt om bevestiging en doet het.

## Fase 4 — OpenClaw als handen

- [ ] `openclaw gateway` met `gateway.http.endpoints.chatCompletions.enabled: true`
- [ ] Backend-entry `openclaw` aanzetten, router stuurt "doe iets"-vragen daarheen

**Verificatie:** *"stuur dit via WhatsApp"* komt aan.

## Fase 5 — Hermes als lerend geheugen

- [ ] `hermes -z "<opdracht>"` als tool voor lange en lerende taken
- [ ] `NVIDIA_API_KEY` in `~/.hermes/.env`, Nous Portal via `hermes model`
- [ ] Later eventueel opwaarderen naar de headless `hermes serve`-API

**Verificatie:** *"zoek dit uit en onthoud wat je leert"* levert een nieuwe skill op.

## Fase 6 — Altijd aan

- [ ] `systemd --user`-units: `openclaw-gateway`, `hermes-gateway`, `jarvis-hud`
- [ ] `loginctl enable-linger`
- [ ] `.desktop`-starter die de HUD kiosk-gewijs opent

## Open punten

- Of de `hermes serve`-API OpenAI-compatibel is, is niet bevestigd. Daarom fase 5
  via `hermes -z`, dat wél gedocumenteerd is als scripted one-shot.
- Nederlandse spraakherkenning is zwakker dan Engelse. Helpt `small` niet genoeg,
  dan is `medium` de volgende stap (~2,5 GB, trager op CPU).
- build.nvidia.com geeft gratis credits met een rate limit; Nous Portal heeft een
  gratis laag met alleen gratis modellen. Voor dagelijks gebruik is een betaalde
  laag waarschijnlijk nodig.
