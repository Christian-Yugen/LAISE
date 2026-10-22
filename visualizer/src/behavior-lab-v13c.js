import "./style.css";
import { RippleField } from "./behavior-ripple-field-v13c.js";
import { OpenBoundaryRippleFieldV13C } from "./behavior-open-boundary-field-v13c.js";
import { BehaviorTimelineV13C } from "./behavior-timeline-v13c.js";
import { AudioCueTimeline } from "./audio-cue-timeline.js";
import { AudioMotionRecovery } from "./audio-motion-recovery.js";

import * as THREE from "three";

import {
  EffectComposer
} from "three/addons/postprocessing/EffectComposer.js";

import {
  RenderPass
} from "three/addons/postprocessing/RenderPass.js";

import {
  UnrealBloomPass
} from "three/addons/postprocessing/UnrealBloomPass.js";


const canvas =
  document.querySelector("#scene");

const audio =
  document.querySelector("#audio");

const startButton =
  document.querySelector("#startButton");

const currentTimeLabel =
  document.querySelector("#currentTime");

const durationLabel =
  document.querySelector("#duration");

const timeline =
  document.querySelector("#timeline");

const timelineFill =
  document.querySelector("#timelineFill");

const energyLabel =
  document.querySelector("#energy");

// Technical metadata is independent of cueReady and must never gate playback.
// BEGIN TECHNICAL MANIFEST
function validateTechnicalManifest(data, masterUrl) {
  if (!data || data.schema_version !== "laise-visualizer-manifest-v1") {
    throw new Error("Unsupported technical manifest schema");
  }
  for (const key of ["track", "master_url", "master_sha256", "master_label",
    "spatial_source", "delivery_source", "visualizer_version", "stems_state", "motion_state"]) {
    if (typeof data[key] !== "string" || !data[key].trim()) throw new Error(`Invalid ${key}`);
  }
  if (data.master_url !== masterUrl || !/^\/audio\/[^?#]+$/.test(data.master_url)) {
    throw new Error("Technical manifest/master URL mismatch");
  }
  if (!/^[a-f0-9]{64}$/.test(data.master_sha256)) throw new Error("Invalid master hash");
  for (const key of ["duration_seconds", "sample_rate", "channels", "source_count",
    "integrated_lufs", "true_peak_dbtp", "spatial_integrity"]) {
    if (!Number.isFinite(data[key])) throw new Error(`Invalid ${key}`);
  }
  for (const key of ["sample_rate", "channels", "source_count"]) {
    if (!Number.isInteger(data[key]) || data[key] <= 0) throw new Error(`Invalid ${key}`);
  }
  if (data.duration_seconds <= 0 || data.spatial_integrity < 0 || data.spatial_integrity > 100) {
    throw new Error("Invalid manifest measurement range");
  }
  if (data.delivery_status !== "VALIDATED" || data.stems_state !== "READY" || data.motion_state !== "OFFLINE") {
    throw new Error("Unsupported technical status");
  }
  return data;
}

function renderTechnicalHud(data) {
  const values = data ? {
    trackTitle: data.track,
    masterLabel: data.master_label,
    integratedLufs: data.integrated_lufs.toFixed(2),
    truePeak: data.true_peak_dbtp.toFixed(2),
    spatialIntegrity: data.spatial_integrity.toFixed(2),
    sourceCount: `${data.source_count} SOURCES`,
    spatialSource: data.spatial_source,
    stemsState: `${data.visualizer_version} ${data.stems_state}`,
    motionState: `${data.visualizer_version} ${data.motion_state}`,
    visualizerVersion: `ORIGINAL CONCEPT · ${data.visualizer_version}`,
    deliveryStatus: data.delivery_status
  } : {
    trackTitle: "--", masterLabel: "--", integratedLufs: "--", truePeak: "--",
    spatialIntegrity: "--", sourceCount: "--", spatialSource: "--", stemsState: "--",
    motionState: "--", visualizerVersion: "--", deliveryStatus: "UNAVAILABLE"
  };
  for (const [id, text] of Object.entries(values)) document.getElementById(id).textContent = text;
  const master = document.getElementById("masterLabel");
  master.dataset.masterUrl = data?.master_url ?? "";
  master.dataset.masterSha256 = data?.master_sha256 ?? "";
  const delivery = document.getElementById("deliveryStatus");
  delivery.dataset.source = data?.delivery_source ?? "";
  delivery.title = data ? `Delivery provenance: ${data.delivery_source}` : "Technical metadata unavailable";
}
// END TECHNICAL MANIFEST

fetch("/audio/tukana-visualizer-manifest.json")
  .then(response => {
    if (!response.ok) throw new Error("Could not load technical manifest");
    return response.json();
  })
  .then(data => renderTechnicalHud(validateTechnicalManifest(data, audio.getAttribute("src"))))
  .catch(error => {
    renderTechnicalHud(null);
    console.error("LAISE technical metadata unavailable:", error);
  });


/* =========================================================
   THREE
========================================================= */

const renderer =
  new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: "high-performance"
  });


