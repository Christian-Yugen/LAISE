import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {compositionProbe} from '../tools/field_configuration.mjs';
const baseline=JSON.parse(readFileSync(new URL('./r1-composition-baseline.json',import.meta.url)));
for(const [key,old] of Object.entries(baseline))test(`R3B approved width, lowered center and signed overlay envelope ${key}`,()=>{
  const [w,h]=key.split('x').map(Number),p=compositionProbe(w,h);
  const xs=p.base.map(c=>c.pixel[0]),ys=p.base.map(c=>c.pixel[1]);
  const width=Math.max(...xs)-Math.min(...xs),front=Math.max(...ys);
  assert.ok(width>old.width*(w<=1920?1.15:1.05));
  assert.ok(Math.abs(width-w*1682.861971225252/1920)<1e-5);
  assert.ok(front>old.front+h*.02);
  const centerY=(Math.min(...ys)+Math.max(...ys))/2;
  assert.ok(centerY>old.center+h*.05);
  assert.ok(Math.abs(Math.min(...xs)+Math.max(...xs)-w)<1e-6);
  assert.equal(p.camera.type,'OrthographicCamera');
  for(const q of p.envelope){
    const x=(q.x+1)*w/2,y=(1-q.y)*h/2;
    assert.ok(x>0&&x<w&&y>0&&q.z>-1&&q.z<1);
  }
});
test('approved R1 calibration and physical equations remain byte-identical',()=>{
  for(const [name,expected] of Object.entries({
    'audio-motion-recovery.js':'2a9939775cbd54c0025eca3c594a69ae0d3324bfbc1d2dd882d24836abc05e21',
    'ripple-field.js':'3525e4ee424a4af054be7195129dc6c458b1132412b46921ef6b42e9f7a03f50'
  }))assert.equal(createHash('sha256').update(readFileSync(new URL('../src/'+name,import.meta.url))).digest('hex'),expected);
});
test('pre-recovery temporal baseline is retained for normal-before/after regression',()=>{
  assert.equal(createHash('sha256').update(readFileSync(new URL('./fixtures/r3b-pre-continuity/src/audio-cue-timeline.js',import.meta.url))).digest('hex'),'035b469b9d8af2e4775bc8dfed8ff08f01aefc90427da286e0b18ed17ba18b9d');
});
