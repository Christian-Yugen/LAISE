import "./style.css";

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


const camera =
  new THREE.PerspectiveCamera(
    42,
    window.innerWidth /
    window.innerHeight,
    0.1,
    100
  );


camera.position.set(
  0,
  6.4,
  12.3
);

camera.lookAt(
  0,
  0,
  0
);


/* =========================================================
   LIGHT
========================================================= */

const warmLight =
  new THREE.PointLight(
    0xe19a51,
    12,
    22
  );

warmLight.position.set(
  0,
  5,
  1
);

scene.add(
  warmLight
);


const coolLight =
  new THREE.PointLight(
    0x37d6bd,
    8,
    20
  );

coolLight.position.set(
  5,
  2,
  -2
);

scene.add(
  coolLight
);


/* =========================================================
   SONIC TERRAIN
========================================================= */

const SEG_X = 170;
const SEG_Z = 96;

const geometry =
  new THREE.PlaneGeometry(
    18,
    10,
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
      (
        x + 9
      ) / 18,
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


terrain.position.y =
  -0.75;


scene.add(
  terrain
);


/* =========================================================
   SECOND CONTOUR LAYER
========================================================= */

const glowGeometry =
  geometry.clone();


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


glowTerrain.position.y =
  -0.70;

glowTerrain.scale.set(
  1.015,
  1.04,
  1.015
);


scene.add(
  glowTerrain
);


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


audio.addEventListener(
  "loadedmetadata",
  () => {

    durationLabel.textContent =
      formatTime(
        audio.duration
      );

  }
);


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

const clock =
  new THREE.Clock();


function animate() {

  requestAnimationFrame(
    animate
  );


  const time =
    clock.getElapsedTime();


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
      smoothed[i] * 0.84
      +
      frequencyData[i] * 0.16;


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


  const bassBins =
    Math.floor(
      frequencyData.length * 0.045
    );


  let bass =
    0;


  for (
    let i = 1;
    i < bassBins;
    i++
  ) {

    bass +=
      smoothed[i] / 255;

  }


  bass /=
    Math.max(
      1,
      bassBins - 1
    );


  for (
    let i = 0;
    i < positions.count;
    i++
  ) {

    const idx =
      i * 3;


    const x =
      basePositions[idx];

    const z =
      basePositions[
        idx + 2
      ];


    const nx =
      THREE.MathUtils.clamp(
        (
          x + 9
        ) / 18,
        0,
        1
      );


    const nz =
      THREE.MathUtils.clamp(
        (
          z + 5
        ) / 10,
        0,
        1
      );


    const freqIndex =
      Math.min(

        smoothed.length - 1,

        Math.floor(
          Math.pow(
            nx,
            2.25
          )
          *
          (
            smoothed.length - 1
          )
        )

      );


    const amp =
      smoothed[
        freqIndex
      ] / 255;


    const centerEnvelope =
      Math.exp(
        -Math.pow(
          (
            z
          ) / 4.2,
          2
        )
      );


    const longitudinal =
      0.64
      +
      0.36
      *
      Math.sin(
        z * 1.55
        +
        time * 0.65
        +
        nx * 4
      );


    const livingFloor =
      0.10
      *
      Math.sin(
        x * 0.9
        +
        z * 0.52
        +
        time * 0.30
      );


    const bassWave =
      bass
      *
      0.55
      *
      Math.sin(
        x * 0.48
        -
        time * 1.1
      );


    const height =
      (
        amp *
        3.15 *
        centerEnvelope *
        longitudinal
      )
      +
      livingFloor
      +
      bassWave;


    positions.array[
      idx + 1
    ] =
      height;


    glowGeometry
      .attributes
      .position
      .array[
        idx + 1
      ] =
      height * 1.025;

  }


  positions.needsUpdate =
    true;


  glowGeometry
    .attributes
    .position
    .needsUpdate =
    true;


  particles.rotation.y =
    time * 0.006;


  particles.position.y =
    averageEnergy * 0.25;


  rings.rotation.y =
    time * 0.025;


  terrain.rotation.y =
    Math.sin(
      time * 0.12
    ) * 0.025;


  glowTerrain.rotation.y =
    terrain.rotation.y;


  camera.position.x =
    Math.sin(
      time * 0.10
    ) * 0.42;


  camera.position.y =
    6.35
    +
    Math.sin(
      time * 0.07
    )
    * 0.10;


  camera.lookAt(
    0,
    0.35,
    -0.3
  );


  bloom.strength =
    0.62
    +
    averageEnergy * 1.8;


  warmLight.intensity =
    7
    +
    bass * 17;


  coolLight.intensity =
    5
    +
    averageEnergy * 12;


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


    camera.updateProjectionMatrix();


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
