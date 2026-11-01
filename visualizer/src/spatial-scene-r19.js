import * as THREE from "three";

// An opt-in spatial layer for the approved terrain presentation.
// The floor shares the terrain's world coordinates, so the perspective camera
// gives it the same vanishing point while its edges fade into the existing sky.
export function addSpatialSceneR19(scene) {
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(100, 100, 64, 64),
    new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      uniforms: {
        uViolet: { value: new THREE.Color(0x542c91) },
        uCyan: { value: new THREE.Color(0x126d85) }
      },
      vertexShader: `
        varying vec2 vWorld;
        void main() {
          vec3 softened = position;
          softened.z += 0.22 * sin(position.x * 0.31) * sin(position.y * 0.25)
            + 0.10 * sin(position.x * 0.71 + position.y * 0.18);
          vec4 world = modelMatrix * vec4(softened, 1.0);
          vWorld = world.xz;
          gl_Position = projectionMatrix * viewMatrix * world;
        }
      `,
      fragmentShader: `
        uniform vec3 uViolet;
        uniform vec3 uCyan;
        varying vec2 vWorld;
        void main() {
          vec2 p = vWorld;
          float radius = length(p);
          float side = smoothstep(-17.0, 17.0, p.x);
          vec3 color = mix(uViolet, uCyan, side);
          // A dim contact region grounds the terrain; the illuminated air
          // around it shares the mesh palette without becoming a second mesh.
          float contact = 1.0 - smoothstep(3.0, 15.0, radius);
          float ambience = exp(-radius * 0.048);
          float ring = exp(-pow((radius - 12.0) / 8.5, 2.0));
          vec3 radiance = color * (0.045 * ambience + 0.11 * ring);
          radiance *= 1.0 - 0.18 * contact;
          float alpha = (0.45 * ambience + 0.17 * ring)
            * smoothstep(2.0, 11.0, radius)
            * (1.0 - smoothstep(30.0, 49.0, radius));
          gl_FragColor = vec4(radiance, alpha);
        }
      `
    })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -2.35;
  floor.renderOrder = -2;
  floor.frustumCulled = false;
  scene.add(floor);

  // Sparse depth cues live behind the terrain and obey camera projection.
  // The existing particle animation remains untouched.
  const count = 180;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const violet = new THREE.Color(0x9a73cf);
  const cyan = new THREE.Color(0x4dacc1);
  for (let i = 0; i < count; i++) {
    const t = i / count;
    const spiral = i * 2.399963229728653;
    const radius = 13 + 27 * Math.sqrt(t);
    positions[3 * i] = Math.cos(spiral) * radius;
    positions[3 * i + 1] = -0.4 + 5.2 * ((i * 37 % count) / count);
    positions[3 * i + 2] = -13 - (i * 71 % count) / count * 36;
    const color = violet.clone().lerp(cyan, (positions[3 * i] + 40) / 80);
    colors[3 * i] = color.r;
    colors[3 * i + 1] = color.g;
    colors[3 * i + 2] = color.b;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const motes = new THREE.Points(geometry, new THREE.PointsMaterial({
    size: 0.055,
    vertexColors: true,
    transparent: true,
    opacity: 0.36,
    sizeAttenuation: true,
    depthWrite: false
  }));
  scene.add(motes);
}
