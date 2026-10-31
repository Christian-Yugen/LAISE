import { EventWaveDetailR9 } from "./event-wave-detail-r9.js";
import "./style.css";
import { RippleField } from "./behavior-ripple-field-v13c.js";
import { OpenBoundaryRippleFieldV13C } from "./behavior-open-boundary-field-v13c.js";
import { BehaviorTimelineV13C } from "./behavior-timeline-v13c.js";
import { NEON_R8A, neonUniformsR8A, neonEmissionGLSL, createNeonCurvatureR8A } from "./neon-emission-r8a.js";
import { installNeonOpticsR8A } from "./neon-optics-r8a.js";
import { AudioCueTimeline } from "./audio-cue-timeline.js";
import { AudioMotionRecovery } from "./audio-motion-recovery.js";

import * as THREE from "three";
import { createReflectiveFloorR8B } from "./reflective-floor-r8b.js";

import {
  EffectComposer
} from "three/addons/postprocessing/EffectComposer.js";

import {
  RenderPass
} from "three/addons/postprocessing/RenderPass.js";

import {
  UnrealBloomPass
} from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";


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
  document.getElementById("depthTrackTitle").textContent = values.trackTitle;
  document.getElementById("depthMasterLabel").textContent = values.masterLabel;
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

// Compress the final composite, including bloom, before display conversion.
renderer.toneMapping = THREE.ReinhardToneMapping;
renderer.toneMappingExposure = NEON_R8A.neonExposure;


const scene =
  new THREE.Scene();

// LAISE_FOREST_BACKGROUND_R8B
// ?background=0 allows a visual comparison without the forest.
const forestBackgroundEnabled =
  new URLSearchParams(window.location.search).get("background") !== "0";

if (forestBackgroundEnabled) {
  // LAISE_R8C_ABSTRACT_BACKGROUND
  // Default: abstract. Use ?background=forest for the previous image.
  const selectedBackgroundR8C =
    new URLSearchParams(window.location.search).get("background");

  const forestUrl = selectedBackgroundR8C === "forest"
    ? new URL("./laise-forest-background-r8b.png", import.meta.url).href
    : new URL("./laise-abstract-background-r8c.png", import.meta.url).href;

  new THREE.TextureLoader().load(
    forestUrl,
    (texture) => {
      texture.colorSpace = THREE.SRGBColorSpace;
      scene.background = texture;
      // LAISE_R8C_BACKGROUND_DIM_TEST
      // ?bgdim=0.25 darkens only the scene background.
      // Without the parameter, the previous appearance is preserved.
      const bgDimParam = new URLSearchParams(window.location.search).get("bgdim");
      const bgDimValue = Number(bgDimParam);
      scene.backgroundIntensity =
        bgDimParam !== null && bgDimParam.trim() !== "" && Number.isFinite(bgDimValue)
          ? THREE.MathUtils.clamp(bgDimValue, 0, 1)
          : 1;

    },
    undefined,
    (error) => {
      console.error("LAISE: falha ao carregar o fundo da floresta.", error);
    }
  );
}



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

// R12 visual-depth test. The existing orthographic camera remains the default.
// Perspective makes near and far terrain project at different apparent sizes;
// audio physics, lighting constants, and bloom settings are unchanged.
const perspectiveDepthEnabledR12 =
  new URLSearchParams(window.location.search).get("depth") === "perspective";
document.documentElement.classList.toggle("perspective-depth-r12", perspectiveDepthEnabledR12);
const horizontalPoseEnabledR12 = perspectiveDepthEnabledR12 &&
  new URLSearchParams(window.location.search).get("flat") === "1";
const presentationYawR12 = horizontalPoseEnabledR12 ? 0 : BASE_POSE.yaw;
const fullSpanEnabledR12 = perspectiveDepthEnabledR12 &&
  new URLSearchParams(window.location.search).get("span") === "1";
const visibleEdgesEnabledR12 = perspectiveDepthEnabledR12 &&
  new URLSearchParams(window.location.search).get("edges") === "1";
const wideCoverageEnabledR12 = perspectiveDepthEnabledR12 &&
  new URLSearchParams(window.location.search).get("fill") === "1";
const camera = perspectiveDepthEnabledR12
  ? new THREE.PerspectiveCamera(38,
      window.innerWidth / window.innerHeight, 0.1, 500)
  : new THREE.OrthographicCamera(
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
  if (camera.isOrthographicCamera) {
    camera.left = -CAMERA.span * width / height / 2;
    camera.right = CAMERA.span * width / height / 2;
    camera.top = CAMERA.span / 2;
    camera.bottom = -CAMERA.span / 2;
  } else {
    camera.aspect = width / height;
  }
  const margin = 8;
  const rect = selector => {
    const element = document.querySelector(selector);
    const bounds = element?.getBoundingClientRect();
    return bounds?.width && bounds?.height ? bounds : null;
  };
  const hudTop = rect(".hud")?.top ?? height * 0.88;
  const frontGap = Math.max(6, Math.min(width, height) * (8 / 1080));
  const frontTarget = perspectiveDepthEnabledR12
    ? height + height * (visibleEdgesEnabledR12 ? 0.02 : 0.23) + SCREEN_POSITION.vertical
    : hudTop - frontGap + SCREEN_POSITION.vertical;
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
  const envelope = perspectiveDepthEnabledR12
    ? [-TERRAIN.width / 2, TERRAIN.width / 2].flatMap(x =>
        [-TERRAIN.depth / 2, TERRAIN.depth / 2].flatMap(z =>
          [-TERRAIN.maxHeight, 12].map(y =>
            new THREE.Vector3(x, y, z).applyEuler(
              new THREE.Euler(BASE_POSE.pitch, presentationYawR12, BASE_POSE.roll)
            ).add(target))))
    : fieldEnvelope();
  const rotation = new THREE.Euler(BASE_POSE.pitch, presentationYawR12, BASE_POSE.roll);
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
  if (perspectiveDepthEnabledR12) {
    place(approvedZoom * (visibleEdgesEnabledR12 ? 1.25 : wideCoverageEnabledR12 ? 1.45 : 1.15));
    if (visibleEdgesEnabledR12) {
      // Open only the horizontal field of view. Camera distance, vertical
      // projection, musical displacement, and lighting remain unchanged.
      camera.projectionMatrix.elements[0] *= fullSpanEnabledR12 && horizontalPoseEnabledR12 ? 1.38 : 0.80;
      camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    }
    return;
  }
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

/*
  R7C-R6: camera-space key/fill, shared by the relief and wire shading.
  Camera local +X is screen right, +Y is up, +Z faces the observer.
  Both the lights AND their targets belong to the camera, so rotating or
  reframing it cannot change the apparent side of the illumination.
*/
const TERRAIN_LIGHTING = Object.freeze({
  keyIntensity: 4.4,
  fillIntensity: 0.20,
  ambientIntensity: 0.08,
  surfaceAlbedo: 0.26,
  wireShadow: 0.10,
  wireKey: 4.6,
  wireFill: 0.08,
  wireRim: 4.8,
  peakBoost: 1.0,
  surfaceLight: 0.50,
  surfacePeakLight: 1.20,
  bloomBase: NEON_R8A.neonBloomStrength,
  bloomEnergy: 0.04,
  bloomRadius: 0.0,
  bloomThreshold: NEON_R8A.neonBloomThreshold
});

const terrainHemisphereLight = new THREE.HemisphereLight(
  0xfff4e8, 0x101522, TERRAIN_LIGHTING.ambientIntensity
);
scene.add(terrainHemisphereLight);

const terrainKeyLight = new THREE.DirectionalLight(
  0xfff2d8, TERRAIN_LIGHTING.keyIntensity
);
const terrainFillLight = new THREE.DirectionalLight(
  0xd5e6ff, TERRAIN_LIGHTING.fillIntensity
);

terrainKeyLight.target.position.set(0, 0, -CAMERA.distance);
terrainFillLight.target.position.copy(terrainKeyLight.target.position);
terrainKeyLight.position.copy(terrainKeyLight.target.position)
  .add(new THREE.Vector3(-0.72, 0.62, 0.42).normalize().multiplyScalar(20));
terrainFillLight.position.copy(terrainFillLight.target.position)
  .add(new THREE.Vector3(0.72, 0.18, 0.50).normalize().multiplyScalar(20));
camera.add(terrainKeyLight, terrainKeyLight.target,
  terrainFillLight, terrainFillLight.target);
scene.add(camera);

// A quiet reference edge behind the terrain: the foreground mesh can cross it.
// Opt in with ?portal=1 for the billboard-like depth comparison.
const portalFrameEnabledR12 = perspectiveDepthEnabledR12 &&
  new URLSearchParams(window.location.search).get("portal") === "1";
const portalFrameR12 = portalFrameEnabledR12
  ? new THREE.LineSegments(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({
        color: 0x87b9c3, transparent: true, opacity: 0.27,
        depthTest: true, depthWrite: false, toneMapped: false
      })
    )
  : null;
function resizePortalFrameR12() {
  if (!portalFrameR12) return;
  const distance = 75;
  const halfHeight = Math.tan(THREE.MathUtils.degToRad(19)) *
    distance / Math.max(0.001, camera.zoom);
  const halfWidth = halfHeight * camera.aspect;
  const x = halfWidth * 0.73, y = halfHeight * 0.66;
  portalFrameR12.geometry.dispose();
  portalFrameR12.geometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-x, y, -distance), new THREE.Vector3(x, y, -distance),
    new THREE.Vector3(x, y, -distance), new THREE.Vector3(x, -y, -distance),
    new THREE.Vector3(x, -y, -distance), new THREE.Vector3(-x, -y, -distance),
    new THREE.Vector3(-x, -y, -distance), new THREE.Vector3(-x, y, -distance)
  ]);
}
if (portalFrameR12) {
  camera.add(portalFrameR12);
  resizePortalFrameR12();
  window.addEventListener("resize", () => requestAnimationFrame(resizePortalFrameR12));
}


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

