// Procedural holographic wireframe bust: a latitude/longitude grid head,
// a grid neck and low-poly triangulated shoulders, all drawn as glowing lines.
import * as THREE from "three";
import { hologramLineMaterial } from "./materials";

const TAU = Math.PI * 2;

/** Piecewise-linear lookup over (y, value) knots sorted by descending y. */
function profile(y: number, knots: [number, number][]): number {
  if (y >= knots[0][0]) return knots[0][1];
  for (let i = 1; i < knots.length; i++) {
    const [y1, v1] = knots[i];
    const [y0, v0] = knots[i - 1];
    if (y >= y1) {
      const t = THREE.MathUtils.smoothstep((y - y1) / (y0 - y1), 0, 1);
      return v1 + (v0 - v1) * t;
    }
  }
  return knots[knots.length - 1][1];
}

// Lower-face cross sections (y below the eye line): width, depth, forward offset.
const WIDTH: [number, number][] = [[0, 0.8], [-0.3, 0.76], [-0.62, 0.62], [-0.88, 0.42], [-1.02, 0.26], [-1.1, 0]];
const DEPTH: [number, number][] = [[0, 0.95], [-0.3, 0.9], [-0.62, 0.74], [-0.88, 0.46], [-1.02, 0.22], [-1.1, 0]];
const CENTER: [number, number][] = [[0, -0.03], [-0.62, 0.03], [-1.1, 0.14]];

/** Gaussian bump on the face, in (theta, y) space. */
function feature(theta: number, y: number, t0: number, y0: number, wt: number, wy: number) {
  let dt = theta - t0;
  dt = Math.atan2(Math.sin(dt), Math.cos(dt));
  return Math.exp(-(dt * dt) / (wt * wt) - ((y - y0) * (y - y0)) / (wy * wy));
}

/**
 * Head surface built from horizontal cross-sections. theta = 0 faces +z
 * (the camera), phi runs from the crown (0) to the chin (PI).
 * `jaw` (0..1) opens the mouth by pulling the lower face down.
 */
export function headPoint(theta: number, phi: number, jaw: number, out: THREE.Vector3) {
  let y = Math.cos(phi);
  if (y < 0) y *= 1.1;
  let w: number;
  let d: number;
  let zc: number;
  if (y >= 0) {
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    w = 0.8 * r;
    d = 0.95 * r;
    zc = -0.03;
  } else {
    w = profile(y, WIDTH);
    d = profile(y, DEPTH);
    zc = profile(y, CENTER);
  }
  // The back of the skull is fuller than the face.
  const back = Math.max(0, -Math.cos(theta));
  if (y > -0.4) d *= 1 + 0.06 * back;

  const front = Math.pow(Math.max(0, Math.cos(theta)), 1.5);
  let bump = 0;
  bump += 0.05 * feature(theta, y, 0.36, 0.13, 0.2, 0.07); // brow ridge
  bump += 0.05 * feature(theta, y, -0.36, 0.13, 0.2, 0.07);
  bump -= 0.1 * feature(theta, y, 0.34, -0.02, 0.16, 0.1); // eye sockets
  bump -= 0.1 * feature(theta, y, -0.34, -0.02, 0.16, 0.1);
  bump += 0.035 * feature(theta, y, 0.34, -0.03, 0.08, 0.05); // eyeballs
  bump += 0.035 * feature(theta, y, -0.34, -0.03, 0.08, 0.05);
  bump += 0.12 * feature(theta, y, 0, -0.18, 0.09, 0.2); // nose bridge
  bump += 0.12 * feature(theta, y, 0, -0.43, 0.13, 0.08); // nose tip
  bump += 0.04 * feature(theta, y, 0.6, -0.32, 0.22, 0.14); // cheekbones
  bump += 0.04 * feature(theta, y, -0.6, -0.32, 0.22, 0.14);
  bump += 0.05 * feature(theta, y, 0, -0.62, 0.28, 0.05); // upper lip
  bump += 0.045 * feature(theta, y, 0, -0.75, 0.24, 0.05); // lower lip
  bump -= 0.025 * feature(theta, y, 0, -0.685, 0.3, 0.02); // mouth line
  bump += 0.05 * feature(theta, y, 0, -0.95, 0.3, 0.09); // chin
  bump *= front;

  let x = Math.sin(theta) * (w + bump * 0.4);
  let z = zc + Math.cos(theta) * (d + bump);

  // Mouth: below the lip line the face drops when the jaw opens.
  if (y < -0.68) {
    const k = THREE.MathUtils.smoothstep(-0.68 - y, 0, 0.06) * front;
    y -= jaw * 0.12 * k;
    z -= jaw * 0.03 * k;
    x *= 1 - jaw * 0.04 * k;
  }

  out.set(x, y, z);
  return out;
}

function gridLines(
  rows: number,
  cols: number,
  wrapCols: boolean,
): { index: number[]; count: number } {
  const index: number[] = [];
  for (let r = 0; r <= rows; r++) {
    for (let c = 0; c <= cols; c++) {
      const i = r * (cols + 1) + c;
      if (c < cols) index.push(i, i + 1);
      else if (wrapCols) index.push(i, r * (cols + 1));
      if (r < rows) index.push(i, i + cols + 1);
    }
  }
  return { index, count: (rows + 1) * (cols + 1) };
}