renderer.setPixelRatio(
  Math.min(
    window.devicePixelRatio,
    1.6
  )
);

renderer.setSize(
  window.innerWidth,
  window.innerHeight
);

renderer.outputColorSpace =
  THREE.SRGBColorSpace;


const scene =
  new THREE.Scene();


scene.fog =
  new THREE.FogExp2(
    0x020706,
    0.048
  );


// One horizontal local XZ plane; only this group owns the terrain pose.
const TERRAIN = Object.freeze({ width: 16, depth: 16, maxHeight: 2.8 });
// AJUSTE AQUI: valores em graus, aplicados uma ?nica vez ? malha e ao glow.
const MESH_ANGLES = Object.freeze({
  horizontal: 45, // Square domain, viewed along its diagonal.
  vertical: 0,
  diagonal: 0
});
const BASE_POSE = Object.freeze({
  y: -0.75,
  yaw: THREE.MathUtils.degToRad(MESH_ANGLES.horizontal),
  pitch: THREE.MathUtils.degToRad(MESH_ANGLES.vertical),
  roll: THREE.MathUtils.degToRad(MESH_ANGLES.diagonal)
});
// Posicao na tela, em pixels: horizontal + direita; vertical + baixo.
const SCREEN_POSITION = Object.freeze({ horizontal: 0, vertical: 0 });
// Approved R3 reference: 1682.861971 px at 1920 px, preserved proportionally.
const CAMERA = Object.freeze({ span: 32, elevation: THREE.MathUtils.degToRad(16), distance: 26, widthTarget: 1682.861971225252 / 1920 });

const camera =
  new THREE.OrthographicCamera(
    -CAMERA.span * window.innerWidth / window.innerHeight / 2,
    CAMERA.span * window.innerWidth / window.innerHeight / 2,
    CAMERA.span / 2, -CAMERA.span / 2, 0.1, 100
  );


// Full local deformation box, including the translated glow's upper extreme.
function fieldEnvelope() {
  const rotation = new THREE.Euler(BASE_POSE.pitch, BASE_POSE.yaw, BASE_POSE.roll);
  return [-TERRAIN.width / 2, TERRAIN.width / 2].flatMap(x =>
    [-TERRAIN.depth / 2, TERRAIN.depth / 2].flatMap(z =>
      [-TERRAIN.maxHeight, TERRAIN.maxHeight + 0.025].map(y =>
        new THREE.Vector3(x, y, z).applyEuler(rotation).add(new THREE.Vector3(0, BASE_POSE.y, 0)))));
}

function convexHull(points) {
  const sorted = [...points].sort((a, b) => a.x - b.x || a.y - b.y);
  const cross = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
  const half = list => {
    const result = [];
    for (const point of list) {
      while (result.length > 1 && cross(result.at(-2), result.at(-1), point) <= 0) result.pop();
      result.push(point);
    }
    return result.slice(0, -1);
  };
  return [...half(sorted), ...half([...sorted].reverse())];
}

// Separating axes avoid reserving an empty full-width band for corner UI.
function polygonsOverlap(a, b) {
  for (const polygon of [a, b]) {
    for (let i = 0; i < polygon.length; i++) {
      const p = polygon[i], q = polygon[(i + 1) % polygon.length];
      const axis = { x: p.y - q.y, y: q.x - p.x };
      const project = shape => shape.map(point => point.x * axis.x + point.y * axis.y);
      const aa = project(a), bb = project(b);
      if (Math.max(...aa) <= Math.min(...bb) || Math.max(...bb) <= Math.min(...aa)) return false;
    }
  }
  return true;
}

