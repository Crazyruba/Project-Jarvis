// Browser voice I/O: Web Speech API for recognition and synthesis, plus a
// microphone level meter so the hologram can react while you speak.

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((ev: any) => void) | null;
  onerror: ((ev: any) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
};

function recognitionCtor(): (new () => SpeechRecognitionLike) | null {
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const speechRecognitionSupported = () => recognitionCtor() !== null;
export const speechSynthesisSupported = () => "speechSynthesis" in window;

export type ListenCallbacks = {
  onInterim?: (text: string) => void;
  onFinal: (text: string) => void;
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (message: string) => void;
};

export class Listener {
  private rec: SpeechRecognitionLike | null = null;
  private stream: MediaStream | null = null;
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private buf: Uint8Array<ArrayBuffer> | null = null;
  active = false;

  constructor(public lang: string) {}

  /** 0..1 microphone loudness, smoothed by the caller. */
  level(): number {
    if (!this.analyser || !this.buf) return 0;
    this.analyser.getByteTimeDomainData(this.buf);
    let sum = 0;
    for (const v of this.buf) {
      const d = (v - 128) / 128;
      sum += d * d;
    }
    return Math.min(1, Math.sqrt(sum / this.buf.length) * 4);
  }

  async start(cb: ListenCallbacks): Promise<void> {
    const Ctor = recognitionCtor();
    if (!Ctor) {
      cb.onError?.("Spraakherkenning wordt niet ondersteund in deze browser (gebruik Chrome of Edge).");
      return;
    }
    if (this.active) return;
    this.active = true;
    await this.openMeter().catch(() => undefined);

    const rec = new Ctor();
    rec.lang = this.lang;
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    let finalText = "";
    rec.onstart = () => cb.onStart?.();
    rec.onresult = (ev: any) => {
      let interim = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interim += r[0].transcript;
      }
      cb.onInterim?.((finalText + interim).trim());
    };
    rec.onerror = (ev: any) => {
      if (ev?.error !== "no-speech" && ev?.error !== "aborted") {
        cb.onError?.(`Microfoon: ${ev?.error ?? "onbekende fout"}`);
      }
    };
    rec.onend = () => {
      this.active = false;
      this.rec = null;
      this.closeMeter();
      cb.onEnd?.();
      const text = finalText.trim();
      if (text) cb.onFinal(text);
    };
    this.rec = rec;
    try {
      rec.start();
    } catch (e) {
      this.active = false;
      this.closeMeter();
      cb.onError?.(String(e));
    }
  }

  stop(): void {
    this.rec?.stop();
  }

  cancel(): void {
    this.rec?.abort();
  }

  private async openMeter() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.ctx = new AudioContext();
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 512;
    this.buf = new Uint8Array(new ArrayBuffer(this.analyser.fftSize));
    src.connect(this.analyser);
  }

  private closeMeter() {
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.ctx?.close().catch(() => undefined);
    this.stream = null;
    this.ctx = null;
    this.analyser = null;
    this.buf = null;
  }
}

/** Strip markdown and code so the voice reads naturally. */
export function speakableText(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " (code weggelaten) ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_#>~|]+/g, "")
    .replace(/https?:\/\/\S+/g, "link")
    .replace(/\s+/g, " ")
    .trim();
}

export class Speaker {
  private voice: SpeechSynthesisVoice | null = null;
  /** Rough mouth openness 0..1 while speaking, driven by word boundaries. */
  private pulse = 0;
  speaking = false;

  constructor(public lang: string) {
    if (speechSynthesisSupported()) {
      const pick = () => (this.voice = this.pickVoice());
      pick();
      speechSynthesis.addEventListener("voiceschanged", pick);
    }
  }

  private pickVoice(): SpeechSynthesisVoice | null {
    const voices = speechSynthesis.getVoices();
    const base = this.lang.split("-")[0].toLowerCase();
    const match = voices.filter((v) => v.lang.toLowerCase().startsWith(base));
    // Prefer a male-sounding or online/natural voice when the browser offers one.
    const preferred =
      match.find((v) => /natural|online/i.test(v.name) && /maarten|colette|fenna|male|man/i.test(v.name)) ??
      match.find((v) => /natural|online|google/i.test(v.name)) ??
      match[0];
    return preferred ?? null;
  }

  mouth(t: number): number {
    if (!this.speaking) return 0;
    this.pulse *= 0.9;
    // Syllable-like flutter on top of the word pulse.
    const flutter = 0.35 + 0.35 * Math.abs(Math.sin(t * 17)) * (0.6 + 0.4 * Math.sin(t * 5.3));
    return Math.min(1, flutter * 0.7 + this.pulse);
  }

  speak(text: string, hooks: { onStart?: () => void; onEnd?: () => void } = {}): void {
    const clean = speakableText(text);
    if (!clean || !speechSynthesisSupported()) {
      hooks.onEnd?.();
      return;
    }
    const base = this.lang.split("-")[0].toLowerCase();
    if (!this.voice || !this.voice.lang.toLowerCase().startsWith(base)) this.voice = this.pickVoice();
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(clean);
    u.lang = this.lang;
    if (this.voice) u.voice = this.voice;
    u.rate = 1.02;
    u.pitch = 0.9;
    u.onstart = () => {
      this.speaking = true;
      hooks.onStart?.();
    };
    u.onboundary = () => {
      this.pulse = 0.6;
    };
    const done = () => {
      this.speaking = false;
      hooks.onEnd?.();
    };
    u.onend = done;
    u.onerror = done;
    speechSynthesis.speak(u);
  }

  stop(): void {
    if (speechSynthesisSupported()) speechSynthesis.cancel();
    this.speaking = false;
  }
}
