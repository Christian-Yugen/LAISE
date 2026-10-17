import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { readFileSync } from 'node:fs';
import { AudioMotionRecovery, approvedResponseSensitivity } from '../src/audio-motion-recovery.js';
import { compositionProbe } from '../tools/field_configuration.mjs';

const source=readFileSync(new URL('../src/audio-motion-recovery.js',import.meta.url),'utf8');
const reference=source.split('// BEGIN APPROVED V1.1 REFERENCE')[1].split('// END APPROVED V1.1 REFERENCE')[0];
function legacy(w,h) {
  return new Function('THREE','window',reference+';return {camera,BASE_POSE};')(THREE,{innerWidth:w,innerHeight:h});
}
function rig(model) {
  const result=new THREE.Group();result.position.y=model.BASE_POSE.y;
  result.rotation.set(model.BASE_POSE.pitch,model.BASE_POSE.yaw,model.BASE_POSE.roll);
  result.updateWorldMatrix(true,false);return result;
}
function displacement(model,group,w,h,height) {
  const base=new THREE.Vector3(0,0,0).applyMatrix4(group.matrixWorld).project(model.camera);
  const p=new THREE.Vector3(0,height,0).applyMatrix4(group.matrixWorld).project(model.camera);
  return Math.hypot((p.x-base.x)*w/2,(p.y-base.y)*h/2);
}

test('approved response calibration retains the known V1.1 center sensitivity',()=>{
  assert.ok(Math.abs(approvedResponseSensitivity(1920,1080)-82.8894383323)<1e-6);
});
test('approved baseline passed as current projection needs no recovery gain',()=>{
  const baseline=legacy(1920,1080);const gain=new AudioMotionRecovery().gainFor(baseline.camera,rig(baseline),1920,1080);
  assert.ok(Math.abs(gain-1)<1e-10);
});
for(const [w,h] of [[1920,1080],[1920,960],[1600,900],[1366,768],[2560,1440],[3840,2160]]) {
  test(`recovers weak transient visibility without camera/pose mutation ${w}x${h}`,()=>{
    const old=legacy(w,h),current=compositionProbe(w,h),a=rig(old),b=rig(current);
    const cameraBefore=current.camera.matrixWorld.toArray(),projectionBefore=current.camera.projectionMatrix.toArray(),poseBefore=b.matrixWorld.toArray();
    const recovery=new AudioMotionRecovery();const gain=recovery.gainFor(current.camera,b,w,h);
    assert.ok(gain>1&&Number.isFinite(gain));
    assert.equal(recovery.gainFor(current.camera,b,w,h),gain);
    for(const raw of [.02,.05,.1,.2]) {
      const expected=displacement(old,a,w,h,2.8*Math.tanh(raw/2.8));
      const before=displacement(current,b,w,h,2.8*Math.tanh(raw/2.8));
      const after=displacement(current,b,w,h,2.8*Math.tanh(raw*gain/2.8));
      assert.ok(Math.abs(after-expected)<Math.abs(before-expected));
      assert.ok(Math.abs(after/expected-1)<.03);
    }
    for(const raw of [-100,-3,-.01,0,.01,3,100]) {
      const mapped=2.8*Math.tanh(raw*gain/2.8);
      assert.ok(Number.isFinite(mapped)&&Math.abs(mapped)<=2.8);
      assert.equal(Math.sign(mapped),Math.sign(raw));
    }
    assert.deepEqual(current.camera.matrixWorld.toArray(),cameraBefore);
    assert.deepEqual(current.camera.projectionMatrix.toArray(),projectionBefore);
    assert.deepEqual(b.matrixWorld.toArray(),poseBefore);
  });
}
test('gain cache responds to a projection change without introducing attack/decay state',()=>{
  const current=compositionProbe(1920,1080),group=rig(current),recovery=new AudioMotionRecovery();
  const first=recovery.gainFor(current.camera,group,1920,1080);
  current.camera.zoom*=2;current.camera.updateProjectionMatrix();
  assert.ok(Math.abs(recovery.gainFor(current.camera,group,1920,1080)-first/2)<1e-8);
  assert.equal(recovery.gainFor(current.camera,group,1920,1080),recovery.gain);
});