function frameTerrain() {
  const width = window.innerWidth, height = window.innerHeight;
  // R3B anchors the BASE front to the listener. Negative deformation is allowed
  // behind the listener/HUD overlays; it never changes the simulated heights.
  camera.left = -CAMERA.span * width / height / 2;
  camera.right = CAMERA.span * width / height / 2;
  camera.top = CAMERA.span / 2;
  camera.bottom = -CAMERA.span / 2;
  const margin = 8;
  const rect = selector => {
    const element = document.querySelector(selector);
    const bounds = element?.getBoundingClientRect();
    return bounds?.width && bounds?.height ? bounds : null;
  };
  const listenerTop = rect(".headphones")?.top ?? rect(".listener")?.top ?? height * 0.8;
  const listenerGap = Math.max(6, Math.min(width, height) * (8 / 1080));
  const frontTarget = listenerTop - listenerGap + SCREEN_POSITION.vertical;
  const obstacles = [".brand", ".field-summary", ".status"].map(rect).filter(Boolean).map(r => [
    { x: r.left - margin / 2, y: r.top - margin / 2 },
    { x: r.right + margin / 2, y: r.top - margin / 2 },
    { x: r.right + margin / 2, y: r.bottom + margin / 2 },
    { x: r.left - margin / 2, y: r.bottom + margin / 2 }
  ]);
  const target = new THREE.Vector3(0, BASE_POSE.y, 0);
  const direction = new THREE.Vector3(0, Math.sin(CAMERA.elevation), Math.cos(CAMERA.elevation));
  camera.position.copy(target).addScaledVector(direction, CAMERA.distance);
  camera.lookAt(target);
  camera.far = 500;
  camera.updateMatrixWorld(true);
  const envelope = fieldEnvelope();
  const rotation = new THREE.Euler(BASE_POSE.pitch, BASE_POSE.yaw, BASE_POSE.roll);
  const base = [-TERRAIN.width / 2, TERRAIN.width / 2].flatMap(x =>
    [-TERRAIN.depth / 2, TERRAIN.depth / 2].map(z =>
      new THREE.Vector3(x, 0, z).applyEuler(rotation).add(target)));
  function place(zoom) {
    camera.zoom = zoom;
    camera.clearViewOffset();
    camera.updateProjectionMatrix();
    const projected = base.map(point => point.clone().project(camera));
    const cx = (Math.min(...projected.map(p => p.x)) + Math.max(...projected.map(p => p.x))) / 2;
    const frontY = Math.max(...projected.map(p => (1 - p.y) * height / 2));
    camera.setViewOffset(width, height, cx * width / 2 - SCREEN_POSITION.horizontal,
      frontY - frontTarget, width, height);
    return envelope.map(point => {
      const p = point.clone().project(camera);
      return { x: (p.x + 1) * width / 2, y: (1 - p.y) * height / 2, z: p.z };
    });
  }
  function fits(points) {
    const epsilon = 1e-7; // Floating-point projection tolerance, in CSS pixels.
    // Lower signed envelope may be occluded by the existing bottom overlays or
    // viewport edge. Only upper/lateral bounds and header legibility limit fit.
    if (!points.every(p => p.x >= margin - epsilon && p.x <= width - margin + epsilon && p.y >= margin - epsilon && p.z > -1 && p.z < 1)) return false;
    const hull = convexHull(points);
    return obstacles.every(obstacle => !polygonsOverlap(hull, obstacle));
  }
  camera.zoom = 1;
  camera.clearViewOffset();
  camera.updateProjectionMatrix();
  const unit = base.map(point => point.clone().project(camera));
  const unitWidth = (Math.max(...unit.map(p => p.x)) - Math.min(...unit.map(p => p.x))) * width / 2;
  const approvedZoom = width * CAMERA.widthTarget / unitWidth;
  if (fits(place(approvedZoom))) return;
  // Only exceptionally constrained viewports may reduce width to protect text.
  let low = 0.01, high = approvedZoom;
  for (let i = 0; i < 40; i++) {
    const zoom = (low + high) / 2;
    if (fits(place(zoom))) low = zoom;
    else high = zoom;
  }
  place(low);
}

frameTerrain();


/* =========================================================
   LIGHT
========================================================= */

// All active scene materials are unlit (MeshBasicMaterial / PointsMaterial).
// PointLights and their exclusive intensity calculations have no visual effect.


/* =========================================================
   SONIC TERRAIN
========================================================= */

const SEG_X = 128;
const SEG_Z = 128;

