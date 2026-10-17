import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { RippleField, RIPPLE_SETTINGS } from '../src/ripple-field.js';
import { AudioCueTimeline } from '../src/audio-cue-timeline.js';
import { fieldConfiguration, compositionProbe } from '../tools/field_configuration.mjs';

const config=fieldConfiguration();
const field=()=>new RippleField(config.width,config.depth,config.segmentsX,config.segmentsZ);
function advance(f,seconds) {for(let i=0;i<Math.round(seconds*120);i++)f.advance(1/120);}
test('square domain: actual geometry has unit aspect, isotropic cells and stable CFL',()=>{
  const f=field();
  assert.equal(config.width,config.depth);
  assert.equal(f.columns,f.rows);
  assert.equal(f.dx,f.dz);
  assert.equal(f.heights.length,16641);
  assert.ok(RIPPLE_SETTINGS.speed*f.step*Math.sqrt(1/f.dx**2+1/f.dz**2)<.8);
  const geometry=new THREE.PlaneGeometry(config.width,config.depth,config.segmentsX,config.segmentsZ);
  geometry.rotateX(-Math.PI/2);
  const positions=geometry.attributes.position;
  assert.equal(positions.count,f.heights.length);
  assert.ok(Math.abs(positions.getZ(0)+config.depth/2)<1e-6);
  assert.ok(Math.abs(positions.getZ(positions.count-1)-config.depth/2)<1e-6);
  assert.equal(geometry.index.count/3,32768);
});

const directions=[['center',0,0],['left',-1,0],['right',1,0],
  ['front / T007 negative Z',0,-1],['rear / T007 positive Z',0,1],
  ['left-front',-.5,-.5],['right-front',.5,-.5],['left-rear',-.5,.5],['right-rear',.5,.5]];
for(const [name,x,z] of directions)test(`mapping preserves ${name}`,()=>{
  const f=field();f.exciteAt(x,z,.6,.64);
  let index=0;for(let i=1;i<f.velocities.length;i++)if(f.velocities[i]>f.velocities[index])index=i;
  assert.ok(Math.abs((index%f.columns)/(f.columns-1)*2-1-x)<1e-8);
  assert.ok(Math.abs(Math.floor(index/f.columns)/(f.rows-1)*2-1-z)<1e-8);
});

for(const [name,x,z] of [['center',0,0],['left',-.5,0],['right',.5,0],['front',0,-.5],['rear',0,.5]]) {
  test(`isotropy: ${name} impulse agrees under X/Z transpose (relative L2 < 1e-5)`,()=>{
    const a=field(),b=field();a.exciteAt(x,z,.8,.64);b.exciteAt(z,x,.8,.64);
    advance(a,3);advance(b,3);let error=0,power=0;
    for(let row=0;row<a.rows;row++)for(let col=0;col<a.columns;col++) {
      const h=a.heights[row*a.columns+col];const d=h-b.heights[col*b.columns+row];error+=d*d;power+=h*h;
    }
    assert.ok(Math.sqrt(error/Math.max(power,1e-20))<1e-5);
  });
}

for(const [name,x,z] of [['left',-.95,0],['right',.95,0],['front',0,-.95],['rear',0,.95],
  ['left-front',-.95,-.95],['right-front',.95,-.95],['left-rear',-.95,.95],['right-rear',.95,.95]]) {
  test(`free boundary ${name}: finite reflection and dissipation`,()=>{
    const f=field();f.exciteAt(x,z,1,.64);let maximum=0,edge=0;
    for(let frame=0;frame<360;frame++) {
      f.advance(1/60);
      for(let i=0;i<f.heights.length;i++) {
        assert.ok(Number.isFinite(f.heights[i])&&Number.isFinite(f.velocities[i]));
        maximum=Math.max(maximum,Math.abs(f.heights[i]));
        if(i<f.columns||i>=f.heights.length-f.columns||i%f.columns===0||i%f.columns===f.columns-1)edge=Math.max(edge,Math.abs(f.heights[i]));
      }
    }
    assert.ok(maximum<10 && edge>.05);
    advance(f,24);assert.ok(Math.max(...f.heights.map(Math.abs))<.01);
  });
}

for(const [w,h] of [[1920,1080],[1920,960],[1600,900],[1366,768],[2560,1440],[3840,2160]]) {
  test(`diamond signed envelope and R3B listener-overlay composition ${w}x${h}`,()=>{
    const p=compositionProbe(w,h);const margin=Math.min(w,h)*.035;
    assert.ok(p.camera.position.y>p.BASE_POSE.y+config.maxHeight);
    for(const point of p.envelope) {
      const x=(point.x+1)*w/2,y=(1-point.y)*h/2;
      assert.ok(x>=margin-1e-5&&x<=w-margin+1e-5&&y>=8-1e-5);
      assert.ok(point.z>-1&&point.z<1);
    }
    const corners=p.base.map(c=>c.pixel);
    const front=corners.reduce((a,b)=>a[1]>b[1]?a:b),rear=corners.reduce((a,b)=>a[1]<b[1]?a:b);
    const gap=p.rectangles['.listener'].top-front[1];
    assert.ok(Math.abs(gap-Math.max(6,Math.min(w,h)*8/1080))<1e-5);
    assert.ok(corners.every(c=>c[0]>0&&c[0]<w&&c[1]>0&&c[1]<h));
    assert.ok(Math.abs(front[0]-w/2)<1e-6&&Math.abs(rear[0]-w/2)<1e-6);
    assert.ok(Math.abs(Math.min(...corners.map(c=>c[0]))+Math.max(...corners.map(c=>c[0]))-w)<1e-6);
    const hull=p.convexHull(p.envelope.map(q=>({x:(q.x+1)*w/2,y:(1-q.y)*h/2})));
    for(const name of ['.brand','.field-summary','.status']) {
      const r=p.rectangles[name];assert.ok(!p.polygonsOverlap(hull,[{x:r.left,y:r.top},{x:r.right,y:r.top},{x:r.right,y:r.bottom},{x:r.left,y:r.bottom}]));
    }
  });
}

test('musical input 46-48 seconds preserves times, source IDs, strengths and normalized positions',()=>{
  const bytes=readFileSync(new URL('../public/audio/tukana-stem-cues.json',import.meta.url));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),'c880676240a480f72cf3dc42fc5b3a656bd38fd466a79474698abd81b99e944c');
  const data=JSON.parse(bytes);const timeline=new AudioCueTimeline(data);timeline.seek(46);
  const expected=data.events.filter(e=>e.time>=46&&e.time<=48),received=[];let simulated=46;
  for(let i=1;i<=240;i++)timeline.step(46+i/120,true,e=>{
    assert.ok(Math.abs(e.time-simulated)<1e-8);received.push(e);
  },dt=>simulated+=dt);
  assert.deepEqual(received,expected);assert.ok(new Set(received.map(e=>e.source)).size>1);
});
