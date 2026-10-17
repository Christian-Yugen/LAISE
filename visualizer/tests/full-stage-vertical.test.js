import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {compositionProbe} from '../tools/field_configuration.mjs';
import {AudioMotionRecovery} from '../src/audio-motion-recovery.js';
for(const [w,h] of [[1920,1080],[1600,900],[1366,768],[2560,1440]])test(`R3B approved width and listener anchor preserve response under vertical lens shift ${w}x${h}`,()=>{
  const p=compositionProbe(w,h),base=p.base.map(c=>c.pixel);
  assert.ok(Math.abs(Math.max(...base.map(c=>c[0]))-Math.min(...base.map(c=>c[0]))-w*1682.861971225252/1920)<1e-5);
  const gap=p.rectangles['.listener'].top-Math.max(...base.map(c=>c[1]));
  assert.ok(Math.abs(gap-Math.max(6,Math.min(w,h)*8/1080))<1e-6);
  const rig=new THREE.Group();rig.position.y=-.75;rig.rotation.y=Math.PI/4;rig.updateWorldMatrix(true,false);
  const centered=p.camera.clone();centered.clearViewOffset();centered.updateProjectionMatrix();
  const shiftedGain=new AudioMotionRecovery().gainFor(p.camera,rig,w,h);
  const centeredGain=new AudioMotionRecovery().gainFor(centered,rig,w,h);
  assert.ok(Math.abs(shiftedGain-centeredGain)<1e-9);
  if(w===1920)assert.ok(Math.abs(shiftedGain-1.159428692757997)<1e-8);
  for(const height of [-2.8,-.2,0,.2,2.8]){
    const a=new THREE.Vector3(0,height,0).applyMatrix4(rig.matrixWorld).project(p.camera);
    const b=new THREE.Vector3(0,height,0).applyMatrix4(rig.matrixWorld).project(centered);
    const a0=new THREE.Vector3(0,0,0).applyMatrix4(rig.matrixWorld).project(p.camera);
    const b0=new THREE.Vector3(0,0,0).applyMatrix4(rig.matrixWorld).project(centered);
    assert.ok(Math.abs((a.y-a0.y)-(b.y-b0.y))<1e-10);
  }
});
