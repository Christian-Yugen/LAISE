// R9 experiment: geometric articulation of every positive recorded attack.
// This is an additive presentation layer, not a new audio/onset detector.
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

export class EventWaveDetailR9 {
  constructor(data, width, depth, segmentsX, segmentsZ) {
    this.width = width;
    this.depth = depth;
    this.columns = segmentsX + 1;
    this.rows = segmentsZ + 1;
    this.dx = width / segmentsX;
    this.dz = depth / segmentsZ;
    this.heights = new Float32Array(this.columns * this.rows);
    this.accents = new Float32Array(this.columns * this.rows);
    this.contoursEnabled = typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("contours") === "1";
    // R9.1: faster travel and shorter tail; original profile retained.
    const originalWaves = typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("waveprofile") === "original";
    this.lifetime = originalWaves ? 1.15 : 0.85;
    this.speed = originalWaves ? 5.0 : 6.5;
    this.decayTime = originalWaves ? 0.40 : 0.28;
    this.bandWidth = Math.max(0.16, 1.25 * Math.max(this.dx, this.dz));
    this.events = [];
    this.rejected = 0;
    for (const b of data.behaviors) {
      for (const [kind, attacks] of [
        ['attack', b.attacks ?? []],
        ['reinforcement', b.reinforcementAttacks ?? []]
      ]) {
        for (const a of attacks) {
          const drive = kind === 'attack' ? a.drive
            : (a.physicalAttackDrive ?? a.residualDrive);
          if (![a.time, a.x, a.z, drive].every(Number.isFinite) || drive <= 0) {
            this.rejected++;
            continue;
          }
          this.events.push({ time: a.time, x: a.x, z: a.z, drive,
            source: b.source, kind, behaviorId: b.behaviorId });
        }
      }
    }
    this.events.sort((a, b) => a.time - b.time || a.source.localeCompare(b.source));
    this.seek(0);
  }

  seek(time) {
    if (!Number.isFinite(time)) return;
    let lo = 0, hi = this.events.length;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (this.events[mid].time < time) lo = mid + 1;
      else hi = mid;
    }
    this.index = lo;
    this.lastTime = time;
    this.active = [];
    this.heights.fill(0);
    this.accents.fill(0);
    this.emitted = 0;
    this.bySource = {};
    this.lastEvent = null;
  }

  update(time, playing, anchorX = 0, anchorZ = 0) {
    if (!Number.isFinite(time) || !playing) return false;
    if (time < this.lastTime - 1e-9) {
      this.seek(time);
      return false;
    }
    // No throttle, dominant-source filter or event-count cap.
    while (this.index < this.events.length && this.events[this.index].time <= time + 1e-9) {
      const e = this.events[this.index++];
      const x = clamp(e.x - anchorX, -1, 1) * this.width / 2;
      const z = clamp(e.z - anchorZ, -1, 1) * this.depth / 2;
      // Bounded visual amplitude, monotonic in recorded drive; no nonzero floor.
      const amplitude = 0.65 * Math.sqrt(e.drive / (e.drive + 0.004));
      this.active.push({ ...e, x, z, amplitude });
      this.emitted++;
      this.bySource[e.source] = (this.bySource[e.source] ?? 0) + 1;
      this.lastEvent = { time: e.time, source: e.source, kind: e.kind };
    }
    this.active = this.active.filter(e => time - e.time < this.lifetime);
    this.heights.fill(0);
    this.accents.fill(0);
    const w = this.bandWidth;
    for (const e of this.active) {
      const age = Math.max(0, time - e.time);
      const radius = this.speed * age;
      const support = radius + 3 * w;
      const envelope = (1 - Math.exp(-age / 0.012)) * Math.exp(-age / this.decayTime)
        * (1 - clamp(age / this.lifetime, 0, 1)) ** 2;
      const amp = e.amplitude * envelope;
      // A short crest remains readable over a tall sustained surface.
      // Max composition avoids multiplying brightness for coincident stems.
      const accent = this.contoursEnabled
        ? Math.min(1, e.amplitude / 0.65)
          * (1 - Math.exp(-age / 0.012)) * Math.exp(-age / 0.20)
        : 0;
      const c0 = Math.max(0, Math.floor((e.x - support + this.width / 2) / this.dx));
      const c1 = Math.min(this.columns - 1, Math.ceil((e.x + support + this.width / 2) / this.dx));
      const r0 = Math.max(0, Math.floor((e.z - support + this.depth / 2) / this.dz));
      const r1 = Math.min(this.rows - 1, Math.ceil((e.z + support + this.depth / 2) / this.dz));
      for (let row = r0; row <= r1; row++) {
        const dz = -this.depth / 2 + row * this.dz - e.z;
        for (let col = c0; col <= c1; col++) {
          const dx = -this.width / 2 + col * this.dx - e.x;
          const q = (Math.hypot(dx, dz) - radius) / w;
          if (Math.abs(q) > 3) continue;
          const index = row * this.columns + col;
          this.heights[index] += amp * (1 - q * q) * Math.exp(-q * q / 2);
          if (this.contoursEnabled && Math.abs(q) < 1.5) {
            this.accents[index] = Math.max(this.accents[index],
              accent * Math.exp(-2 * q * q));
          }
        }
      }
    }
    this.lastTime = time;
    return true;
  }

  get debug() {
    return { mode: 'R9_EVENT_DETAIL', totalRecorded: this.events.length,
      rejected: this.rejected, emittedSinceSeek: this.emitted,
      bySource: { ...this.bySource }, activePackets: this.active.length,
      time: this.lastTime, lastEvent: this.lastEvent };
  }
}