// R12 rounded tips: smooth only the tallest visible crest geometry.
// Audio, propagation, color spin, and lighting inputs remain unchanged.
const roundedTipsEnabledR12 = new URLSearchParams(window.location.search).get("roundtips") === "1";
const sustainedSwayEnabledR12 = roundedTipsEnabledR12 &&
  new URLSearchParams(window.location.search).get("sway") === "1";
const roundedTipBufferR12 = roundedTipsEnabledR12 ? new Float32Array(positions.count) : null;
const originalLightHeightsR12 = roundedTipsEnabledR12 ? new Float32Array(positions.count) : null;
const originalLightNormalsR12 = roundedTipsEnabledR12 ?
  new Float32Array(geometry.attributes.normal.array.length) : null;
const roundedTipRadiusR12 = 9;
const roundedTipKernelR12 = Array.from(
  { length: 2 * roundedTipRadiusR12 + 1 },
  (_, i) => Math.exp(-0.5 * ((i - roundedTipRadiusR12) / 3.0) ** 2)
);
const roundedTipKernelSumR12 = roundedTipKernelR12.reduce((a, b) => a + b, 0);
function roundVisibleTipsR12() {
  const vertexHeights = positions.array;
  const columns = SEG_X + 1;
  const rows = SEG_Z + 1;
  // A wider Gaussian rounds the overall crown, including clustered attacks.
  // Filtering is display-only; the simulated field is unchanged.
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < columns; col++) {
      let sum = 0;
      for (let k = -roundedTipRadiusR12; k <= roundedTipRadiusR12; k++) {
        const sample = Math.max(0, Math.min(columns - 1, col + k));
        sum += roundedTipKernelR12[k + roundedTipRadiusR12] *
          vertexHeights[(row * columns + sample) * 3 + 1];
      }
      roundedTipBufferR12[row * columns + col] = sum / roundedTipKernelSumR12;
    }
  }
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < columns; col++) {
      const index = row * columns + col;
      const original = vertexHeights[index * 3 + 1];
      let sum = 0;
      for (let k = -roundedTipRadiusR12; k <= roundedTipRadiusR12; k++) {
        const sample = Math.max(0, Math.min(rows - 1, row + k));
        sum += roundedTipKernelR12[k + roundedTipRadiusR12] *
          roundedTipBufferR12[sample * columns + col];
      }
      const rounded = sum / roundedTipKernelSumR12;
      // Smooth only protruding crowns. The lower slopes, troughs and
      // small beat-driven ripples keep their full original movement.
      const heightT = Math.max(0, Math.min(1, (original - 1.0) / 1.0));
      const prominenceT = Math.max(0, Math.min(1, (original - rounded - 0.04) / 0.34));
      const heightGate = heightT * heightT * (3 - 2 * heightT);
      const prominenceGate = prominenceT * prominenceT * (3 - 2 * prominenceT);
      const blend = 0.95 * heightGate * prominenceGate;
      vertexHeights[index * 3 + 1] = original + (rounded - original) * blend;
    }
  }
}



const colors =
  new Float32Array(
    positions.count * 3
  );


/*
  R7C ? CONTINUOUS GOLDEN SPECTRUM

  One continuous chromatic surface.

  There are no warm/cool halves and no central seam.

  Gold has the largest visual territory, then gradually
  evolves through coral, magenta, violet, cyan and blue.

  Position / propagation remain physical.
  Color is presentation only.
*/

const originalSpectrumStops = [

  {
    t: 0.00,
    color: new THREE.Color(0x587cff)
  },

  {
    t: 0.14,
    color: new THREE.Color(0x8a60ed)
  },

  {
    t: 0.27,
    color: new THREE.Color(0xd34bc4)
  },

  {
    t: 0.34,
    color: new THREE.Color(0xd66762)
  },

  /*
    R7C-R2 GOLDEN CENTER

    The perceptual center deliberately receives the
    largest warm luminous territory.

    Important musical mountains therefore tend to appear
    golden rather than predominantly red.
  */

  {
    t: 0.52,
    color: new THREE.Color(0xe3a642)
  },

  {
    t: 0.58,
    color: new THREE.Color(0xf0bd4f)
  },

  {
    t: 0.67,
    color: new THREE.Color(0xdaa344)
  },

  /*
    R8A.5 ? GOLD -> GREEN -> CYAN -> BLUE

    The green intermediate preserves chroma and avoids
    the pale neutral band perceived in R8A.4.

    All color stops remain spatially fixed and continuous.
    Musical geometry, lighting and neon emission are unchanged.
  */

  {
    t: 0.72,
    color: new THREE.Color(0xa7c74c)
  },

  {
    t: 0.78,
    color: new THREE.Color(0x45ce69)
  },

  {
    t: 0.84,
    color: new THREE.Color(0x19c8a0)
  },

  {
    t: 0.90,
    color: new THREE.Color(0x24e0d1)
  },

  {
    t: 1.00,
    color: new THREE.Color(0x298fe8)
  }

];

// LAISE_R8C_FOREST_PALETTE
// Default: forest palette. Use ?palette=original for comparison.
// Emission, bloom, exposure and terrain behavior are unchanged.
const forestPaletteColors = [
  0xf2b858, // warm gold
  0xf28a78, // coral
  0xe95dbb, // pink
  0xc260e8, // violet
  0x854fe9, // purple
  0x605fe9, // blue-violet
  0x3d7df0, // blue
  0x278fe9, // blue
  0x1ba8ed, // bright blue
  0x1fc6ed, // cyan-blue
  0x35d7dc, // cyan
  0x338fe2  // blue
];

