// GLSL for the hologram materials and post effects, registered in Babylon's ShadersStore.
import { Effect } from "@babylonjs/core/Materials/effect";

/** Hologram head: grid lines in model space, fresnel rim, scan band, moving jaw. */
Effect.ShadersStore["holoHeadVertexShader"] = /* glsl */ `
precision highp float;
attribute vec3 position;
attribute vec3 normal;
uniform mat4 world;
uniform mat4 viewProjection;
uniform float uJaw;
uniform vec4 uMouth;      // x: mouth line y, y: chin y, z: min face z, w: half mouth width
varying vec3 vLocal;
varying vec3 vWorld;
varying vec3 vNormal;
void main() {
  vec3 p = position;
  // Lower face drops below the mouth line while speaking.
  float below = (1.0 - smoothstep(uMouth.x - 0.25, uMouth.x, p.y)) * smoothstep(uMouth.y - 0.6, uMouth.y, p.y);
  float front = smoothstep(uMouth.z, uMouth.z + 0.6, p.z);
  float side = 1.0 - smoothstep(uMouth.w * 0.6, uMouth.w * 1.6, abs(p.x));
  float k = below * front * side;
  p.y -= uJaw * 0.32 * k;
  p.z -= uJaw * 0.08 * k;
  vLocal = p;
  vec4 w = world * vec4(p, 1.0);
  vWorld = w.xyz;
  vNormal = normalize(mat3(world) * normal);
  gl_Position = viewProjection * w;
}
`;

Effect.ShadersStore["holoHeadFragmentShader"] = /* glsl */ `
#extension GL_OES_standard_derivatives : enable
precision highp float;
uniform vec3 uColor;
uniform float uIntensity;
uniform float uTime;
uniform float uScanY;
uniform float uFlicker;
uniform vec3 cameraPosition;
uniform vec2 uGrid;       // x: rings per unit, y: meridians around
uniform float uChestY;    // below this the grid becomes triangular facets
varying vec3 vLocal;
varying vec3 vWorld;
varying vec3 vNormal;

float gridLine(float v, float width) {
  float d = abs(fract(v - 0.5) - 0.5);
  float fw = fwidth(v) * width;
  return 1.0 - smoothstep(0.0, fw, d);
}

void main() {
  vec3 N = normalize(vNormal);
  vec3 V = normalize(cameraPosition - vWorld);
  float facing = abs(dot(N, V));
  float rim = pow(1.0 - facing, 2.2);
  // Soft key light from the upper front so the face reads as convex, not as a hollow mask.
  float key = clamp(dot(N, normalize(vec3(-0.35, 0.55, -0.75))), 0.0, 1.0);

  float ang = atan(vLocal.x, vLocal.z) / 6.2831853 * uGrid.y;
  float ring = vLocal.y * uGrid.x;
  float head = gridLine(ring, 1.1) + gridLine(ang, 1.1);

  // Chest: diamond/triangle lattice like a low-poly wireframe.
  float tri = gridLine(ang * 0.5 + ring * 0.35, 1.3) + gridLine(ang * 0.5 - ring * 0.35, 1.3) + gridLine(ring * 0.35, 1.3);
  float chest = 1.0 - smoothstep(uChestY - 0.3, uChestY + 0.3, vLocal.y);
  float lines = clamp(mix(head, tri, chest), 0.0, 1.0);

  float scan = exp(-pow((vWorld.y - uScanY) * 6.0, 2.0));
  float shimmer = 0.88 + 0.12 * sin(vWorld.y * 38.0 - uTime * 5.0);
  float flick = 1.0 - uFlicker * step(0.55, fract(sin(floor(uTime * 22.0)) * 43758.5453));

  vec3 col = uColor * (lines * (0.35 + 0.95 * key) * shimmer + rim * 0.35 + key * 0.05 + 0.015) * uIntensity;
  col += vec3(0.7, 0.95, 1.0) * scan * (0.5 + lines) * uIntensity;
  gl_FragColor = vec4(col * flick, 1.0);
}
`;

/** Vertical light streams rising from the emitter. uv.x = seed, uv.y = height 0..1. */
Effect.ShadersStore["holoStreamVertexShader"] = /* glsl */ `
precision highp float;
attribute vec3 position;
attribute vec2 uv;
uniform mat4 worldViewProjection;
varying vec2 vUV;
void main() { vUV = uv; gl_Position = worldViewProjection * vec4(position, 1.0); }
`;

