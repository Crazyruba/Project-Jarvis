/**
 * Het hologram.
 *
 * Alles is procedureel: er zijn geen modelbestanden die kunnen ontbreken.
 * Bewust géén EffectComposer/bloom — dat is zwaar op de Intel UHD 620 van een
 * T580. De glow komt van extra additieve lagen, wat goedkoper is en in een
 * wireframe zelfs overtuigender oogt.
 *
 * Naar buiten: window.holo = { setState, setLevel, setLite, ready }
 */

import * as THREE from "three";

const CYAN = 0x66e8ff;
const DEEP = 0x0a2a4a;
const AMBER = 0xffb470;

const canvas = document.getElementById("scene");

let renderer, scene, camera;
let head, headGlow, shoulders, neck, beams, platform, ring, thinkRing;
let racks = [], shafts = [];
let clock;

let state = "idle";
let level = 0;        // 0..1, audio-amplitude
let smoothLevel = 0;
let lite = false;
let running = true;
let baseHeadPositions = null;

/* -- opbouw ------------------------------------------------------------- */

// Silhouet van een hoofd, als breedte en diepte per hoogte (y van kin -1 tot
// kruin +1). Een bol vermenigvuldigen met een profiel levert punten op aan de
// polen; deze tabel geeft de straal rechtstreeks, dus de kruin blijft rond.
const HEAD_WIDTH = [
  [ 1.00, 0.16], [ 0.92, 0.46], [ 0.82, 0.70], [ 0.70, 0.85], [ 0.50, 0.95],
  [ 0.28, 1.00], [ 0.05, 0.99], [-0.18, 0.94], [-0.40, 0.85], [-0.60, 0.72],
  [-0.78, 0.56], [-0.92, 0.38], [-1.00, 0.20],
];
const HEAD_DEPTH = [
  [ 1.00, 0.18], [ 0.92, 0.52], [ 0.82, 0.78], [ 0.70, 0.92], [ 0.50, 1.02],
  [ 0.28, 1.05], [ 0.05, 1.04], [-0.18, 1.00], [-0.40, 0.92], [-0.60, 0.80],
  [-0.78, 0.64], [-0.92, 0.46], [-1.00, 0.26],
];

function profile(table, y) {
  if (y >= table[0][0]) return table[0][1];
  for (let i = 1; i < table.length; i++) {
    if (y >= table[i][0]) {
      const [y0, v0] = table[i - 1];
      const [y1, v1] = table[i];
      const k = (y - y1) / (y0 - y1);
      return v1 + (v0 - v1) * k;
    }
  }
  return table[table.length - 1][1];
}


/** Torus als schone lengte-/breedtelijnen, in dezelfde stijl als het hoofd. */
function makeRingGeometry(majorR, minorR, majorSeg, minorSeg, flatten) {
  const grid = [];
  for (let i = 0; i < majorSeg; i++) {
    const a = (i / majorSeg) * Math.PI * 2;
    const ring = [];
    for (let j = 0; j < minorSeg; j++) {
      const b = (j / minorSeg) * Math.PI * 2;
      const r = majorR + minorR * Math.cos(b);
      ring.push(new THREE.Vector3(
        Math.cos(a) * r,
        minorR * Math.sin(b) * flatten,
        Math.sin(a) * r,
      ));
    }
    grid.push(ring);
  }

  const verts = [];
  const cols3 = [];
  const base = new THREE.Color(CYAN);
  const shade = (v) => {
    const t = Math.min(1, Math.max(0, (v.z / (majorR + minorR) + 1) / 2));
    const k = 0.16 + 0.84 * Math.pow(t, 1.7);
    cols3.push(base.r * k, base.g * k, base.b * k);
  };
  const push = (x, y) => {
    verts.push(x.x, x.y, x.z, y.x, y.y, y.z);
    shade(x); shade(y);
  };

  for (let i = 0; i < majorSeg; i++) {
    for (let j = 0; j < minorSeg; j++) {
      push(grid[i][j], grid[i][(j + 1) % minorSeg]);            // dwarsdoorsnede
      push(grid[i][j], grid[(i + 1) % majorSeg][j]);            // rondom
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(verts), 3));
  geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(cols3), 3));
  return geo;
}