const geometry =
  new THREE.PlaneGeometry(
    TERRAIN.width,
    TERRAIN.depth,
    SEG_X,
    SEG_Z
  );


geometry.rotateX(
  -Math.PI / 2
);


const positions =
  geometry.attributes.position;


const basePositions =
  new Float32Array(
    positions.array
  );


const colors =
  new Float32Array(
    positions.count * 3
  );


const colorA =
  new THREE.Color(
    0xd89a48
  );

const colorB =
  new THREE.Color(
    0xc54c3d
  );

const colorC =
  new THREE.Color(
    0x36d2b3
  );

const colorD =
  new THREE.Color(
    0x318cbe
  );


for (
  let i = 0;
  i < positions.count;
  i++
) {

  const x =
    basePositions[
      i * 3
    ];

  const t =
    THREE.MathUtils.clamp(
      (x + TERRAIN.width / 2) / TERRAIN.width,
      0,
      1
    );


  let c =
    new THREE.Color();


  if (t < 0.33) {

    c.copy(
      colorA
    ).lerp(
      colorB,
      t / 0.33
    );

  } else if (t < 0.68) {

    c.copy(
      colorB
    ).lerp(
      colorC,
      (
        t - 0.33
      ) / 0.35
    );

  } else {

    c.copy(
      colorC
    ).lerp(
      colorD,
      (
        t - 0.68
      ) / 0.32
    );

  }


  colors[
    i * 3
  ] = c.r;

  colors[
    i * 3 + 1
  ] = c.g;

  colors[
    i * 3 + 2
  ] = c.b;

}


geometry.setAttribute(
  "color",
  new THREE.BufferAttribute(
    colors,
    3
  )
);


const terrainMaterial =
  new THREE.MeshBasicMaterial({

    vertexColors: true,

    wireframe: true,

    transparent: true,

    opacity: 0.83,

    blending:
      THREE.AdditiveBlending,

    depthWrite: false

  });


const terrain =
  new THREE.Mesh(
    geometry,
    terrainMaterial
  );


const terrainRig = new THREE.Group();
terrainRig.position.set(0, BASE_POSE.y, 0);
terrainRig.rotation.set(BASE_POSE.pitch, BASE_POSE.yaw, BASE_POSE.roll);
terrainRig.scale.set(1, 1, 1);
terrainRig.add(terrain);
scene.add(terrainRig);


/* =========================================================
   SECOND CONTOUR LAYER
========================================================= */

// Shared geometry guarantees identical silhouettes and deformation.
const glowGeometry = geometry;


const glowMaterial =
  new THREE.MeshBasicMaterial({

    color:
      0x46d6ae,

    wireframe: true,

    transparent: true,

    opacity: 0.08,

    blending:
      THREE.AdditiveBlending,

    depthWrite: false

  });


const glowTerrain =
  new THREE.Mesh(
    glowGeometry,
    glowMaterial
  );


glowTerrain.position.set(0, 0.025, 0);
terrainRig.add(glowTerrain);

// Include both crests and troughs in the deformation bounds.
geometry.boundingBox = new THREE.Box3(
  new THREE.Vector3(-TERRAIN.width / 2, -TERRAIN.maxHeight, -TERRAIN.depth / 2),
  new THREE.Vector3(TERRAIN.width / 2, TERRAIN.maxHeight, TERRAIN.depth / 2)
);
geometry.boundingSphere = geometry.boundingBox.getBoundingSphere(new THREE.Sphere());

// Audio excites a signed wave field; the pose and camera remain independent.
const rippleField = new RippleField(TERRAIN.width, TERRAIN.depth, SEG_X, SEG_Z);


// ------------------------------------------------------------
// V1.3C R5:
// independent extended physical field.
//
// V1.2 keeps the legacy reflective RippleField above.
// ------------------------------------------------------------

const behaviorRippleField =
  new OpenBoundaryRippleFieldV13C(
    TERRAIN.width,
    TERRAIN.depth,
    SEG_X,
    SEG_Z,
    {
      guardCells: 24,
      maxHiddenDamping: 6
    }
  );


function resetRippleFields() {

  rippleField.reset();
  behaviorRippleField.reset();
}

const audioMotionRecovery = new AudioMotionRecovery();
// All vertices, including the outer rows, now follow the wave field.


/* =========================================================
   PARTICLES
========================================================= */

const particleCount =
  1900;


