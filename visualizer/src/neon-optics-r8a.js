import { Vector2 } from 'three';

// Optical scatter only. The scene, emission, audio and wave state are untouched.
export const NEON_OPTICS_R8A = Object.freeze({
  auraStrength: 0.08,
  streakStrength: 1.20,
  streakThreshold: 1.20,
  streakRadius: 0.085
});

/** Extend the existing bloom composite, reusing its textures and draw call. */
export function installNeonOpticsR8A(bloom) {
  const material = bloom.compositeMaterial;
  const marker = 'float bloomAlpha =';
  if (!material.fragmentShader.includes(marker)) throw new Error('Unsupported bloom composite for R8A optics');

  Object.assign(material.uniforms, {
    uOpticsAura: { value: NEON_OPTICS_R8A.auraStrength },
    uOpticsStreak: { value: NEON_OPTICS_R8A.streakStrength },
    uOpticsThreshold: { value: NEON_OPTICS_R8A.streakThreshold },
    uOpticsAxis: { value: new Vector2() },
    uOpticsTexel: { value: new Vector2() }
  });
  material.fragmentShader = `
    uniform float uOpticsAura;
    uniform float uOpticsStreak;
    uniform float uOpticsThreshold;
    uniform vec2 uOpticsAxis;
    uniform vec2 uOpticsTexel;
  ` + material.fragmentShader;
  material.fragmentShader = material.fragmentShader.replace('void main() {', `
    vec3 opticalSource(vec2 uv) {
      // Zero outside the frame; clamping a bright edge would create a streak.
      if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) return vec3(0.0);
      // The second existing mip suppresses the wire grid before convolution;
      // a sharp source would repeat individual mesh lines along the streak.
      vec3 source = texture2D(blurTexture2, uv).rgb;
      float luminance = dot(source, vec3(0.2126, 0.7152, 0.0722));
      if (luminance <= uOpticsThreshold) return vec3(0.0);
      // Emit streaks from vertical brightness peaks, not whole lit faces.
      // Otherwise horizontal convolution extrudes mountains into light sheets.
      vec2 vertical = vec2(0.0, uOpticsTexel.y * 3.0);
      float above = dot(texture2D(blurTexture2, uv + vertical).rgb, vec3(0.2126, 0.7152, 0.0722));
      float below = dot(texture2D(blurTexture2, uv - vertical).rgb, vec3(0.2126, 0.7152, 0.0722));
      // Soft positive curvature has finite width. A hard local-max mask would
      // turn a smooth source into subpixel ridges and produce repeated copies.
      float peak = smoothstep(0.03, 0.25, luminance - 0.5 * (above + below));
      return source * peak * smoothstep(uOpticsThreshold, uOpticsThreshold * 2.0, luminance);
    }
    void main() {`);
  material.fragmentShader = material.fragmentShader.replace(marker, `
    vec3 streak = opticalSource(vUv);
    float totalWeight = 1.0;
    for (int i = 1; i <= 16; i++) {
      float distance = float(i) / 16.0;
      float weight = exp(-3.0 * distance);
      vec2 offset = uOpticsAxis * distance;
      streak += (opticalSource(vUv + offset) + opticalSource(vUv - offset)) * weight;
      totalWeight += 2.0 * weight;
    }
    streak /= totalWeight;
    vec3 aura = texture2D(blurTexture3, vUv).rgb * 0.60
      + texture2D(blurTexture4, vUv).rgb * 0.40;
    bloom += bloomStrength * (uOpticsStreak * streak + uOpticsAura * aura);
    ${marker}`);
  material.needsUpdate = true;

  // Fixed angular size relative to the viewport height, independent of aspect
  // ratio and DPR. Resize through the existing pass lifecycle, no extra loop.
  const setSize = bloom.setSize.bind(bloom);
  bloom.setSize = (width, height) => {
    setSize(width, height);
    material.uniforms.uOpticsAxis.value.set(
      NEON_OPTICS_R8A.streakRadius * height / Math.max(width, 1), 0
    );
    material.uniforms.uOpticsTexel.value.set(
      1 / bloom.renderTargetsVertical[1].width,
      1 / bloom.renderTargetsVertical[1].height
    );
  };
  bloom.setSize(bloom.resolution.x, bloom.resolution.y);
}
