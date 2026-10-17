"""Test-only normal rendering probe retained for approved continuity audits."""
EXPOSE = r"""
window.__motionEvents=[];
window.__motion = {
  ready:cueReady,
  configureExport:()=>{renderer.setPixelRatio(.5);renderer.setSize(innerWidth,innerHeight);composer.setPixelRatio(.5);composer.setSize(innerWidth,innerHeight);},
  reset:(start)=>{
    rippleField.reset();cueTimeline.seek(0);window.__motionEvents=[];
    for(let i=1;i<=Math.round(start*10);i++)cueTimeline.step(i/10,true,
      c=>{window.__motionEvents.push(c);rippleField.exciteAt(c.x,c.z,c.strength,c.width);},dt=>rippleField.advance(dt));
  },
  frame:(time)=>{
    cueTimeline.step(time,true,c=>{window.__motionEvents.push(c);rippleField.exciteAt(c.x,c.z,c.strength,c.width);},dt=>rippleField.advance(dt));
    const gain=typeof audioMotionRecovery==='undefined'?1:audioMotionRecovery.gainFor(camera,terrainRig,innerWidth,innerHeight);
    for(let i=0;i<positions.count;i++)positions.array[i*3+1]=TERRAIN.maxHeight*Math.tanh(rippleField.heights[i]*gain/TERRAIN.maxHeight);
    positions.needsUpdate=true;composer.render();
    return {image:canvas.toDataURL('image/jpeg',.92),gain,time,camera:camera.position.toArray(),zoom:camera.zoom,pose:terrainRig.rotation.toArray()};
  },
  live:()=>({time:audio.currentTime,ended:audio.ended,paused:audio.paused,duration:audio.duration,
    label:durationLabel.textContent,energy:energyLabel.textContent,error:audio.error?.message||null,
    gain:typeof audioMotionRecovery==='undefined'?1:audioMotionRecovery.gain,emitted:window.__liveEvents?.length||0})
};

window.__startLiveAudit = () => {
  window.__liveEvents=[];window.__resets=[];
  const step=cueTimeline.step.bind(cueTimeline);
  cueTimeline.step=(time,playing,emit,advance)=>step(time,playing,c=>{
    window.__liveEvents.push({cue:c,delayMs:(audio.currentTime-c.time)*1000});emit(c);
  },advance);
  const reset=rippleField.reset.bind(rippleField);
  rippleField.reset=()=>{window.__resets.push(audio.currentTime);return reset();};
};
"""