const particlePositions =
  new Float32Array(
    particleCount * 3
  );


for (
  let i = 0;
  i < particleCount;
  i++
) {

  particlePositions[
    i * 3
  ] =
    THREE.MathUtils.randFloat(
      -9,
      9
    );

  particlePositions[
    i * 3 + 1
  ] =
    THREE.MathUtils.randFloat(
      -0.2,
      6.5
    );

  particlePositions[
    i * 3 + 2
  ] =
    THREE.MathUtils.randFloat(
      -6,
      5
    );

}


const particleGeometry =
  new THREE.BufferGeometry();


particleGeometry.setAttribute(
  "position",
  new THREE.BufferAttribute(
    particlePositions,
    3
  )
);


const particleMaterial =
  new THREE.PointsMaterial({

    color:
      0xdba765,

    size:
      0.024,

    transparent:
      true,

    opacity:
      0.44,

    blending:
      THREE.AdditiveBlending,

    depthWrite:
      false

  });


const particles =
  new THREE.Points(
    particleGeometry,
    particleMaterial
  );


scene.add(
  particles
);


/* =========================================================
   CENTRAL LISTENER RINGS
========================================================= */

const rings =
  new THREE.Group();


for (
  let i = 0;
  i < 5;
  i++
) {

  const ringGeometry =
    new THREE.RingGeometry(
      0.9 + i * 0.52,
      0.91 + i * 0.52,
      128
    );


  const ringMaterial =
    new THREE.MeshBasicMaterial({

      color:
        0xc58d4d,

      transparent:
        true,

      opacity:
        0.15 - i * 0.018,

      side:
        THREE.DoubleSide,

      blending:
        THREE.AdditiveBlending,

      depthWrite:
        false

    });


  const ring =
    new THREE.Mesh(
      ringGeometry,
      ringMaterial
    );


  ring.rotation.x =
    -Math.PI / 2;


  ring.position.y =
    -0.57;


  rings.add(
    ring
  );

}


scene.add(
  rings
);


/* =========================================================
   AUDIO ENGINE
========================================================= */

const AudioContextClass =
  window.AudioContext ||
  window.webkitAudioContext;


const audioContext =
  new AudioContextClass();


const mediaSource =
  audioContext.createMediaElementSource(
    audio
  );


const analyser =
  audioContext.createAnalyser();


analyser.fftSize =
  2048;


analyser.smoothingTimeConstant =
  0.78;


mediaSource.connect(
  analyser
);


analyser.connect(
  audioContext.destination
);


const frequencyData =
  new Uint8Array(
    analyser.frequencyBinCount
  );


const smoothed =
  new Float32Array(
    analyser.frequencyBinCount
  );


// The original master remains the only audible source. These small cue records
// come from its 12 aligned spatial stems and drive visuals only.
let cueTimeline = null;
let cueLoadError = null;
const cueReady = fetch("/audio/tukana-stem-cues.json")
  .then(response => {
    if (!response.ok) throw new Error("Could not load Tukana stem cues");
    return response.json();
  })
  .then(data => {
    if (data.master.url !== audio.getAttribute("src")) throw new Error("Stem cue/master mismatch");
    cueTimeline = new AudioCueTimeline(data);
    cueTimeline.seek(audio.currentTime);
  })
  .catch(error => {
    cueLoadError = error;
    console.error(error);
  });

// A seek starts a new acoustic moment; do not keep waves from the old section.
function beginMediaSeek() {
  if (cueTimeline?.isSeeking) return;
  resetRippleFields();
  smoothed.fill(0);
  cueTimeline?.seek(audio.currentTime);
  if (cueTimeline) cueTimeline.isSeeking = true;
}
audio.addEventListener("seeking", beginMediaSeek);
audio.addEventListener("seeked", () => {
  if (!cueTimeline) return;
  // Final destination may differ from the requested position after clamping.
  const epoch = cueTimeline.playbackEpoch;
  cueTimeline.seek(audio.currentTime);
  cueTimeline.playbackEpoch = epoch;
  cueTimeline.isSeeking = false;
});
audio.addEventListener("emptied", () => {
  resetRippleFields();
  cueTimeline?.seek(0);
});