/**
 * Het hoofd als lengte- en breedtelijnen, niet als driehoeks-wireframe:
 * schoner beeld, minder lijnen om te tekenen, en volledige controle over de
 * vorm. Gezichtskenmerken worden op het genormaliseerde profiel aangebracht
 * en pas daarna naar de juiste verhoudingen geschaald.
 */
function makeHeadGeometry(detail) {
  const rows = detail ? 24 : 16;   // breedtecirkels van kruin tot kin
  const cols = detail ? 30 : 20;   // lengtelijnen rondom

  const grid = [];
  for (let r = 0; r <= rows; r++) {
    const y = 1 - (r / rows) * 2;              // +1 kruin .. -1 kin
    const hw = profile(HEAD_WIDTH, y);
    const hd = profile(HEAD_DEPTH, y);
    const ring = [];

    for (let c = 0; c < cols; c++) {
      const theta = (c / cols) * Math.PI * 2;
      let x = Math.sin(theta) * hw;
      let z = Math.cos(theta) * hd;           // +z is het gezicht

      // Gezicht platter, achterhoofd voller.
      z *= z > 0 ? 0.88 : 1.10;

      if (z > 0) {
        const ax = Math.abs(x);
        // Wenkbrauwboog.
        if (y > 0.26 && y < 0.50) z += 0.07 * Math.cos(Math.min(ax * 3, 1.4));
        // Oogkassen liggen dieper.
        if (y > 0.02 && y < 0.30 && ax > 0.16 && ax < 0.46) z -= 0.085;
        // Neusrug over de middenlijn.
        if (ax < 0.16 && y > -0.28 && y < 0.38) {
          const prof = Math.sin(((y + 0.28) / 0.66) * Math.PI);
          z += 0.24 * prof * (1 - ax / 0.16);
        }
        // Mondlijn.
        if (ax < 0.28 && y > -0.54 && y < -0.36) z -= 0.035;
        // Kin steekt iets vooruit.
        if (y < -0.58) z += 0.07 * Math.min(1, (-y - 0.58) / 0.3);
      }

      // Eindverhoudingen, ongeveer breedte 1 : hoogte 1,35 : diepte 1,15.
      ring.push(new THREE.Vector3(x * 0.78, y * 1.05, z * 0.86));
    }
    grid.push(ring);
  }

  const verts = [];
  const cols3 = [];
  const base = new THREE.Color(CYAN);

  // Zonder diepteverschil blijft een draadmodel een doorzichtige ballon.
  // Lijnen aan de voorkant krijgen daarom meer helderheid dan die erachter.
  const shade = (v) => {
    const t = Math.min(1, Math.max(0, (v.z / 0.78 + 1) / 2));
    const k = 0.14 + 0.86 * Math.pow(t, 1.7);
    cols3.push(base.r * k, base.g * k, base.b * k);
  };
  const push = (a, b) => {
    verts.push(a.x, a.y, a.z, b.x, b.y, b.z);
    shade(a); shade(b);
  };

  for (let r = 0; r <= rows; r++) {
    for (let c = 0; c < cols; c++) push(grid[r][c], grid[r][(c + 1) % cols]);
  }
  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) push(grid[r][c], grid[r + 1][c]);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position",
    new THREE.BufferAttribute(new Float32Array(verts), 3));
  geo.setAttribute("color",
    new THREE.BufferAttribute(new Float32Array(cols3), 3));
  return geo;
}

