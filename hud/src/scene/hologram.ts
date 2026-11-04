// The HUD scene in Babylon.js: a scanned head rendered as a hologram on a glowing
// platform, in a purple server-room corridor with haze, god rays and a mirror floor.
import { Engine } from "@babylonjs/core/Engines/engine";
import { Constants } from "@babylonjs/core/Engines/constants";
import { Scene } from "@babylonjs/core/scene";
import { Quaternion, Vector2, Vector3 } from "@babylonjs/core/Maths/math.vector";
import { Color3, Color4 } from "@babylonjs/core/Maths/math.color";
import { Plane } from "@babylonjs/core/Maths/math.plane";
import { FreeCamera } from "@babylonjs/core/Cameras/freeCamera";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight";
import { PointLight } from "@babylonjs/core/Lights/pointLight";
import { Mesh } from "@babylonjs/core/Meshes/mesh";
import { TransformNode } from "@babylonjs/core/Meshes/transformNode";
import { MeshBuilder } from "@babylonjs/core/Meshes/meshBuilder";
import { VertexData } from "@babylonjs/core/Meshes/mesh.vertexData";
import { StandardMaterial } from "@babylonjs/core/Materials/standardMaterial";
import { ShaderMaterial } from "@babylonjs/core/Materials/shaderMaterial";
import { ImageProcessingConfiguration } from "@babylonjs/core/Materials/imageProcessingConfiguration";
import { DynamicTexture } from "@babylonjs/core/Materials/Textures/dynamicTexture";
import { MirrorTexture } from "@babylonjs/core/Materials/Textures/mirrorTexture";
import { Texture } from "@babylonjs/core/Materials/Textures/texture";
import { GlowLayer } from "@babylonjs/core/Layers/glowLayer";
import { DefaultRenderingPipeline } from "@babylonjs/core/PostProcesses/RenderPipeline/Pipelines/defaultRenderingPipeline";
import { VolumetricLightScatteringPostProcess } from "@babylonjs/core/PostProcesses/volumetricLightScatteringPostProcess";
import { PostProcess } from "@babylonjs/core/PostProcesses/postProcess";
import { ParticleSystem } from "@babylonjs/core/Particles/particleSystem";
import "@babylonjs/core/Particles/particleSystemComponent";
import "@babylonjs/core/Layers/effectLayerSceneComponent";
import "@babylonjs/core/Rendering/depthRendererSceneComponent";
import "@babylonjs/core/Rendering/edgesRenderer";
import { ImportMeshAsync } from "@babylonjs/core/Loading/sceneLoader";
import "@babylonjs/loaders/glTF/2.0";
import "./shaders";
import { HoloHead } from "./holoHead";
import { attachIdleMotion } from "./idleMotion";

export type HoloState = "offline" | "idle" | "listening" | "thinking" | "speaking";

const COLORS: Record<HoloState, Color3> = {
  offline: Color3.FromHexString("#2a4a66"),
  idle: Color3.FromHexString("#00f0ff"),
  listening: Color3.FromHexString("#86f2ff"),
  thinking: Color3.FromHexString("#8a7dff"),
  speaking: Color3.FromHexString("#66e6ff"),
};
const INTENSITY: Record<HoloState, number> = { offline: 0.3, idle: 1, listening: 1.2, thinking: 1.05, speaking: 1.3 };

/** Model-space landmarks of models/head.glb (Lee Perry-Smith scan, y-up, face toward +z). */
const HEAD = {
  url: "models/head.glb",
  height: 8, // model units from chest to crown
  mouthY: 0.45,
  chinY: -0.5,
  faceZ: 1.3,
  mouthHalfWidth: 0.8,
  chestY: -2.2,
  eyes: [new Vector3(-0.58, 1.55, 2.1), new Vector3(0.58, 1.55, 2.1)],
};

const FLOOR_Y = -1.2;
const QUALITY_KEY = "jarvis.hud.quality";
const MAX_TIER = 3;

