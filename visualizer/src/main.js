import "./style.css";
import { RippleField } from "./ripple-field.js";
import { AudioCueTimeline } from "./audio-cue-timeline.js";

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
const TERRAIN = Object.freeze({ width: 16, depth: 12, maxHeight: 2.8 });
// AJUSTE AQUI: valores em graus, aplicados uma ?nica vez ? malha e ao glow.
const MESH_ANGLES = Object.freeze({
  horizontal: 47, // Eixo Y: giro sobre a mesa. Antes: 8?; agora: +20?.
  vertical: -6,    // Eixo X: inclina a frente e o fundo.
  diagonal: -3   // Eixo Z: inclina a esquerda e a direita.
});
const BASE_POSE = Object.freeze({
  y: -0.75,
  yaw: THREE.MathUtils.degToRad(MESH_ANGLES.horizontal),
  pitch: THREE.MathUtils.degToRad(MESH_ANGLES.vertical),
  roll: THREE.MathUtils.degToRad(MESH_ANGLES.diagonal)
});
// Posicao na tela, em pixels: horizontal + direita; vertical + baixo.
const SCREEN_POSITION = Object.freeze({ horizontal: 70, vertical: 0 });
const CAMERA = Object.freeze({ fov: 36, elevation: Math.PI / 9, magnification: 1.4 });

const camera =
  new THREE.PerspectiveCamera(
    CAMERA.fov,
    window.innerWidth /
    window.innerHeight,
    0.1,
    100
  );


// Center the projected base rectangle, rather than aiming at a world-space point.
// Perspective makes those two centers different. Lens shift fixes the composition
// without tilting the horizontal plane or moving the camera during playback.
function frameTerrain() {
  camera.zoom = 1;
  const width = window.innerWidth;
  const height = window.innerHeight;
  const target = new THREE.Vector3(0, BASE_POSE.y, 0);
  const direction = new THREE.Vector3(0, Math.sin(CAMERA.elevation), Math.cos(CAMERA.elevation));
  const poseRotation = new THREE.Euler(BASE_POSE.pitch, BASE_POSE.yaw, BASE_POSE.roll);
  const corners = [];
  for (const x of [-TERRAIN.width / 2, TERRAIN.width / 2]) {
    for (const z of [-TERRAIN.depth / 2, TERRAIN.depth / 2]) {
      corners.push(new THREE.Vector3(x, 0, z).applyEuler(poseRotation).add(target));
    }
  }
  // Conservative envelope: every point in this box can reach maxHeight.
  const envelope = corners.flatMap(point => [point, point.clone().add(new THREE.Vector3(0, TERRAIN.maxHeight + 0.025, 0).applyEuler(poseRotation))]);
  function place(distance) {
    camera.clearViewOffset();
    camera.position.copy(target).addScaledVector(direction, distance);
    camera.lookAt(target);
    camera.updateMatrixWorld(true);
    const projected = corners.map(point => point.clone().project(camera));
    const centerX = (Math.min(...projected.map(p => p.x)) + Math.max(...projected.map(p => p.x))) / 2;
    const centerY = (Math.min(...projected.map(p => p.y)) + Math.max(...projected.map(p => p.y))) / 2;
    camera.setViewOffset(
      width,
      height,
      centerX * width / 2,
      -centerY * height / 2,
      width,
      height
    );
    return envelope.every(point => {
      const p = point.clone().project(camera);
      return Math.abs(p.x) <= 0.78 && Math.abs(p.y) <= 0.58 && p.z > -1 && p.z < 1;
    });
  }
  // Binary search gives a reproducible fit for the fixed pose at every aspect ratio.
  let near = 10;
  let far = 200;
  camera.far = 500;
  for (let i = 0; i < 36; i++) {
    const distance = (near + far) / 2;
    if (place(distance)) far = distance;
    else near = distance;
  }
  place(far);
  // Enlarge the approved composition by 40%, keeping the same perspective.
  // On narrow screens, retain margin around the complete deformation envelope.
  const projectedEnvelope = envelope.map(point => point.clone().project(camera));
  const extentX = Math.max(...projectedEnvelope.map(p => Math.abs(p.x)));
  const extentY = Math.max(...projectedEnvelope.map(p => Math.abs(p.y)));
  camera.zoom = Math.min(CAMERA.magnification, 0.90 / extentX, 0.84 / extentY);
  place(far);
  // Apply the screen translation after fitting, so size and angles stay unchanged.
  const finalEnvelope = envelope.map(point => point.clone().project(camera));
  const minX = Math.min(...finalEnvelope.map(p => p.x));
  const maxX = Math.max(...finalEnvelope.map(p => p.x));
  const horizontal = THREE.MathUtils.clamp(SCREEN_POSITION.horizontal,
    (-0.98 - minX) * width / 2, (0.98 - maxX) * width / 2);
  const view = camera.view;
  camera.setViewOffset(width, height,
    view.offsetX - horizontal, view.offsetY - SCREEN_POSITION.vertical, width, height);

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

const SEG_X = 120;
const SEG_Z = 100;

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
audio.addEventListener("seeking", () => {
  rippleField.reset();
  smoothed.fill(0);
  cueTimeline?.seek(audio.currentTime);
});

// Flush the fraction of audio played since the last rendered frame before pause.
audio.addEventListener("pause", () => {
  if (!audio.seeking) updateSoundWaves(0, true);
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
      startButton.textContent = "FALHA NA ANALISE - RECARREGUE A PAGINA";
      return;
    }


    if (
      audio.paused
    ) {

      await audio.play();


      startButton.innerHTML =
        "<span>Ⅱ</span> PAUSAR";

    } else {

      audio.pause();


      startButton.innerHTML =
        "<span>▶</span> CONTINUAR";

    }

  }
);


/* =========================================================
   ANIMATION
========================================================= */

const clock = new THREE.Clock();
let previousTime = 0;



function updateSoundWaves(delta, flushPause = false) {
  const playing = flushPause || (!audio.paused && !audio.seeking && !audio.ended);
  if (playing && cueTimeline && Math.abs(audio.currentTime - cueTimeline.lastTime) > 0.3) {
    rippleField.reset();
  }
  const synced = cueTimeline?.step(audio.currentTime, playing,
    cue => rippleField.exciteAt(cue.x, cue.z, cue.strength, cue.width),
    seconds => rippleField.advance(seconds));
  // After pause/end, existing waves are allowed to reflect and settle naturally.
  if (!synced) {
    rippleField.advance(delta);
  }
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

  for (let i = 0; i < positions.count; i++) {
    // Signed heights produce rising crests and falling troughs. Fixed simulation
    // timesteps supply temporal continuity without smearing the travelling wave.
    positions.array[i * 3 + 1] = TERRAIN.maxHeight *
      Math.tanh(rippleField.heights[i] / TERRAIN.maxHeight);
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