function buildBust() {
  const group = new THREE.Group();
  group.position.y = 1.62;
  group.scale.setScalar(0.92);

  const geo = makeHeadGeometry(!lite);
  baseHeadPositions = geo.attributes.position.array.slice();

  head = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({
    vertexColors: true, transparent: true, opacity: 0.85,
  }));
  group.add(head);

  // Nepglow: dezelfde vorm, iets groter, additief.
  headGlow = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({
    vertexColors: true, transparent: true, opacity: 0.20,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }));
  headGlow.scale.setScalar(1.05);
  group.add(headGlow);

  // Nek, zichtbaar tussen hoofd en schouders.
  neck = new THREE.LineSegments(
    new THREE.EdgesGeometry(
      new THREE.CylinderGeometry(0.26, 0.40, 0.62, lite ? 10 : 18, 1, true), 1),
    new THREE.LineBasicMaterial({ color: CYAN, transparent: true, opacity: 0.3 })
  );
  neck.position.y = -1.18;
  group.add(neck);

  // Schouders: afgeplatte ring, zoals in het ontwerp.
  shoulders = new THREE.LineSegments(
    makeRingGeometry(1.02, 0.30, lite ? 26 : 44, lite ? 7 : 11, 0.42),
    new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.6 })
  );
  shoulders.position.y = -1.56;
  group.add(shoulders);

  scene.add(group);
  return group;
}

function buildBeams() {
  beams = new THREE.Group();
  beams.position.y = 0.05;
  const count = lite ? 4 : 7;
  const mat = new THREE.MeshBasicMaterial({
    color: CYAN, transparent: true, opacity: 0.10,
    blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
  });

  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2;
    const r = 0.34 + (i % 2) * 0.22;
    const beam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.04, 0.11, 1.15, 6, 1, true), mat
    );
    beam.position.set(Math.cos(a) * r, 0, Math.sin(a) * r);
    beams.add(beam);
  }
  scene.add(beams);
}

function buildPlatform() {
  platform = new THREE.Group();
  platform.position.y = -0.56;

  // Gloeiende schijf waar de projectie op landt.
  const disc = new THREE.Mesh(
    new THREE.CircleGeometry(0.92, lite ? 24 : 48),
    new THREE.MeshBasicMaterial({
      color: CYAN, transparent: true, opacity: 0.20,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })
  );
  disc.rotation.x = -Math.PI / 2;
  platform.add(disc);

  ring = new THREE.Mesh(
    new THREE.RingGeometry(1.12, 1.20, lite ? 32 : 64),
    new THREE.MeshBasicMaterial({
      color: CYAN, transparent: true, opacity: 0.55,
      blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
    })
  );
  ring.rotation.x = -Math.PI / 2;
  platform.add(ring);

  const outer = new THREE.Mesh(
    new THREE.RingGeometry(1.62, 1.65, lite ? 32 : 64),
    new THREE.MeshBasicMaterial({
      color: CYAN, transparent: true, opacity: 0.22,
      blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
    })
  );
  outer.rotation.x = -Math.PI / 2;
  platform.add(outer);

  // Het podium waar de projector op staat.
  const dais = new THREE.Mesh(
    new THREE.CylinderGeometry(1.9, 2.05, 0.3, lite ? 16 : 32, 1, true),
    new THREE.MeshBasicMaterial({
      color: DEEP, wireframe: true, transparent: true, opacity: 0.34,
    })
  );
  dais.position.y = -0.2;
  platform.add(dais);

  scene.add(platform);
}

function buildThinkRing() {
  thinkRing = new THREE.Mesh(
    new THREE.TorusGeometry(1.26, 0.010, 3, lite ? 40 : 80),
    new THREE.MeshBasicMaterial({
      color: CYAN, transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })
  );
  thinkRing.position.y = 1.62;
  thinkRing.rotation.x = 1.15;
  scene.add(thinkRing);
}