// LAISE_R8C_PALETTE_V2
// Keep the previous forest palette for ?palette=forest1.
const forestPaletteV1 = forestPaletteColors.slice();

const paletteChoiceR8C =
  new URLSearchParams(window.location.search).get("palette");

if (paletteChoiceR8C !== "forest1" && paletteChoiceR8C !== "original") {
  // Only the two central color stops change.
  forestPaletteColors[4] = 0x713de8;
  forestPaletteColors[5] = 0x4d48ef;
}

const forestPaletteEnabled =
  new URLSearchParams(window.location.search).get("palette") !== "original";

const spectrumStops = forestPaletteEnabled
  ? originalSpectrumStops.map((stop, index) => ({
      t: stop.t,
      color: new THREE.Color(forestPaletteColors[index])
    }))
  : originalSpectrumStops;



const observerColorCos =
  Math.cos(
    BASE_POSE.yaw
  );

const observerColorSin =
  Math.sin(
    BASE_POSE.yaw
  );


const observerColorHalfSpan =
  TERRAIN.width / 2 *
    Math.abs(observerColorCos) +
  TERRAIN.depth / 2 *
    Math.abs(observerColorSin);


/*
  Quintic smootherstep.

  Besides color continuity, the RATE of chromatic change
  also approaches zero at each palette control point.

  That prevents a visible chromatic seam.
*/

function spectrumSmootherStep(value) {

  const u =
    THREE.MathUtils.clamp(
      value,
      0,
      1
    );

  return (
    u * u * u *
    (
      u *
      (
        u * 6 - 15
      ) +
      10
    )
  );
}


function continuousSpectrumColor(
  t,
  target
) {

  // R8A.8: Continuous interpolation with no per-stop
  // smootherstep plateaus. This avoids visible color bands.
  //
  // Catmull-Rom/Hermite interpolation with bounded tangents:
  // preserves continuous first derivatives and avoids
  // overshooting RGB endpoints.

  const first = spectrumStops[0];
  const last = spectrumStops[spectrumStops.length - 1];

  if (t <= first.t) {
    return target.copy(first.color);
  }

  if (t >= last.t) {
    return target.copy(last.color);
  }

  for (let i = 0; i < spectrumStops.length - 1; i++) {

    const a = spectrumStops[i];
    const b = spectrumStops[i + 1];

    if (t < a.t || t > b.t) continue;

    const before = spectrumStops[Math.max(0, i - 1)];
    const after = spectrumStops[
      Math.min(spectrumStops.length - 1, i + 2)
    ];

    const span = b.t - a.t;
    const u = (t - a.t) / span;

    const u2 = u * u;
    const u3 = u2 * u;

    const h00 = 2 * u3 - 3 * u2 + 1;
    const h10 = u3 - 2 * u2 + u;
    const h01 = -2 * u3 + 3 * u2;
    const h11 = u3 - u2;

    const interpolateChannel = (key) => {

      const y0 = a.color[key];
      const y1 = b.color[key];

      const secant = (y1 - y0) / span;

      const leftSpan = b.t - before.t;
      const rightSpan = after.t - a.t;

      let m0 = leftSpan > 0
        ? (b.color[key] - before.color[key]) / leftSpan
        : secant;

      let m1 = rightSpan > 0
        ? (after.color[key] - a.color[key]) / rightSpan
        : secant;

      // A monotonic channel must not overshoot its endpoints.
      if (Math.abs(secant) < 1e-10) {
        m0 = 0;
        m1 = 0;
      } else {
        if (m0 * secant <= 0) m0 = 0;
        if (m1 * secant <= 0) m1 = 0;

        const alpha = m0 / secant;
        const beta = m1 / secant;
        const norm = alpha * alpha + beta * beta;

        if (norm > 9) {
          const scale = 3 / Math.sqrt(norm);
          m0 *= scale;
          m1 *= scale;
        }
      }

      const value =
        h00 * y0 +
        h10 * span * m0 +
        h01 * y1 +
        h11 * span * m1;

      return THREE.MathUtils.clamp(
        value,
        Math.min(y0, y1),
        Math.max(y0, y1)
      );
    };

    return target.setRGB(
      interpolateChannel("r"),
      interpolateChannel("g"),
      interpolateChannel("b"),
      THREE.LinearSRGBColorSpace
    );
  }

  return target.copy(last.color);
}


const spectrumColor =
  new THREE.Color();


for (
  let i = 0;
  i < positions.count;
  i++
) {

  const x =
    basePositions[
      i * 3
    ];

  const z =
    basePositions[
      i * 3 + 2
    ];


  /*
    Horizontal axis as perceived by the observer.

    The terrain can remain yawed 45 degrees while
    the chromatic progression remains visually ordered.
  */

  const observerX =
    x * observerColorCos +
    z * observerColorSin;


  const t =
    THREE.MathUtils.clamp(
      (
        observerX +
        observerColorHalfSpan
      ) /
      (
        2 *
        observerColorHalfSpan
      ),
      0,
      1
    );


  continuousSpectrumColor(
    t,
    spectrumColor
  );


  colors[
    i * 3
  ] =
    spectrumColor.r;

  colors[
    i * 3 + 1
  ] =
    spectrumColor.g;

  colors[
    i * 3 + 2
  ] =
    spectrumColor.b;
}


geometry.setAttribute(
  "color",
  new THREE.BufferAttribute(
    colors,
    3
  )
);


/*
  R7C-R2 ? IMMUTABLE CHROMATIC BASE

  Runtime light/shadow modifies only the displayed color.
  This copy preserves the original spectrum.
*/

const baseSpectrumColors =
  new Float32Array(
    colors
  );

// R12 color-only rotation: retain the approved gradient and its lighting.
const colorSpinEnabledR12 = perspectiveDepthEnabledR12 &&
  new URLSearchParams(window.location.search).get("colorspin") !== "0";
const colorSpinLookupR12 = colorSpinEnabledR12
  ? Array.from({ length: 1025 }, (_, index) =>
      continuousSpectrumColor(index / 1024, new THREE.Color()).clone())
  : null;
let colorSpinElapsedR12 = 0;
function updateColorSpinR12(delta) {
  if (!colorSpinLookupR12) return;
  if (!audio.paused && !audio.seeking && !audio.ended) {
    colorSpinElapsedR12 += delta;
  }
  const angle = horizontalRotationOffsetR10(colorSpinElapsedR12);
  const axisX = Math.cos(BASE_POSE.yaw + angle);
  const axisZ = Math.sin(BASE_POSE.yaw + angle);
  terrainSpectrumAxis.set(axisX, axisZ);
  const inverseSpan = 1 / (2 * observerColorHalfSpan);
  for (let i = 0; i < positions.count; i++) {
    const offset = i * 3;
    const t = THREE.MathUtils.clamp(
      (basePositions[offset] * axisX +
        basePositions[offset + 2] * axisZ + observerColorHalfSpan) *
        inverseSpan, 0, 1);
    const sample = colorSpinLookupR12[Math.round(t * 1024)];
    baseSpectrumColors[offset] = sample.r;
    baseSpectrumColors[offset + 1] = sample.g;
    baseSpectrumColors[offset + 2] = sample.b;
  }
  geometry.attributes.color.needsUpdate = true;
}



