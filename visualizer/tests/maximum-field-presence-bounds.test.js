import test from 'node:test';import assert from 'node:assert/strict';
import {DIAGONAL,envelopeHeight,maximumWidth,frontUpperBound} from '../tools/maximum_field_presence_bounds.mjs';
import {compositionProbe} from '../tools/field_configuration.mjs';
test('full signed envelope at fixed R2 angle has a strict zero-margin bound below 92%',()=>{
 const p=compositionProbe(1920,1080),limit=maximumWidth(p.rectangles['.listener'].top,16*Math.PI/180);
 assert.ok(limit<1920*.92&&limit>1920*.88);
 const base=p.base.map(c=>c.pixel);const width=Math.max(...base.map(c=>c[0]))-Math.min(...base.map(c=>c[0]));
 const ys=p.envelope.map(c=>(1-c.y)*1080/2);
 assert.ok(Math.abs(envelopeHeight(width,16*Math.PI/180)-(Math.max(...ys)-Math.min(...ys)))<1e-6);
});
for(const ratio of [.92,.94,.96])test(`width ${ratio*100}% cannot lower FRONT even if elevation were relaxed`,()=>{
 const width=1920*ratio,bound=frontUpperBound(width,878);
 assert.ok(bound.front<676.39);
 assert.ok(bound.elevationDegrees<16);
 assert.ok(Math.abs(envelopeHeight(width,bound.elevationDegrees*Math.PI/180)-878)<1e-6);
});
test('a single admissible front vertex can hit the actual listener border, not just an empty AABB',()=>{
 const width=1920*.94,k=width/DIAGONAL,angle=16*Math.PI/180;
 const flatFront=966-8-2.8*k*Math.cos(angle);
 const y=-(878-flatFront)/(k*Math.cos(angle));
 assert.ok(y>=-2.8&&y<=2.8);
 const projectedY=flatFront-k*Math.cos(angle)*y;
 assert.ok(Math.abs(projectedY-878)<1e-8);
});
