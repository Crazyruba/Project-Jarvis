/**
 * HUD-client: WebSocket, statuslampjes, ondertitels, instellingen.
 */

const $ = (id) => document.getElementById(id);

const els = {
  rows:      document.querySelectorAll(".status-row"),
  connNote:  $("conn-note"),
  transcript:$("transcript"),
  subtitle:  $("subtitle"),
  composer:  $("composer"),
  input:     $("input"),
  mic:       $("mic"),
  gear:      $("gear"),
  panel:     $("panel"),
  backend:   $("backend-select"),
  healthBtn: $("health-check"),
  healthList:$("health-list"),
  lite:      $("lite-toggle"),
  toast:     $("toast"),
  title:     $("hud-title"),
  subtitleTop: $("hud-subtitle"),
};

const LABELS = { idle: "ONLINE", listening: "LUISTERT", thinking: "DENKT", speaking: "SPREEKT" };

let ws = null;
let reconnectDelay = 500;
let streaming = false;
let streamText = "";

/* -- toestand ------------------------------------------------------------ */

function setState(value) {
  els.rows.forEach((row) => {
    row.classList.toggle("active", row.dataset.state === value);
  });
  window.holo?.setState(value);

  // Tijdens spreken het hologram laten meebewegen; echte RMS komt in fase 2.
  if (value === "speaking" || value === "listening") startFakeLevel();
  else stopFakeLevel();
}

let levelTimer = null;
function startFakeLevel() {
  if (levelTimer) return;
  levelTimer = setInterval(() => {
    window.holo?.setLevel(0.25 + Math.random() * 0.55);
  }, 90);
}
function stopFakeLevel() {
  clearInterval(levelTimer);
  levelTimer = null;
  window.holo?.setLevel(0);
}

/* -- ondertitels --------------------------------------------------------- */

function say(role, text, { error = false } = {}) {
  els.transcript.classList.toggle("is-user", role === "user");
  els.transcript.classList.toggle("is-error", error);
  els.transcript.querySelector(".who").textContent =
    error ? "FOUT" : role === "user" ? (window.__owner || "JIJ") : "JARVIS";
  els.subtitle.textContent = text;
}

function beginStream() {
  streaming = true;
  streamText = "";
  els.transcript.classList.remove("is-user", "is-error");
  els.transcript.querySelector(".who").textContent = "JARVIS";
  els.subtitle.innerHTML = '<span class="caret"></span>';
}

function pushToken(piece) {
  streamText += piece;
  els.subtitle.textContent = streamText;
  els.subtitle.insertAdjacentHTML("beforeend", '<span class="caret"></span>');
}

function endStream(final) {
  streaming = false;
  els.subtitle.textContent = final || streamText;
}

function toast(text) {
  els.toast.textContent = text;
  els.toast.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { els.toast.hidden = true; }, 6000);
}

/* -- verbinding ---------------------------------------------------------- */

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    reconnectDelay = 500;
    els.connNote.textContent = "verbonden";
    say("jarvis", "Online. Waarmee kan ik helpen?");
  };

  ws.onmessage = (event) => {
    let msg;
    try { msg = JSON.parse(event.data); } catch { return; }

    switch (msg.type) {
      case "hello":
        window.__owner = (msg.owner || "JIJ").toUpperCase();
        break;
      case "state":
        setState(msg.value);
        break;
      case "message":
        if (msg.role === "user") say("user", msg.text);
        else say("jarvis", msg.text);
        break;
      case "reply_start":
        beginStream();
        break;
      case "token":
        if (!streaming) beginStream();
        pushToken(msg.text);
        break;
      case "reply_end":
        endStream(msg.text);
        break;
      case "level":
        window.holo?.setLevel(msg.value);
        break;
      case "tool":
        say("jarvis", `⚙ ${msg.name}`);
        break;
      case "backend":
        toast(`Brein: ${msg.label}`);
        break;
      case "error":
        streaming = false;
        say("jarvis", msg.text, { error: true });
        break;
    }
  };

  ws.onclose = () => {
    els.connNote.textContent = "verbinding verbroken";
    els.rows.forEach((r) => r.classList.remove("active"));
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 10000);
  };

  ws.onerror = () => { els.connNote.textContent = "verbindingsfout"; };
}