// R7C-R6: immutable palette and shared position/normal buffers. The surface
// and its lines now shade the SAME visible slope, without CPU recoloring.
geometry.setAttribute("color", new THREE.BufferAttribute(baseSpectrumColors, 3));
// R9.3: optional, short attack contours independent of the terrain height.
const attackAccentR93 = new THREE.BufferAttribute(
  new Float32Array((SEG_X + 1) * (SEG_Z + 1)), 1
);
attackAccentR93.setUsage(THREE.DynamicDrawUsage);
geometry.setAttribute("attackAccent", attackAccentR93);
// Lighting retains the original unsmoothed slopes while geometry can round.
const lightingNormalR12 = new THREE.BufferAttribute(
  new Float32Array(geometry.attributes.normal.array.length), 3
);
lightingNormalR12.setUsage(THREE.DynamicDrawUsage);
geometry.setAttribute("lightingNormal", lightingNormalR12);
const wireGeometry = new THREE.BufferGeometry();
wireGeometry.setIndex(geometry.index);
wireGeometry.setAttribute("position", positions);
wireGeometry.setAttribute("normal", geometry.attributes.normal);
wireGeometry.setAttribute("color", geometry.attributes.color);
wireGeometry.setAttribute("attackAccent", attackAccentR93);
wireGeometry.setAttribute("lightingNormal", lightingNormalR12);

const updateNeonCurvature = createNeonCurvatureR8A(
  geometry, wireGeometry, SEG_X, SEG_Z, TERRAIN.width, TERRAIN.depth
);

const wireLightDirection = new THREE.Vector3();
const wireFillDirection = new THREE.Vector3();
const wireViewLightDirection = new THREE.Vector3();
const wireViewFillDirection = new THREE.Vector3();
const wireViewUpDirection = new THREE.Vector3();
const inverseTerrainMatrix = new THREE.Matrix4();
const lightWorldPosition = new THREE.Vector3();
const lightWorldTarget = new THREE.Vector3();

function updateTerrainLighting() {
  camera.updateWorldMatrix(true, true);
  terrainRig.updateWorldMatrix(true, false);
  inverseTerrainMatrix.copy(terrainRig.matrixWorld).invert();
  const localDirection = (light, direction) => {
    light.getWorldPosition(lightWorldPosition);
    light.target.getWorldPosition(lightWorldTarget);
    direction.subVectors(lightWorldPosition, lightWorldTarget)
      .transformDirection(inverseTerrainMatrix);
  };
  localDirection(terrainKeyLight, wireLightDirection);
  localDirection(terrainFillLight, wireFillDirection);
  // The shader normalMatrix produces VIEW-space normals. Transform the key
  // and fill to that same space; camera-local illumination remains stable.
  wireViewLightDirection.copy(wireLightDirection)
    .transformDirection(terrainRig.matrixWorld)
    .transformDirection(camera.matrixWorldInverse);
  wireViewFillDirection.copy(wireFillDirection)
    .transformDirection(terrainRig.matrixWorld)
    .transformDirection(camera.matrixWorldInverse);
  wireViewUpDirection.set(0, 1, 0)
    .transformDirection(terrainRig.matrixWorld)
    .transformDirection(camera.matrixWorldInverse);
}


/*
  One depth-tested, directionally luminous wireframe replaces the former
  unlit CPU-tinted lines plus displaced additive duplicate. The shadow floor
  is deliberately weak. Rim light is gated by the KEY response, so a dark
  slope never gains a view-only emissive contour that would erase its shade.
*/
// Presentation grade only: preserve the palette's dominant channel while
// strengthening its chroma, rather than diluting lit colors toward white.
// The palette and the gold enhancement use the SAME observer-space axis.
// A broad spatial blend avoids a hue-threshold band at the red/gold boundary.
const terrainSpectrumAxis = new THREE.Vector2(observerColorCos, observerColorSin);
const terrainColorGLSL = `
  vec3 vividTerrainColor(vec3 source, float spectrumT) {
    float peak = max(max(source.r, source.g), source.b);
    vec3 chroma = clamp(source / max(peak, 0.0001), 0.0, 1.0);
    vec3 vivid = pow(chroma, vec3(1.40));
    // Let red, orange and gold overlap across a wide part of the field.
    // The central gold retains its full gain; the cool side fades gently.
    float gold = smoothstep(0.32, 0.56, spectrumT)
      * (1.0 - smoothstep(0.62, 0.71, spectrumT));
    // More yellow-gold, less copper: lift green relative to dominant red,
    // retain low blue for saturation, and give gold a modest luminous gain.
    // LAISE_R8C_COLOR_GRADE_TEST
    // Original palette or ?grade=legacy: preserve the previous gold grading.
    // Forest palette: let the selected blue/violet colors remain authoritative.
    ${
      (!forestPaletteEnabled ||
        new URLSearchParams(window.location.search).get("grade") === "legacy")
        ? `vivid.g = mix(vivid.g, max(vivid.g, 0.72), gold * 0.90);
           vivid.b *= 1.0 - 0.20 * gold;`
        : ""
    }
    return vivid * peak * (1.0 + 0.15 * gold);
  }
  float terrainPeakLight(float height) {
    return smoothstep(1.5, 6.5, max(height, 0.0));
  }
`;

const terrainMaterial = new THREE.ShaderMaterial({
  vertexColors: true,
  wireframe: true,
  side: THREE.DoubleSide,
  transparent: false,
  depthTest: true,
  depthWrite: false,
  // Global atmospheric fog suppressed the old lines while the projected
  // layer bypassed it. Both terrain materials now use the same clear medium.
  fog: false,
  uniforms: {
    uKeyDirection: { value: wireViewLightDirection },
    uFillDirection: { value: wireViewFillDirection },
    uTerrainUp: { value: wireViewUpDirection },
    uOrthographic: { value: camera.isOrthographicCamera },
    uSpectrumAxis: { value: terrainSpectrumAxis },
    uSpectrumHalfSpan: { value: observerColorHalfSpan },
    uShadow: { value: TERRAIN_LIGHTING.wireShadow },
    uKey: { value: TERRAIN_LIGHTING.wireKey },
    uFill: { value: TERRAIN_LIGHTING.wireFill },
    uRim: { value: TERRAIN_LIGHTING.wireRim },
    uPeakBoost: { value: TERRAIN_LIGHTING.peakBoost },
    ...neonUniformsR8A
  },
  vertexShader: `
    attribute float attackAccent;
    varying float vAttackAccent;
    attribute float neonCurvature;
    attribute vec3 neonNormal;
    attribute vec3 lightingNormal;
    varying float vNeonCurvature;
    varying vec3 vNeonViewNormal;
    varying vec3 vViewNormal;
    varying vec3 vViewPosition;
    varying vec3 vSpectrum;
    varying float vTerrainHeight;
    varying float vSpectrumT;
    uniform vec2 uSpectrumAxis;
    uniform float uSpectrumHalfSpan;
    void main() {
      vAttackAccent = attackAccent;
      vNeonCurvature = neonCurvature;
      vNeonViewNormal = normalMatrix * neonNormal;
      vTerrainHeight = position.y;
      vSpectrumT = (dot(position.xz, uSpectrumAxis) + uSpectrumHalfSpan)
        / (2.0 * uSpectrumHalfSpan);
      vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
      vViewNormal = normalMatrix * lightingNormal;
      vViewPosition = -mvPosition.xyz;
      vSpectrum = color;
      gl_Position = projectionMatrix * mvPosition;
    }
  `,
  fragmentShader: `
    varying float vAttackAccent;
    uniform vec3 uKeyDirection;
    uniform vec3 uFillDirection;
    uniform vec3 uTerrainUp;
    uniform bool uOrthographic;
    uniform float uShadow;
    uniform float uKey;
    uniform float uFill;
    uniform float uRim;
    uniform float uPeakBoost;
    varying float vTerrainHeight;
    varying float vSpectrumT;
    ${terrainColorGLSL}
    ${neonEmissionGLSL}
    varying vec3 vViewNormal;
    varying vec3 vViewPosition;
    varying vec3 vSpectrum;
    void main() {
      vec3 viewDirection = uOrthographic ? vec3(0.0, 0.0, 1.0)
        : normalize(vViewPosition);
      vec3 faceNormal = normalize(vViewNormal);
      // Wireframe primitives are lines: gl_FrontFacing cannot orient their
      // normals. Face them toward the observer, matching the visible side
      // of the depth-writing, double-sided relief beneath them.
      if (dot(faceNormal, viewDirection) < 0.0) faceNormal = -faceNormal;
      float keyFacing = max(dot(faceNormal, uKeyDirection), 0.0);
      float key = pow(smoothstep(0.35, 0.98, keyFacing), 2.6);
      float fill = max(dot(faceNormal, uFillDirection), 0.0);
      // The camera looks across a shallow plane: Fresnel alone would also
      // light the entire flat base. Gate the rim by actual terrain slope.
      float slope = 1.0 - abs(dot(faceNormal, uTerrainUp));
      float rim = pow(1.0 - max(dot(faceNormal, viewDirection), 0.0), 2.8)
        * smoothstep(0.02, 0.40, slope);
      float litRim = rim * smoothstep(0.12, 0.85, keyFacing);
      // Actual musical height accents only the lit contribution. Shadows
      // keep their existing floor; no displacement or physical drive changes.
      float peakGain = 1.0 + uPeakBoost * terrainPeakLight(vTerrainHeight);
      float radiance = uShadow + uFill * fill
        + (uKey * key + uRim * litRim) * peakGain;
      // Reflected color and selective linear HDR emission remain independent.
      // Only locally convex, favorably lit regions approach a white-hot core.
      // Tone mapping and sRGB output remain in the existing final OutputPass.
      vec3 chromaticBase = vividTerrainColor(vSpectrum, vSpectrumT);
      vec3 emission = r8aNeonEmission(chromaticBase, vSpectrumT,
        faceNormal, uTerrainUp, uKeyDirection);
      // A brief chromatic crest marks each recorded onset on the same mesh.
      gl_FragColor = vec4(chromaticBase * radiance + emission
        + chromaticBase * (0.55 * vAttackAccent), 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }
  `
});


