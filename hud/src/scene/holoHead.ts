// Hologram look for the head mesh: a GridMaterial raster plus a fresnel rim shell, and a
// CPU-side jaw that drops the lower face while Jarvis speaks.
import type { Scene } from "@babylonjs/core/scene";
import { Constants } from "@babylonjs/core/Engines/constants";
import { Color3 } from "@babylonjs/core/Maths/math.color";
import { VertexBuffer } from "@babylonjs/core/Buffers/buffer";
import type { Mesh } from "@babylonjs/core/Meshes/mesh";
import { StandardMaterial } from "@babylonjs/core/Materials/standardMaterial";
import { FresnelParameters } from "@babylonjs/core/Materials/fresnelParameters";
import type { GlowLayer } from "@babylonjs/core/Layers/glowLayer";
import { GridMaterial } from "@babylonjs/materials/grid/gridMaterial";

/** Model-space region that moves with the jaw (see HEAD in hologram.ts). */
export interface MouthRegion {
  mouthY: number; // lips line: everything below it opens
  chinY: number; // below this the effect fades out toward the neck
  faceZ: number; // only the front of the face moves
  halfWidth: number; // half the mouth width
}

export interface HoloHeadOptions {
  /** Grid cell size in model units (the scan is 8 units tall). */
  gridRatio?: number;
  /** Every n-th line is a brighter major line. */
  majorUnitFrequency?: number;
  mouth?: MouthRegion;
}

const LINE = Color3.FromHexString("#00f0ff");
const BODY = Color3.FromHexString("#060a2e");

export class HoloHead {
  readonly grid: GridMaterial;
  readonly rim: StandardMaterial;
  private shells: Mesh[] = [];
  private jaws: JawDeformer[] = [];
  private lineColor = LINE.clone();

  constructor(scene: Scene, private glow: GlowLayer, private opts: HoloHeadOptions = {}) {
    const grid = (this.grid = new GridMaterial("holoGrid", scene));
    grid.mainColor = BODY.clone();
    grid.lineColor = LINE.clone();
    grid.gridRatio = opts.gridRatio ?? 0.12;
    grid.majorUnitFrequency = opts.majorUnitFrequency ?? 6;
    grid.minorUnitVisibility = 0.5;
    grid.opacity = 0.62; // see-through body, lines stay bright
    grid.antialias = true;
    grid.backFaceCulling = true;
    // Only the nearest surface draws, so the scan's mouth cavity and inner folds stay hidden.
    grid.needDepthPrePass = true;
    grid.fogEnabled = false;

    // Rim shell: same geometry, additive, bright at grazing angles and clear in the middle.
    const rim = (this.rim = new StandardMaterial("holoRim", scene));
    rim.disableLighting = true;
    rim.emissiveColor = LINE.clone();
    rim.diffuseColor = Color3.Black();
    rim.specularColor = Color3.Black();
    rim.alphaMode = Constants.ALPHA_ADD;
    rim.disableDepthWrite = true;
    rim.backFaceCulling = true;
    rim.fogEnabled = false;
    // Same geometry as the grid: pull it slightly forward so the two never z-fight.
    rim.zOffset = -2;
    // Babylon's term is pow(bias + |N·V|, power): 1 where the face looks at the camera, toward 0
    // at the silhouette. leftColor is used at the edges, rightColor in the middle.
    rim.emissiveFresnelParameters = fresnel(Color3.White(), LINE.scale(0.12), 1, 0.2);
    rim.opacityFresnelParameters = fresnel(Color3.White(), Color3.Black(), 1.5, 0.15);
  }

  /** Apply the hologram look to the loaded head meshes. */
  attach(meshes: Mesh[]) {
    for (const mesh of meshes) {
      mesh.material = this.grid;
      mesh.alphaIndex = 10;
      // The grid lines feed the glow layer with their own colors.
      this.glow.referenceMeshToUseItsOwnMaterial(mesh);

      const shell = mesh.clone(`${mesh.name}-rim`, mesh.parent);
      shell.material = this.rim;
      shell.alphaIndex = 11; // after the grid, so its depth pre-pass hides inner geometry
      this.glow.addExcludedMesh(shell);
      this.shells.push(shell);

      if (this.opts.mouth) this.jaws.push(new JawDeformer(mesh, this.opts.mouth));
    }
  }

  /** Per-frame look: state color, brightness (1 = idle) and jaw opening (0..1). */
  update(color: Color3, intensity: number, jaw: number) {
    // Blend the state color toward neon cyan so the raster always reads as cyan.
    Color3.LerpToRef(LINE, color, 0.55, this.lineColor);
    this.lineColor.scaleToRef(0.65 + 0.55 * intensity, this.grid.lineColor);
    BODY.scaleToRef(0.6 + 0.4 * intensity, this.grid.mainColor);
    this.lineColor.scaleToRef(0.9 * intensity, this.rim.emissiveColor);
    this.rim.emissiveFresnelParameters!.leftColor.copyFrom(Color3.White().scale(Math.min(1, 0.7 + 0.3 * intensity)));
    for (const j of this.jaws) j.set(jaw);
  }

  dispose() {
    this.shells.forEach((s) => s.dispose());
    this.grid.dispose();
    this.rim.dispose();
  }
}

function fresnel(edge: Color3, center: Color3, power: number, bias: number): FresnelParameters {
  const f = new FresnelParameters();
  f.leftColor = edge;
  f.rightColor = center;
  f.power = power;
  f.bias = bias;
  return f;
}

/**
 * Moves the lower face down on the CPU. Only the vertices around the mouth are touched, and
 * only when the opening changes, so it costs a few hundred float writes per frame at most.
 */
class JawDeformer {
  private base: Float32Array;
  private work: Float32Array;
  private idx: Uint32Array;
  private weight: Float32Array;
  private current = 0;

  constructor(private mesh: Mesh, m: MouthRegion) {
    const pos = mesh.getVerticesData(VertexBuffer.PositionKind) ?? [];
    this.base = Float32Array.from(pos);
    this.work = Float32Array.from(pos);
    const idx: number[] = [];
    const w: number[] = [];
    for (let i = 0; i < this.base.length; i += 3) {
      const x = this.base[i], y = this.base[i + 1], z = this.base[i + 2];
      const below = (1 - smooth(m.mouthY - 0.25, m.mouthY, y)) * smooth(m.chinY - 0.6, m.chinY, y);
      const front = smooth(m.faceZ, m.faceZ + 0.6, z);
      const side = 1 - smooth(m.halfWidth * 0.6, m.halfWidth * 1.6, Math.abs(x));
      const k = below * front * side;
      if (k > 0.001) {
        idx.push(i);
        w.push(k);
      }
    }
    this.idx = Uint32Array.from(idx);
    this.weight = Float32Array.from(w);
    if (idx.length) mesh.markVerticesDataAsUpdatable(VertexBuffer.PositionKind, true);
  }

  set(jaw: number) {
    if (!this.idx.length || Math.abs(jaw - this.current) < 0.004) return;
    this.current = jaw;
    const { base, work, idx, weight } = this;
    for (let n = 0; n < idx.length; n++) {
      const i = idx[n];
      const k = weight[n] * jaw;
      work[i + 1] = base[i + 1] - 0.32 * k;
      work[i + 2] = base[i + 2] - 0.08 * k;
    }
    this.mesh.updateVerticesData(VertexBuffer.PositionKind, work, false, false);
  }
}

function smooth(e0: number, e1: number, x: number): number {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
}