function buildRoom() {
  // Vloerraster, verdwijnend in de mist.
  const grid = new THREE.GridHelper(60, lite ? 30 : 60, DEEP, DEEP);
  grid.position.y = -0.72;
  grid.material.transparent = true;
  grid.material.opacity = 0.32;
  scene.add(grid);

  // Serverkasten links en rechts: nette rijen ledjes, als een gangpad.
  const rows = lite ? 9 : 16;      // hoogte
  const cols = lite ? 16 : 30;     // diepte
  const c = new THREE.Color();

  for (const side of [-1, 1]) {
    const count = rows * cols;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    let i = 0;

    for (let r = 0; r < rows; r++) {
      for (let col = 0; col < cols; col++) {
        // Regelmatig raster met net genoeg ruis om niet machinaal te ogen.
        positions[i * 3]     = side * (4.6 + Math.random() * 0.5);
        positions[i * 3 + 1] = -0.6 + r * 0.33 + (Math.random() - 0.5) * 0.06;
        positions[i * 3 + 2] = 2.5 - col * 1.05 + (Math.random() - 0.5) * 0.18;

        // Mix van blauw en amber, zoals rackledjes.
        const amber = Math.random() < 0.3;
        c.setHex(amber ? AMBER : CYAN);
        c.multiplyScalar(0.35 + Math.random() * 0.65);
        colors[i * 3] = c.r; colors[i * 3 + 1] = c.g; colors[i * 3 + 2] = c.b;
        i++;
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const rack = new THREE.Points(geo, new THREE.PointsMaterial({
      size: 0.085, vertexColors: true, transparent: true, opacity: 0.85,
      blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true,
    }));
    racks.push(rack);
    scene.add(rack);

    // De wand zelf, zwak zichtbaar achter de ledjes.
    const wall = new THREE.Mesh(
      new THREE.PlaneGeometry(32, 6),
      new THREE.MeshBasicMaterial({
        color: DEEP, transparent: true, opacity: 0.28, side: THREE.DoubleSide,
      })
    );
    wall.position.set(side * 5.3, 1.6, -11);
    wall.rotation.y = side * Math.PI / 2;
    scene.add(wall);
  }

  // Lichtbundels van rechtsboven, zoals de spots in het ontwerp.
  if (!lite) {
    for (let i = 0; i < 3; i++) {
      const shaft = new THREE.Mesh(
        new THREE.PlaneGeometry(0.6 + i * 0.5, 20),
        new THREE.MeshBasicMaterial({
          color: CYAN, transparent: true, opacity: 0.05 - i * 0.009,
          blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
        })
      );
      shaft.position.set(4.2 - i * 0.8, 3.2, -9);
      shaft.rotation.z = -0.66 + i * 0.05;
      shafts.push(shaft);
      scene.add(shaft);
    }
  }
}

/* -- animatie ------------------------------------------------------------ */

function deformHead(time) {
  if (!baseHeadPositions || lite) return;

  const pos = head.geometry.attributes.position;
  const arr = pos.array;
  const amp = 0.012 + smoothLevel * 0.085;

  for (let i = 0; i < arr.length; i += 3) {
    const bx = baseHeadPositions[i];
    const by = baseHeadPositions[i + 1];
    const bz = baseHeadPositions[i + 2];
    const wave = Math.sin(by * 5.5 + time * 2.4) * Math.cos(bx * 4.2 - time * 1.7);
    const k = 1 + wave * amp;
    arr[i] = bx * k; arr[i + 1] = by * k; arr[i + 2] = bz * k;
  }
  pos.needsUpdate = true;
}

function animate() {
  if (!running) return;
  requestAnimationFrame(animate);

  const time = clock.getElapsedTime();
  smoothLevel += (level - smoothLevel) * 0.18;
  if (state !== "speaking" && state !== "listening") smoothLevel *= 0.9;

  // Het hoofd wiegt traag, en kijkt op tijdens het luisteren.
  const bust = head.parent;
  bust.rotation.y = Math.sin(time * 0.22) * 0.26;
  bust.position.y = 1.62 + Math.sin(time * 0.6) * 0.03;
  bust.rotation.x = state === "listening" ? -0.06 : Math.sin(time * 0.17) * 0.02;

  deformHead(time);

  const pulse = 1 + smoothLevel * 0.9;
  headGlow.material.opacity = 0.12 + smoothLevel * 0.34;
  headGlow.scale.setScalar(1.04 + smoothLevel * 0.06);

  // Platform ademt mee met de toestand.
  const beat = state === "listening" ? 2.6 : state === "speaking" ? 4.0 : 1.1;
  ring.material.opacity = 0.35 + Math.abs(Math.sin(time * beat)) * 0.35 + smoothLevel * 0.3;
  ring.scale.setScalar(1 + Math.sin(time * beat) * 0.015 + smoothLevel * 0.05);
  platform.children[0].material.opacity = 0.16 + smoothLevel * 0.3;

  beams.children.forEach((beam, i) => {
    beam.material.opacity = 0.08 + Math.abs(Math.sin(time * 1.6 + i)) * 0.06
                            + smoothLevel * 0.12;
  });
  beams.scale.y = pulse;

  // Denk-ring: alleen zichtbaar tijdens DENKT.
  const want = state === "thinking" ? 0.55 : 0;
  thinkRing.material.opacity += (want - thinkRing.material.opacity) * 0.12;
  thinkRing.rotation.z += 0.016;
  thinkRing.rotation.y = time * 0.5;

  racks.forEach((rack, i) => {
    rack.material.opacity = 0.75 + Math.sin(time * 0.8 + i * 2) * 0.12;
  });
  shafts.forEach((shaft, i) => {
    shaft.material.opacity = (0.045 - i * 0.008) * (1 + Math.sin(time * 0.5 + i) * 0.3);
  });

  camera.position.x = Math.sin(time * 0.13) * 0.22;
  camera.lookAt(0, 1.35, 0);

  renderer.render(scene, camera);
}

/* -- opstarten ----------------------------------------------------------- */

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  // Bij een smal of laag venster iets verder weg, anders loopt de bust uit beeld.
  const tight = Math.min(1, (w / h) / 1.5);
  camera.position.z = 8.2 + (1 - tight) * 4.2;
  camera.updateProjectionMatrix();
}

function rebuild() {
  // Lite-modus wisselt de detailgraad, dus de scene gaat opnieuw op.
  while (scene.children.length) {
    const obj = scene.children.pop();
    obj.traverse?.((o) => {
      o.geometry?.dispose?.();
      if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose?.());
      else o.material?.dispose?.();
    });
  }
  racks = []; shafts = [];
  buildRoom(); buildBust(); buildBeams(); buildPlatform(); buildThinkRing();
  renderer.setPixelRatio(lite ? 1 : Math.min(window.devicePixelRatio, 1.5));
}