const terrain =
  new THREE.Mesh(
    wireGeometry,
    terrainMaterial
  );


// V1.3C may deform beyond the legacy framing envelope.
terrain.frustumCulled = false;


/*
  R7A ? SHADED RELIEF SURFACE

  Same geometry, same deformation, same vertex colors.

  This surface does not create another wave.
  It only makes the existing geometry readable through
  light and shade.
*/

// A depth-writing surface prevents bright hidden slopes and rear wire
// segments from washing over a shadow-facing foreground slope.
const reliefSurfaceMaterial = new THREE.MeshStandardMaterial({
  vertexColors: true,
  color: new THREE.Color().setScalar(TERRAIN_LIGHTING.surfaceAlbedo),
  side: THREE.DoubleSide,
  transparent: false,
  opacity: 1.0,
  roughness: 0.72,
  metalness: 0.0,
  fog: false,
  depthTest: true,
  depthWrite: true,
  polygonOffset: true,
  polygonOffsetFactor: 1,
  polygonOffsetUnits: 1
});


// Keep the solid body chromatic as well as the lines. This replaces no
// normals or lighting model: the Standard shader still supplies its live
// view-space normal, occlusion, key/fill and depth behavior.
reliefSurfaceMaterial.onBeforeCompile = shader => {
  Object.assign(shader.uniforms, neonUniformsR8A);
  shader.uniforms.uTerrainUp = { value: wireViewUpDirection };
  shader.uniforms.uR8A10SurfaceAlbedo = {
    value: TERRAIN_LIGHTING.surfaceAlbedo
  };
  shader.uniforms.uTerrainKeyDirection = { value: wireViewLightDirection };
  shader.uniforms.uSpectrumAxis = { value: terrainSpectrumAxis };
  shader.uniforms.uSpectrumHalfSpan = { value: observerColorHalfSpan };
  shader.uniforms.uTerrainSurfaceLight = { value: TERRAIN_LIGHTING.surfaceLight };
  shader.uniforms.uTerrainSurfacePeakLight = { value: TERRAIN_LIGHTING.surfacePeakLight };
  shader.vertexShader = `
    attribute float attackAccent;
    varying float vAttackAccent;
    attribute float neonCurvature;
    attribute vec3 neonNormal;
    varying float vNeonCurvature;
    varying vec3 vNeonViewNormal;
    varying float vTerrainHeight;
    varying float vSpectrumT;
    varying vec3 vR8A10Spectrum;
    uniform vec2 uSpectrumAxis;
    uniform float uSpectrumHalfSpan;
  ` + shader.vertexShader;
  shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>",
    `#include <begin_vertex>
    vAttackAccent = attackAccent;
    vNeonCurvature = neonCurvature;
    vNeonViewNormal = normalMatrix * neonNormal;
    vTerrainHeight = position.y;
    vR8A10Spectrum = color;
    vSpectrumT = (dot(position.xz, uSpectrumAxis) + uSpectrumHalfSpan)
      / (2.0 * uSpectrumHalfSpan);`);
  shader.fragmentShader = `
    varying float vAttackAccent;
    varying float vTerrainHeight;
    varying float vSpectrumT;
    varying vec3 vR8A10Spectrum;
    uniform float uR8A10SurfaceAlbedo;
    uniform vec3 uTerrainKeyDirection;
    uniform vec3 uTerrainUp;
    uniform float uTerrainSurfaceLight;
    uniform float uTerrainSurfacePeakLight;
    ${terrainColorGLSL}
    ${neonEmissionGLSL}
  ` + shader.fragmentShader;
  shader.fragmentShader = shader.fragmentShader.replace("#include <color_fragment>",
    "#include <color_fragment>\ndiffuseColor.rgb = vividTerrainColor(vR8A10Spectrum, vSpectrumT) * uR8A10SurfaceAlbedo;");
  shader.fragmentShader = shader.fragmentShader.replace("#include <emissivemap_fragment>", `
    #include <emissivemap_fragment>
    float litFace = pow(smoothstep(0.18, 0.95,
      max(dot(normal, uTerrainKeyDirection), 0.0)), 1.4);
    totalEmissiveRadiance += diffuseColor.rgb * litFace
      * (uTerrainSurfaceLight + uTerrainSurfacePeakLight * terrainPeakLight(vTerrainHeight));
    totalEmissiveRadiance += ${NEON_R8A.surfaceEmissionFraction.toFixed(4)}
      * r8aNeonEmission(diffuseColor.rgb, vSpectrumT,
        normal, uTerrainUp, uTerrainKeyDirection);
    totalEmissiveRadiance += diffuseColor.rgb * (0.16 * vAttackAccent);
  `);
};
reliefSurfaceMaterial.customProgramCacheKey = () => "r8a-hdr-neon-emission-v2";

const reliefSurface =
  new THREE.Mesh(
    geometry,
    reliefSurfaceMaterial
  );


reliefSurface.frustumCulled =
  false;

reliefSurface.renderOrder =
  0;

terrain.renderOrder =
  1;

const terrainRig = new THREE.Group();
terrainRig.position.set(0, BASE_POSE.y, 0);
terrainRig.rotation.set(BASE_POSE.pitch, presentationYawR12, BASE_POSE.roll);
terrainRig.scale.set(1, 1, 1);
// R10: approved full horizontal turn, one revolution per two minutes
// of playback. ?rotate=0 restores the fixed pose for comparison.
const horizontalRotationEnabledR10 = !colorSpinEnabledR12 &&
  new URLSearchParams(window.location.search).get("rotate") !== "0";
let horizontalRotationElapsedR10 = 0;
function horizontalRotationOffsetR10(seconds) {
  return seconds * (2 * Math.PI / 120);
}
terrainRig.add(
  reliefSurface
);

