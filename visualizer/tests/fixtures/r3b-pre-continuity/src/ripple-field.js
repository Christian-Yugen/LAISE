// Ajustes das ondas: velocidade, dissipacao e intensidade dos impulsos.
export const RIPPLE_SETTINGS = Object.freeze({
  speed: 3.0,
  damping: 0.65,
  edgeDamping: 0.20, // Mais alto: reflexos perdem mais forca nas bordas.
  restoring: 2.5,
  impulseGain: 20,
  step: 1 / 120
});

const clamp = (value, low, high) => Math.max(low, Math.min(high, value));

// Damped wave equation on the terrain's local XZ grid. Heights are signed;
// the renderer applies a smooth amplitude limit, including at the free edges.
export class RippleField {
  constructor(width, depth, segmentsX, segmentsZ) {
    this.columns = segmentsX + 1;
    this.rows = segmentsZ + 1;
    this.heights = new Float32Array(this.columns * this.rows);
    this.velocities = new Float32Array(this.heights.length);
    this.dx = width / segmentsX;
    this.dz = depth / segmentsZ;
    // Keep the explicit solver below the 2D Courant stability limit.
    this.step = Math.min(RIPPLE_SETTINGS.step,
      0.8 / (RIPPLE_SETTINGS.speed * Math.sqrt(1 / this.dx ** 2 + 1 / this.dz ** 2)));
    this.time = 0;
    this.accumulator = 0;
    this.impulseCount = 0;

    // Central bass impacts; mids/highs excite smaller, offset regions.
    const sources = [
      [0, 0, 0.75],
      [-width * 0.16, depth * 0.08, 0.58],
      [width * 0.16, -depth * 0.10, 0.58],
      [width * 0.08, depth * 0.19, 0.40]
    ];
    this.kernels = Array.from({ length: sources.length + 2 }, () => new Float32Array(this.heights.length));
    this.attenuation = new Float32Array(this.heights.length);
    for (let row = 0; row < this.rows; row++) {
      for (let col = 0; col < this.columns; col++) {
        const i = row * this.columns + col;
        const x = -width / 2 + col * this.dx;
        const z = -depth / 2 + row * this.dz;
        const edge = Math.min(col / segmentsX, 1 - col / segmentsX,
          row / segmentsZ, 1 - row / segmentsZ);
        // Mild loss allows the moving edge to reflect most of the arriving wave.
        const edgeZone = Math.max(0, 1 - edge / 0.10);
        this.attenuation[i] = Math.exp(-(RIPPLE_SETTINGS.damping +
          edgeZone ** 2 * RIPPLE_SETTINGS.edgeDamping) * this.step);
        sources.forEach(([cx, cz, sigma], source) => {
          const q = ((x - cx) ** 2 + (z - cz) ** 2) / sigma ** 2;
          // Zero-mean radial impulse: positive center, negative surrounding ring.
          this.kernels[source][i] = (1 - q / 2) * Math.exp(-q / 2);
        });
        // Long impulse profiles create travelling straight/diagonal fronts.
        // Their smooth transverse envelopes avoid a seam at the ends.
        const normals = [[0, 1], [Math.SQRT1_2, Math.SQRT1_2]];
        normals.forEach(([nx, nz], line) => {
          const normal = x * nx + z * nz;
          const tangent = -x * nz + z * nx;
          const q = (normal / 0.70) ** 2;
          const taper = Math.exp(-((tangent / (Math.max(width, depth) * 0.48)) ** 4));
          this.kernels[sources.length + line][i] = (1 - q) * Math.exp(-q / 2) * taper;
        });
      }
    }
  }

  excite(source, strength) {
    const kernel = this.kernels[source];
    if (!kernel || !Number.isFinite(strength) || strength <= 0) return;
    const amplitude = RIPPLE_SETTINGS.impulseGain * clamp(strength, 0, 1);
    for (let row = 0; row < this.rows; row++) {
      for (let col = 0; col < this.columns; col++) {
        const i = row * this.columns + col;
        this.velocities[i] = clamp(this.velocities[i] + kernel[i] * amplitude, -40, 40);
      }
    }
    this.impulseCount++;
  }

  exciteAt(normalizedX, normalizedZ, strength, width = 0.7) {
    if (![normalizedX, normalizedZ, strength, width].every(Number.isFinite) || strength <= 0 || width <= 0) return;
    const cx = (clamp(normalizedX, -1, 1) + 1) * (this.columns - 1) / 2;
    const cz = (clamp(normalizedZ, -1, 1) + 1) * (this.rows - 1) / 2;
    const radiusX = 5 * width / this.dx;
    const radiusZ = 5 * width / this.dz;
    const amplitude = RIPPLE_SETTINGS.impulseGain * clamp(strength, 0, 1);
    // Bounded support keeps independent simultaneous sources inexpensive.
    for (let row = Math.max(0, Math.floor(cz - radiusZ)); row <= Math.min(this.rows - 1, Math.ceil(cz + radiusZ)); row++) {
      for (let col = Math.max(0, Math.floor(cx - radiusX)); col <= Math.min(this.columns - 1, Math.ceil(cx + radiusX)); col++) {
        const q = (((col - cx) * this.dx) ** 2 + ((row - cz) * this.dz) ** 2) / width ** 2;
        if (q > 25) continue;
        const kernel = (1 - q / 2) * Math.exp(-q / 2);
        const i = row * this.columns + col;
        this.velocities[i] = clamp(this.velocities[i] + kernel * amplitude, -40, 40);
      }
    }
    this.impulseCount++;
  }

  advance(delta) {
    this.accumulator += clamp(delta, 0, 0.1);
    const { heights: h, velocities: v, columns: n, step: dt } = this;
    const cx = RIPPLE_SETTINGS.speed ** 2 / this.dx ** 2;
    const cz = RIPPLE_SETTINGS.speed ** 2 / this.dz ** 2;
    while (this.accumulator + 1e-10 >= dt) {
      for (let row = 0; row < this.rows; row++) {
        const previousRow = row === 0 ? n : (row - 1) * n;
        const nextRow = row === this.rows - 1 ? (row - 1) * n : (row + 1) * n;
        for (let col = 0; col < n; col++) {
          const i = row * n + col;
          // Mirrored neighbours impose zero normal slope (free boundary).
          // Edge heights evolve with the field and reflect waves into the grid.
          const left = col === 0 ? i + 1 : i - 1;
          const right = col === n - 1 ? i - 1 : i + 1;
          const acceleration = cx * (h[left] - 2 * h[i] + h[right]) +
            cz * (h[previousRow + col] - 2 * h[i] + h[nextRow + col]) - RIPPLE_SETTINGS.restoring * h[i];
          v[i] = (v[i] + acceleration * dt) * this.attenuation[i];
        }
      }
      // Separate pass: every acceleration uses heights from the same timestep.
      for (let i = 0; i < h.length; i++) h[i] += v[i] * dt;
      this.time += dt;
      this.accumulator -= dt;
    }
  }

  reset() {
    this.heights.fill(0);
    this.velocities.fill(0);
    this.accumulator = 0;
    this.time = 0;
    this.impulseCount = 0;
  }
}