// Flush the fraction of audio played since the last rendered frame before pause.
audio.addEventListener("pause", () => {
  if (!audio.seeking) updateSoundWaves(0, true);
});
audio.addEventListener("ended", () => {
  updateSoundWaves(0, true);
});
audio.addEventListener("play", () => {
  if (cueTimeline && audio.currentTime < cueTimeline.lastTime && !audio.seeking) {
    resetRippleFields();
    cueTimeline.seek(audio.currentTime);
  }
});


/* =========================================================
   POST PROCESSING
========================================================= */

const composer =
  new EffectComposer(
    renderer
  );


composer.addPass(
  new RenderPass(
    scene,
    camera
  )
);


const bloom =
  new UnrealBloomPass(

    new THREE.Vector2(
      window.innerWidth,
      window.innerHeight
    ),

    0.9,
    0.55,
    0.12

  );


composer.addPass(
  bloom
);


/* =========================================================
   UI
========================================================= */

// Presentation only: the existing play/pause/seek timing stays unchanged.
function renderPlaybackButton(state) {
  const label = {
    playing: "Pausar", paused: "Continuar", ended: "Reproduzir novamente",
    error: "Falha na análise — recarregue a página"
  }[state];
  const icon = state === "playing" ? "Ⅱ" : state === "error" ? "!" : "▶";
  startButton.innerHTML = `<span aria-hidden="true">${icon}</span>`;
  startButton.setAttribute("aria-label", label);
  startButton.title = label;
  startButton.dataset.state = state;
}

audio.addEventListener("play", () => renderPlaybackButton("playing"));
audio.addEventListener("pause", () => renderPlaybackButton("paused"));
audio.addEventListener("ended", () => renderPlaybackButton("ended"));

function formatTime(
  seconds
) {

  if (
    !Number.isFinite(
      seconds
    )
  ) {
    return "00:00";
  }


  const m =
    Math.floor(
      seconds / 60
    );


  const s =
    Math.floor(
      seconds % 60
    );


  return (
    String(m).padStart(
      2,
      "0"
    )
    +
    ":"
    +
    String(s).padStart(
      2,
      "0"
    )
  );

}


function syncDurationLabel() {
  if (Number.isFinite(audio.duration) && audio.duration > 0) {
    durationLabel.textContent = formatTime(audio.duration);
  }
}

audio.addEventListener("loadedmetadata", syncDurationLabel);
audio.addEventListener("durationchange", syncDurationLabel);
syncDurationLabel();


audio.addEventListener(
  "timeupdate",
  () => {

    currentTimeLabel.textContent =
      formatTime(
        audio.currentTime
      );


    if (
      audio.duration > 0
    ) {

      const percent =
        (
          audio.currentTime /
          audio.duration
        )
        * 100;


      timelineFill.style.width =
        `${percent}%`;

    }

  }
);


timeline.addEventListener(
  "click",
  event => {

    if (
      !audio.duration
    ) {
      return;
    }


    const box =
      timeline.getBoundingClientRect();


    const ratio =
      THREE.MathUtils.clamp(
        (
          event.clientX -
          box.left
        ) /
        box.width,
        0,
        1
      );


    beginMediaSeek();
    audio.currentTime =
      ratio *
      audio.duration;

  }
);


startButton.addEventListener(
  "click",
  async () => {

    await audioContext.resume();
    await cueReady;
    if (cueLoadError) {
      renderPlaybackButton("error");
      return;
    }


    if (
      audio.paused
    ) {

      await audio.play();



    } else {

      audio.pause();



    }

  }
);


/* =========================================================
   ANIMATION
========================================================= */

const clock = new THREE.Clock();
let previousTime = 0;




/* =========================================================
   V1.3C ISOLATED VISIBLE BEHAVIOR LAB
   Production main.js is NOT modified.
========================================================= */

let behaviorTimelineV13C = null;
let behaviorMode = "v13c";
let behaviorLoadError = null;


const behaviorLabPanel =
  document.createElement("div");

behaviorLabPanel.id =
  "behaviorLabPanel";

behaviorLabPanel.innerHTML = `
  <div class="lab-title">
    V1.3C BEHAVIOR LAB
  </div>

  <div class="lab-switch">
    <button
      type="button"
      data-mode="v12">
      V1.2
    </button>

    <button
      type="button"
      data-mode="v13c"
      class="active">
      V1.3C
    </button>
  </div>

  <div
    id="behaviorLabState"
    class="lab-state">
    Loading V1.3C...
  </div>

  <div class="lab-note">
    SINGLE MASTER CLOCK · PROVISIONAL LAB
  </div>
`;

