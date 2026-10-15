import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RippleField } from '../src/ripple-field.js';

const field = () => new RippleField(16, 12, 120, 100);
function advance(f, seconds, fps = 120) {
  for (let i = 0; i < Math.round(seconds * fps); i++) f.advance(1 / fps);
}
function peak(f) {
  let height = -Infinity;
  let radius = 0;
  for (let i = 0; i < f.heights.length; i++) {
    if (f.heights[i] > height) {
      height = f.heights[i];
      radius = Math.hypot((i % f.columns) * f.dx - 8, Math.floor(i / f.columns) * f.dz - 6);
    }
  }
  return { height, radius };
}

test('an impulse forms a central peak, then an outward ring with troughs and decay', () => {
  const f = field();
  f.excite(0, 1);
  advance(f, 0.15);
  const initial = peak(f);
  advance(f, 0.5);
  const middle = peak(f);
  advance(f, 0.5);
  const later = peak(f);
  assert.ok(initial.height > 1 && initial.radius < 0.3);
  assert.ok(middle.radius > 1 && later.radius > middle.radius + 1);
  assert.ok(Math.min(...f.heights) < -0.05);
  // Reflected waves persist after their first trip, but still settle naturally.
  advance(f, 14);
  assert.ok(Math.max(...f.heights.map(Math.abs)) < 0.01);
});

test('fixed timesteps give matching motion at 30 and 120 rendered frames per second', () => {
  const a = field();
  const b = field();
  a.excite(0, 0.8);
  b.excite(0, 0.8);
  advance(a, 2, 30);
  advance(b, 2, 120);
  for (let i = 0; i < a.heights.length; i++) assert.ok(Math.abs(a.heights[i] - b.heights[i]) < 1e-6);
});

test('without measured audio events the surface stays flat', () => {
  const f = field();
  advance(f, 10);
  assert.equal(f.impulseCount, 0);
  assert.ok(f.heights.every(h => h === 0));
});

test('repeated impacts move the boundary, remain finite, and reset cleanly on a seek', () => {
  const f = field();
  for (let i = 0; i < 900; i++) {
    if (i % 15 === 0) f.excite((i / 15) % 6, 1);
    f.advance(1 / 60);
  }
  assert.ok(f.heights.every(Number.isFinite));
  let edgeMotion = 0;
  for (let row = 0; row < f.rows; row++) {
    for (let col = 0; col < f.columns; col++) {
      if (row === 0 || col === 0 || row === f.rows - 1 || col === f.columns - 1) {
        edgeMotion = Math.max(edgeMotion, Math.abs(f.heights[row * f.columns + col]));
      }
    }
  }
  assert.ok(edgeMotion > 0.05);
  advance(f, 24);
  assert.ok(Math.max(...f.heights.map(Math.abs)) < 0.005);
  f.reset();
  assert.equal(f.impulseCount, 0);
  assert.ok(f.heights.every(h => h === 0));
  assert.ok(f.velocities.every(v => v === 0));
});

test('a wave reaches the free edge and returns to the center', () => {
  const f = field();
  // Same spatial resolution, distant Z edges: no Z reflection returns by t=4s.
  const distantEdges = new RippleField(16, 36, 120, 300);
  f.excite(0, 1);
  distantEdges.excite(0, 1);
  advance(f, 2);
  advance(distantEdges, 2);
  const center = 50 * 121 + 60;
  const referenceCenter = 150 * 121 + 60;
  assert.ok(Math.abs(f.heights[60]) > 0.1, 'the edge itself must rise and fall');
  assert.ok(Math.abs(f.heights[center] - distantEdges.heights[referenceCenter]) < 0.001);
  advance(f, 2);
  advance(distantEdges, 2);
  assert.ok(Math.abs(f.heights[center] - distantEdges.heights[referenceCenter]) > 0.05,
    'the returned wave must reach the center, unlike in the distant-edge field');
});

test('an elongated impulse produces a broad, nearly straight travelling crest', () => {
  const line = field();
  const circular = field();
  line.excite(4, 1);
  circular.excite(0, 1);
  advance(line, 0.15);
  advance(circular, 0.15);
  const centerRow = 50 * 121;
  const center = line.heights[centerRow + 60];
  const side = line.heights[centerRow + 82];
  assert.ok(side > 1 && side / center > 0.85);
  assert.ok(Math.abs(circular.heights[centerRow + 82]) < 0.02);
});

test('crossing circular and straight waves reinforce and cancel each other', () => {
  const a = field();
  const b = field();
  const combined = field();
  a.excite(0, 0.5);
  b.excite(5, 0.5);
  combined.excite(0, 0.5);
  combined.excite(5, 0.5);
  advance(a, 1);
  advance(b, 1);
  advance(combined, 1);
  let reinforcement = false;
  let cancellation = false;
  for (let i = 0; i < a.heights.length; i++) {
    const x = a.heights[i];
    const y = b.heights[i];
    const sum = combined.heights[i];
    assert.ok(Math.abs(sum - x - y) < 1e-5);
    if (x > 0.02 && y > 0.02 && sum > Math.max(x, y)) reinforcement = true;
    if (x * y < 0 && Math.min(Math.abs(x), Math.abs(y)) > 0.02 &&
        Math.abs(sum) < Math.max(Math.abs(x), Math.abs(y))) cancellation = true;
  }
  assert.ok(reinforcement && cancellation);
});