terrainRig.add(
  terrain
);

scene.add(
  terrainRig
);

// LAISE_R8C_EDGE_GLOW_TEST
// Experimental perimeter light: enabled only with ?edge=1.
// Positions and colors are shared with the existing animated terrain.
const edgeGlowEnabledR8C =
  new URLSearchParams(window.location.search).get("edge") === "1";

if (edgeGlowEnabledR8C) {
  // LAISE_R8C_EDGE_UNIFORM_TEST
  // ?edgeuniform=0 restores the previous edge color intensity.
  const edgeUniformR8C =
    new URLSearchParams(window.location.search).get("edgeuniform") !== "0";

  // LAISE_R8C_EDGE_POWER_TEST
  // Previous intensity: ?edge=1&edgepower=2.4
  const edgePowerParamR8C =
    new URLSearchParams(window.location.search).get("edgepower");
  const parsedEdgePowerR8C = Number(edgePowerParamR8C);
  const edgeGlowPowerR8C =
    edgePowerParamR8C !== null &&
    edgePowerParamR8C.trim() !== "" &&
    Number.isFinite(parsedEdgePowerR8C)
      ? THREE.MathUtils.clamp(parsedEdgePowerR8C, 0, 12)
      : 8.0;

  const columns = SEG_X + 1;
  const rows = SEG_Z + 1;
  const expectedVertices = columns * rows;

  if (positions.count !== expectedVertices) {
    console.error(
      "LAISE edge test disabled: unexpected terrain vertex count.",
      positions.count,
      expectedVertices
    );
  } else {
    const edgeIndices = [];

    // Horizontal boundaries.
    for (let col = 0; col < SEG_X; col++) {
      edgeIndices.push(col, col + 1);

      const lastRow = (rows - 1) * columns;
      edgeIndices.push(lastRow + col, lastRow + col + 1);
    }

    // Vertical boundaries.
    for (let row = 0; row < SEG_Z; row++) {
      edgeIndices.push(row * columns, (row + 1) * columns);
      edgeIndices.push(
        row * columns + SEG_X,
        (row + 1) * columns + SEG_X
      );
    }

    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setIndex(edgeIndices);
    edgeGeometry.setAttribute("position", positions);
    edgeGeometry.setAttribute("color", geometry.attributes.color);

    const edgeMaterial = new THREE.ShaderMaterial({
      vertexColors: true,
      transparent: false,
      depthTest: true,
      depthWrite: false,
      vertexShader: `
        varying vec3 vEdgeColor;

        void main() {
          vEdgeColor = color;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vEdgeColor;

        void main() {
          // HDR color feeds the existing post-processing pipeline.
          // Preserve hue while equalizing the strongest color channel.
          vec3 edgeHue = vEdgeColor / max(
            max(max(vEdgeColor.r, vEdgeColor.g), vEdgeColor.b),
            0.0001
          );
          vec3 edgeOutput = ${edgeUniformR8C ? "edgeHue" : "vEdgeColor"};
          gl_FragColor = vec4(
            edgeOutput * ${edgeGlowPowerR8C.toFixed(2)},
            1.0
          );
        }
      `
    });

    const edgeGlow = new THREE.LineSegments(edgeGeometry, edgeMaterial);
    edgeGlow.name = "LAISE_R8C_EDGE_GLOW_TEST";
    edgeGlow.frustumCulled = false;
    edgeGlow.renderOrder = 2;

    // LAISE_R8C_EDGE_CORE_OPTION
    // The intense experimental line is off by default.
    // ?edgecore=1 restores it for comparison.
    const edgeCoreEnabledR8C =
      new URLSearchParams(window.location.search).get("edgecore") === "1";

    if (edgeCoreEnabledR8C) {
      terrainRig.add(edgeGlow);
    }


    // LAISE_R8C_EDGE_HALO_TEST
    // Default with ?edge=1: halo enabled.
    // Use ?edge=1&edgehalo=0 to compare with the previous line.
    const edgeHaloEnabledR8C =
      new URLSearchParams(window.location.search).get("edgehalo") !== "0";

    if (edgeHaloEnabledR8C) {
      // LAISE_R8C_HALO_STRENGTH_TEST
      // ?halostrength=0.15 restores the previous halo strength.
      const haloStrengthParamR8C =
        new URLSearchParams(window.location.search).get("halostrength");

      const haloStrengthValueR8C = Number(haloStrengthParamR8C);

      const haloStrengthR8C =
        haloStrengthParamR8C !== null &&
        haloStrengthParamR8C.trim() !== "" &&
        Number.isFinite(haloStrengthValueR8C)
          ? THREE.MathUtils.clamp(haloStrengthValueR8C, 0, 0.5)
          : 0.24;

      const haloGeometry = new THREE.BufferGeometry();

      // One point per unique perimeter vertex. The position and color
      // attributes are the same buffers used by the animated terrain.
      const uniqueEdgeIndices = [...new Set(edgeIndices)];

      haloGeometry.setIndex(uniqueEdgeIndices);
      haloGeometry.setAttribute("position", positions);
      haloGeometry.setAttribute("color", geometry.attributes.color);

      const haloMaterial = new THREE.ShaderMaterial({
        vertexColors: true,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthTest: true,
        depthWrite: false,
        uniforms: {
          uHaloSize: {
            value: 18 * Math.min(window.devicePixelRatio || 1, 1.6)
          }
        },
        vertexShader: `
          uniform float uHaloSize;
          varying vec3 vHaloColor;

          void main() {
            float peak = max(max(color.r, color.g), color.b);
            vHaloColor = color / max(peak, 0.0001);

            gl_Position =
              projectionMatrix * modelViewMatrix * vec4(position, 1.0);

            gl_PointSize = uHaloSize;
          }
        `,
        fragmentShader: `
          varying vec3 vHaloColor;

          void main() {
            float distanceFromCenter = length(gl_PointCoord - vec2(0.5));
            if (distanceFromCenter >= 0.5) discard;

            float glow = 1.0 - smoothstep(0.0, 0.5, distanceFromCenter);
            glow = glow * glow;

            gl_FragColor = vec4(vHaloColor * 1.8, glow * ${haloStrengthR8C.toFixed(3)});
          }
        `
      });

      const edgeHalo = new THREE.Points(haloGeometry, haloMaterial);
      edgeHalo.name = "LAISE_R8C_EDGE_HALO_TEST";
      edgeHalo.frustumCulled = false;
      edgeHalo.renderOrder = 3;

      terrainRig.add(edgeHalo);

      console.info(
        "LAISE edge halo enabled:",
        uniqueEdgeIndices.length,
        "perimeter points"
      );
    }


    console.info(
      "LAISE edge test enabled:",
      edgeIndices.length / 2,
      "segments"
    );
  }
}


// R8B.3 - Real-time reflective floor.
// Query flag ?floor=0 disables the experiment without changing files.
const reflectiveFloorEnabled =
  new URLSearchParams(window.location.search).get("floor") === "1";

if (reflectiveFloorEnabled) {
  const reflectiveFloorR8B = createReflectiveFloorR8B({
    width: TERRAIN.width,
    depth: TERRAIN.depth,
    minimumTerrainY: BASE_POSE.y - TERRAIN.maxHeight
  });
  scene.add(reflectiveFloorR8B.floor);
}



// R7C-R6 removes the projectedGoldenLightSurface and the translated
// additive glowTerrain. Bloom now comes from the single lit wireframe;
// it cannot expose hidden geometry or blanket a whole shaded face.

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


// Decorative listener rings intentionally removed from
// the V1.3C visual composition.
rings.visible = false;

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

    TERRAIN_LIGHTING.bloomBase,
    TERRAIN_LIGHTING.bloomRadius,
    TERRAIN_LIGHTING.bloomThreshold

  );


