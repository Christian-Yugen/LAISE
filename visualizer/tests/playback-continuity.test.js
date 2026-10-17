import test from 'node:test';
import assert from 'node:assert/strict';
import {AudioCueTimeline} from '../src/audio-cue-timeline.js';
const cue=time=>({time,strength:.5,x:0,z:0,width:.65});
test('950 ms continuous media advance without seek preserves every intervening cue',()=>{
  const t=new AudioCueTimeline({schema:'laise-stem-cues-v1',duration:3,events:[.1,.3,.6,.95,1].map(cue)});
  const seen=[]; let simulated=0;
  const step=time=>t.step(time,true,c=>seen.push([c.time,simulated]),dt=>simulated+=dt);
  step(.05);step(1);
  assert.deepEqual(seen.map(x=>x[0]),[.1,.3,.6,.95,1]);
  for(const [expected,actual] of seen)assert.ok(Math.abs(expected-actual)<1e-8);
});
