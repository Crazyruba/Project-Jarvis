# J.A.R.V.I.S HUD voor OpenClaw

Een holografische 3D-interface voor je OpenClaw-assistent, gebouwd met Babylon.js: een
gescand hoofd als hologram-raster op een gloeiend platform in een paarse serverruimte. Je praat via de microfoon van je browser,
Jarvis antwoordt hardop, en een klein statuspaneel laat zien of hij **online** is,
**luistert**, **denkt** of **spreekt**.

![Jarvis HUD](../docs/hud-screenshot.png)

## Wat je nodig hebt

- OpenClaw met een draaiende Gateway op dezelfde machine (standaard `ws://127.0.0.1:18789`)
- Node.js 20 of nieuwer
- Chrome of Edge (voor spraakherkenning via de Web Speech API)

## Starten

```bash
cd hud
npm install
cp .env.example .env.local   # optioneel, zie hieronder
npm run dev
```

Open daarna http://localhost:5173.

### Verbinden met OpenClaw

De HUD heeft het Gateway-token nodig. Dat vraag je op met:

```bash
openclaw config get gateway.auth.token
```

Vul het token in via het tandwiel rechtsboven, of zet het in `.env.local` als
`VITE_OPENCLAW_TOKEN`. Je kunt het ook één keer meegeven in de URL:
`http://localhost:5173/?token=JOUW_TOKEN` (het wordt daarna uit de adresbalk gehaald).

Bij de eerste verbinding maakt de HUD een eigen apparaat-sleutel (Ed25519) aan. Omdat
de HUD op dezelfde machine draait als OpenClaw, keurt de Gateway dit apparaat
automatisch goed. Daarna bewaart de HUD het apparaat-token, zodat het gedeelde token
niet meer nodig is.

Draait de HUD op een **ander** apparaat dan OpenClaw? Dan vraagt de Gateway om
goedkeuring. De HUD toont dan het commando, bijvoorbeeld
`openclaw devices approve <requestId>`, dat je op de OpenClaw-machine uitvoert. Zet in
dat geval ook het adres van de HUD in `gateway.controlUi.allowedOrigins`.

## Bediening

| Actie | Hoe |
| --- | --- |
| Praten | Klik op de microfoonknop, of houd **spatie** ingedrukt |
| Typen | Typ in het invoerveld en druk op Enter |
| Jarvis onderbreken | Begin te praten, of druk op **Esc** |
| Instellingen | Tandwiel rechtsboven: Gateway-URL, token, taal, stem aan/uit |

## Hoe het werkt

```
Browser (HUD)                                    OpenClaw Gateway
─────────────                                    ────────────────
microfoon → Web Speech API → tekst ── chat.send ──▶  agent
luidspreker ◀ speechSynthesis ◀ tekst ◀── chat-events (delta/final)
Babylon.js-hologram reageert op: online · luistert · denkt · spreekt
```

- `src/gateway/` — WebSocket-client voor Gateway-protocol v4: `connect.challenge`,
  ondertekende `connect`, `chat.send` en `chat`-events, automatisch opnieuw verbinden.
- `src/voice/` — spraakherkenning, spraakuitvoer en een microfoon-niveaumeter.
- `src/scene/` — de Babylon.js-scène: gescand hoofd (`public/models/head.glb`) met een
  hologram-shader en bewegende kaak, platform met ringen, datastralen, serverkasten met
  knipperende leds, rook, spiegelende vloer, lichtbundel met god rays, glow en bloom.
  De shaders staan in `src/scene/shaders.ts`.

## Prestaties

De scène is afgesteld op geïntegreerde grafische kaarten zoals de Intel UHD 620 in een
Lenovo ThinkPad T580: de pixelratio is begrensd op 1,25 en glow en bloom renderen op halve
resolutie.

Haalt de browser geen 40 beelden per seconde, dan schakelt de HUD stap voor stap zware
effecten uit: eerst de spiegelende vloer en filmkorrel, dan de god rays, en als laatste een
lagere renderresolutie. Het gekozen niveau wordt onthouden. Open
`http://localhost:5173/?quality=high` om weer met de volle kwaliteit te beginnen.

## Credits

Het hoofdmodel is de "Lee Perry-Smith head scan" van Infinite Realities, onder
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Zie
[`public/models/CREDITS.md`](public/models/CREDITS.md).

## Scripts

- `npm run dev` — ontwikkelserver op poort 5173
- `npm run build` — typecheck en productie-build in `dist/`
- `npm run preview` — de build lokaal bekijken op poort 4173