Effect.ShadersStore["holoStreamFragmentShader"] = /* glsl */ `
precision highp float;
uniform float uTime;
uniform float uSpeed;
uniform vec3 uColor;
uniform float uIntensity;
varying vec2 vUV;
void main() {
  float pulse = fract(vUV.y * 1.4 - uTime * 0.55 * uSpeed - vUV.x);
  float head = smoothstep(0.0, 0.06, pulse) * (1.0 - smoothstep(0.06, 0.45, pulse));
  float base = (1.0 - vUV.y) * 0.5;
  vec3 col = mix(uColor, vec3(0.9, 0.98, 1.0), head) * (base + head * 1.6) * uIntensity;
  gl_FragColor = vec4(col, 1.0);
}
`;

/** Glowing grid panel behind the head. */
Effect.ShadersStore["holoPanelVertexShader"] = Effect.ShadersStore["holoStreamVertexShader"];
Effect.ShadersStore["holoPanelFragmentShader"] = /* glsl */ `
#extension GL_OES_standard_derivatives : enable
precision highp float;
uniform vec3 uColor;
uniform float uTime;
uniform vec2 uCells;
varying vec2 vUV;
void main() {
  vec2 g = vUV * uCells;
  vec2 d = abs(fract(g - 0.5) - 0.5) / fwidth(g);
  float line = 1.0 - clamp(min(d.x, d.y), 0.0, 1.0);
  vec2 e = min(vUV, 1.0 - vUV);
  float frame = 1.0 - smoothstep(0.0, 0.006, min(e.x, e.y));
  float sweep = exp(-pow((vUV.y - fract(uTime * 0.12)) * 18.0, 2.0)) * 0.6;
  float fade = 0.55 + 0.45 * smoothstep(0.0, 0.5, vUV.y);
  vec3 col = uColor * (line * 0.12 * fade + frame * 0.5 + sweep * line * 0.6);
  gl_FragColor = vec4(col, 1.0);
}
`;

/** Spotlight cone: brighter near the lamp, ray streaks around the cone. */
Effect.ShadersStore["holoBeamVertexShader"] = Effect.ShadersStore["holoStreamVertexShader"];
Effect.ShadersStore["holoBeamFragmentShader"] = /* glsl */ `
precision highp float;
uniform vec3 uColor;
uniform float uTime;
varying vec2 vUV;
void main() {
  // uv.y runs from the wide far end (0) to the lamp (1).
  float along = pow(vUV.y, 1.8);
  float rays = 0.5 + 0.5 * sin(vUV.x * 90.0 + sin(vUV.x * 17.0) * 3.0);
  float drift = 0.85 + 0.15 * sin(uTime * 0.7 + vUV.y * 6.0);
  gl_FragColor = vec4(uColor * along * rays * drift * 0.16, 1.0);
}
`;

/** Screen-space finish: scanlines, a soft horizontal glitch and a cyan tint. */
Effect.ShadersStore["holoFinishFragmentShader"] = /* glsl */ `
precision highp float;
varying vec2 vUV;
uniform sampler2D textureSampler;
uniform float uTime;
uniform float uGlitch;
uniform vec2 uRes;
float hash(float n) { return fract(sin(n) * 43758.5453); }
void main() {
  vec2 uv = vUV;
  // Glitch: a few horizontal bands slide sideways for a moment.
  float band = floor(uv.y * 24.0 + floor(uTime * 12.0));
  float g = step(0.86, hash(band)) * uGlitch;
  uv.x += (hash(band + 3.1) - 0.5) * 0.04 * g;
  vec3 c = texture2D(textureSampler, uv).rgb;
  // Split channels slightly on glitching bands.
  c.r = mix(c.r, texture2D(textureSampler, uv + vec2(0.004 * g, 0.0)).r, g);
  c.b = mix(c.b, texture2D(textureSampler, uv - vec2(0.004 * g, 0.0)).b, g);
  // Fine scanlines.
  float scan = 0.965 + 0.035 * sin(uv.y * uRes.y * 1.6);
  c *= scan;
  gl_FragColor = vec4(c, 1.0);
}
`;
