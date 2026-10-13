"""Cached-control renderer with exact 256-frame automation grid and float32 audio."""
import time
import numpy as np
from music02_t005_common import *
from dearvr_adapter import azimuth_to_raw,elevation_to_raw

def render(a,source,start=0.,curve=None,policy='total',grid=DIST,progress=None,gain_time_offset=0.):
    plugin=load_plugin(str(PLUGIN_PATH));configure_direct_signal(plugin)
    parameters=plugin.parameters
    ap,ep,dp=parameters['azimuth'],parameters['elevation'],parameters['distance']
    times=start+np.arange(0,a.shape[1],BLOCK)/RATE;keys=source['keyframes']
    kt=np.array([k['time_seconds'] for k in keys])
    az=np.interp(times,kt,[k['azimuth_deg_unwrapped'] if 'azimuth_deg_unwrapped' in k else k['azimuth_deg'] for k in keys])
    el=np.interp(times,kt,[k['elevation_deg'] for k in keys]);gain_times=times+gain_time_offset
    gain_db=float(source.get('gain_db',0))+np.interp(gain_times,kt,[k.get('gain_db',0) for k in keys])
    dk=source.get('distance_keyframes',[])
    radius=np.interp(times,[k['time_seconds'] for k in dk],[k['distance_m'] for k in dk]) if dk else np.full(len(times),3.)
    assert np.min(radius)>=.2499 and np.max(radius)<=3.0001
    gain_radius=np.interp(gain_times,[k['time_seconds'] for k in dk],[k['distance_m'] for k in dk]) if dk else radius
    compensation=np.zeros(len(times)) if curve is None else np.interp(gain_radius,grid,curve)
    home=source.get('growth_reference_distance_m',source.get('home',{}).get('distance_m',1.5))
    ref=0. if curve is None else float(np.interp(home,grid,curve))
    retained=np.zeros(len(times)) if policy=='total' else np.minimum(np.maximum(ref-compensation,0),2.5 if policy=='partial' else 4.5)
    gains=10**((gain_db+compensation+retained)/20)
    out=np.zeros_like(a,np.float32);dry=np.zeros_like(a,np.float32);controls=[]
    previous_gain=float(gains[0]);last_pose=None;index=0;started=time.time();next_progress=.1
    while index<len(times):
        end_index=index+1
        # Every call retains the approved 256-frame boundary. A single large process call was
        # empirically different, so grouping is deliberately disabled.
        cursor=index*BLOCK;end=min(end_index*BLOCK,a.shape[1]);pose=(az[index],el[index],radius[index])
        if last_pose is None or pose[0]!=last_pose[0]:ap.raw_value=azimuth_to_raw(pose[0])
        if last_pose is None or pose[1]!=last_pose[1]:ep.raw_value=elevation_to_raw(pose[1])
        if last_pose is None or pose[2]!=last_pose[2]:dp.raw_value=(float(pose[2])-.1)/29.9
        processed=plugin.process(a[:,cursor:end],sample_rate=RATE,buffer_size=BLOCK,reset=index==0)
        assert processed.shape==(2,end-cursor)
        for j in range(index,end_index):
            left=j*BLOCK;right=min(left+BLOCK,a.shape[1]);ramp=np.linspace(previous_gain,gains[j],right-left,dtype=np.float32)
            out[:,left:right]=processed[:,left-cursor:right-cursor]*ramp;dry[:,left:right]=a[:,left:right]*ramp
            previous_gain=float(gains[j])
        last_pose=pose
        if index%200==0 or end_index==len(times):controls.append(dict(time_seconds=float(times[index]),azimuth_deg_unwrapped=float(pose[0]),
            elevation_deg=float(pose[1]),distance_m=float(pose[2]),retained_growth_db=float(retained[index]),gain_db=float(db(gains[index]))))
        fraction=end/a.shape[1]
        if progress and (fraction>=next_progress or end==a.shape[1]):
            progress(fraction,time.time()-started);next_progress=fraction+.1
        index=end_index
    assert np.isfinite(out).all()
    return out,dry,controls

def equivalence():
    from music02_t004 import render as slow,distance_keys
    from music02_t003 import key
    rng=np.random.default_rng(5018);a=rng.normal(0,.005,(2,48000)).astype(np.float32)
    source=dict(gain_db=-2.,keyframes=[key(0,-80,5,'Test'),key(.5,80,35,'Test'),key(1,160,15,'Test')],
        distance_keyframes=distance_keys(1,1.),growth_reference_distance_m=1.)
    y,_,_=render(a,source,0,curve=None)
    reference,_=slow(a,source,0,source['distance_keyframes'],curve=None)
    error=float(np.max(np.abs(y-reference)))
    assert error<2e-6,error
    fixed=dict(gain_db=0.,keyframes=[key(0,30,20,'Fixed'),key(1,30,20,'Fixed')],distance_keyframes=distance_keys(1,1.))
    y,_,_=render(a,fixed,0);reference,_=slow(a,fixed,0,fixed['distance_keyframes'])
    fixed_error=float(np.max(np.abs(y-reference)));assert fixed_error<2e-6,(fixed_error,float(np.max(np.abs(reference))))
    record=dict(status='PASS',dynamic_max_error=error,grouped_static_max_error=fixed_error,
        control_grid_frames=256,approved_renderer_modified=False)
    dump(OUT/'reports/cached_renderer_equivalence.json',record);print(record,flush=True)

if __name__=='__main__':equivalence()
