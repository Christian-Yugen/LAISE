import * as THREE from "three";
const COUNT = 8;
const SPEED = 8.5;
export function addPropagatingGroundR24(scene) {
  const active = Array.from({length: COUNT}, () => new THREE.Vector4(0,0,-1000,0));
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(110,110,128,128),
    new THREE.ShaderMaterial({
      uniforms: {uWaves: {value: active}},
      transparent: true, depthWrite: false, side: THREE.DoubleSide,
      vertexShader: `
        uniform vec4 uWaves[8];
        varying vec2 vWorld;
        varying float vLift;
        void main() {
          vec3 p = position;
          vec2 xz = vec2(p.x,-p.y);
          float lift = 0.0;
          for (int i=0; i<8; i++) {
            vec4 w=uWaves[i];
            float d=length(xz-w.xy);
            float front=(d-w.z)/2.0;
            lift += 0.34 * exp(-front*front) * w.w
              * (front < 0.0 ? -0.65 : 1.0);
          }
          p.z += clamp(lift,-0.38,0.42);
          vLift=lift;
          vec4 world=modelMatrix*vec4(p,1.0);
          vWorld=world.xz;
          gl_Position=projectionMatrix*viewMatrix*world;
        }
      `,
      fragmentShader: `
        uniform vec4 uWaves[8];
        varying vec2 vWorld;
        varying float vLift;
        void main() {
          float basin=0.0;
          float edge=0.0;
          float glint=0.0;
          for (int i=0; i<8; i++) {
            vec4 w=uWaves[i];
            float d=length(vWorld-w.xy);
            // The dark interior stays behind the outward traveling front.
            float inside=1.0-smoothstep(w.z-1.7,w.z+1.7,d);
            basin=max(basin,inside*w.w);
            float front=(d-w.z)/2.2;
            float rim=exp(-front*front)*w.w;
            vec2 direction=(vWorld-w.xy)/max(d,0.001);
            float lit=0.35+0.65*max(dot(direction,vec2(-0.82,0.57)),0.0);
            edge += rim*lit;
            glint += rim*pow(max(sin(d*2.4),0.0),6.0);
          }
          basin=clamp(basin,0.0,1.0);
          edge=clamp(edge,0.0,1.6);
          float side=smoothstep(-19.0,19.0,vWorld.x);
          vec3 tint=mix(vec3(0.27,0.10,0.45),vec3(0.06,0.37,0.50),side);
          vec3 deep=vec3(0.003,0.008,0.022);
          vec3 shallow=tint*(0.13+0.12*edge);
          vec3 body=mix(shallow,deep,smoothstep(0.16,0.95,basin));
          vec3 highlight=tint*(0.18*edge+0.10*glint);
          float alpha=clamp(0.67*basin+0.32*edge+0.10*abs(vLift),0.0,0.86);
          alpha *= 1.0-smoothstep(49.0,55.0,length(vWorld));
          gl_FragColor=vec4(body+highlight,alpha);
        }
      `
    })
  );
  ground.rotation.x=-Math.PI/2;
  ground.position.y=-1.16;
  ground.renderOrder=-2;
  ground.frustumCulled=false;
  scene.add(ground);
  const waves=[];
  const lastAt=new Map();
  const sample=new THREE.Vector3();
  const world=new THREE.Vector3();
  let lastTime=-1;
  return {
    update(time,energy,positions,rig) {
      if (time<lastTime || time-lastTime>1.5) {
        waves.length=0;
        lastAt.clear();
      }
      lastTime=time;
      const candidates=[];
      for (let i=0; i<positions.count; i+=59) {
        const h=positions.getY(i);
        if (h<2.4) continue;
        sample.set(positions.getX(i),h,positions.getZ(i));
        world.copy(sample).applyMatrix4(rig.matrixWorld);
        const near=candidates.findIndex(p=>Math.hypot(world.x-p.x,world.z-p.z)<3.4);
        if (near>=0) {
          if (h>candidates[near].h) candidates[near]={x:world.x,z:world.z,h};
        } else candidates.push({x:world.x,z:world.z,h});
        candidates.sort((a,b)=>b.h-a.h);
        if (candidates.length>3) candidates.pop();
      }
      for (const p of candidates) {
        const key=Math.round(p.x/4)+":"+Math.round(p.z/4);
        const previous=lastAt.get(key) ?? -Infinity;
        if (time-previous<1.2 || energy<0.025) continue;
        waves.push({x:p.x,z:p.z,born:time,
          power:THREE.MathUtils.clamp(0.40+(p.h-2.4)*0.15,0.4,1)});
        lastAt.set(key,time);
      }
      while (waves.length && (time-waves[0].born)*SPEED>68) waves.shift();
      while (waves.length>COUNT) waves.shift();
      for (let i=0; i<COUNT; i++) {
        const w=waves[i];
        active[i].set(w?.x ?? 0,w?.z ?? 0,
          w?Math.max(0,time-w.born)*SPEED:-1000,w?.power ?? 0);
      }
    }
  };
}