document.body.appendChild(
  behaviorLabPanel
);


const behaviorLabStyle =
  document.createElement("style");

behaviorLabStyle.textContent = `
  #behaviorLabPanel {
    position: fixed;
    top: 18px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 30;

    min-width: 310px;
    padding: 10px 12px;

    border: 1px solid rgba(239,184,107,.25);
    background: rgba(2,7,6,.82);
    backdrop-filter: blur(12px);

    color: #b7c7c0;
    font-family: inherit;

    box-shadow:
      0 0 30px rgba(0,0,0,.25);
  }

  #behaviorLabPanel .lab-title {
    margin-bottom: 8px;
    text-align: center;

    color: #efb86b;
    font-size: 9px;
    letter-spacing: .18em;
  }

  #behaviorLabPanel .lab-switch {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }

  #behaviorLabPanel button {
    padding: 7px 10px;

    border:
      1px solid rgba(255,255,255,.10);

    background:
      rgba(255,255,255,.025);

    color: #71857c;

    font: inherit;
    font-size: 9px;
    letter-spacing: .12em;

    cursor: pointer;
  }

  #behaviorLabPanel button.active {
    border-color:
      rgba(239,184,107,.65);

    color: #efb86b;

    background:
      rgba(239,184,107,.08);
  }

  #behaviorLabPanel .lab-state {
    margin-top: 8px;

    color: #7fa99b;
    font-size: 8px;
    line-height: 1.5;
    letter-spacing: .08em;
    text-align: center;
  }

  #behaviorLabPanel .lab-note {
    margin-top: 5px;

    color: #53665e;
    font-size: 7px;
    letter-spacing: .12em;
    text-align: center;
  }
`;

document.head.appendChild(
  behaviorLabStyle
);


const behaviorLabState =
  document.querySelector(
    "#behaviorLabState"
  );


function renderBehaviorLabState() {

  const buttons =
    behaviorLabPanel.querySelectorAll(
      "[data-mode]"
    );

  for (
    const button
    of buttons
  ) {

    button.classList.toggle(
      "active",
      button.dataset.mode ===
        behaviorMode
    );
  }


  if (
    behaviorMode === "v12"
  ) {

    behaviorLabState.textContent =
      "V1.2 · T007 ABSOLUTO · CUES LEGADOS";

    return;
  }


  if (behaviorLoadError) {

    behaviorLabState.textContent =
      "V1.3C LOAD ERROR";

    return;
  }


  if (!behaviorTimelineV13C) {

    behaviorLabState.textContent =
      "LOADING V1.3C...";

    return;
  }


  const state =
    behaviorTimelineV13C.debug;


  behaviorLabState.textContent =
    `V1.3C · ANCHOR ${state.anchorSource}` +
    ` · DRIVE ${state.anchorDrive.toFixed(5)}` +
    ` · FOOTPRINT ×${state.footprintScale.toFixed(2)}` +
    ` · ACTIVE ${state.activeContinuous}`;
}


function setBehaviorMode(
  mode
) {

  if (
    mode !== "v12" &&
    mode !== "v13c"
  ) {
    return;
  }


  behaviorMode = mode;

  /*
    One audio element, one currentTime.

    Only the visual field is reset when
    A/B mode changes. Audio never duplicates.
  */

  resetRippleFields();

  cueTimeline?.seek(
    audio.currentTime
  );

  behaviorTimelineV13C?.seek(
    audio.currentTime
  );


  renderBehaviorLabState();
}


behaviorLabPanel.addEventListener(
  "click",
  event => {

    const button =
      event.target.closest(
        "[data-mode]"
      );

    if (!button) {
      return;
    }

    setBehaviorMode(
      button.dataset.mode
    );
  }
);


fetch(
  "/audio/tukana-musical-behavior-runtime-v1.json"
)
  .then(response => {

    if (!response.ok) {

      throw new Error(
        "Could not load V1.3C behavior runtime"
      );
    }

    return response.json();
  })
  .then(data => {

    if (
      data.masterUrl !==
      audio.getAttribute("src")
    ) {

      throw new Error(
        "V1.3C behavior/master mismatch"
      );
    }


    behaviorTimelineV13C =
      new BehaviorTimelineV13C(
        data
      );


    behaviorTimelineV13C.seek(
      audio.currentTime
    );


    renderBehaviorLabState();
  })
  .catch(error => {

    behaviorLoadError =
      error;

    console.error(
      error
    );

    renderBehaviorLabState();
  });


