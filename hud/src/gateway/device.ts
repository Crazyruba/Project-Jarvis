// Ed25519 device identity for the OpenClaw Gateway handshake.
// Mirrors the OpenClaw Control UI: raw public key as base64url, device id is
// the SHA-256 hex of the raw public key, signatures are base64url.
import { getPublicKeyAsync, signAsync } from "@noble/ed25519";

const IDENTITY_KEY = "jarvis-hud.device-identity.v1";
const TOKEN_KEY = "jarvis-hud.device-token.v1";

export type DeviceIdentity = {
  deviceId: string;
  publicKey: string;
  privateKey: string;
};

export type StoredDeviceToken = {
  gatewayUrl: string;
  deviceId: string;
  token: string;
  scopes: string[];
};

function b64urlEncode(bytes: Uint8Array): string {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/g, "");
}

function b64urlDecode(input: string): Uint8Array {
  const norm = input.replaceAll("-", "+").replaceAll("_", "/");
  const padded = norm + "=".repeat((4 - (norm.length % 4)) % 4);
  const bin = atob(padded);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes.slice().buffer);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage blocked: identity stays in memory for this page lifetime.
  }
}

let memoryIdentity: DeviceIdentity | null = null;

export async function loadOrCreateIdentity(): Promise<DeviceIdentity> {
  const stored = readJson<DeviceIdentity>(IDENTITY_KEY);
  if (stored?.publicKey && stored.privateKey) {
    const deviceId = await sha256Hex(b64urlDecode(stored.publicKey));
    return { ...stored, deviceId };
  }
  if (memoryIdentity) return memoryIdentity;
  const priv = crypto.getRandomValues(new Uint8Array(32));
  const pub = await getPublicKeyAsync(priv);
  const identity: DeviceIdentity = {
    deviceId: await sha256Hex(pub),
    publicKey: b64urlEncode(pub),
    privateKey: b64urlEncode(priv),
  };
  memoryIdentity = identity;
  writeJson(IDENTITY_KEY, identity);
  return identity;
}

export async function signPayload(identity: DeviceIdentity, payload: string): Promise<string> {
  const sig = await signAsync(new TextEncoder().encode(payload), b64urlDecode(identity.privateKey));
  return b64urlEncode(sig);
}

/** v2 device auth payload, byte-for-byte as the Gateway verifies it. */
export function buildDeviceAuthPayload(p: {
  deviceId: string;
  clientId: string;
  clientMode: string;
  role: string;
  scopes: string[];
  signedAtMs: number;
  token: string | null;
  nonce: string;
}): string {
  return [
    "v2",
    p.deviceId,
    p.clientId,
    p.clientMode,
    p.role,
    p.scopes.join(","),
    String(p.signedAtMs),
    p.token ?? "",
    p.nonce,
  ].join("|");
}

export function loadDeviceToken(gatewayUrl: string, deviceId: string): StoredDeviceToken | null {
  const t = readJson<StoredDeviceToken>(TOKEN_KEY);
  return t && t.gatewayUrl === gatewayUrl && t.deviceId === deviceId ? t : null;
}

export function storeDeviceToken(t: StoredDeviceToken): void {
  writeJson(TOKEN_KEY, t);
}

export function clearDeviceToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}
