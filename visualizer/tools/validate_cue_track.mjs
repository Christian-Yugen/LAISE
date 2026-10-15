import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import assert from 'node:assert/strict';
import { AudioCueTimeline } from '../src/audio-cue-timeline.js';
import { RippleField } from '../src/ripple-field.js';

const data=JSON.parse(readFileSync(new URL('../public/audio/tukana-stem-cues.json',import.meta.url),'utf8'));
const timeline=new AudioCueTimeline(data);
const field=new RippleField(16,12,120,100);
let maxHeight=0;
for(let frame=0;frame<=Math.ceil(data.duration*60);frame++) {
  timeline.step(Math.min(data.duration,frame/60),true,
    e=>field.exciteAt(e.x,e.z,e.strength,e.width),dt=>field.advance(dt));
  if(frame%60===0) for(const height of field.heights) {
    assert.ok(Number.isFinite(height));
    maxHeight=Math.max(maxHeight,Math.abs(height));
  }
}
assert.equal(field.impulseCount,data.events.length);
assert.equal(timeline.emittedCount,data.events.length);
for(let i=0;i<240;i++) field.advance(0.1);
const settled=Math.max(...field.heights.map(Math.abs));
assert.ok(settled<0.01);
const report={durationSeconds:data.duration,expectedEvents:data.events.length,
  emittedEvents:field.impulseCount,sourceCount:data.stems.length,
  maxSampledRawHeight:maxHeight,settledHeight:settled,checks:'passed'};
const output=new URL('../validation-stem-sync/',import.meta.url);
mkdirSync(output,{recursive:true});
writeFileSync(new URL('full-track.json',output),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
