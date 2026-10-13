"""504 known-pose probes, independent temporal holdout and HRTF feature classifier."""
import itertools
import time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from music02_t005_common import *
from music02_t005_common import _sha256
from music02_t005_render import render
from music02_t003 import key,distance_keys

def reference():
    rng=np.random.default_rng(5017);noise=rng.normal(size=RATE+RATE//4)
    # Same deterministic broadband mono reference at every position; non-overlapping halves
    # provide independent noise realizations without changing reference source or timbre.
    spectrum=np.fft.rfft(noise);freq=np.fft.rfftfreq(len(noise),1/RATE)
    spectrum*=np.where((freq>=60)&(freq<=20000),1/np.sqrt(np.maximum(freq,60)),0.)
    mono=np.fft.irfft(spectrum,n=len(noise));mono*=.03/max(np.max(np.abs(mono)),1e-12)
    return np.vstack((mono,mono)).astype(np.float32)

def worker(spec):
    az,el,distance=spec;a=reference()
    source=dict(gain_db=0.,keyframes=[key(0,az,el,'Known probe'),key(300,az,el,'Hold')],distance_keyframes=distance_keys(300,distance))
    y,_,_=render(a,source);y=y[:,RATE//4:]
    assert y.shape==(2,RATE) and np.isfinite(y).all()
    name=f'az_{az:+04d}_el_{el:+03d}_d_{distance:g}'
    path=OUT/f'probes/native256/{name}.wav';assert not path.exists();write24(path,y)
    return dict(id=name,path=str(path),sha256=_sha256(path),azimuth_deg=az,elevation_deg=el,distance_m=distance,
        train=features(y[:,:RATE//2]),holdout=features(y[:,RATE//2:]),full=features(y),
        transient=transient_proxy(a[:,RATE//4:],y),peak=float(np.max(np.abs(y))))

def run():
    assert OUT.exists() and not (OUT/'reports/probe_library_native256.json').exists()
    records=[];started=time.time()
    with ProcessPoolExecutor(max_workers=2) as pool:
        for i,result in enumerate(pool.map(worker,itertools.product(AZ,EL,DIST)),1):
            records.append(result)
            if i%42==0:print(f'T005 probes {i}/504 ({time.time()-started:.1f}s)',flush=True)
    models=[]
    for az,el in itertools.product(AZ,EL):
        group=[r for r in records if r['azimuth_deg']==az and r['elevation_deg']==el]
        f=group[0]['train'].copy();f['vector']=np.mean([r['train']['vector'] for r in group],axis=0).tolist()
        models.append(dict(azimuth_deg=az,elevation_deg=el,features=f))
    train=np.array([m['features']['vector'] for m in models]);scale=np.std(train,axis=0)
    scale=np.maximum(scale,np.r_[np.ones(6),np.ones(12)*.1,20.,1.,np.ones(6)])
    library=dict(test_id='M02-T005-PROBES',positions=504,azimuths=AZ,elevations=EL,distances_m=DIST,
        same_mono_reference=True,reference_seed=5017,reference_description='Broadband pink-shaped deterministic noise 60Hz–20kHz; quarter-second warm-up, one-second measured output',
        feature_scale=scale.tolist(),position_models=models,records=records,absolute_gain_excluded_from_classifier=True,
        process_call_frames=256,initial_batch_probe_library='Preserved as superseded compatibility diagnostic; excluded from selection')
    estimates=[];self_dist=[]
    for r in records:
        estimate=classify(r['holdout'],library);intended=intended_distance(r['holdout'],r['azimuth_deg'],r['elevation_deg'],library)
        self_dist.append(intended)
        angular=math.degrees(math.acos(float(np.clip(np.dot(unit(r['azimuth_deg'],r['elevation_deg']),unit(estimate['azimuth_deg'],estimate['elevation_deg'])),-1,1))))
        estimates.append(dict(probe_id=r['id'],intended=[r['azimuth_deg'],r['elevation_deg']],estimated=estimate,
            angular_error_deg=angular,front_back_correct=estimate['front_rear']==direction(r['azimuth_deg']),
            elevation_band_correct=estimate['elevation_band']==elevation_band(r['elevation_deg']),intended_feature_distance=intended))
    threshold=float(np.percentile(self_dist,95)*2);redundant=[]
    for i,m in enumerate(models):
        for n in models[i+1:]:
            separation=feature_distance(m['features'],n['features'],library)
            if separation<threshold:redundant.append(dict(a=[m['azimuth_deg'],m['elevation_deg']],b=[n['azimuth_deg'],n['elevation_deg']],feature_distance=separation))
    validation=dict(heldout_count=504,front_back_accuracy=float(np.mean([e['front_back_correct'] for e in estimates])),
        elevation_band_accuracy=float(np.mean([e['elevation_band_correct'] for e in estimates])),
        median_angular_error_deg=float(np.median([e['angular_error_deg'] for e in estimates])),
        p95_angular_error_deg=float(np.percentile([e['angular_error_deg'] for e in estimates],95)),
        within_pose_feature_distance_p95=float(np.percentile(self_dist,95)),redundancy_threshold=threshold,
        redundant_position_pairs=redundant,holdout_estimates=estimates,
        caveats=['Temporal holdout of same broadband reference, not independent human HRTF validation.',
            'Instrument spectra and native stereo are domain shifts; confidence is a feature-margin/coverage heuristic, not calibrated perceptual probability.',
            'Distance mostly gain: no distance classifier or near-field bonus. Technically redundant labels are not claimed universally perceptually identical.'])
    library['validation']=validation
    dump(OUT/'reports/probe_library_native256.json',library)
    print(json.dumps({k:v for k,v in validation.items() if k not in ('holdout_estimates','redundant_position_pairs')},indent=2),flush=True)

if __name__=='__main__':run()
