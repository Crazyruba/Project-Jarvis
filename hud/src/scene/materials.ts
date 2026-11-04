import * as THREE from "three";

/** Shared uniforms so every hologram line reacts to state together. */
export const holoUniforms = {
  uTime: { value: 0 },
  uColor: { value: new THREE.Color(0x4fd8ff) },
  uIntensity: { value: 1 },
  uScanY: { value: -10 }, // world-space y of the thinking scan band
  uFlicker: { value: 0 },
};

/** Additive glowing lines; back-facing lines fade, a scan band brightens. */
export function hologramLineMaterial(boost = 1, backFade = 0.12): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: { ...holoUniforms, uBoost: { value: boost }, uBack: { value: backFade } },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */ `
      varying float vDepth;
      varying float vWorldY;
      void main() {
        vec4 world = modelMatrix * vec4(position, 1.0);
        vec4 view = viewMatrix * world;
        // Local z relative to the bust: front lines bright, back lines dim.
        vec3 local = (modelMatrix * vec4(position, 1.0)).xyz - (modelMatrix * vec4(0.0,0.0,0.0,1.0)).xyz;
        vec3 toCam = normalize(cameraPosition - (modelMatrix * vec4(0.0,0.0,0.0,1.0)).xyz);
        vDepth = dot(normalize(local + vec3(0.0001)), toCam);
        vWorldY = world.y;
        gl_Position = projectionMatrix * view;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor;
      uniform float uIntensity;
      uniform float uScanY;
      uniform float uTime;
      uniform float uFlicker;
      uniform float uBoost;
      uniform float uBack;
      varying float vDepth;
      varying float vWorldY;
      void main() {
        float facing = smoothstep(-0.6, 0.7, vDepth);
        float a = mix(uBack, 1.0, facing) * uBoost;
        float scan = exp(-pow((vWorldY - uScanY) * 7.0, 2.0)) * 1.6;
        float shimmer = 0.9 + 0.1 * sin(vWorldY * 40.0 - uTime * 6.0);
        float flick = 1.0 - uFlicker * step(0.5, fract(sin(floor(uTime * 24.0)) * 43758.5));
        vec3 col = uColor * (a * shimmer + scan) * uIntensity * flick;
        col += vec3(0.6, 0.9, 1.0) * scan * 0.4 * uIntensity;
        gl_FragColor = vec4(col, 1.0);
      }
    `,
  });
}

/** Vertical light streams rising from the platform into the chest. */
export function streamMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: { uTime: holoUniforms.uTime, uColor: holoUniforms.uColor, uSpeed: { value: 1 }, uIntensity: holoUniforms.uIntensity },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */ `
      attribute float aT;
      attribute float aSeed;
      varying float vT;
      varying float vSeed;
      void main() {
        vT = aT; vSeed = aSeed;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float uTime;
      uniform float uSpeed;
      uniform vec3 uColor;
      uniform float uIntensity;
      varying float vT;
      varying float vSeed;
      void main() {
        float pulse = fract(vT * 1.5 - uTime * 0.6 * uSpeed - vSeed);
        float head = smoothstep(0.0, 0.08, pulse) * (1.0 - smoothstep(0.08, 0.5, pulse));
        float base = (1.0 - vT) * 0.55;
        vec3 col = mix(uColor, vec3(0.85, 0.97, 1.0), head) * (base + head * 1.4) * uIntensity;
        gl_FragColor = vec4(col, 1.0);
      }
    `,
  });
}

/** Radial glow disc (platform emitter, floor pool). */
export function discMaterial(color: THREE.ColorRepresentation, strength = 1): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(color) }, uStrength: { value: strength } },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor;
      uniform float uStrength;
      varying vec2 vUv;
      void main() {
        float d = length(vUv - 0.5) * 2.0;
        float core = smoothstep(0.55, 0.0, d);
        float halo = smoothstep(1.0, 0.2, d) * 0.35;
        vec3 col = mix(uColor, vec3(1.0), core * 0.7) * (core + halo) * uStrength;
        gl_FragColor = vec4(col, 1.0);
      }
    `,
  });
}

/** Volumetric-looking light cone (the purple spotlight beam). */
export function beamMaterial(color: THREE.ColorRepresentation): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(color) }, uTime: holoUniforms.uTime },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor;
      uniform float uTime;
      varying vec2 vUv;
      void main() {
        // uv.y: 1 at the lamp, 0 at the far end. uv.x wraps around the cone.
        float along = pow(vUv.y, 1.6);
        float rays = 0.55 + 0.45 * sin(vUv.x * 80.0 + sin(vUv.x * 13.0) * 3.0);
        float drift = 0.85 + 0.15 * sin(uTime * 0.7 + vUv.y * 6.0);
        gl_FragColor = vec4(uColor * along * rays * drift * 0.14, 1.0);
      }
    `,
  });
}
