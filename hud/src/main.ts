import "./style.css";
import { GatewayClient, extractMessageText, type ChatEvent, type ConnectionState } from "./gateway/client";
import { HoloScene, type HoloState } from "./scene/hologram";
import { Listener, Speaker, speechRecognitionSupported } from "./voice/voice";

// ------------------------------------------------------------- settings
type Settings = { url: string; token: string; lang: string; voice: boolean };
const SETTINGS_KEY = "jarvis-hud.settings.v1";

function loadSettings(): Settings {
  const env = import.meta.env;
  const defaults: Settings = {
    url: env.VITE_OPENCLAW_URL || "ws://127.0.0.1:18789",
    token: env.VITE_OPENCLAW_TOKEN || "",
    lang: env.VITE_JARVIS_LANG || "nl-NL",
    voice: true,
  };
  let saved: Partial<Settings> = {};
  try {
    saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
  } catch {
    /* ignore */
  }
  const s = { ...defaults, ...saved };
  // Allow one-off overrides: ?gateway=ws://...&token=...
  const q = new URLSearchParams(location.search);
  if (q.get("gateway")) s.url = q.get("gateway")!;
  if (q.get("token")) {
    s.token = q.get("token")!;
    history.replaceState(null, "", location.pathname); // keep the token out of the address bar
    saveSettings(s);
  }
  return s;
}

