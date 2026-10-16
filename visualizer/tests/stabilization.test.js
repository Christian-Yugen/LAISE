import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const main = fs.readFileSync(new URL('../src/main.js', import.meta.url), 'utf8').replaceAll('\r\n', '\n');
const html = fs.readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const manifest = JSON.parse(fs.readFileSync(new URL('../public/audio/tukana-visualizer-manifest.json', import.meta.url), 'utf8'));
const functions = main.split('// BEGIN TECHNICAL MANIFEST')[1].split('// END TECHNICAL MANIFEST')[0];
const ids = ['trackTitle', 'masterLabel', 'integratedLufs', 'truePeak', 'spatialIntegrity',
  'sourceCount', 'spatialSource', 'stemsState', 'motionState', 'visualizerVersion', 'deliveryStatus'];
function hud() {
  const nodes = Object.fromEntries(ids.map(id => [id, {textContent: '', dataset: {}}]));
  const context = vm.createContext({document: {getElementById: id => nodes[id]}});
  vm.runInContext(functions, context);
  return {nodes, validate: (data, url = manifest.master_url) => context.validateTechnicalManifest(data, url),
    render: data => context.renderTechnicalHud(data)};
}
function duration(initial) {
  const audio = new EventTarget(); audio.duration = initial;
  const label = {textContent: '00:00'};
  const context = vm.createContext({audio, durationLabel: label});
  const start = main.indexOf('function formatTime(');
  const end = main.indexOf('audio.addEventListener(\n  "timeupdate"', start);
  assert.ok(start >= 0 && end > start);
  vm.runInContext(main.slice(start, end).replaceAll('\r\n', '\n'), context);
  return {audio, label};
}

test('duration: metadata available before handlers synchronizes immediately', () => {
  assert.equal(duration(330).label.textContent, '05:30');
});
test('duration: later metadata and durationchange use actual media duration', () => {
  const {audio, label} = duration(NaN);
  assert.equal(label.textContent, '00:00');
  audio.duration = 330; audio.dispatchEvent(new Event('loadedmetadata'));
  assert.equal(label.textContent, '05:30');
  audio.duration = 95; audio.dispatchEvent(new Event('durationchange'));
  assert.equal(label.textContent, '01:35');
});
test('duration: nonpositive and nonfinite values never replace valid duration', () => {
  const {audio, label} = duration(330);
  for (const value of [0, -1, NaN, Infinity]) {
    audio.duration = value; audio.dispatchEvent(new Event('durationchange'));
    assert.equal(label.textContent, '05:30');
  }
});
test('manifest: approved schema validates', () => {
  assert.equal(hud().validate(manifest), manifest);
});
test('manifest: missing required fields are rejected', () => {
  for (const key of Object.keys(manifest).filter(key => key !== 'provenance')) {
    const copy = {...manifest}; delete copy[key];
    assert.throws(() => hud().validate(copy), undefined, key);
  }
});
test('manifest: invalid types, nonfinite numbers, count and status rejected', () => {
  for (const patch of [
    {schema_version: 'other'}, {track: 42}, {master_sha256: 'bad'},
    {integrated_lufs: '-16.9'}, {integrated_lufs: NaN}, {true_peak_dbtp: Infinity},
    {spatial_integrity: -1}, {spatial_integrity: 101}, {duration_seconds: 0},
    {source_count: 0}, {source_count: -1}, {source_count: 1.5},
    {sample_rate: '48000'}, {channels: null}, {delivery_status: 'PASS'},
    {stems_state: 'V2 READY'}, {motion_state: 'LIVE'}, {master_url: '/audio/other.wav'}
  ]) assert.throws(() => hud().validate({...manifest, ...patch}));
  assert.throws(() => hud().validate(null));
});
test('HUD: values come from supplied manifest, not literal application metrics', () => {
  const {nodes, render} = hud();
  render({...manifest, track: 'Another track', integrated_lufs: -20.123,
    true_peak_dbtp: -3.5, spatial_integrity: 88.8, source_count: 7,
    spatial_source: 'T123', delivery_source: 'T456', visualizer_version: 'V1.1R1'});
  assert.equal(nodes.trackTitle.textContent, 'Another track');
  assert.equal(nodes.integratedLufs.textContent, '-20.12');
  assert.equal(nodes.truePeak.textContent, '-3.50');
  assert.equal(nodes.spatialIntegrity.textContent, '88.80');
  assert.equal(nodes.sourceCount.textContent, '7 SOURCES');
  assert.equal(nodes.spatialSource.textContent, 'T123');
  assert.equal(nodes.deliveryStatus.dataset.source, 'T456');
  assert.equal(nodes.masterLabel.dataset.masterUrl, manifest.master_url);
  assert.equal(nodes.masterLabel.dataset.masterSha256, manifest.master_sha256);
  assert.equal(nodes.stemsState.textContent, 'V1.1R1 READY');
  assert.equal(nodes.motionState.textContent, 'V1.1R1 OFFLINE');
});
test('HUD: approved manifest preserves current numeric values', () => {
  const {nodes, render} = hud(); render(manifest);
  for (const [id, value] of Object.entries({integratedLufs: '-16.90', truePeak: '-2.00',
    spatialIntegrity: '97.34', sourceCount: '12 SOURCES', spatialSource: 'T007', deliveryStatus: 'VALIDATED'})) {
    assert.equal(nodes[id].textContent, value);
  }
});
test('HUD: failure clears metadata instead of retaining a false validation claim', () => {
  const {nodes, render} = hud(); render(manifest); render(null);
  for (const id of ids) assert.equal(nodes[id].textContent, id === 'deliveryStatus' ? 'UNAVAILABLE' : '--');
  assert.equal(nodes.deliveryStatus.dataset.source, '');
  assert.equal(nodes.masterLabel.dataset.masterSha256, '');
});
test('HTML: technical slots are neutral placeholders and old hardcodes absent', () => {
  for (const id of ids) assert.match(html, new RegExp(`id="${id}">\\s*--\\s*<`));
  assert.doesNotMatch(html, /-16\.90|-2\.00|97\.34|12 SOURCES|T007 LOCKED|V002 READY|>VALIDATED</);
});
test('dead lights: only unlit materials; no PointLights or exclusive bass computations', () => {
  const materials = [...main.matchAll(/new THREE\.(\w+Material)\(/g)].map(m => m[1]);
  assert.ok(materials.length > 0);
  assert.ok(materials.every(m => ['MeshBasicMaterial', 'PointsMaterial'].includes(m)));
  assert.doesNotMatch(main, /new THREE\.PointLight|warmLight|coolLight|bandEnergy\(|const bass\s*=/);
  assert.match(main, /analyser\.getByteFrequencyData/);
  assert.match(main, /0\.45 \+ Math\.min\(averageEnergy \* 0\.8, 0\.25\)/);
});
