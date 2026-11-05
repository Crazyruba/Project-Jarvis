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

## Fase 2 — Nederlandse stem en oren ✅ code af, audio nog te testen

- [x] `voice/stt.py`: `language` uit `config.LANG` (`nl`), Whisper naar `small`
- [x] `voice/tts.py`: **Piper** met `nl_NL-pim-medium`, pyttsx3 als terugval
- [x] `voice/piper_setup.py` en `voice/enroll.py` als losse commando's
- [x] RMS tijdens opnemen én spreken naar de eventbus → hologram beweegt mee
- [x] `voice/loop.py`: wake word, sprekercontrole, gesprek met vervolgvragen
- [x] Push-to-talk vanuit de HUD neemt serverzijdig op
- [x] Sprekerherkenning losgekoppeld van een vaste naam
- [ ] **Op de T580 testen** — audio is hier niet te verifiëren

**Verificatie:** "Hey Jarvis" → `LUISTERT`, Nederlandse zin correct getranscribeerd,
Piper antwoordt in het Nederlands, hologram beweegt mee. Vreemde stem wordt geweigerd.

> In deze container is geen microfoon en blokkeert de proxy Hugging Face, dus
> Piper-synthese en Whisper-herkenning zijn **niet** end-to-end gedraaid. De
> logica eromheen (motorkeuze, terugval, niveaus, gespreksverloop, toestanden)
> is wel getest met nagebootste onderdelen.

## Fase 3 — Tools op het nieuwe brein ✅

- [x] `tools/base.py` van Gemini `FunctionDeclaration` → OpenAI JSON-schema
- [x] `core/agent.py` van `function_call` → `tool_calls`, met streaming
- [x] Gemini-pad (`core/llm.py`) en `google-genai` eruit
- [x] Tool-aanroepen als `tool`-event in beeld
- [x] `core/permissions.py`: bevestigen met een knop in de HUD
- [x] `core/assembly.py`: één plek waar het brein in elkaar gezet wordt
- [x] `main.py` is nu een terminal-REPL op dezelfde agent
- [x] Tool-antwoorden naar het Nederlands (ze worden voorgelezen)
- [x] `pyautogui` wordt lui geladen, zodat een machine zonder scherm werkt

**Verificatie (gedraaid):** in de browser tegen een mock-backend die tool-calls
stuurt — `write_file` vraagt toestemming, weigeren maakt géén bestand aan,
toestaan wél.

## Fase 4 — OpenClaw als handen ✅

- [x] `tools/delegation.py`: `openclaw_task` praat met de Gateway via
      `POST /v1/chat/completions`
- [x] Wordt alleen aangeboden als `OPENCLAW_GATEWAY_TOKEN` gezet is
- [x] Staat standaard achter een bevestiging (`DELEGATE_CONFIRM`)
- [x] Systeemprompt stuurt "doe iets"-vragen hierheen
- [ ] **Op de T580**: `openclaw gateway` draaien met
      `gateway.http.endpoints.chatCompletions.enabled: true`

**Verificatie (gedraaid):** tegen een nagebootste gateway op `127.0.0.1:18789` —
juiste Bearer-token, model `openclaw/default`, opdracht komt aan, antwoord terug.

## Fase 5 — Hermes als lerend geheugen ✅

- [x] `hermes_task` roept `hermes -z "<opdracht>"` aan als subprocess
- [x] Wordt alleen aangeboden als het commando op het PATH staat
- [x] Nette melding bij een time-out, foutcode of ontbrekende installatie
- [x] Lange uitvoer wordt ingekort — het antwoord wordt voorgelezen
- [ ] **Op de T580**: `NVIDIA_API_KEY` in `~/.hermes/.env`, Nous Portal via
      `hermes model`
- [ ] Later eventueel opwaarderen naar de headless `hermes serve`-API

**Verificatie (gedraaid):** met een echt uitvoerbaar bestand op het PATH —
opdracht komt met `-z` aan, uitvoer komt terug, foutcode wordt netjes gemeld.

## Fase 6 — Altijd aan ✅

- [x] `deploy/systemd/`: `jarvis-hud`, `openclaw-gateway`, `hermes-gateway`
- [x] `deploy/install.sh` plaatst en start ze als **gebruikers**dienst
- [x] Wijst op `loginctl enable-linger` als dat nog niet aanstaat
- [x] `deploy/jarvis.desktop` opent de HUD
- [ ] **Op de T580**: `./deploy/install.sh --all` draaien

> De units zijn structureel nagelopen (secties, absolute ExecStart, Restart).
> `systemd-analyze verify` kon hier niet draaien: de container heeft geen
> systemd-manager.

## Open punten

- Of de `hermes serve`-API OpenAI-compatibel is, is niet bevestigd. Daarom fase 5
  via `hermes -z`, dat wél gedocumenteerd is als scripted one-shot.
- Nederlandse spraakherkenning is zwakker dan Engelse. Helpt `small` niet genoeg,
  dan is `medium` de volgende stap (~2,5 GB, trager op CPU).
- build.nvidia.com geeft gratis credits met een rate limit; Nous Portal heeft een
  gratis laag met alleen gratis modellen. Voor dagelijks gebruik is een betaalde
  laag waarschijnlijk nodig.