// Favor the fine blur mip. The default broad mips spread luminous crests
// across neighboring dark slopes, undoing their directional contrast.
bloom.compositeMaterial.uniforms.bloomFactors.value = [1.0, 0.28, 0.06, 0.0, 0.0];
installNeonOpticsR8A(bloom);
composer.addPass(
  bloom
);
composer.addPass(new OutputPass());


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
// LAISE_R9_EVENT_DETAIL: independent, additive visual attack packets.
const eventWavesEnabledR9 = new URLSearchParams(window.location.search).get("events") === "1";
const articulationR92 = eventWavesEnabledR9 && new URLSearchParams(window.location.search).get("articulation") === "1";
const contoursR93 = eventWavesEnabledR9 &&
  new URLSearchParams(window.location.search).get("contours") === "1";
let eventWaveDetailR9 = null;
window.__LAISE_EVENT_WAVES__ = {
  get status() { return eventWaveDetailR9?.debug ?? { mode: "OFF", requested: eventWavesEnabledR9 }; }
};
for (const eventName of ["seeking", "seeked", "emptied"]) {
  audio.addEventListener(eventName, () => {
    eventWaveDetailR9?.seek(eventName === "emptied" ? 0 : audio.currentTime);
  });
}


// V1.3C is now the definitive visual behavior.
// No public V1.2/V1.3C mode selector remains.
const behaviorMode = "v13c";

/* =========================================================
   R6.4 ? SCULPTED PEAK ENVELOPE

   Physical field is never clipped.

   Up to 4.8:
     1:1 visual response.

   Above 4.8:
     progressive logarithmic containment.

   This keeps exceptional peaks visually dominant without
   allowing them to overwhelm the entire camera composition.
========================================================= */

const V13C_VISUAL_PEAK_KNEE = 4.8;
const V13C_VISUAL_PEAK_LOG_SCALE = 1.4;

function visualHeightV13C(
  physicalVisualHeight
) {

  const sign =
    Math.sign(
      physicalVisualHeight
    );

  const magnitude =
    Math.abs(
      physicalVisualHeight
    );


  if (
    magnitude <=
    V13C_VISUAL_PEAK_KNEE
  ) {

    return physicalVisualHeight;
  }


  const excess =
    magnitude -
    V13C_VISUAL_PEAK_KNEE;


  const contained =
    V13C_VISUAL_PEAK_KNEE +
    V13C_VISUAL_PEAK_LOG_SCALE *
    Math.log1p(
      excess /
      V13C_VISUAL_PEAK_LOG_SCALE
    );


  return (
    sign *
    contained
  );
}


let behaviorLoadError = null;


/* =========================================================
   V1.3C LIVE MUSICAL TELEMETRY

   Kept intentionally visible:
   - dominant causal source / anchor
   - physical drive
   - footprint
   - active continuous behaviors

   This is telemetry only. It never drives physics.
========================================================= */

const behaviorLabState =
  document.createElement("div");

behaviorLabState.id =
  "behaviorLabState";

behaviorLabState.setAttribute(
  "aria-live",
  "polite"
);


const statusPanel =
  document.querySelector(
    ".status"
  );


if (!statusPanel) {

  throw new Error(
    "V1.3C status HUD not found"
  );
}


statusPanel.appendChild(
  behaviorLabState
);


// Main visual title: stronger hierarchy without changing
// the dynamic ENERGY or musical telemetry below it.
const masterReactiveTitle =
  [...statusPanel.querySelectorAll("*")]
    .find(
      element =>
        element.textContent.trim() ===
        "MASTER REACTIVE TERRAIN"
    );

if (masterReactiveTitle) {
  masterReactiveTitle.classList.add(
    "v13c-master-reactive-title"
  );
}


const behaviorLabStyle =
  document.createElement("style");

behaviorLabStyle.textContent = `

  /* =====================================================
     V1.3C FINAL VISUAL HIERARCHY
  ===================================================== */

  .v13c-master-reactive-title {
    font-size: 18px !important;
    font-weight: 700 !important;
    letter-spacing: .12em !important;
    line-height: 1.15 !important;
  }


  /* Historical/static metadata remains in the project
     evidence, but no longer occupies the musical image. */

  .brand,
  .field-summary,
  .hud .metric,
  .release {
    display: none !important;
  }


  #behaviorLabState {
    margin-top: 12px;

    max-width: 520px;

    color: #7fd8b9;

    font-size: 12px;
    font-weight: 400;
    line-height: 1.6;
    letter-spacing: .10em;

    text-align: right;

    text-shadow:
      0 1px 4px #020706,
      0 0 12px rgba(69,199,159,.16);

    pointer-events: none;
  }

  #behaviorLabState .behavior-telemetry-row {
    display: grid;
    grid-template-columns: auto minmax(90px, auto);
    justify-content: end;
    column-gap: 18px;

    min-height: 20px;
    align-items: baseline;
  }

  #behaviorLabState .behavior-telemetry-label {
    color: #708f84;

    font-size: 10px;
    font-weight: 400;
    letter-spacing: .16em;
  }

  #behaviorLabState .behavior-telemetry-value {
    color: #7fd8b9;

    font-size: 13px;
    font-weight: 400;
    letter-spacing: .08em;

    white-space: nowrap;
  }

  #behaviorLabState[data-error="true"] {
    color: #e47a68;
  }
`;

document.head.appendChild(
  behaviorLabStyle
);

/* =========================================================
   R6.4 ? FINAL VISUAL COMPOSITION
========================================================= */

const r64CompositionStyle =
  document.createElement("style");

r64CompositionStyle.textContent = `

  /* -----------------------------------------
     LAISE ? identity only
  ----------------------------------------- */

  .brand {
    display: flex !important;
  }

  .brand .mark,
  .brand .subtitle,
  .brand .version {
    display: none !important;
  }

  .brand .laise {
    display: block !important;
  }


  /* -----------------------------------------
     Static technical metadata belongs to
     reports, not to the live musical image.
  ----------------------------------------- */

  .field-summary,
  .hud .metric,
  .release {
    display: none !important;
  }


  /* -----------------------------------------
     Stronger main reactive title
  ----------------------------------------- */

  .status-title,
  .v13c-master-reactive-title {
    font-size:
      clamp(15px, 1.1vw, 20px)
      !important;

    font-weight:
      700
      !important;

    letter-spacing:
      .11em
      !important;

    line-height:
      1.15
      !important;
  }


  /* -----------------------------------------
     Bottom HUD now contains only information
     useful during playback.
  ----------------------------------------- */

  .hud {
    grid-template-columns:
      minmax(220px, .85fr)
      minmax(0, 2.15fr)
      !important;
  }

`;

document.head.appendChild(
  r64CompositionStyle
);




