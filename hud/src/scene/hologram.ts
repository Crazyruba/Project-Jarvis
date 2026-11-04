// The full HUD scene: server-room corridor, purple haze, light beam,
// glowing platform with rings, data streams and the hologram bust.
import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { HologramBust, glowTexture, mulberry32 } from "./head";
import { beamMaterial, discMaterial, holoUniforms, streamMaterial } from "./materials";

export type HoloState = "offline" | "idle" | "listening" | "thinking" | "speaking";

const COLORS: Record<HoloState, THREE.Color> = {
  offline: new THREE.Color(0x2a4a66),
  idle: new THREE.Color(0x4fd8ff),
  listening: new THREE.Color(0x7ff0ff),
  thinking: new THREE.Color(0x8a7dff),
  speaking: new THREE.Color(0x66e6ff),
};

export class HoloScene {
  private renderer: THREE.WebGLRenderer;
  private composer: EffectComposer;
  private bloom: UnrealBloomPass;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private bust = new HologramBust();
  private hologram = new THREE.Group();
  private rings: THREE.Mesh[] = [];
  private emitter!: THREE.Mesh;
  private streams!: THREE.LineSegments;
  private smoke!: THREE.Points;
  private smokeVel: Float32Array = new Float32Array(0);
  private panel = new THREE.Group();
  private leds!: THREE.InstancedMesh;
  private ledPhase: Float32Array = new Float32Array(0);
  private ledBase: THREE.Color[] = [];
  private ledTick = -1;
  private tmpColor = new THREE.Color();
  private clock = new THREE.Clock();
  private state: HoloState = "offline";
  private color = COLORS.offline.clone();
  private intensity = 0.4;
  private pointer = new THREE.Vector2();
  private level = 0;
  private jaw = 0;

  /** Audio drivers set by the app each frame. */
  micLevel = 0;
  mouthLevel = 0;

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.95;
    this.scene.background = new THREE.Color(0x05040d);
    this.scene.fog = new THREE.FogExp2(0x0c0820, 0.05);

    this.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    this.camera.position.set(0, 0.7, 6.8);

