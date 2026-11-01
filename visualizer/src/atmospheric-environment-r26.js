import * as THREE from "three";

// Background-only depth study. Every layer sits behind the terrain volume;
// no surface, material, light, camera, or audio parameter is changed.
export function addAtmosphericEnvironmentR26(scene) {
  const layers = [
    { z: -16, x: -13, y: 4, width: 23, height: 14,
      color: 0x5b2a8e, opacity: 0.10, drift: 0.14 },
    { z: -30, x: 13, y: 6, width: 28, height: 18,
      color: 0x14688c, opacity: 0.12, drift: -0.11 },
    { z: -46, x: 0, y: 8, width: 38, height: 17,
      color: 0x252471, opacity: 0.07, drift: 0.08 }
  ];
  const clouds = layers.map((layer, index) => {
    const cloud = new THREE.Mesh(
      new THREE.PlaneGeometry(layer.width, layer.height),
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        depthTest: true,
        blending: THREE.AdditiveBlending,
        uniforms: {
          uColor: { value: new THREE.Color(layer.color) },
          uOpacity: { value: layer.opacity }
        },
        vertexShader: `
          varying vec2 vUv;
          void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: `
          uniform vec3 uColor;
          uniform float uOpacity;
          varying vec2 vUv;
          void main() {
            vec2 p = (vUv - 0.5) * vec2(2.0, 2.0);
            float core = exp(-dot(p * vec2(1.0, 1.5), p * vec2(1.0, 1.5)) * 3.4);
            float texture = 0.82 + 0.18 * sin(p.x * 13.0 + p.y * 4.0)
              * sin(p.y * 10.0 - p.x * 3.0);
            float alpha = core * texture * uOpacity;
            gl_FragColor = vec4(uColor, alpha);
          }
        `
      })
    );
    cloud.position.set(layer.x, layer.y, layer.z);
    cloud.userData.originalX = layer.x;
    cloud.userData.drift = layer.drift;
    cloud.userData.phase = index * 1.7;
    cloud.renderOrder = -3;
    scene.add(cloud);
    return cloud;
  });

  // Near and far motes provide size and occlusion cues without a floor.
  const count = 220;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const violet = new THREE.Color(0x8852b3);
  const blue = new THREE.Color(0x4089ab);
  for (let i = 0; i < count; i++) {
    // Deterministic low-discrepancy distribution, stable across reloads.
    const x = ((i * 73) % 223) / 223;
    const y = ((i * 97) % 227) / 227;
    const depth = ((i * 131) % 229) / 229;
    positions[3 * i] = (x - 0.5) * 66;
    positions[3 * i + 1] = -3 + y * 25;
    positions[3 * i + 2] = -12 - depth * 48;
    const color = violet.clone().lerp(blue, x);
    colors[3 * i] = color.r;
    colors[3 * i + 1] = color.g;
    colors[3 * i + 2] = color.b;
    sizes[i] = 0.055 + 0.08 * (1 - depth);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
  const motes = new THREE.Points(geometry, new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    depthTest: true,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float aSize;
      varying vec3 vColor;
      void main() {
        vColor = color;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = clamp(aSize * 300.0 / max(-mv.z, 1.0), 1.0, 3.0);
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      void main() {
        float r = length(gl_PointCoord - 0.5) * 2.0;
        float alpha = 0.45 * smoothstep(1.0, 0.0, r);
        gl_FragColor = vec4(vColor, alpha);
      }
    `
  }));
  scene.add(motes);
  return {
    update(time) {
      for (const cloud of clouds) {
        cloud.position.x = cloud.userData.originalX
          + cloud.userData.drift * Math.sin(time * 0.09 + cloud.userData.phase);
      }
    }
  };
}