function init() {
  try {
    renderer = new THREE.WebGLRenderer({
      canvas, antialias: !lite, alpha: false, powerPreference: "low-power",
    });
  } catch (e) {
    console.error("WebGL niet beschikbaar:", e);
    canvas.style.display = "none";
    document.body.style.background =
      "radial-gradient(ellipse at 50% 45%, #0a2a4a 0%, #01050f 70%)";
    return false;
  }

  renderer.setClearColor(0x01050f, 1);
  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x01050f, 0.038);

  camera = new THREE.PerspectiveCamera(38, window.innerWidth / window.innerHeight, 0.1, 120);
  camera.position.set(0, 1.85, 8.2);

  clock = new THREE.Clock();
  rebuild();
  resize();

  window.addEventListener("resize", resize);
  document.addEventListener("visibilitychange", () => {
    // Niet renderen in een onzichtbaar tabblad: scheelt accu.
    if (document.hidden) { running = false; }
    else if (!running) { running = true; clock.getDelta(); animate(); }
  });
  canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); running = false; });
  canvas.addEventListener("webglcontextrestored", () => {
    rebuild(); running = true; animate();
  });

  animate();
  return true;
}

const ok = init();

window.holo = {
  ready: ok,
  setState(next) { state = next; },
  setLevel(value) { level = Math.max(0, Math.min(1, value || 0)); },
  setLite(on) {
    if (!ok || on === lite) return;
    lite = on;
    document.body.classList.toggle("lite", on);
    rebuild();
  },
};