function send(payload) {
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
  else toast("Geen verbinding met JARVIS.");
}

/* -- invoer -------------------------------------------------------------- */

els.composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = els.input.value.trim();
  if (!text) return;
  send({ type: "text", content: text });
  els.input.value = "";
});

els.mic.addEventListener("click", () => {
  els.mic.classList.add("live");
  send({ type: "ptt_start" });
  setTimeout(() => {
    els.mic.classList.remove("live");
    send({ type: "ptt_stop" });
  }, 400);
});

// Spatie ingedrukt houden = praten. Niet terwijl je typt.
let ptt = false;
document.addEventListener("keydown", (e) => {
  const typing = document.activeElement === els.input;

  if (e.key === "/" && !typing) { e.preventDefault(); els.input.focus(); return; }
  if (e.key === "Escape") { send({ type: "cancel" }); els.input.blur(); return; }

  if (e.code === "Space" && !typing && !ptt && !e.repeat) {
    e.preventDefault();
    ptt = true;
    els.mic.classList.add("live");
    send({ type: "ptt_start" });
  }
});
document.addEventListener("keyup", (e) => {
  if (e.code === "Space" && ptt) {
    ptt = false;
    els.mic.classList.remove("live");
    send({ type: "ptt_stop" });
  }
});

/* -- instellingen -------------------------------------------------------- */

els.gear.addEventListener("click", () => {
  const open = els.panel.hidden;
  els.panel.hidden = !open;
  els.gear.setAttribute("aria-expanded", String(open));
});

els.backend.addEventListener("change", () => {
  send({ type: "backend", name: els.backend.value });
});

els.lite.addEventListener("change", () => {
  const on = els.lite.checked;
  window.holo?.setLite(on);
  try { localStorage.setItem("jarvis.lite", on ? "1" : "0"); } catch {}
});

els.healthBtn.addEventListener("click", async () => {
  els.healthBtn.textContent = "testen…";
  els.healthList.innerHTML = "";
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    for (const b of data.backends) {
      const li = document.createElement("li");
      li.innerHTML = b.ok
        ? `<span class="ok">●</span><span>${b.label}</span>`
        : `<span class="bad">●</span><span>${b.label}</span>` +
          `<span class="reason">— ${b.reason ?? "onbekend"}</span>`;
      els.healthList.appendChild(li);
    }
  } catch (e) {
    els.healthList.innerHTML = `<li><span class="bad">●</span><span>${e}</span></li>`;
  }
  els.healthBtn.textContent = "Backends testen";
});

async function loadBackends() {
  try {
    const data = await (await fetch("/api/backends")).json();
    window.__owner = (data.owner || "JIJ").toUpperCase();
    if (data.title) els.title.textContent = data.title.split("").join(" ").toUpperCase();
    if (data.subtitle) els.subtitleTop.textContent = data.subtitle;

    els.backend.innerHTML = "";
    for (const b of data.backends) {
      const opt = document.createElement("option");
      opt.value = b.name;
      opt.textContent = b.configured ? b.label : `${b.label} (geen sleutel)`;
      opt.disabled = !b.configured;
      opt.selected = b.name === data.active;
      els.backend.appendChild(opt);
    }
    if (!data.backends.some((b) => b.configured)) {
      toast("Geen API-sleutel ingesteld — zet NOUS_API_KEY of NVIDIA_API_KEY in .env");
    }
  } catch {
    toast("Kon de backends niet ophalen.");
  }
}

/* -- start --------------------------------------------------------------- */

try {
  if (localStorage.getItem("jarvis.lite") === "1") {
    els.lite.checked = true;
    window.holo?.setLite(true);
  }
} catch {}

if (window.holo && !window.holo.ready) {
  toast("WebGL is niet beschikbaar — de HUD werkt, maar zonder hologram.");
}

loadBackends();
connect();
setState("idle");