function safeGet(key: string): string | null {
  try {
    // ?quality=high starts over at full quality.
    if (new URLSearchParams(location.search).get("quality") === "high") localStorage.removeItem(key);
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: keep the tier for this session only */
  }
}

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class HoloScene {
  private engine: Engine;
  private scene: Scene;
  private camera: FreeCamera;
  private glow: GlowLayer;
  private holo: TransformNode;
  private bust: TransformNode;
  private head: HoloHead;
  private streamMat!: ShaderMaterial;
  private panelMat!: ShaderMaterial;
  private beamMat!: ShaderMaterial;
  private rings: Mesh[] = [];
  private emitterMat!: StandardMaterial;
  private eyeMat!: StandardMaterial;
  private eyes: Mesh[] = [];
  private ledTex!: DynamicTexture;
  private ledSeeds: number[] = [];
  private sparkles!: ParticleSystem;
  private finish!: PostProcess;
  private mirror!: MirrorTexture;
  private floorMat!: StandardMaterial;
  private vls: VolumetricLightScatteringPostProcess | null = null;
  private pipe!: DefaultRenderingPipeline;
  /** Quality tier: 0 = full, each step drops a costly effect (see degrade()). */
  private tier = 0;
  private fpsWindow = { frames: 0, time: 0, warmup: 4 };

  private state: HoloState = "offline";
  private color = COLORS.offline.clone();
  private intensity = 0.3;
  private level = 0;
  private jaw = 0;
  private glitch = 0;
  private time = 0;
  private pointer = new Vector2();

  /** Audio drivers set by the app each frame. */
  micLevel = 0;
  mouthLevel = 0;
  /** Dev-only: fixed yaw for inspecting the model. */
  debugYaw: number | null = null;

  constructor(canvas: HTMLCanvasElement) {
    this.engine = new Engine(canvas, true, { stencil: true, preserveDrawingBuffer: false, powerPreference: "high-performance" }, false);
    // Integrated GPUs (e.g. Intel UHD 620): cap the render resolution.
    this.engine.setHardwareScalingLevel(1 / Math.min(window.devicePixelRatio || 1, 1.25));
    const scene = (this.scene = new Scene(this.engine));
    scene.clearColor = new Color4(0.02, 0.016, 0.05, 1);
    scene.fogMode = Scene.FOGMODE_EXP2;
    scene.fogDensity = 0.05;
    scene.fogColor = Color3.FromHexString("#0c0820");
    scene.skipPointerMovePicking = true;
    if (import.meta.env.DEV) {
      (window as any).__scene = scene;
      (window as any).__holo = this;
    }

    this.camera = new FreeCamera("cam", new Vector3(0, 0.7, -6.8), scene);
    this.camera.fov = 0.74;
    this.camera.minZ = 0.1;
    this.camera.setTarget(new Vector3(0, 0.45, 0));

    this.holo = new TransformNode("hologram", scene);
    this.bust = new TransformNode("bust", scene);
    this.holo.position.y = 1.15;
    this.bust.parent = this.holo;

    this.glow = new GlowLayer("glow", scene, { mainTextureRatio: 0.5, blurKernelSize: 48 });
    this.glow.intensity = 0.9;
    this.head = new HoloHead(scene, this.glow, {
      gridRatio: 0.12,
      majorUnitFrequency: 6,
      mouth: { mouthY: HEAD.mouthY, chinY: HEAD.chinY, faceZ: HEAD.faceZ, halfWidth: HEAD.mouthHalfWidth },
    });

    this.buildRoom();
    this.buildPlatform();
    this.buildHologramExtras();
    this.buildParticles();
    this.buildFloor();
    this.buildPost();
    void this.loadHead();

    window.addEventListener("resize", () => this.resize());
    window.addEventListener("pointermove", (e) => {
      this.pointer.set((e.clientX / window.innerWidth) * 2 - 1, (e.clientY / window.innerHeight) * 2 - 1);
    });
    this.resize();
    const saved = Number(safeGet(QUALITY_KEY));
    for (let i = 0; i < Math.min(saved || 0, MAX_TIER); i++) this.degrade();
  }

  setState(state: HoloState) {
    if (state !== this.state && (state === "offline" || this.state === "offline")) this.glitch = 1;
    else if (state !== this.state) this.glitch = Math.max(this.glitch, 0.45);
    this.state = state;
  }

  start() {
    this.engine.runRenderLoop(() => {
      const dt = this.engine.getDeltaTime() / 1000;
      this.update(Math.min(dt, 0.05));
      this.scene.render();
      this.watchFps(dt);
    });
  }

  /**
   * Adaptive quality for integrated GPUs: when the frame rate stays below ~40 fps, switch off
   * the most expensive effect, wait, and measure again. The chosen tier is remembered.
   */
  private watchFps(dt: number) {
    const w = this.fpsWindow;
    if (this.tier >= MAX_TIER || document.hidden) return;
    if (w.warmup > 0) { w.warmup -= dt; return; }
    w.frames++;
    w.time += dt;
    if (w.time < 2.5) return;
    const fps = w.frames / w.time;
    w.frames = 0;
    w.time = 0;
    if (fps < 40) {
      this.degrade();
      safeSet(QUALITY_KEY, String(this.tier));
      w.warmup = 1.5;
    }
  }

  private degrade() {
    this.tier++;
    switch (this.tier) {
      case 1: // floor reflection and film grain
        this.floorMat.reflectionTexture = null;
        this.mirror.dispose();
        this.pipe.grainEnabled = false;
        this.pipe.chromaticAberrationEnabled = false;
        break;
      case 2: // god rays and the wide glow blur
        this.vls?.dispose(this.camera);
        this.vls = null;
        this.glow.blurKernelSize = 24;
        this.pipe.bloomKernel = 24;
        break;
      case 3: // render fewer pixels
        this.engine.setHardwareScalingLevel(this.engine.getHardwareScalingLevel() * 1.4);
        break;
    }
    console.info(`HUD-kwaliteit verlaagd naar niveau ${this.tier}`);
  }

  private resize() {
    this.engine.resize();
    const aspect = window.innerWidth / window.innerHeight;
    this.camera.position.z = aspect < 1 ? -6.8 / Math.max(0.55, aspect) : -6.8;
  }

  // ------------------------------------------------------------ materials
  private shader(name: string, uniforms: string[]): ShaderMaterial {
    const m = new ShaderMaterial(name, this.scene, { vertex: name, fragment: name }, {
      attributes: ["position", "uv"],
      uniforms: ["worldViewProjection", ...uniforms],
      needAlphaBlending: true,
    });
    m.alphaMode = Constants.ALPHA_ADD;
    m.disableDepthWrite = true;
    m.backFaceCulling = false;
    return m;
  }

  // ----------------------------------------------------------------- head
  private async loadHead() {
    try {
      const result = await ImportMeshAsync(HEAD.url, this.scene);
      const meshes = result.meshes.filter((m): m is Mesh => m instanceof Mesh && m.getTotalVertices() > 0);
      const root = result.meshes[0];
      root.parent = this.bust;
      // Mirror z (the loader's handedness flip) so the face (+z in the file) looks at the camera (-z).
      root.rotationQuaternion = null;
      root.rotation.set(0, 0, 0);
      root.scaling.set(1, 1, -1);
      const s = 2.45 / HEAD.height;
      this.bust.scaling.setAll(s);
      this.bust.position.y = -0.2;
      this.head.attach(meshes);
      for (const mesh of meshes) this.mirror?.renderList?.push(mesh);
      this.addEyes(root);
      attachIdleMotion(this.scene, root as TransformNode);
    } catch (err) {
      console.warn("Hoofdmodel niet geladen, val terug op een eenvoudige vorm", err);
      const head = MeshBuilder.CreateSphere("fallbackHead", { diameterX: 3.1, diameterY: 4, diameterZ: 3.6, segments: 48 }, this.scene);
      head.parent = this.bust;
      head.position.y = 1.6;
      head.scaling.z = -1;
      const chest = MeshBuilder.CreateCylinder("fallbackChest", { diameterTop: 2.2, diameterBottom: 8.4, height: 2.6, tessellation: 32 }, this.scene);
      chest.parent = this.bust;
      chest.position.y = -2.6;
      this.bust.scaling.setAll(2.45 / HEAD.height);
      this.bust.position.y = -0.2;
      this.head.attach([head, chest]);
    }
  }

  private addEyes(parent: TransformNode) {
    this.eyeMat = new StandardMaterial("eye", this.scene);
    this.eyeMat.disableLighting = true;
    this.eyeMat.emissiveColor = Color3.FromHexString("#c8f6ff");
    this.eyeMat.alpha = 0.9;
    for (const p of HEAD.eyes) {
      const eye = MeshBuilder.CreateSphere("eye", { diameterX: 0.27, diameterY: 0.15, diameterZ: 0.1, segments: 10 }, this.scene);
      eye.material = this.eyeMat;
      eye.parent = parent;
      eye.position.copyFrom(p);
      this.eyes.push(eye);
    }
  }

  // ----------------------------------------------------------------- room
  private buildRoom() {
    const scene = this.scene;
    const rand = mulberry32(42);

    new HemisphericLight("amb", new Vector3(0, 1, 0), scene).intensity = 0.25;
    const purple = new PointLight("purple", new Vector3(3.2, 2.8, 1), scene);
    purple.diffuse = Color3.FromHexString("#9b5cff");
    purple.intensity = 1.6;
    purple.range = 12;
    const cyan = new PointLight("cyan", new Vector3(0, 0.2, -0.8), scene);
    cyan.diffuse = Color3.FromHexString("#3fb8ff");
    cyan.intensity = 1.4;
    cyan.range = 8;
    const back = new PointLight("back", new Vector3(-2.5, 2.5, 7), scene);
    back.diffuse = Color3.FromHexString("#5a3cff");
    back.intensity = 1.1;
    back.range = 14;

    // Rack faces share one LED texture that we redraw to make lights blink.
    this.ledTex = new DynamicTexture("leds", { width: 256, height: 512 }, scene, false);
    for (let i = 0; i < 140; i++) this.ledSeeds.push(rand());
    this.drawLeds(0);

    const rackMat = new StandardMaterial("rack", scene);
    rackMat.diffuseColor = Color3.FromHexString("#0b0d1c");
    rackMat.specularColor = new Color3(0.25, 0.25, 0.4);
    const faceMat = new StandardMaterial("rackFace", scene);
    faceMat.diffuseColor = Color3.FromHexString("#06070f");
    faceMat.emissiveTexture = this.ledTex;
    faceMat.specularColor = new Color3(0.3, 0.3, 0.5);
    const trimMat = new StandardMaterial("trim", scene);
    trimMat.diffuseColor = Color3.FromHexString("#1a1d3a");
    trimMat.specularColor = new Color3(0.6, 0.6, 0.9);

    for (const side of [-1, 1]) {
      for (let i = 0; i < 6; i++) {
        const z = -1.5 + i * 2.1;
        const rack = MeshBuilder.CreateBox("rack", { width: 1.1, height: 4.4, depth: 1.95 }, scene);
        rack.position.set(side * 4.3, 1.0, z);
        rack.material = rackMat;
        const face = MeshBuilder.CreatePlane("rackFace", { width: 1.85, height: 4.2 }, scene);
        face.position.set(side * 3.74, 1.0, z);
        face.rotation.y = side * Math.PI / 2;
        face.material = faceMat;
        // Vary which part of the LED sheet each rack shows.
        if (i % 2) face.scaling.x = -1;
        const trim = MeshBuilder.CreateBox("trim", { width: 0.06, height: 4.4, depth: 0.06 }, scene);
        trim.position.set(side * 3.73, 1.0, z - 0.97);
        trim.material = trimMat;
      }
      const strip = MeshBuilder.CreateBox("strip", { width: 0.03, height: 0.03, depth: 13 }, scene);
      strip.position.set(side * 3.7, 3.1, 3.5);
      const stripMat = new StandardMaterial("strip", scene);
      stripMat.disableLighting = true;
      stripMat.emissiveColor = Color3.FromHexString("#6a44d8");
      strip.material = stripMat;
    }

    const wall = MeshBuilder.CreatePlane("wall", { width: 14, height: 8 }, scene);
    wall.position.set(0, 1.5, 11);
    const wallMat = new StandardMaterial("wall", scene);
    wallMat.diffuseColor = Color3.FromHexString("#080816");
    wallMat.specularColor = Color3.Black();
    wall.material = wallMat;
    for (let i = 0; i < 6; i++) {
      const beam = MeshBuilder.CreateBox("beam", { width: 8.6, height: 0.12, depth: 0.25 }, scene);
      beam.position.set(0, 3.4, -1 + i * 2.4);
      beam.material = trimMat;
    }

    // Spotlight from the upper right: a lamp that casts god rays plus a soft cone.
    const lampPos = new Vector3(3.65, 2.65, 0.2);
    const lamp = MeshBuilder.CreateSphere("lamp", { diameter: 0.28, segments: 12 }, scene);
    lamp.position.copyFrom(lampPos);
    const lampMat = new StandardMaterial("lamp", scene);
    lampMat.disableLighting = true;
    lampMat.emissiveColor = Color3.FromHexString("#e2d4ff");
    lamp.material = lampMat;
    this.lampMesh = lamp;

    this.beamMat = this.shader("holoBeam", ["uColor", "uTime"]);
    this.beamMat.setColor3("uColor", Color3.FromHexString("#a070ff"));
    const cone = MeshBuilder.CreateCylinder("beam", { height: 5, diameterTop: 0.05, diameterBottom: 1.8, tessellation: 48, cap: Mesh.NO_CAP }, scene);
    cone.material = this.beamMat;
    // Point the cone from the lamp toward the hologram.
    const target = new Vector3(-0.6, 0.4, 1.2);
    const dir = target.subtract(lampPos).normalize();
    cone.position = lampPos.add(dir.scale(2.5));
    // Local +y (the narrow end) points back at the lamp.
    cone.rotationQuaternion = new Quaternion();
    Quaternion.FromUnitVectorsToRef(Vector3.Up(), dir.negate(), cone.rotationQuaternion);
    this.glow.addExcludedMesh(cone);
  }

  private lampMesh!: Mesh;

  private drawLeds(t: number) {
    const ctx = this.ledTex.getContext() as CanvasRenderingContext2D;
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, 256, 512);
    const palette = ["#ffa040", "#9a6bff", "#4fb8ff", "#ffc070", "#7a5cff"];
    // Server units with LED rows.
    for (let u = 0; u < 20; u++) {
      const y = 10 + u * 25;
      ctx.fillStyle = "#0b0d1e";
      ctx.fillRect(8, y, 240, 20);
      for (let k = 0; k < 7; k++) {
        const s = this.ledSeeds[(u * 7 + k) % this.ledSeeds.length];
        const on = Math.sin(t * (0.6 + (s * 7) % 3) + s * 100) > -0.3;
        if (!on) continue;
        ctx.fillStyle = palette[Math.floor(s * 997) % palette.length];
        ctx.fillRect(16 + k * 30 + (s * 12) % 8, y + 7, 9, 4);
      }
    }
    this.ledTex.update();
  }

  // ------------------------------------------------------------- platform
  private buildPlatform() {
    const scene = this.scene;
    const base = MeshBuilder.CreateBox("platform", { width: 3.6, height: 0.25, depth: 2.6 }, scene);
    base.position.y = -0.97;
    const baseMat = new StandardMaterial("platform", scene);
    baseMat.diffuseColor = Color3.FromHexString("#0c0f22");
    baseMat.specularColor = new Color3(0.5, 0.5, 0.8);
    baseMat.specularPower = 64;
    base.material = baseMat;
    base.enableEdgesRendering();
    base.edgesWidth = 1.2;
    base.edgesColor = new Color4(0.31, 0.66, 1, 0.6);

    // Emitter: radial glow texture on a disc.
    const tex = new DynamicTexture("emitter", { width: 256, height: 256 }, scene, false);
    const ctx = tex.getContext() as CanvasRenderingContext2D;
    const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.3, "rgba(170,240,255,0.9)");
    g.addColorStop(0.6, "rgba(80,200,255,0.35)");
    g.addColorStop(1, "rgba(40,120,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 256, 256);
    tex.update();
    tex.hasAlpha = true;
    const emitter = MeshBuilder.CreateDisc("emitter", { radius: 1.15, tessellation: 64 }, scene);
    emitter.rotation.x = Math.PI / 2;
    emitter.position.y = -0.83;
    this.emitterMat = new StandardMaterial("emitter", scene);
    this.emitterMat.disableLighting = true;
    this.emitterMat.emissiveTexture = tex;
    this.emitterMat.opacityTexture = tex;
    this.emitterMat.alphaMode = Constants.ALPHA_ADD;
    this.emitterMat.disableDepthWrite = true;
    emitter.material = this.emitterMat;

    const specs = [
      { r: 0.62, t: 0.02, arc: 1, c: "#bff4ff" },
      { r: 0.84, t: 0.035, arc: 0.8, c: "#4fd8ff" },
      { r: 1.03, t: 0.016, arc: 1, c: "#8a7dff" },
      { r: 1.18, t: 0.045, arc: 0.45, c: "#4fd8ff" },
      { r: 1.32, t: 0.012, arc: 1, c: "#6a8cff" },
    ];
    for (const s of specs) {
      const pts: Vector3[] = [];
      const n = Math.max(8, Math.round(96 * s.arc));
      for (let i = 0; i <= n; i++) {
        const a = (i / n) * Math.PI * 2 * s.arc;
        pts.push(new Vector3(Math.cos(a) * s.r, 0, Math.sin(a) * s.r));
      }
      const ring = MeshBuilder.CreateTube("ring", { path: pts, radius: s.t / 2, tessellation: 6 }, scene);
      ring.position.y = -0.82;
      const mat = new StandardMaterial("ring", scene);
      mat.disableLighting = true;
      mat.emissiveColor = Color3.FromHexString(s.c);
      ring.material = mat;
      this.rings.push(ring);
    }
  }

  // ------------------------------------------------------ hologram extras
  private buildHologramExtras() {
    const scene = this.scene;
    // Data streams: thin vertical quads from the emitter up into the chest.
    const rand = mulberry32(3);
    const positions: number[] = [];
    const uvs: number[] = [];
    const indices: number[] = [];
    let v = 0;
    for (let i = 0; i < 36; i++) {
      const x = (rand() - 0.5) * 1.3;
      const z = (rand() - 0.5) * 0.5 - 0.1;
      const h = 0.8 + rand() * 1.2;
      const w = 0.006 + rand() * 0.008;
      const seed = rand();
      positions.push(x - w, -0.82, z, x + w, -0.82, z, x + w, -0.82 + h, z, x - w, -0.82 + h, z);
      uvs.push(seed, 0, seed, 0, seed, 1, seed, 1);
      indices.push(v, v + 1, v + 2, v, v + 2, v + 3);
      v += 4;
    }
    const streams = new Mesh("streams", scene);
    const vd = new VertexData();
    vd.positions = positions;
    vd.uvs = uvs;
    vd.indices = indices;
    vd.applyToMesh(streams);
    this.streamMat = this.shader("holoStream", ["uTime", "uSpeed", "uColor", "uIntensity"]);
    this.streamMat.setFloat("uSpeed", 1);
    streams.material = this.streamMat;
    this.glow.referenceMeshToUseItsOwnMaterial(streams);

    // Grid panel behind the head with small data bars.
    const panel = MeshBuilder.CreatePlane("panel", { width: 2.7, height: 3.1 }, scene);
    panel.position.set(0, 1.25, 1.3);
    this.panelMat = this.shader("holoPanel", ["uColor", "uTime", "uCells"]);
    this.panelMat.setColor3("uColor", Color3.FromHexString("#4a5cff"));
    this.panelMat.setVector2("uCells", new Vector2(26, 30));
    panel.material = this.panelMat;
    this.glow.addExcludedMesh(panel);
    const barMat = new StandardMaterial("bar", scene);
    barMat.disableLighting = true;
    barMat.emissiveColor = Color3.FromHexString("#7a54d8");
    barMat.alpha = 0.7;
    const bars = (x: number, y: number, n: number) => {
      for (let i = 0; i < n; i++) {
        const bar = MeshBuilder.CreatePlane("bar", { width: 0.32 - (i % 3) * 0.05, height: 0.035 }, scene);
        bar.position.set(x, y - i * 0.07, 1.29);
        bar.material = barMat;
      }
    };
    bars(-1.4, 2.35, 6);
    bars(1.4, 0.45, 7);
  }

  // ------------------------------------------------------------ particles
  private softTexture(): Texture {
    const t = new DynamicTexture("soft", { width: 64, height: 64 }, this.scene, false);
    const ctx = t.getContext() as CanvasRenderingContext2D;
    const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.3, "rgba(255,255,255,0.5)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 64, 64);
    t.hasAlpha = true;
    t.update();
    return t;
  }

  private buildParticles() {
    const scene = this.scene;
    const soft = this.softTexture();

    // Low purple haze drifting across the floor.
    const smoke = new ParticleSystem("smoke", 160, scene);
    smoke.particleTexture = soft;
    smoke.emitter = new Vector3(0, -0.7, 0);
    smoke.minEmitBox = new Vector3(-4.5, -0.3, -2.5);
    smoke.maxEmitBox = new Vector3(4.5, 0.5, 3);
    smoke.color1 = new Color4(0.45, 0.2, 0.9, 0.05);
    smoke.color2 = new Color4(0.3, 0.15, 0.8, 0.04);
    smoke.colorDead = new Color4(0.2, 0.1, 0.5, 0);
    smoke.minSize = 1.6;
    smoke.maxSize = 3.2;
    smoke.minLifeTime = 8;
    smoke.maxLifeTime = 14;
    smoke.emitRate = 14;
    smoke.blendMode = ParticleSystem.BLENDMODE_ADD;
    smoke.direction1 = new Vector3(-0.08, 0.01, -0.02);
    smoke.direction2 = new Vector3(0.08, 0.03, 0.02);
    smoke.minEmitPower = 0.5;
    smoke.maxEmitPower = 1;
    smoke.minAngularSpeed = -0.1;
    smoke.maxAngularSpeed = 0.1;
    smoke.preWarmCycles = 200;
    smoke.preWarmStepOffset = 5;
    smoke.start();

    // Sparkles rising from the emitter.
    const sp = (this.sparkles = new ParticleSystem("sparkles", 220, scene));
    sp.particleTexture = soft;
    sp.emitter = new Vector3(0, -0.8, 0);
    sp.createCylinderEmitter(0.9, 0.02, 0.1, 0);
    sp.color1 = new Color4(0.55, 0.9, 1, 0.9);
    sp.color2 = new Color4(0.4, 0.6, 1, 0.7);
    sp.colorDead = new Color4(0.2, 0.3, 1, 0);
    sp.minSize = 0.015;
    sp.maxSize = 0.045;
    sp.minLifeTime = 1.2;
    sp.maxLifeTime = 2.6;
    sp.emitRate = 40;
    sp.blendMode = ParticleSystem.BLENDMODE_ADD;
    sp.gravity = new Vector3(0, 0.5, 0);
    sp.minEmitPower = 0.1;
    sp.maxEmitPower = 0.4;
    sp.preWarmCycles = 60;
    sp.start();
  }

  // ---------------------------------------------------------------- floor
  private buildFloor() {
    const scene = this.scene;
    const floor = MeshBuilder.CreateGround("floor", { width: 14, height: 26 }, scene);
    floor.position.set(0, FLOOR_Y, 4);
    const mat = new StandardMaterial("floor", scene);
    mat.diffuseColor = Color3.FromHexString("#06070f");
    mat.specularColor = new Color3(0.15, 0.15, 0.3);
    this.mirror = new MirrorTexture("mirror", { ratio: 0.35 }, scene, true);
    this.mirror.mirrorPlane = new Plane(0, -1, 0, FLOOR_Y);
    this.mirror.level = 0.45;
    this.mirror.adaptiveBlurKernel = 24;
    this.mirror.renderList = scene.meshes.filter((m) => m !== floor && m.name !== "wall");
    mat.reflectionTexture = this.mirror;
    floor.material = mat;
    this.floorMat = mat;

    // Glowing floor seams.
    const lines: Vector3[][] = [];
    for (let x = -3; x <= 3; x += 1.5) lines.push([new Vector3(x, FLOOR_Y + 0.01, -4), new Vector3(x, FLOOR_Y + 0.01, 12)]);
    for (let z = -4; z <= 12; z += 1.5) lines.push([new Vector3(-3.6, FLOOR_Y + 0.01, z), new Vector3(3.6, FLOOR_Y + 0.01, z)]);
    const seams = MeshBuilder.CreateLineSystem("seams", { lines }, scene);
    seams.color = Color3.FromHexString("#3a3a8a");
    seams.alpha = 0.45;
  }

  // ----------------------------------------------------------------- post
  private buildPost() {
    const scene = this.scene;
    const cam = this.camera;

    const vls = (this.vls = new VolumetricLightScatteringPostProcess("godrays", 0.4, cam, this.lampMesh, 48, Texture.BILINEAR_SAMPLINGMODE, this.engine, false));
    vls.exposure = 0.22;
    vls.decay = 0.965;
    vls.weight = 0.55;
    vls.density = 0.9;

    const pipe = (this.pipe = new DefaultRenderingPipeline("pipe", true, scene, [cam]));
    pipe.samples = 1;
    pipe.fxaaEnabled = true;
    pipe.bloomEnabled = true;
    pipe.bloomThreshold = 0.55;
    pipe.bloomWeight = 0.35;
    pipe.bloomKernel = 48;
    pipe.bloomScale = 0.5;
    pipe.chromaticAberrationEnabled = true;
    pipe.chromaticAberration.aberrationAmount = 14;
    pipe.chromaticAberration.radialIntensity = 0.6;
    pipe.grainEnabled = true;
    pipe.grain.intensity = 6;
    pipe.grain.animated = true;
    pipe.imageProcessingEnabled = true;
    pipe.imageProcessing.toneMappingEnabled = true;
    pipe.imageProcessing.toneMappingType = ImageProcessingConfiguration.TONEMAPPING_ACES;
    pipe.imageProcessing.exposure = 1.1;
    pipe.imageProcessing.contrast = 1.25;
    pipe.imageProcessing.vignetteEnabled = true;
    pipe.imageProcessing.vignetteWeight = 2.2;
    pipe.imageProcessing.vignetteColor = new Color4(0.02, 0, 0.06, 0);

    this.finish = new PostProcess("finish", "holoFinish", ["uTime", "uGlitch", "uRes"], null, 1, cam);
    this.finish.onApply = (effect) => {
      effect.setFloat("uTime", this.time);
      effect.setFloat("uGlitch", this.glitch);
      effect.setFloat2("uRes", this.finish.width, this.finish.height);
    };
  }

  // ---------------------------------------------------------------- frame
  private update(dt: number) {
    this.time += dt;
    const t = this.time;
    const k = 1 - Math.exp(-dt * 4);
    Color3.LerpToRef(this.color, COLORS[this.state], k, this.color);
    this.intensity += (INTENSITY[this.state] - this.intensity) * k;
    this.glitch = Math.max(0, this.glitch - dt * 2.2);
    if (this.state === "offline" && Math.random() < dt * 0.6) this.glitch = 0.6;

    const drive = this.state === "listening" ? this.micLevel : this.state === "speaking" ? this.mouthLevel : 0;
    this.level += (drive - this.level) * (1 - Math.exp(-dt * 12));
    const jawTarget = this.state === "speaking" ? this.mouthLevel : 0;
    this.jaw += (jawTarget - this.jaw) * (1 - Math.exp(-dt * 18));

    this.head.update(this.color, this.intensity, this.jaw);

    this.streamMat.setFloat("uTime", t);
    this.streamMat.setColor3("uColor", this.color);
    this.streamMat.setFloat("uIntensity", this.intensity);
    this.streamMat.setFloat("uSpeed", this.state === "speaking" ? 2.6 : this.state === "thinking" ? 1.8 : 1);
    this.panelMat.setFloat("uTime", t);
    this.beamMat.setFloat("uTime", t);

    // Follow the pointer a little (breathing and the slow turn live in idleMotion.ts).
    const yaw = this.debugYaw ?? -this.pointer.x * 0.15;
    const ease = 1 - Math.exp(-dt * 2);
    this.bust.rotation.y += (yaw - this.bust.rotation.y) * ease;
    this.bust.rotation.x += (this.pointer.y * 0.05 - this.bust.rotation.x) * ease;

    if (this.eyeMat) {
      const e = 0.7 + this.level * 0.6 + (this.state === "speaking" ? 0.3 : 0);
      this.eyeMat.emissiveColor.set(0.78 * e, 0.96 * e, 1.0 * e);
      this.eyeMat.alpha = this.state === "offline" ? 0.25 : 0.9;
    }

    const spin = this.state === "thinking" ? 1.8 : this.state === "offline" ? 0.1 : 0.4;
    this.rings.forEach((ring, i) => {
      ring.rotation.y += dt * spin * (i % 2 === 0 ? 1 : -1.3) * (0.4 + i * 0.15);
      ring.scaling.setAll(1 + this.level * 0.12 * (1 + i * 0.3));
      ring.visibility = (0.45 + 0.45 * this.intensity) * (this.state === "offline" ? 0.4 : 1);
    });
    const em = 0.9 + this.level * 0.8 + Math.sin(t * 3) * 0.06;
    this.emitterMat.emissiveColor.set(em * this.intensity, em * this.intensity, em * this.intensity);
    this.sparkles.emitRate = this.state === "offline" ? 6 : 40 + this.level * 120;

    if (Math.floor(t * 4) !== Math.floor((t - dt) * 4)) this.drawLeds(t);

    // Subtle camera parallax.
    this.camera.position.x += (-this.pointer.x * 0.35 - this.camera.position.x) * (1 - Math.exp(-dt * 1.5));
    this.camera.position.y += (0.7 - this.pointer.y * 0.2 - this.camera.position.y) * (1 - Math.exp(-dt * 1.5));
    this.camera.setTarget(new Vector3(0, 0.45, 0));
  }
}
