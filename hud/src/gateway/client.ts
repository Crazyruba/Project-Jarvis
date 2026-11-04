// Minimal OpenClaw Gateway WebSocket client (wire protocol v4).
// Handshake: wait for `connect.challenge`, sign it with the device key,
// send `connect`, then use `chat.send` and listen to `chat` events.
import {
  buildDeviceAuthPayload,
  clearDeviceToken,
  loadDeviceToken,
  loadOrCreateIdentity,
  signPayload,
  storeDeviceToken,
} from "./device";

const PROTOCOL_VERSION = 4;
const CLIENT_ID = "webchat-ui";
const CLIENT_MODE = "webchat";
const ROLE = "operator";
const SCOPES = ["operator.read", "operator.write"];

export type ConnectionState = "offline" | "connecting" | "online" | "pairing";

export type ChatEvent = {
  runId: string;
  sessionKey: string;
  state: "status" | "delta" | "final" | "aborted" | "error";
  deltaText?: string;
  replace?: boolean;
  message?: unknown;
  errorMessage?: string;
  phase?: string;
};

type Frame =
  | { type: "event"; event: string; payload?: any; seq?: number }
  | { type: "res"; id: string; ok: boolean; payload?: any; error?: GatewayError };

export type GatewayError = { code: string; message: string; details?: any };

type Pending = { resolve: (v: any) => void; reject: (e: unknown) => void; timer: number };

export type GatewayClientOptions = {
  url: string;
  token?: string;
  onState?: (state: ConnectionState, detail?: string) => void;
  onChat?: (evt: ChatEvent) => void;
  onEvent?: (event: string, payload: unknown) => void;
};

export class GatewayClient {
  private ws: WebSocket | null = null;
  private pending = new Map<string, Pending>();
  private reqCounter = 0;
  private stopped = false;
  private backoffMs = 1000;
  private reconnectTimer: number | null = null;
  private challengeTimer: number | null = null;
  sessionKey = "main";
  serverVersion = "";

  constructor(private opts: GatewayClientOptions) {}

  start(): void {
    this.stopped = false;
    this.open();
  }

  stop(): void {
    this.stopped = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close(1000, "hud closed");
    this.ws = null;
  }

  async sendChat(message: string): Promise<{ runId?: string }> {
    return this.request("chat.send", {
      sessionKey: this.sessionKey,
      message,
      idempotencyKey: crypto.randomUUID(),
    });
  }

  async abort(): Promise<void> {
    await this.request("chat.abort", { sessionKey: this.sessionKey }).catch(() => undefined);
  }