audio.addEventListener(
  "seeking",
  () => {

    behaviorTimelineV13C?.seek(
      audio.currentTime
    );
  }
);


audio.addEventListener(
  "seeked",
  () => {

    behaviorTimelineV13C?.seek(
      audio.currentTime
    );
  }
);


audio.addEventListener(
  "emptied",
  () => {

    behaviorTimelineV13C?.seek(
      0
    );
  }
);


audio.addEventListener(
  "play",
  () => {

    if (
      behaviorTimelineV13C &&
      audio.currentTime <
        behaviorTimelineV13C.lastTime
    ) {

      behaviorTimelineV13C.seek(
        audio.currentTime
      );
    }
  }
);


function updateSoundWaves(delta, flushPause = false) {

  const playing =
    flushPause ||
    (
      !audio.paused &&
      !audio.seeking &&
      !audio.ended
    );


  const targetTime =
    flushPause &&
    Number.isFinite(
      audio.duration
    )
      ? Math.min(
          audio.currentTime,
          audio.duration
        )
      : audio.currentTime;


  /*
    V1.3C:
    gesture/behavior timeline owns excitation.

    Same audio.currentTime as V1.2.
  */

  if (
    behaviorMode === "v13c" &&
    behaviorTimelineV13C
  ) {

    const synced =
      behaviorTimelineV13C.step(
        targetTime,
        playing,
        behaviorRippleField
      );


    /*
      Paused audio adds no new musical force.
      Existing physical waves may dissipate.
    */

    if (!synced) {
      behaviorRippleField.advance(
        delta
      );
    }


    renderBehaviorLabState();

    return;
  }


  /*
    V1.2:
    original approved cue behavior.
  */

  const synced =
    cueTimeline?.step(
      targetTime,
      playing,

      cue =>
        rippleField.exciteAt(
          cue.x,
          cue.z,
          cue.strength,
          cue.width
        ),

      seconds =>
        rippleField.advance(
          seconds
        )
    );


  if (!synced) {

    rippleField.advance(
      delta
    );
  }


  renderBehaviorLabState();
}


function animate() {

  requestAnimationFrame(
    animate
  );


  const time =
    clock.getElapsedTime();


  const delta = Math.min(0.1, Math.max(0, time - previousTime));
  previousTime = time;
  const smoothing = 1 - Math.exp(-delta / 0.10);

  analyser.getByteFrequencyData(
    frequencyData
  );


  let totalEnergy =
    0;


  for (
    let i = 0;
    i < frequencyData.length;
    i++
  ) {

    smoothed[i] =
      smoothed[i] + (frequencyData[i] - smoothed[i]) * smoothing;


    totalEnergy +=
      smoothed[i];

  }


  const averageEnergy =
    totalEnergy /
    frequencyData.length /
    255;


  energyLabel.textContent =
    `ENERGY ${
      Math.round(
        averageEnergy * 100
      )
    }%`;


  updateSoundWaves(delta);

  const motionGain = audioMotionRecovery.gainFor(camera, terrainRig,
    window.innerWidth, window.innerHeight);
  const visibleRippleField =
    behaviorMode === "v13c"
      ? behaviorRippleField
      : rippleField;

  for (let i = 0; i < positions.count; i++) {
    // Signed heights produce rising crests and falling troughs. Fixed simulation
    // timesteps supply temporal continuity without smearing the travelling wave.
    positions.array[i * 3 + 1] = TERRAIN.maxHeight *
      Math.tanh(visibleRippleField.heights[i] * motionGain / TERRAIN.maxHeight);
  }
  positions.needsUpdate = true;


  particles.rotation.y =
    time * 0.006;


  particles.position.y =
    averageEnergy * 0.25;


  rings.rotation.y =
    time * 0.025;


  bloom.strength =
    0.45 + Math.min(averageEnergy * 0.8, 0.25);




  composer.render();

}


animate();


/* =========================================================
   RESIZE
========================================================= */

window.addEventListener(
  "resize",
  () => {

    const width =
      window.innerWidth;

    const height =
      window.innerHeight;


    camera.aspect =
      width /
      height;


    frameTerrain();


    renderer.setSize(
      width,
      height
    );


    composer.setSize(
      width,
      height
    );

  }
);