export class HologramBust {
  readonly group = new THREE.Group();
  readonly material = hologramLineMaterial(0.75);
  private featureMaterial = hologramLineMaterial(1.6, 0);
  private headGeo: THREE.BufferGeometry;
  private headRows = 32;
  private headCols = 48;
  private phiMax = Math.PI;
  private lastJaw = -1;
  private featureGeo = new THREE.BufferGeometry();
  private featureParams: number[] = [];
  private tmp = new THREE.Vector3();
  readonly eyes: THREE.Points;

  constructor() {
    // --- Head -----------------------------------------------------------
    const { index, count } = gridLines(this.headRows, this.headCols, false);
    this.headGeo = new THREE.BufferGeometry();
    this.headGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    this.headGeo.setIndex(index);
    this.updateHead(0);
    const head = new THREE.Group();
    head.add(new THREE.LineSegments(this.headGeo, this.material));
    this.buildFeatures();
    this.updateHead(0);
    head.add(new THREE.LineSegments(this.featureGeo, this.featureMaterial));
    head.position.y = 0.42;
    head.scale.setScalar(0.8);
    this.group.add(head);

    // Ears: small vertical ellipses on the sides.
    for (const side of [-1, 1]) {
      const ear = new THREE.LineSegments(this.earGeometry(), this.material);
      ear.position.set(side * 0.79, -0.12, -0.08);
      ear.rotation.y = side * -Math.PI / 2.4;
      head.add(ear);
    }

    // Glowing eyes.
    const eyeGeo = new THREE.BufferGeometry();
    const e = new THREE.Vector3();
    const pts: number[] = [];
    for (const t of [-0.34, 0.34]) {
      headPoint(t, Math.acos(-0.03 / 1.1), 0, e);
      pts.push(e.x, e.y, e.z + 0.03);
    }
    eyeGeo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    this.eyes = new THREE.Points(
      eyeGeo,
      new THREE.PointsMaterial({
        size: 0.22,
        map: glowTexture(),
        color: 0xbff4ff,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    head.add(this.eyes);

    // --- Neck -----------------------------------------------------------
    this.group.add(new THREE.LineSegments(this.neckGeometry(), this.material));

    // --- Shoulders / chest (low-poly triangles) ---------------------------
    this.group.add(new THREE.LineSegments(this.shoulderGeometry(), this.material));
  }

  /** Recompute head vertices when the jaw moves. */
  updateHead(jaw: number) {
    if (Math.abs(jaw - this.lastJaw) < 0.01) return;
    this.lastJaw = jaw;
    const pos = this.headGeo.getAttribute("position") as THREE.BufferAttribute;
    let i = 0;
    for (let r = 0; r <= this.headRows; r++) {
      const phi = (r / this.headRows) * this.phiMax + 0.0001;
      for (let c = 0; c <= this.headCols; c++) {
        const theta = (c / this.headCols) * TAU - Math.PI;
        headPoint(theta, phi, jaw, this.tmp);
        pos.setXYZ(i++, this.tmp.x, this.tmp.y, this.tmp.z);
      }
    }
    pos.needsUpdate = true;
    this.headGeo.computeBoundingSphere();

    const fp = this.featureGeo.getAttribute("position") as THREE.BufferAttribute | undefined;
    if (fp) {
      for (let k = 0; k < this.featureParams.length / 2; k++) {
        headPoint(this.featureParams[k * 2], this.featureParams[k * 2 + 1], jaw, this.tmp);
        // Lift strokes slightly off the surface so they read as contours.
        this.tmp.x *= 1.012;
        this.tmp.z = this.tmp.z * 1.012 + 0.004;
        fp.setXYZ(k, this.tmp.x, this.tmp.y, this.tmp.z);
      }
      fp.needsUpdate = true;
    }
  }

  /** Contour strokes (brows, eyes, nose, lips) that make the face readable. */
  private buildFeatures() {
    const phiOf = (y: number) => Math.acos(THREE.MathUtils.clamp(y >= 0 ? y : y / 1.1, -1, 1));
    const P = this.featureParams;
    const stroke = (fn: (t: number) => [number, number], n = 14) => {
      for (let i = 0; i < n; i++) {
        const [t0, y0] = fn(i / n);
        const [t1, y1] = fn((i + 1) / n);
        P.push(t0, phiOf(y0), t1, phiOf(y1));
      }
    };
    for (const side of [-1, 1]) {
      // Brow arc
      stroke((t) => [side * (0.14 + t * 0.42), 0.1 + Math.sin(t * Math.PI) * 0.035]);
      // Eye: almond shape (upper and lower lid)
      stroke((t) => [side * (0.22 + t * 0.24), -0.03 + Math.sin(t * Math.PI) * 0.035]);
      stroke((t) => [side * (0.22 + t * 0.24), -0.03 - Math.sin(t * Math.PI) * 0.022]);
      // Nose side + nostril wing
      stroke((t) => [side * (0.07 + t * 0.05), -0.08 - t * 0.34], 8);
      stroke((t) => [side * (0.02 + Math.sin(t * Math.PI * 0.9) * 0.13), -0.46 + Math.sin(t * Math.PI) * 0.03], 8);
      // Cheek / nasolabial fold
      stroke((t) => [side * (0.2 + t * 0.1), -0.44 - t * 0.28], 8);
    }
    // Upper lip (cupid's bow), mouth line, lower lip
    stroke((t) => [(t - 0.5) * 0.56, -0.645 + Math.abs(Math.sin((t - 0.5) * Math.PI * 2)) * 0.012], 18);
    stroke((t) => [(t - 0.5) * 0.52, -0.685 - Math.sin(t * Math.PI) * 0.008], 18);
    stroke((t) => [(t - 0.5) * 0.4, -0.73 - Math.sin(t * Math.PI) * 0.03], 14);
    // Chin crease
    stroke((t) => [(t - 0.5) * 0.3, -0.86 - Math.sin(t * Math.PI) * 0.02], 10);
    this.featureGeo.setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array((P.length / 2) * 3), 3),
    );
    this.lastJaw = -1;
  }

  private earGeometry() {
    const pts: number[] = [];
    const n = 16;
    for (let ring = 0; ring < 3; ring++) {
      const s = 1 - ring * 0.3;
      for (let i = 0; i < n; i++) {
        const a0 = (i / n) * TAU;
        const a1 = ((i + 1) / n) * TAU;
        pts.push(Math.cos(a0) * 0.08 * s, Math.sin(a0) * 0.17 * s, 0);
        pts.push(Math.cos(a1) * 0.08 * s, Math.sin(a1) * 0.17 * s, 0);
      }
    }
    return new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  }

  private neckGeometry() {
    const rows = 7;
    const cols = 28;
    const { index, count } = gridLines(rows, cols, true);
    const pos = new Float32Array(count * 3);
    let i = 0;
    for (let r = 0; r <= rows; r++) {
      const t = r / rows;
      const y = -0.2 - t * 0.55;
      const rad = 0.31 + t * t * 0.24;
      for (let c = 0; c <= cols; c++) {
        const a = (c / cols) * TAU;
        pos[i++] = Math.sin(a) * rad;
        pos[i++] = y;
        pos[i++] = Math.cos(a) * rad * 0.9 - 0.02;
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setIndex(index);
    return g;
  }

  private shoulderGeometry() {
    // A curved, faceted torso shell: grid with alternating diagonals and jitter.
    const rows = 5;
    const cols = 14;
    const rand = mulberry32(7);
    const verts: THREE.Vector3[] = [];
    for (let r = 0; r <= rows; r++) {
      const t = r / rows; // 0 at collar, 1 at bottom
      for (let c = 0; c <= cols; c++) {
        const u = c / cols; // 0..1 across
        const a = (u - 0.5) * Math.PI * 1.05; // around the body
        const width = 0.42 + 1.1 * Math.sqrt(Math.min(1, t * 1.7));
        const x = Math.sin(a) * width;
        const edge = Math.abs(u - 0.5) * 2;
        const y = -0.6 - t * 0.95 - Math.pow(edge, 1.6) * 0.32 * (1 - t);
        const z = Math.cos(a) * (0.45 + 0.25 * t) - 0.1;
        const jitter = r === 0 || r === rows || c === 0 || c === cols ? 0.02 : 0.07;
        verts.push(
          new THREE.Vector3(
            x + (rand() - 0.5) * jitter,
            y + (rand() - 0.5) * jitter,
            z + (rand() - 0.5) * jitter,
          ),
        );
      }
    }
    const idx = (r: number, c: number) => r * (cols + 1) + c;
    const lines: number[] = [];
    const push = (a: THREE.Vector3, b: THREE.Vector3) => lines.push(a.x, a.y, a.z, b.x, b.y, b.z);
    for (let r = 0; r <= rows; r++) {
      for (let c = 0; c <= cols; c++) {
        const v = verts[idx(r, c)];
        if (c < cols) push(v, verts[idx(r, c + 1)]);
        if (r < rows) push(v, verts[idx(r + 1, c)]);
        if (r < rows && c < cols) {
          if ((r + c) % 2 === 0) push(v, verts[idx(r + 1, c + 1)]);
          else push(verts[idx(r, c + 1)], verts[idx(r + 1, c)]);
        }
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
    return g;
  }
}

export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

let glowTex: THREE.Texture | null = null;
/** Soft radial sprite used for eyes, particles and smoke. */
export function glowTexture(): THREE.Texture {
  if (glowTex) return glowTex;
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, "rgba(255,255,255,1)");
  grd.addColorStop(0.25, "rgba(255,255,255,0.55)");
  grd.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grd;
  g.fillRect(0, 0, 64, 64);
  glowTex = new THREE.CanvasTexture(c);
  return glowTex;
}