  request<T = any>(method: string, params: unknown, timeoutMs = 30_000): Promise<T> {
    const ws = this.ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("Niet verbonden met OpenClaw"));
    }
    const id = `hud-${++this.reqCounter}`;
    return new Promise<T>((resolve, reject) => {
      const timer = window.setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${method}: timeout`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      ws.send(JSON.stringify({ type: "req", id, method, params }));
    });
  }

  private setState(state: ConnectionState, detail?: string) {
    this.opts.onState?.(state, detail);
  }

  private open() {
    this.setState("connecting");
    let ws: WebSocket;
    try {
      ws = new WebSocket(this.opts.url);
    } catch (e) {
      this.setState("offline", String(e));
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;
    let challenged = false;

    ws.onmessage = (msg) => {
      let frame: Frame;
      try {
        frame = JSON.parse(String(msg.data));
      } catch {
        return;
      }
      if (frame.type === "event" && frame.event === "connect.challenge" && !challenged) {
        challenged = true;
        if (this.challengeTimer) clearTimeout(this.challengeTimer);
        void this.handshake(frame.payload);
        return;
      }
      if (frame.type === "res") {
        const p = this.pending.get(frame.id);
        if (!p) return;
        this.pending.delete(frame.id);
        clearTimeout(p.timer);
        if (frame.ok) p.resolve(frame.payload);
        else p.reject(frame.error ?? { code: "UNKNOWN", message: "request failed" });
        return;
      }
      if (frame.type === "event") {
        if (frame.event === "chat") this.opts.onChat?.(frame.payload as ChatEvent);
        this.opts.onEvent?.(frame.event, frame.payload);
      }
    };

    ws.onopen = () => {
      // Gateways always send a challenge first; give up if it never comes.
      this.challengeTimer = window.setTimeout(() => {
        if (!challenged) ws.close(4000, "no challenge");
      }, 10_000);
    };

    ws.onclose = (ev) => {
      for (const p of this.pending.values()) {
        clearTimeout(p.timer);
        p.reject(new Error("verbinding gesloten"));
      }
      this.pending.clear();
      if (this.ws === ws) this.ws = null;
      if (!this.stopped) {
        this.setState("offline", ev.reason || `code ${ev.code}`);
        this.scheduleReconnect();
      }
    };
  }

  private scheduleReconnect() {
    if (this.stopped) return;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    const delay = this.backoffMs;
    this.backoffMs = Math.min(this.backoffMs * 2, 15_000);
    this.reconnectTimer = window.setTimeout(() => this.open(), delay);
  }

  private async handshake(challenge: { nonce?: string; ts?: number }) {
    const nonce = challenge?.nonce ?? "";
    const signedAt = challenge?.ts;
    if (typeof signedAt !== "number" || !Number.isSafeInteger(signedAt) || signedAt < 0) {
      this.setState("offline", "ongeldige connect.challenge");
      this.ws?.close(4001, "invalid challenge");
      return;
    }

    const identity = await loadOrCreateIdentity();
    const explicitToken = this.opts.token?.trim() || undefined;
    const stored = loadDeviceToken(this.opts.url, identity.deviceId);
    // Explicit gateway token wins; otherwise reuse the device token from pairing.
    const auth = explicitToken
      ? { token: explicitToken }
      : stored
        ? { deviceToken: stored.token }
        : undefined;
    const signatureToken = explicitToken ?? stored?.token ?? null;

    const client = {
      id: CLIENT_ID,
      displayName: "Jarvis HUD",
      version: "jarvis-hud/0.1.0",
      platform: navigator.platform || "web",
      mode: CLIENT_MODE,
      timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || undefined,
    };
    const payload = buildDeviceAuthPayload({
      deviceId: identity.deviceId,
      clientId: client.id,
      clientMode: client.mode,
      role: ROLE,
      scopes: SCOPES,
      signedAtMs: signedAt,
      token: signatureToken,
      nonce,
    });
    const signature = await signPayload(identity, payload);

    try {
      const hello = await this.request<any>("connect", {
        minProtocol: PROTOCOL_VERSION,
        maxProtocol: PROTOCOL_VERSION,
        client,
        role: ROLE,
        scopes: SCOPES,
        caps: [],
        auth,
        locale: navigator.language,
        userAgent: navigator.userAgent,
        device: {
          id: identity.deviceId,
          publicKey: identity.publicKey,
          signature,
          signedAt,
          nonce,
        },
      });
      this.backoffMs = 1000;
      this.serverVersion = hello?.server?.version ?? "";
      const defaults = hello?.snapshot?.sessionDefaults;
      if (defaults?.mainSessionKey) this.sessionKey = defaults.mainSessionKey;
      const deviceToken = hello?.auth?.deviceToken;
      if (typeof deviceToken === "string" && deviceToken) {
        storeDeviceToken({
          gatewayUrl: this.opts.url,
          deviceId: identity.deviceId,
          token: deviceToken,
          scopes: hello?.auth?.scopes ?? SCOPES,
        });
      }
      this.setState("online", this.serverVersion);
    } catch (err) {
      const e = err as GatewayError;
      const code = e?.details?.code ?? e?.code ?? "";
      if (String(code).includes("PAIRING")) {
        const requestId = e?.details?.requestId ?? e?.details?.request?.id ?? "";
        this.setState(
          "pairing",
          `Koppeling nodig: voer op de OpenClaw-machine uit: openclaw devices approve ${requestId}`.trim(),
        );
      } else {
        if (String(code).includes("DEVICE_TOKEN") || String(code).includes("TOKEN_MISMATCH")) {
          clearDeviceToken();
        }
        this.setState("offline", e?.message ?? String(err));
      }
      this.ws?.close(4002, "connect rejected");
    }
  }
}

/** Pull plain text out of a chat `final` message (content blocks or string). */
export function extractMessageText(message: unknown): string {
  if (!message) return "";
  if (typeof message === "string") return message;
  const m = message as { content?: unknown; text?: unknown };
  if (typeof m.text === "string") return m.text;
  if (typeof m.content === "string") return m.content;
  if (Array.isArray(m.content)) {
    return m.content
      .map((block: any) => (block?.type === "text" && typeof block.text === "string" ? block.text : ""))
      .join("");
  }
  return "";
}