    this.buildRoom();
    this.buildPlatform();
    this.buildHologram();
    this.buildSmoke();

    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(512, 512), 0.8, 0.45, 0.22);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    window.addEventListener("resize", () => this.resize());
    window.addEventListener("pointermove", (e) => {
      this.pointer.set((e.clientX / window.innerWidth) * 2 - 1, (e.clientY / window.innerHeight) * 2 - 1);
    });
    this.resize();
  }

  setState(state: HoloState) {
    this.state = state;
  }

  start() {
    const loop = () => {
      this.frame();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  private resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.renderer.setSize(w, h, false);
    this.composer.setSize(w, h);
    // Half-resolution bloom keeps integrated GPUs (e.g. Intel UHD 620) smooth.
    this.bloom.resolution.set(w / 2, h / 2);
    this.camera.aspect = w / h;
    // Portrait screens: pull back so the bust stays in frame.
    this.camera.position.z = w / h < 1 ? 6.8 / Math.max(0.55, w / h) : 6.8;
    this.camera.updateProjectionMatrix();
  }

  // ---------------------------------------------------------------- room
  private buildRoom() {
    const rand = mulberry32(42);
    const rackMat = new THREE.MeshStandardMaterial({ color: 0x0b0d1c, metalness: 0.7, roughness: 0.45 });
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x1a1d3a, metalness: 0.9, roughness: 0.3 });
    const ledGeo = new THREE.PlaneGeometry(0.08, 0.025);
    const ledMat = new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false });
    const ledCount = 900;
    this.leds = new THREE.InstancedMesh(ledGeo, ledMat, ledCount);
    this.ledPhase = new Float32Array(ledCount);
    let led = 0;
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const palette = [0xffa040, 0x9a6bff, 0x4fb8ff, 0xffc070, 0x7a5cff];

    for (const side of [-1, 1]) {
      for (let i = 0; i < 6; i++) {
        const z = 1.5 - i * 2.1;
        const rack = new THREE.Mesh(new THREE.BoxGeometry(1.1, 4.4, 1.9), rackMat);
        rack.position.set(side * 4.3, 1.0, z);
        this.scene.add(rack);
        const trim = new THREE.Mesh(new THREE.BoxGeometry(0.06, 4.4, 0.06), frameMat);
        trim.position.set(side * 3.73, 1.0, z + 0.93);
        this.scene.add(trim);
        // LEDs on the corridor-facing side.
        q.setFromEuler(new THREE.Euler(0, -side * Math.PI / 2, 0));
        for (let k = 0; k < 70 && led < ledCount; k++) {
          const y = -0.9 + rand() * 3.8;
          const zz = z - 0.8 + rand() * 1.6;
          m.compose(new THREE.Vector3(side * 3.74, y, zz), q, new THREE.Vector3(1, 1, 1));
          this.leds.setMatrixAt(led, m);
          const base = new THREE.Color(palette[Math.floor(rand() * palette.length)]);
          this.ledBase[led] = base;
          this.leds.setColorAt(led, base);
          this.ledPhase[led] = rand() * 100;
          led++;
        }
      }
      // Purple strip light along the racks.
      const strip = new THREE.Mesh(
        new THREE.BoxGeometry(0.03, 0.03, 13),
        new THREE.MeshBasicMaterial({ color: 0x6a44d8, toneMapped: false }),
      );
      strip.position.set(side * 3.7, 3.1, -3.5);
      this.scene.add(strip);
    }
    this.leds.count = led;
    this.scene.add(this.leds);

    // Back wall and ceiling beams.
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(14, 8), new THREE.MeshStandardMaterial({ color: 0x080816, roughness: 0.9 }));
    wall.position.set(0, 1.5, -11);
    this.scene.add(wall);
    for (let i = 0; i < 6; i++) {
      const beam = new THREE.Mesh(new THREE.BoxGeometry(8.6, 0.12, 0.25), frameMat);
      beam.position.set(0, 3.4, 1 - i * 2.4);
      this.scene.add(beam);
    }

    // Glossy dark floor with glowing seams.
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(14, 26),
      new THREE.MeshStandardMaterial({ color: 0x070814, metalness: 0.85, roughness: 0.25 }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(0, -1.2, -4);
    this.scene.add(floor);
    const seams: number[] = [];
    for (let x = -3; x <= 3; x += 1.5) seams.push(x, -1.19, 4, x, -1.19, -12);
    for (let z = 4; z >= -12; z -= 1.5) seams.push(-3.6, -1.19, z, 3.6, -1.19, z);
    const seamGeo = new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(seams, 3));
    this.scene.add(
      new THREE.LineSegments(seamGeo, new THREE.LineBasicMaterial({ color: 0x3a3a8a, transparent: true, opacity: 0.45 })),
    );

    // Lighting.
    this.scene.add(new THREE.AmbientLight(0x1c1640, 0.8));
    const purple = new THREE.PointLight(0x9b5cff, 12, 12, 1.8);
    purple.position.set(3.2, 2.8, -1);
    this.scene.add(purple);
    const cyan = new THREE.PointLight(0x3fb8ff, 18, 9, 1.8);
    cyan.position.set(0, 0.2, 0.8);
    this.scene.add(cyan);
    const back = new THREE.PointLight(0x5a3cff, 8, 14, 1.6);
    back.position.set(-2.5, 2.5, -7);
    this.scene.add(back);

    // Purple spotlight beam from the upper right, like the reference.
    const cone = new THREE.Mesh(new THREE.ConeGeometry(1.5, 7, 48, 1, true), beamMaterial(0xa070ff));
    cone.geometry.translate(0, -3.5, 0);
    cone.position.set(3.65, 2.65, -0.2);
    cone.lookAt(new THREE.Vector3(-0.8, 0.1, 0.5));
    cone.rotateX(-Math.PI / 2);
    this.scene.add(cone);
    const lamp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: 0xd8c8ff, blending: THREE.AdditiveBlending, depthWrite: false }));
    lamp.position.copy(cone.position);
    lamp.scale.setScalar(0.35);
    this.scene.add(lamp);
  }

  // ------------------------------------------------------------ platform
  private buildPlatform() {
    const base = new THREE.Mesh(
      new THREE.BoxGeometry(3.6, 0.25, 2.6),
      new THREE.MeshStandardMaterial({ color: 0x0c0f22, metalness: 0.9, roughness: 0.3 }),
    );
    base.position.set(0, -0.97, 0);
    this.scene.add(base);
    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(base.geometry),
      new THREE.LineBasicMaterial({ color: 0x4fa8ff, transparent: true, opacity: 0.5 }),
    );
    edge.position.copy(base.position);
    this.scene.add(edge);

    this.emitter = new THREE.Mesh(new THREE.CircleGeometry(1.1, 64), discMaterial(0x6fe0ff, 1.6));
    this.emitter.rotation.x = -Math.PI / 2;
    this.emitter.position.y = -0.83;
    this.scene.add(this.emitter);

    const ringSpecs = [
      { r: 0.62, w: 0.025, arc: Math.PI * 2, c: 0xbff4ff },
      { r: 0.82, w: 0.04, arc: Math.PI * 1.6, c: 0x4fd8ff },
      { r: 1.02, w: 0.018, arc: Math.PI * 2, c: 0x8a7dff },
      { r: 1.18, w: 0.05, arc: Math.PI * 0.9, c: 0x4fd8ff },
      { r: 1.32, w: 0.012, arc: Math.PI * 2, c: 0x6a8cff },
    ];
    for (const s of ringSpecs) {
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(s.r, s.r + s.w, 96, 1, 0, s.arc),
        new THREE.MeshBasicMaterial({ color: s.c, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, depthWrite: false, toneMapped: false }),
      );
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = -0.82;
      this.rings.push(ring);
      this.scene.add(ring);
    }
  }

  // ----------------------------------------------------------- hologram
  private buildHologram() {
    this.hologram.add(this.bust.group);
    this.hologram.position.y = 1.15;
    this.hologram.scale.setScalar(0.95);
    this.scene.add(this.hologram);

    // Data streams: vertical lines from the emitter up into the chest.
    const rand = mulberry32(3);
    const pos: number[] = [];
    const t: number[] = [];
    const seed: number[] = [];
    const segs = 12;
    for (let i = 0; i < 34; i++) {
      const x = (rand() - 0.5) * 1.3;
      const z = (rand() - 0.5) * 0.5 + 0.1;
      const h = 0.8 + rand() * 1.2;
      const s = rand();
      for (let k = 0; k < segs; k++) {
        const a = k / segs;
        const b = (k + 1) / segs;
        pos.push(x, -0.82 + a * h, z, x, -0.82 + b * h, z);
        t.push(a, b);
        seed.push(s, s);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("aT", new THREE.Float32BufferAttribute(t, 1));
    g.setAttribute("aSeed", new THREE.Float32BufferAttribute(seed, 1));
    this.streams = new THREE.LineSegments(g, streamMaterial());
    this.scene.add(this.streams);

    // Grid panel behind the head with small data bars.
    const grid: number[] = [];
    const W = 2.7;
    const H = 3.1;
    const step = 0.15;
    for (let x = -W / 2; x <= W / 2 + 1e-6; x += step) grid.push(x, -H / 2, 0, x, H / 2, 0);
    for (let y = -H / 2; y <= H / 2 + 1e-6; y += step) grid.push(-W / 2, y, 0, W / 2, y, 0);
    const gridGeo = new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(grid, 3));
    const gridMat = new THREE.LineBasicMaterial({ color: 0x4a5cff, transparent: true, opacity: 0.14, blending: THREE.AdditiveBlending, depthWrite: false });
    this.panel.add(new THREE.LineSegments(gridGeo, gridMat));
    const frame = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.PlaneGeometry(W, H)),
      new THREE.LineBasicMaterial({ color: 0x6a7dff, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending }),
    );
    this.panel.add(frame);
    const barMat = new THREE.MeshBasicMaterial({ color: 0x9a6bff, transparent: true, opacity: 0.45, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false });
    const bars = (x: number, y: number, n: number) => {
      for (let i = 0; i < n; i++) {
        const bar = new THREE.Mesh(new THREE.PlaneGeometry(0.32 - (i % 3) * 0.05, 0.035), barMat);
        bar.position.set(x, y - i * 0.07, 0.01);
        this.panel.add(bar);
      }
    };
    bars(-W / 2 - 0.05, H / 2 - 0.45, 6);
    bars(W / 2 + 0.05, -H / 2 + 0.75, 7);
    this.panel.position.set(0, 1.25, -1.3);
    this.scene.add(this.panel);
  }

  // -------------------------------------------------------------- smoke
  private buildSmoke() {
    const n = 220;
    const rand = mulberry32(9);
    const pos = new Float32Array(n * 3);
    this.smokeVel = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      pos[i * 3] = (rand() - 0.5) * 8;
      pos[i * 3 + 1] = -1.1 + rand() * 1.1;
      pos[i * 3 + 2] = -3 + rand() * 5;
      this.smokeVel[i] = 0.05 + rand() * 0.12;
    }
    const g = new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(pos, 3));
    this.smoke = new THREE.Points(
      g,
      new THREE.PointsMaterial({
        size: 2.0,
        map: glowTexture(),
        color: 0x7a3cff,
        transparent: true,
        opacity: 0.035,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    this.scene.add(this.smoke);
  }

  // -------------------------------------------------------------- frame
  private frame() {
    const dt = Math.min(this.clock.getDelta(), 0.05);
    const t = this.clock.elapsedTime;
    holoUniforms.uTime.value = t;

    // Ease colour and intensity toward the current state.
    const targetIntensity = { offline: 0.35, idle: 1, listening: 1.2, thinking: 1.05, speaking: 1.3 }[this.state];
    this.color.lerp(COLORS[this.state], 1 - Math.exp(-dt * 4));
    this.intensity += (targetIntensity - this.intensity) * (1 - Math.exp(-dt * 4));
    holoUniforms.uColor.value.copy(this.color);
    holoUniforms.uIntensity.value = this.intensity;
    holoUniforms.uFlicker.value = this.state === "offline" ? 0.35 : 0;

    // Scan band sweeps the head while thinking.
    holoUniforms.uScanY.value =
      this.state === "thinking" ? this.hologram.position.y + 0.3 + Math.sin(t * 2.2) * 1.3 : -10;

    // Audio drivers.
    const drive = this.state === "listening" ? this.micLevel : this.state === "speaking" ? this.mouthLevel : 0;
    this.level += (drive - this.level) * (1 - Math.exp(-dt * 12));
    const jawTarget = this.state === "speaking" ? this.mouthLevel : 0;
    this.jaw += (jawTarget - this.jaw) * (1 - Math.exp(-dt * 18));
    this.bust.updateHead(this.jaw);

    // Gentle hologram motion: hover, slow turn, look toward the pointer.
    const lookYaw = this.state === "speaking" || this.state === "listening" ? 0 : Math.sin(t * 0.25) * 0.35;
    const yaw = lookYaw + this.pointer.x * 0.15;
    this.bust.group.rotation.y += (yaw - this.bust.group.rotation.y) * (1 - Math.exp(-dt * 2));
    this.bust.group.rotation.x += (this.pointer.y * 0.06 - this.bust.group.rotation.x) * (1 - Math.exp(-dt * 2));
    this.hologram.position.y = 1.15 + Math.sin(t * 1.1) * 0.03;
    (this.bust.eyes.material as THREE.PointsMaterial).size = 0.18 + this.level * 0.12 + (this.state === "speaking" ? 0.04 : 0);
    (this.bust.eyes.material as THREE.PointsMaterial).opacity = this.state === "offline" ? 0.3 : 1;

    // Platform rings spin faster while thinking and pulse with audio.
    const spin = this.state === "thinking" ? 1.8 : this.state === "offline" ? 0.1 : 0.4;
    this.rings.forEach((ring, i) => {
      ring.rotation.z += dt * spin * (i % 2 === 0 ? 1 : -1.3) * (0.4 + i * 0.15);
      const s = 1 + this.level * 0.12 * (1 + i * 0.3);
      ring.scale.setScalar(s);
      (ring.material as THREE.MeshBasicMaterial).opacity = (0.5 + 0.4 * this.intensity) * (this.state === "offline" ? 0.4 : 1);
    });
    const disc = this.emitter.material as THREE.ShaderMaterial;
    disc.uniforms.uStrength.value = (1.1 + this.level * 1.2 + Math.sin(t * 3) * 0.08) * this.intensity;
    (this.streams.material as THREE.ShaderMaterial).uniforms.uSpeed.value =
      this.state === "speaking" ? 2.6 : this.state === "thinking" ? 1.8 : 1;

    // LEDs blink (every few frames is plenty).
    if (Math.floor(t * 20) !== this.ledTick) {
      this.ledTick = Math.floor(t * 20);
      const c = this.tmpColor;
      for (let i = 0; i < this.leds.count; i++) {
        const ph = this.ledPhase[i];
        const on = Math.sin(t * (0.6 + (ph % 3)) + ph) > -0.3 ? 1 : 0.12;
        c.copy(this.ledBase[i]).multiplyScalar(on);
        this.leds.setColorAt(i, c);
      }
      if (this.leds.instanceColor) this.leds.instanceColor.needsUpdate = true;
    }

    // Drifting haze.
    const sp = this.smoke.geometry.getAttribute("position") as THREE.BufferAttribute;
    for (let i = 0; i < sp.count; i++) {
      let x = sp.getX(i) + this.smokeVel[i] * dt * (i % 2 ? 1 : -1);
      if (x > 4.5) x = -4.5;
      if (x < -4.5) x = 4.5;
      sp.setX(i, x);
      sp.setY(i, sp.getY(i) + Math.sin(t * 0.3 + i) * 0.0008);
    }
    sp.needsUpdate = true;

    // Subtle camera parallax.
    this.camera.position.x += (this.pointer.x * 0.35 - this.camera.position.x) * (1 - Math.exp(-dt * 1.5));
    this.camera.position.y += (0.7 - this.pointer.y * 0.2 - this.camera.position.y) * (1 - Math.exp(-dt * 1.5));
    this.camera.lookAt(0, 0.4, 0);

    this.composer.render();
  }
}
