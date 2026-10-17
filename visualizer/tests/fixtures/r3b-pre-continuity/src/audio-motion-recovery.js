import * as THREE from 'three';

// Response calibration only: no reference camera is attached to the scene.
// The approved V1.1 fit below is frozen from tag LAISE_VISUALIZER_V1_1_APPROVED
// (commit e862bca42a0c785c6da62d03ef99fadcddb45a3d). It is NOT the active camera.
export function projectedVerticalSensitivity(camera, matrixWorld, width, height) {
  const base = new THREE.Vector3(0, 0, 0).applyMatrix4(matrixWorld).project(camera);
  const raised = new THREE.Vector3(0, 0.01, 0).applyMatrix4(matrixWorld).project(camera);
  return Math.hypot((raised.x - base.x) * width / 2,
    (raised.y - base.y) * height / 2) / 0.01;
}

export function approvedResponseSensitivity(width, height) {
  const window = { innerWidth: width, innerHeight: height };
  // BEGIN APPROVED V1.1 REFERENCE
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
  // END APPROVED V1.1 REFERENCE
  const matrix = new THREE.Matrix4().compose(new THREE.Vector3(0, BASE_POSE.y, 0),
    new THREE.Quaternion().setFromEuler(new THREE.Euler(BASE_POSE.pitch, BASE_POSE.yaw, BASE_POSE.roll)),
    new THREE.Vector3(1, 1, 1));
  return projectedVerticalSensitivity(camera, matrix, width, height);
}

// Uniform small-signal amplitude recovery, without new attacks, inertia or damping.
// Recalculated only when projection/pose/viewport changes, never per instrument.
export class AudioMotionRecovery {
  constructor() {
    this.projection = new THREE.Matrix4();
    this.view = new THREE.Matrix4();
    this.pose = new THREE.Matrix4();
    this.width = 0;
    this.height = 0;
    this.gain = 1;
    this.referenceSensitivity = 0;
    this.currentSensitivity = 0;
  }

  gainFor(camera, terrainRig, width, height) {
    terrainRig.updateWorldMatrix(true, false);
    if (width !== this.width || height !== this.height ||
        !this.projection.equals(camera.projectionMatrix) || !this.view.equals(camera.matrixWorld) ||
        !this.pose.equals(terrainRig.matrixWorld)) {
      this.referenceSensitivity = approvedResponseSensitivity(width, height);
      this.currentSensitivity = projectedVerticalSensitivity(camera, terrainRig.matrixWorld, width, height);
      const gain = this.referenceSensitivity / this.currentSensitivity;
      this.gain = Number.isFinite(gain) && gain > 0 ? gain : 1;
      this.projection.copy(camera.projectionMatrix);
      this.view.copy(camera.matrixWorld);
      this.pose.copy(terrainRig.matrixWorld);
      this.width = width;
      this.height = height;
    }
    return this.gain;
  }
}