function renderBehaviorLabState() {

  if (behaviorLoadError) {

    behaviorLabState.dataset.error =
      "true";

    behaviorLabState.textContent =
      "V1.3C TELEMETRY UNAVAILABLE";

    return;
  }


  behaviorLabState.dataset.error =
    "false";


  if (!behaviorTimelineV13C) {

    behaviorLabState.textContent =
      "V1.3C ? LOADING MUSICAL BEHAVIOR...";

    return;
  }


  const state =
    behaviorTimelineV13C.debug;


  behaviorLabState.replaceChildren();

  const telemetryRows = [
    ["ANCHOR", state.anchorSource],
    ["DRIVE", state.anchorDrive.toFixed(5)],
    ["FOOTPRINT", `?${state.footprintScale.toFixed(2)}`],
    ["ACTIVE", String(state.activeContinuous)]
  ];

  for (const [label, value] of telemetryRows) {

    const row =
      document.createElement("div");

    row.className =
      "behavior-telemetry-row";


    const labelElement =
      document.createElement("span");

    labelElement.className =
      "behavior-telemetry-label";

    labelElement.textContent =
      label;


    const valueElement =
      document.createElement("strong");

    valueElement.className =
      "behavior-telemetry-value";

    valueElement.textContent =
      value;


    row.append(
      labelElement,
      valueElement
    );

    behaviorLabState.appendChild(
      row
    );
  }
}


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


    if (eventWavesEnabledR9) {
      eventWaveDetailR9 = new EventWaveDetailR9(data, TERRAIN.width, TERRAIN.depth, SEG_X, SEG_Z);
      eventWaveDetailR9.seek(audio.currentTime);
      console.info("LAISE R9 event detail enabled", eventWaveDetailR9.debug);
    }

    behaviorTimelineV13C =
      new BehaviorTimelineV13C(
        // LAISE_PERCUSSION_MOTION_TEST
        !eventWavesEnabledR9 && (
          new URLSearchParams(window.location.search).get("percussion") === "1" ||
          new URLSearchParams(window.location.search).get("rhythm") === "1"
        )
          ? {
              ...data,
              behaviors: data.behaviors.map((behavior) => {
                // LAISE_DRUMS_PERCUSSION_TEST
                if (
                  behavior.source !== "percussion" &&
                  behavior.source !== "drums"
                ) return behavior;

                // Smoothly favors small positive signals; zero stays zero.
                // The original event times and positions are preserved.
                const boost = (value) => {
                  if (!Number.isFinite(value) || value <= 0) return value;
                  // LAISE_RHYTHM_MOTION_TEST
                  // Stronger test only when ?rhythm=1 is present.
                  if (
                    new URLSearchParams(window.location.search)
                      .get("rhythm") === "1"
                  ) {
                    return value * (1 + 2.5 / (1 + value / 0.005));
                  }

                  return value * (1 + 0.70 / (1 + value / 0.002));
                };

                return {
                  ...behavior,

                  continuous: behavior.continuous.map((sample) => {
                    const copy = sample.slice();
                    copy[1] = boost(sample[1]);
                    return copy;
                  }),

                  attacks: behavior.attacks.map((attack) => ({
                    ...attack,
                    drive: boost(attack.drive)
                  })),

                  reinforcementAttacks:
                    (behavior.reinforcementAttacks ?? []).map((attack) => {
                      const copy = { ...attack };

                      if (Number.isFinite(attack.physicalAttackDrive)) {
                        copy.physicalAttackDrive =
                          boost(attack.physicalAttackDrive);
                      } else if (Number.isFinite(attack.residualDrive)) {
                        copy.residualDrive = boost(attack.residualDrive);
                      }

                      return copy;
                    })
                };
              })
            }
          : data
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

  // Keep the approved projection gain calibrated to the original pose.
  // Rotation changes presentation only, never the musical displacement.
  if (horizontalRotationEnabledR10 || horizontalPoseEnabledR12) {
    terrainRig.rotation.y = BASE_POSE.yaw;
  }
  const motionGain = audioMotionRecovery.gainFor(camera, terrainRig,
    window.innerWidth, window.innerHeight);
  if (horizontalPoseEnabledR12) terrainRig.rotation.y = presentationYawR12;
  if (horizontalRotationEnabledR10) {
    if (!audio.paused && !audio.seeking && !audio.ended) {
      horizontalRotationElapsedR10 += delta;
    }
    terrainRig.rotation.y = BASE_POSE.yaw +
      horizontalRotationOffsetR10(horizontalRotationElapsedR10);
  }
  updateColorSpinR12(delta);
  const visibleRippleField =
    behaviorMode === "v13c"
      ? behaviorRippleField
      : rippleField;

  if (eventWaveDetailR9) {
    eventWaveDetailR9.update(
      audio.currentTime, !audio.paused && !audio.seeking && !audio.ended,
      behaviorTimelineV13C?.anchorX ?? 0,
      behaviorTimelineV13C?.anchorZ ?? 0
    );
  }

  if (contoursR93 && eventWaveDetailR9) {
    attackAccentR93.array.set(eventWaveDetailR9.accents);
    attackAccentR93.needsUpdate = true;
  }

  for (let i = 0; i < positions.count; i++) {

    // Physical field remains untouched.
    // V1.2 preserves the approved legacy ?2.8 soft limiter.
    //
    // V1.3C intentionally keeps an open vertical response:
    // exceptional physical peaks may reach or leave the
    // camera frame instead of flattening into a common cap.

    const baseVisualHeight = visibleRippleField.heights[i] * motionGain;
    const detailVisualHeight = (eventWaveDetailR9?.heights[i] ?? 0) * motionGain;

    if (articulationR92 && behaviorMode === "v13c") {
      // R9.2: articulate attacks relative to the existing surface.
      // Bound the added relief; the physical field and audio stay untouched.
      const relativeGain = 1 + Math.min(1.4, Math.abs(baseVisualHeight) / 3.0);
      const relief = 1.1 * Math.tanh(detailVisualHeight * relativeGain / 1.1);
      positions.array[i * 3 + 1] = visualHeightV13C(baseVisualHeight) + relief;
    } else {
      const physicalVisualHeight = baseVisualHeight + detailVisualHeight;
      positions.array[i * 3 + 1] =
        behaviorMode === "v13c"
          ? visualHeightV13C(physicalVisualHeight)
          : TERRAIN.maxHeight * Math.tanh(
              physicalVisualHeight / TERRAIN.maxHeight
            );
    }
    if (wideCoverageEnabledR12) {
      // Display-only peak reduction balances the closer fixed perspective.
      positions.array[i * 3 + 1] *= 0.82;
    }
    // A sustained crest shifts gently in the plane as attacks cross it.
    // Rest and low ripples remain anchored; no camera or physics movement.
    const offset = i * 3;
    const x = basePositions[offset];
    const z = basePositions[offset + 2];
    if (sustainedSwayEnabledR12) {
      const heightT = Math.max(0, Math.min(1,
        (positions.array[offset + 1] - 0.7) / 2.0));
      const crestGate = heightT * heightT * (3 - 2 * heightT);
      const attackActivity = Math.min(1, Math.abs(detailVisualHeight) * 2.0);
      const sway = crestGate * (0.45 + 0.55 * attackActivity);
      const phase = audio.currentTime * 2.1 + x * 0.18 + z * 0.12;
      positions.array[offset] = x + 0.24 * sway * Math.sin(phase);
      positions.array[offset + 2] = z + 0.14 * sway * Math.cos(phase * 0.83);
    } else {
      positions.array[offset] = x;
      positions.array[offset + 2] = z;
    }
  }

  if (roundedTipsEnabledR12) {
    geometry.computeVertexNormals();
    originalLightNormalsR12.set(geometry.attributes.normal.array);
    for (let i = 0; i < positions.count; i++) {
      originalLightHeightsR12[i] = positions.array[i * 3 + 1];
    }
    roundVisibleTipsR12();
  }
  positions.needsUpdate = true;

  // Shared live normals drive the depth-writing surface and wire shader.
  // All directional shading is evaluated per fragment in view coordinates.
  geometry.computeVertexNormals();
  lightingNormalR12.array.set(originalLightNormalsR12 ?? geometry.attributes.normal.array);
  lightingNormalR12.needsUpdate = true;
  updateNeonCurvature(originalLightHeightsR12, originalLightNormalsR12);
  updateTerrainLighting();


  particles.rotation.y =
    time * 0.006;


  particles.position.y =
    averageEnergy * 0.25;


  rings.rotation.y =
    time * 0.025;


  bloom.strength = TERRAIN_LIGHTING.bloomBase
    + TERRAIN_LIGHTING.bloomEnergy * THREE.MathUtils.clamp(averageEnergy, 0, 1);




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


