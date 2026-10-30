import * as THREE from "three";
import { Reflector } from "three/addons/objects/Reflector.js";

// R8B.3: Only presentation. No musical wave or source processing.
export const FLOOR_R8B = Object.freeze({
  clearance: 0.22,
  extentMultiplier: 2.25,
  reflectionOpacity: 0.34,
  textureSize: 768,
  tint: 0x080d12
});

export function createReflectiveFloorR8B({
  width,
  depth,
  minimumTerrainY
}) {
  const floorY = minimumTerrainY - FLOOR_R8B.clearance;
  const size = Math.max(width, depth) * FLOOR_R8B.extentMultiplier;

  const geometry = new THREE.PlaneGeometry(size, size);

  // Use the official Reflector shader without replacing its source.
  const floor = new Reflector(geometry, {
    clipBias: 0.003,
    textureWidth: FLOOR_R8B.textureSize,
    textureHeight: FLOOR_R8B.textureSize,
    color: FLOOR_R8B.tint,
    multisample: 0
  });

  floor.name = "LAISE_R8B_REFLECTIVE_FLOOR";
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = floorY;
  floor.frustumCulled = false;

  // Opacity is applied through standard material blending.
  // It changes the mirror's final image, not the original scene.
  floor.material.transparent = true;
  floor.material.opacity = FLOOR_R8B.reflectionOpacity;
  floor.material.depthWrite = false;

  return {
    floor,
    floorY,
    dispose() {
      floor.getRenderTarget().dispose();
      floor.material.dispose();
      geometry.dispose();
    }
  };
}
