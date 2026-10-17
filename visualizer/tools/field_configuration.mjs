// Validation-only access to the actual entry-point configuration, not a second config.
import { readFileSync } from 'node:fs';
import * as THREE from 'three';

export const fieldSource = () => readFileSync(new URL('../src/main.js', import.meta.url), 'utf8');
export function fieldConfiguration() {
  const source = fieldSource();
  const terrain = new Function(`return (${source.match(/const TERRAIN = Object.freeze\((\{[^\n]+\})\)/)[1]});`)();
  return {...terrain, segmentsX: Number(source.match(/const SEG_X = (\d+)/)[1]),
    segmentsZ: Number(source.match(/const SEG_Z = (\d+)/)[1])};
}

export function compositionProbe(width, height) {
  const source = fieldSource();
  const start = source.indexOf('const TERRAIN =');
  const end = source.indexOf('frameTerrain();', start) + 'frameTerrain();'.length;
  const rect = (left, top, w, h) => ({left, top, right: left+w, bottom: top+h, width: w, height: h});
  const rectangles = {
    '.brand': rect(45,34,299.4375,89), '.field-summary': rect(45,139,356.265625,10),
    '.status': rect(width-213.421875,38,169.421875,33),
    '.listener': rect(width/2-55.2890625,height-202,110.578125,73),
    '.hud': rect(24,height-114,width-48,94)
  };
  const get = new Function('THREE','window','document',source.slice(start,end) +
    '; return {camera, TERRAIN, BASE_POSE, CAMERA, fieldEnvelope, convexHull, polygonsOverlap};');
  const result = get(THREE, {innerWidth: width,innerHeight: height}, {
    querySelector: selector => ({getBoundingClientRect: () => rectangles[selector]})
  });
  const {camera,TERRAIN,BASE_POSE} = result;
  const rotation = new THREE.Euler(BASE_POSE.pitch,BASE_POSE.yaw,BASE_POSE.roll);
  result.base = [-TERRAIN.width/2,TERRAIN.width/2].flatMap(x=>[-TERRAIN.depth/2,TERRAIN.depth/2].map(z=>{
    const p=new THREE.Vector3(x,0,z).applyEuler(rotation).add(new THREE.Vector3(0,BASE_POSE.y,0)).project(camera);
    return {local:[x,z],ndc:p.toArray(),pixel:[(p.x+1)*width/2,(1-p.y)*height/2]};
  }));
  result.envelope = result.fieldEnvelope().map(p=>p.clone().project(camera));
  result.rectangles = rectangles;
  return result;
}
