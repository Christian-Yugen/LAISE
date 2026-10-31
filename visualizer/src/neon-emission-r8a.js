import { BufferAttribute, DynamicDrawUsage } from 'three';

// Presentation only. Curvature is measured in scene units, never audio energy.
export const NEON_R8A = Object.freeze({
  neonEmissionStrength: 4.8,
  neonFaceStrength: 1.25,
  neonCrestStrength: 2.2,
  neonHighlightThreshold: 4.5,
  neonHighlightSoftness: 3.0,
  neonHighlightWarmth: 0.28,
  neonBloomStrength: 0.18,
  neonBloomThreshold: 2.0,
  neonExposure: 1.15,
  surfaceEmissionFraction: 0.035
});

export const neonUniformsR8A = {
  uNeonStrength: { value: NEON_R8A.neonEmissionStrength },
  uNeonFaceStrength: { value: NEON_R8A.neonFaceStrength },
  uNeonCrestStrength: { value: NEON_R8A.neonCrestStrength },
  uNeonThreshold: { value: NEON_R8A.neonHighlightThreshold },
  uNeonSoftness: { value: NEON_R8A.neonHighlightSoftness },
  uNeonWarmth: { value: NEON_R8A.neonHighlightWarmth }
};

export const neonEmissionGLSL = `
  uniform float uNeonStrength;
  uniform float uNeonFaceStrength;
  uniform float uNeonCrestStrength;
  uniform float uNeonThreshold;
  uniform float uNeonSoftness;
  uniform float uNeonWarmth;
  varying float vNeonCurvature;
  varying vec3 vNeonViewNormal;

  vec3 r8aNeonEmission(vec3 chromaticBase, float spectrumT,
    vec3 faceNormal, vec3 terrainUp, vec3 keyDirection) {
    vec3 emissionNormal = normalize(vNeonViewNormal);
    if (dot(emissionNormal, faceNormal) < 0.0) emissionNormal = -emissionNormal;
    float keyFacing = max(dot(emissionNormal, keyDirection), 0.0);
    // The original face remains authoritative at the light/shadow boundary.
    float shadowGate = smoothstep(0.02, 0.28, dot(faceNormal, keyDirection));
    float litGate = smoothstep(0.10, 0.95, keyFacing) * shadowGate;
    float slope = smoothstep(0.015, 0.35,
      1.0 - abs(dot(emissionNormal, terrainUp)));
    float faceLight = pow(litGate, 1.15) * slope;
    float crest = smoothstep(max(0.0, uNeonThreshold - uNeonSoftness),
      uNeonThreshold + uNeonSoftness, max(vNeonCurvature, 0.0));
    float highlight = crest * litGate * (0.40 + 0.60 * slope);

    // Chroma follows the immutable R7C palette. Only local high emission
    // approaches a warm/neutral white; shadow-facing slopes keep their floor.
    float peak = max(max(chromaticBase.r, chromaticBase.g), chromaticBase.b);
    vec3 neonHue = chromaticBase / max(peak, 0.0001);
    float gold = smoothstep(0.32, 0.56, spectrumT)
      * (1.0 - smoothstep(0.62, 0.71, spectrumT));
    vec3 coreWhite = mix(vec3(1.0), vec3(1.0, 0.88, 0.68), gold * uNeonWarmth);
    float whiteCore = smoothstep(0.82, 1.0, highlight) * 0.30;
    vec3 crestHue = mix(neonHue, coreWhite, whiteCore);
    // A continuous colored face carries the form. Curvature only accents it.
    return uNeonStrength * (
      neonHue * uNeonFaceStrength * faceLight +
      crestHue * uNeonCrestStrength * highlight);
  }
`;

/** Adds an emissive descriptor; never writes positions, normals or wave state. */
export function createNeonCurvatureR8A(geometry, wireGeometry, segmentsX, segmentsZ, width, depth) {
  const columns = segmentsX + 1, rows = segmentsZ + 1;
  const values = new Float32Array(columns * rows);
  const rawCurvature = new Float32Array(values.length);
  const horizontalCurvature = new Float32Array(values.length);
  const emissionNormals = new Float32Array(values.length * 3);
  const horizontalNormals = new Float32Array(emissionNormals.length);
  const attribute = new BufferAttribute(values, 1).setUsage(DynamicDrawUsage);
  const normalAttribute = new BufferAttribute(emissionNormals, 3).setUsage(DynamicDrawUsage);
  geometry.setAttribute('neonCurvature', attribute);
  wireGeometry.setAttribute('neonCurvature', attribute);
  geometry.setAttribute('neonNormal', normalAttribute);
  wireGeometry.setAttribute('neonNormal', normalAttribute);
  const dx2 = (width / segmentsX) ** 2, dz2 = (depth / segmentsZ) ** 2;
  return (originalLightHeights = null) => {
    const p = geometry.attributes.position.array;
    const heightAt = (i) => originalLightHeights ? originalLightHeights[i] : p[i * 3 + 1];
    for (let row = 1; row < rows - 1; row++) {
      for (let col = 1; col < columns - 1; col++) {
        const i = row * columns + col, h = heightAt(i);
        // Keep the sign through filtering so noise is not rectified into light.
        rawCurvature[i] =
          (2 * h - heightAt(i - 1) - heightAt(i + 1)) / dx2 +
          (2 * h - heightAt(i - columns) - heightAt(i + columns)) / dz2;
      }
    }
    // Extend the adjacent interior descriptor; do not invent a luminous border.
    for (let row = 1; row < rows - 1; row++) {
      rawCurvature[row * columns] = rawCurvature[row * columns + 1];
      rawCurvature[(row + 1) * columns - 1] = rawCurvature[(row + 1) * columns - 2];
    }
    for (let col = 0; col < columns; col++) {
      rawCurvature[col] = rawCurvature[columns + col];
      rawCurvature[(rows - 1) * columns + col] = rawCurvature[(rows - 2) * columns + col];
    }

    // Separable 3x3 binomial filter, presentation attributes only. It bridges
    // vertex-scale light islands without moving vertices or delaying playback.
    const normals = geometry.attributes.normal.array;
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < columns; col++) {
        const i = row * columns + col;
        const left = row * columns + Math.max(0, col - 1);
        const right = row * columns + Math.min(columns - 1, col + 1);
        horizontalCurvature[i] = (rawCurvature[left] + 2 * rawCurvature[i] + rawCurvature[right]) * 0.25;
        for (let axis = 0; axis < 3; axis++) {
          horizontalNormals[i * 3 + axis] =
            (normals[left * 3 + axis] + 2 * normals[i * 3 + axis] + normals[right * 3 + axis]) * 0.25;
        }
      }
    }
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < columns; col++) {
        const i = row * columns + col;
        const up = Math.max(0, row - 1) * columns + col;
        const down = Math.min(rows - 1, row + 1) * columns + col;
        values[i] = Math.max(0, (horizontalCurvature[up] + 2 * horizontalCurvature[i] + horizontalCurvature[down]) * 0.25);
        for (let axis = 0; axis < 3; axis++) {
          emissionNormals[i * 3 + axis] =
            (horizontalNormals[up * 3 + axis] + 2 * horizontalNormals[i * 3 + axis] + horizontalNormals[down * 3 + axis]) * 0.25;
        }
        const n = i * 3;
        const length = Math.hypot(emissionNormals[n], emissionNormals[n + 1], emissionNormals[n + 2]) || 1;
        emissionNormals[n] /= length;
        emissionNormals[n + 1] /= length;
        emissionNormals[n + 2] /= length;
      }
    }
    attribute.needsUpdate = true;
    normalAttribute.needsUpdate = true;
  };
}
