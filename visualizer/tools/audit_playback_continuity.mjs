import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {performance} from 'node:perf_hooks';
import {AudioCueTimeline} from '../src/audio-cue-timeline.js';
import {AudioCueTimeline as Before} from '../tests/fixtures/r3b-pre-continuity/src/audio-cue-timeline.js';
import {RippleField} from '../src/ripple-field.js';
const out=new URL('../reports/v1_2br3b_r1-playback-continuity/',import.meta.url);
const data=JSON.parse(readFileSync(new URL('../public/audio/tukana-stem-cues.json',import.meta.url)));
const result={tolerance:1e-6,stalls:[],seeks:[],benchmarks:[],seed:73129};
function engine(Type=AudioCueTimeline){
 const t=new Type(data),f=new RippleField(16,16,128,128),ids=[],times=[];
 const emit=c=>{ids.push(data.events.indexOf(c));times.push(c.time);f.exciteAt(c.x,c.z,c.strength,c.width)};
 return {t,f,ids,times,step:time=>t.step(time,true,emit,dt=>f.advance(dt)),pause:time=>t.step(time,false,emit,dt=>f.advance(dt))};
}
function equal(a,b){assert.deepEqual(a.ids,b.ids);assert.deepEqual(a.times,b.times);assert.equal(a.t.index,b.t.index);assert.equal(a.t.lastTime,b.t.lastTime);const errors={};for(const k of ['heights','velocities']){let max=0;for(let i=0;i<a.f[k].length;i++)max=Math.max(max,Math.abs(a.f[k][i]-b.f[k][i]));errors[k]=max;assert.ok(max<=result.tolerance,`${k}: ${max}`);}return errors;}
function advance(e,start,end){for(let i=1;start+i/60<end;i++)e.step(start+i/60);e.step(end);}
const starts=[0,3,46,156.0992,200,325,...[-1e-5,0,1e-5].map(d=>data.events[4000].time+d)];
for(const ms of [50,100,250,301,350,500,950,1500,3000,5000])for(const start of starts){
 const end=Math.min(330,start+ms/1000),a=engine(),b=engine();a.t.seek(start);b.t.seek(start);
 advance(a,start,end);b.step(end);const errors=equal(a,b);
 const expected=data.events.map((c,i)=>({c,i})).filter(x=>x.c.time>=start&&x.c.time<=end).map(x=>x.i);
 assert.deepEqual(b.ids,expected);assert.equal(new Set(b.ids).size,b.ids.length);
 result.stalls.push({ms,start,end,count:b.ids.length,...errors});
}
console.log('90 synthetic stall/boundary cases PASS');
const normal=engine(),before=engine(Before),stress=engine();
advance(normal,0,330);advance(before,0,330);result.normalBeforeAfter=equal(normal,before);
let seed=result.seed;const random=()=>((seed=(1664525*seed+1013904223)>>>0)/2**32);
let time=0;while(time<330){time=Math.min(330,time+(random()<.22?.02+random()*1.48:1/60));stress.step(time);}
result.stress={...equal(normal,stress),applied:stress.ids.length,unique:new Set(stress.ids).size,nextCueIndex:stress.t.index,simulationTime:stress.t.simulationTime};assert.equal(stress.ids.length,10282);
// End flush without a following render; replay begins an independent epoch.
const ending=engine();advance(ending,0,329);ending.step(330);equal(normal,ending);const epoch=ending.t.playbackEpoch;
ending.t.seek(0);ending.f.reset();ending.ids.length=0;ending.times.length=0;advance(ending,0,330);equal(normal,ending);assert.equal(ending.t.playbackEpoch,epoch+1);
result.endedReplay={applied:ending.ids.length,epoch:ending.t.playbackEpoch};
for(const intervals of [[[0,2],[120,122],[30,32]],[[0,1],[329,330],[.001,1]],[[46,47],[200,201],[46,48]]]){
 const e=engine();let expected=[];for(const [start,end] of intervals){e.t.seek(start);e.f.reset();const epoch=e.t.playbackEpoch;e.pause(start);e.pause(start);assert.equal(e.t.playbackEpoch,epoch);advance(e,start,end);expected.push(...data.events.map((c,i)=>({c,i})).filter(x=>x.c.time>=start&&x.c.time<=end).map(x=>x.i));}assert.deepEqual(e.ids,expected);result.seeks.push({intervals,applied:e.ids.length,epoch:e.t.playbackEpoch});
}
result.sameTimestampPairs=data.events.filter((c,i)=>i&&c.time===data.events[i-1].time).length;
for(const seconds of [1,3,5,10]){const e=engine();e.t.seek(150);const start=performance.now();e.step(150+seconds);result.benchmarks.push({seconds,milliseconds:performance.now()-start});}
result.pass=true;writeFileSync(new URL('synthetic-audit.json',out),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
