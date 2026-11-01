import * as THREE from "three";

// Optional dark liquid beneath the existing musical terrain.
// It does not change the terrain geometry, lighting, or audio response.
export function addDarkWaterR20(scene) {
  const peaks = Array.from({ length: 3 }, () => new THREE.Vector4(0, 0, 0, 0));
  const uniforms = {
    uTime: { value: 0 },
    uEnergy: { value: 0 },
    uPeaks: { value: peaks }
  };
  const water = new THREE.Mesh(
    new THREE.PlaneGeometry(100, 100, 96, 96),
    new THREE.ShaderMaterial({
      uniforms,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      vertexShader: `
        uniform float uTime;
        uniform float uEnergy;
        uniform vec4 uPeaks[3];
        varying vec2 vWorld;
        varying float vDisplacement;
        float ripple(vec2 p, vec2 center, float amplitude, float phase) {
          float r = length(p - center);
          return amplitude * exp(-r * 0.18)
            * sin(r * 2.3 - phase * 2.0);
        }
        void main() {
          vec3 p = position;
          // Local plane xy becomes world xz after rotation.
          vec2 coord = vec2(p.x, -p.y);
          float wave = 0.07 * sin(coord.x * 0.42 + uTime * 0.6)
            * sin(coord.y * 0.38 - uTime * 0.4);
          for (int i = 0; i < 3; i++) {
            wave += ripple(coord, uPeaks[i].xy,
              uPeaks[i].z * (0.14 + 0.06 * uEnergy), uTime);
          }
          p.z += wave;
          vDisplacement = wave;
          vec4 world = modelMatrix * vec4(p, 1.0);
          vWorld = world.xz;
          gl_Position = projectionMatrix * viewMatrix * world;
        }
      `,
      fragmentShader: `
        uniform float uTime;
        uniform float uEnergy;
        uniform vec4 uPeaks[3];
        varying vec2 vWorld;
        varying float vDisplacement;
        void main() {
          float radius = length(vWorld);
          float side = smoothstep(-17.0, 17.0, vWorld.x);
          vec3 tint = mix(vec3(0.42, 0.12, 0.60),
            vec3(0.06, 0.52, 0.68), side);
          float lit = 0.0;
          float glint = 0.0;
          for (int i = 0; i < 3; i++) {
            float d = length(vWorld - uPeaks[i].xy);
            float strength = uPeaks[i].z;
            // Light scattered from tall illuminated peaks onto nearby water.
            lit += strength * exp(-d * 0.19);
            float crest = sin(d * 2.3 - uTime * 2.0);
            glint += strength * exp(-d * 0.14)
              * pow(max(crest, 0.0), 10.0);
          }
          float ambient = exp(-radius * 0.052);
          float rippled = 0.5 + 0.5 * sin(
            vWorld.x * 1.9 + vWorld.y * 0.45 + uTime * 1.1
            + vDisplacement * 8.0);
          float reflected = (0.045 + 0.12 * lit + 0.22 * glint)
            * (0.55 + 0.45 * rippled);
          vec3 color = vec3(0.006, 0.011, 0.029)
            + tint * (0.028 * ambient + reflected);
          float alpha = (0.73 * ambient + 0.15 * exp(-radius * 0.08))
            * (1.0 - smoothstep(37.0, 49.0, radius));
          gl_FragColor = vec4(color, alpha);
        }
      `
    })
  );
  water.rotation.x = -Math.PI / 2;
  water.position.y = -1.12;
  water.renderOrder = -2;
  water.frustumCulled = false;
  scene.add(water);

  const dropsPerPeak = 12;
  const dropPositions = new Float32Array(3 * dropsPerPeak * 3);
  const dropGeometry = new THREE.BufferGeometry();
  dropGeometry.setAttribute("position", new THREE.BufferAttribute(
    dropPositions, 3).setUsage(THREE.DynamicDrawUsage));
  const drops = new THREE.Points(dropGeometry, new THREE.PointsMaterial({
    color: 0xa9dafa,
    size: 0.085,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.72,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  }));
  drops.frustumCulled = false;
  scene.add(drops);
  const candidate = new THREE.Vector3();
  const world = new THREE.Vector3();
  return {
    update(time, energy, terrainPositions, terrainRig) {
      uniforms.uTime.value = time;
      uniforms.uEnergy.value = THREE.MathUtils.clamp(energy, 0, 1);
      // Select a few distinct tall crests. The water follows their current
      // position, including the approved local sway, without driving them.
      const picked = [];
      for (let i = 0; i < terrainPositions.count; i += 47) {
        const h = terrainPositions.getY(i);
        if (h < 2.3) continue;
        candidate.set(terrainPositions.getX(i), h, terrainPositions.getZ(i));
        world.copy(candidate).applyMatrix4(terrainRig.matrixWorld);
        const near = picked.findIndex(p => Math.hypot(world.x - p.x, world.z - p.z) < 3.3);
        if (near >= 0) {
          if (h > picked[near].h) picked[near] = { x: world.x, z: world.z, h };
        } else {
          picked.push({ x: world.x, z: world.z, h });
        }
        picked.sort((a, b) => b.h - a.h);
        if (picked.length > 3) picked.pop();
      }
      for (let k = 0; k < 3; k++) {
        const p = picked[k];
        peaks[k].set(p?.x ?? 0, p?.z ?? 0,
          p ? THREE.MathUtils.clamp((p.h - 2.0) / 6.0, 0, 1) : 0, 0);
        for (let j = 0; j < dropsPerPeak; j++) {
          const index = (k * dropsPerPeak + j) * 3;
          const phase = j * 2.399963229728653;
          const cycle = ((time * 0.7 + j / dropsPerPeak) % 1 + 1) % 1;
          const spread = 0.28 + cycle * 1.35;
          const lift = Math.max(0, 4 * cycle * (1 - cycle)) * 0.62;
          dropPositions[index] = p ? p.x + Math.cos(phase) * spread : 0;
          dropPositions[index + 1] = p
            ? water.position.y + 0.15 + lift * peaks[k].z : -1000;
          dropPositions[index + 2] = p ? p.z + Math.sin(phase) * spread : 0;
        }
      }
      dropGeometry.attributes.position.needsUpdate = true;
    }
  };
}