function saveSettings(s: Settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

let settings = loadSettings();

// ------------------------------------------------------------- elements
const $ = <T extends HTMLElement>(sel: string) => document.querySelector(sel) as T;
const canvas = $<HTMLCanvasElement>("#scene");
const subtitle = $<HTMLParagraphElement>("#subtitle");
const micBtn = $<HTMLButtonElement>("#mic-btn");
const textForm = $<HTMLFormElement>("#text-form");
const textInput = $<HTMLInputElement>("#text-input");
const onlineValue = $<HTMLSpanElement>("#status-online");
const dialog = $<HTMLDialogElement>("#settings");
const settingsForm = $<HTMLFormElement>("#settings-form");
const pairingHint = $<HTMLParagraphElement>("#pairing-hint");
const rows = {
  online: $<HTMLDivElement>('.status-row[data-key="online"]'),
  listening: $<HTMLDivElement>('.status-row[data-key="listening"]'),
  thinking: $<HTMLDivElement>('.status-row[data-key="thinking"]'),
  speaking: $<HTMLDivElement>('.status-row[data-key="speaking"]'),
};

// ---------------------------------------------------------------- state
const status = { connection: "offline" as ConnectionState, listening: false, thinking: false, speaking: false };

const scene = new HoloScene(canvas);
const listener = new Listener(settings.lang);
const speaker = new Speaker(settings.lang);

function render() {
  const online = status.connection === "online";
  rows.online.classList.toggle("on", online);
  rows.online.classList.toggle("warn", status.connection === "pairing" || status.connection === "connecting");
  onlineValue.textContent =
    status.connection === "online" ? "verbonden" : status.connection === "connecting" ? "verbinden…" : status.connection === "pairing" ? "koppelen" : "offline";
  rows.listening.classList.toggle("on", status.listening);
  rows.thinking.classList.toggle("on", status.thinking);
  rows.speaking.classList.toggle("on", status.speaking);
  micBtn.classList.toggle("active", status.listening);

  const holo: HoloState = !online
    ? "offline"
    : status.speaking
      ? "speaking"
      : status.listening
        ? "listening"
        : status.thinking
          ? "thinking"
          : "idle";
  scene.setState(holo);
}

function say(who: string, text: string, error = false) {
  subtitle.classList.toggle("error", error);
  subtitle.replaceChildren();
  if (who) {
    const tag = document.createElement("span");
    tag.className = "who";
    tag.textContent = who;
    subtitle.append(tag);
  }
  subtitle.append(document.createTextNode(text));
}

// -------------------------------------------------------------- gateway
let gateway: GatewayClient;
let replyBuffer = "";
let activeRunId: string | null = null;

function connect() {
  gateway?.stop();
  gateway = new GatewayClient({
    url: settings.url,
    token: settings.token,
    onState: (state, detail) => {
      status.connection = state;
      if (state !== "online") status.thinking = false;
      if (state === "pairing") {
        pairingHint.textContent = detail ?? "";
        say("Systeem", detail ?? "Koppeling nodig", true);
      } else if (state === "online") {
        pairingHint.textContent = "";
        say("Jarvis", "Online. Waarmee kan ik helpen?");
      } else if (state === "offline" && detail) {
        say("Systeem", `OpenClaw niet bereikbaar (${detail}). Ik probeer opnieuw…`, true);
      }
      render();
    },
    onChat: onChatEvent,
  });
  gateway.start();
}

function onChatEvent(evt: ChatEvent) {
  if (!evt || evt.sessionKey !== gateway.sessionKey) return;
  if (activeRunId && evt.runId !== activeRunId && evt.state !== "final") {
    // Another client started a run in this session; follow it anyway.
    activeRunId = evt.runId;
    replyBuffer = "";
  }
  switch (evt.state) {
    case "status":
      status.thinking = true;
      break;
    case "delta":
      status.thinking = true;
      replyBuffer = evt.replace ? evt.deltaText ?? "" : replyBuffer + (evt.deltaText ?? "");
      say("Jarvis", replyBuffer);
      break;
    case "final": {
      status.thinking = false;
      const text = extractMessageText(evt.message) || replyBuffer;
      replyBuffer = "";
      activeRunId = null;
      if (text) {
        say("Jarvis", text);
        if (settings.voice) {
          speaker.speak(text, {
            onStart: () => {
              status.speaking = true;
              render();
            },
            onEnd: () => {
              status.speaking = false;
              render();
            },
          });
        }
      }
      break;
    }
    case "aborted":
    case "error":
      status.thinking = false;
      replyBuffer = "";
      activeRunId = null;
      if (evt.state === "error") say("Systeem", evt.errorMessage || "Er ging iets mis.", true);
      break;
  }
  render();
}

async function ask(text: string) {
  const message = text.trim();
  if (!message) return;
  say("Jij", message);
  if (status.connection !== "online") {
    say("Systeem", "Nog niet verbonden met OpenClaw.", true);
    return;
  }
  speaker.stop();
  status.speaking = false;
  status.thinking = true;
  replyBuffer = "";
  render();
  try {
    const res = await gateway.sendChat(message);
    if (status.thinking) activeRunId = res?.runId ?? null;
  } catch (err: any) {
    status.thinking = false;
    say("Systeem", err?.message ?? String(err), true);
    render();
  }
}

// ---------------------------------------------------------------- voice
function startListening() {
  if (status.listening) return;
  speaker.stop(); // barge-in: talking over Jarvis stops the reply
  status.speaking = false;
  listener.start({
    onStart: () => {
      status.listening = true;
      say("Luistert", "…");
      render();
    },
    onInterim: (t) => say("Jij", t),
    onEnd: () => {
      status.listening = false;
      render();
    },
    onFinal: (t) => void ask(t),
    onError: (m) => say("Systeem", m, true),
  });
}

function stopListening() {
  listener.stop();
}

if (!speechRecognitionSupported()) {
  micBtn.disabled = true;
  micBtn.title = "Spraakherkenning werkt in Chrome of Edge";
}

micBtn.addEventListener("click", () => (status.listening ? stopListening() : startListening()));

// Push-to-talk with the space bar (when not typing).
let spaceHeld = false;
window.addEventListener("keydown", (e) => {
  if (e.code !== "Space" || e.repeat || document.activeElement === textInput || dialog.open) return;
  e.preventDefault();
  spaceHeld = true;
  startListening();
});
window.addEventListener("keyup", (e) => {
  if (e.code !== "Space" || !spaceHeld) return;
  spaceHeld = false;
  stopListening();
});
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && (status.speaking || status.thinking)) {
    speaker.stop();
    status.speaking = false;
    if (status.thinking) void gateway.abort();
    render();
  }
});

textForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const t = textInput.value;
  textInput.value = "";
  void ask(t);
});

// ------------------------------------------------------------- settings UI
$<HTMLButtonElement>("#settings-btn").addEventListener("click", () => {
  const f = settingsForm.elements as any;
  f.url.value = settings.url;
  f.token.value = settings.token;
  f.lang.value = settings.lang;
  f.voice.checked = settings.voice;
  dialog.showModal();
});
dialog.addEventListener("close", () => {
  if (dialog.returnValue !== "save") return;
  const f = settingsForm.elements as any;
  const next: Settings = {
    url: String(f.url.value).trim() || "ws://127.0.0.1:18789",
    token: String(f.token.value).trim(),
    lang: String(f.lang.value),
    voice: Boolean(f.voice.checked),
  };
  const reconnect = next.url !== settings.url || next.token !== settings.token;
  settings = next;
  saveSettings(settings);
  listener.lang = settings.lang;
  speaker.lang = settings.lang;
  if (reconnect) connect();
});

// -------------------------------------------------------------- animate
function tick(t: number) {
  scene.micLevel = status.listening ? listener.level() : 0;
  scene.mouthLevel = speaker.mouth(t / 1000);
  micBtn.style.setProperty("--level", scene.micLevel.toFixed(2));
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

render();
scene.start();
connect();
