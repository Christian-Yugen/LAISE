// Cues are measured from the aligned stems. The player, not frame count or a
// random emitter, determines when and where each visual impulse is injected.
export class AudioCueTimeline {
  constructor(data) {
    if (data.schema !== 'laise-stem-cues-v1' || !Array.isArray(data.events) ||
        !Number.isFinite(data.duration) || data.duration <= 0) {
      throw new Error('Invalid stem cue timeline');
    }
    let previous = -Infinity;
    for (const cue of data.events) {
      if (!Number.isFinite(cue.time) || cue.time < previous || cue.time < 0 || cue.time > data.duration ||
          !Number.isFinite(cue.strength) || cue.strength < 0 || cue.strength > 1 ||
          !Number.isFinite(cue.x) || !Number.isFinite(cue.z) ||
          Math.abs(cue.x) > 1 || Math.abs(cue.z) > 1 ||
          !Number.isFinite(cue.width) || cue.width <= 0) {
        throw new Error('Invalid stem attack cue');
      }
      previous = cue.time;
    }
    this.events = data.events;
    this.duration = data.duration;
    this.emittedCount = 0;
    this.lastEvent = null;
    this.seek(0);
  }

  seek(time) {
    let low = 0;
    let high = this.events.length;
    while (low < high) {
      const middle = (low + high) >>> 1;
      if (this.events[middle].time < time) low = middle + 1;
      else high = middle;
    }
    this.index = low;
    this.lastTime = time;
    this.emittedCount = 0;
    this.lastEvent = null;
  }

  step(time, playing, emit, advance) {
    if (!Number.isFinite(time)) return false;
    if (!playing) {
      this.lastTime = time;
      return false;
    }
    // A seek/background jump must not release a backlog of old hits at once.
    if (time < this.lastTime || time - this.lastTime > 0.3) this.seek(time);
    let cursor = this.lastTime;
    const advanceTo = next => {
      while (next - cursor > 0.000001) {
        const delta = Math.min(0.1, next - cursor);
        advance(delta);
        cursor += delta;
      }
    };
    while (this.index < this.events.length && this.events[this.index].time <= time) {
      const cue = this.events[this.index++];
      advanceTo(Math.max(cursor, cue.time));
      emit(cue);
      this.emittedCount++;
      this.lastEvent = cue;
    }
    advanceTo(time);
    this.lastTime = time;
    return true;
  }
}
