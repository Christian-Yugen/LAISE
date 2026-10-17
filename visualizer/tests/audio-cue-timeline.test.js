import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AudioCueTimeline } from '../src/audio-cue-timeline.js';
import { RippleField } from '../src/ripple-field.js';

const cue = (time, strength = 0.5, source = 'drums', x = 0) =>
  ({time,strength,source,x,z:0,width:0.65});
const timeline = events => new AudioCueTimeline({schema:'laise-stem-cues-v1',duration:10,events});

test('three rapid hits emit exactly three impulses, in order and at their subframe times', () => {
  const events = [cue(0.1,0.25),cue(0.2,0.5),cue(0.28,0.9)];
  const track = timeline(events);
  const emitted = [];
  let simulationTime = 0;
  for (const time of [0.08,0.16,0.29]) {
    track.step(time,true,event => emitted.push([event.time,simulationTime,event.strength]),
      dt => simulationTime += dt);
  }
  assert.equal(emitted.length,3);
  emitted.forEach(([time,actual],i) => {
    assert.equal(time,events[i].time);
    assert.ok(Math.abs(time-actual)<1e-8);
  });
  assert.deepEqual(emitted.map(e=>e[2]),[0.25,0.5,0.9]);
});

test('simultaneous sources retain independent positions and absolute strengths', () => {
  const track=timeline([cue(0.1,0.2,'guitar',-0.5),cue(0.1,0.8,'drums',0.5)]);
  const events=[];
  track.step(0.15,true,event=>events.push(event),()=>{});
  assert.equal(events.length,2);
  assert.deepEqual(events.map(e=>e.x),[-0.5,0.5]);
  assert.deepEqual(events.map(e=>e.strength),[0.2,0.8]);
});

test('pause/resume never repeats an attack; seeking skips old hits and permits replay', () => {
  const track=timeline([cue(0.1),cue(0.2),cue(0.4)]);
  const emitted=[];
  const emit=event=>emitted.push(event.time);
  track.step(0.15,true,emit,()=>{});
  track.step(0.15,false,emit,()=>{});
  track.step(0.15,false,emit,()=>{});
  track.step(0.25,true,emit,()=>{});
  assert.deepEqual(emitted,[0.1,0.2]);
  track.seek(0.35);
  track.step(0.45,true,emit,()=>{});
  assert.deepEqual(emitted,[0.1,0.2,0.4]);
  track.seek(0);
  track.step(0.15,true,emit,()=>{});
  assert.deepEqual(emitted,[0.1,0.2,0.4,0.1]);
});

test('explicit discontinuity skips unplayed events instead of creating a burst', () => {
  const track=timeline([cue(0.1),cue(0.2),cue(2.1)]);
  const emitted=[];
  track.seek(2);
  track.step(2,true,e=>emitted.push(e.time),()=>{});
  track.step(2.2,true,e=>emitted.push(e.time),()=>{});
  assert.deepEqual(emitted,[2.1]);
});

test('spatial impulses peak near the requested source and louder hits produce larger waves', () => {
  const weak=new RippleField(16,12,120,100);
  const strong=new RippleField(16,12,120,100);
  weak.exciteAt(-0.45,0.3,0.2);
  strong.exciteAt(-0.45,0.3,0.8);
  for(let i=0;i<18;i++) {weak.advance(1/120);strong.advance(1/120);}
  let index=0;
  for(let i=1;i<strong.heights.length;i++) if(strong.heights[i]>strong.heights[index]) index=i;
  const x=(index%121)/120*2-1;
  const z=Math.floor(index/121)/100*2-1;
  assert.ok(Math.abs(x+0.45)<0.04 && Math.abs(z-0.3)<0.04);
  assert.ok(strong.heights[index]>weak.heights[index]*3.8);
});
