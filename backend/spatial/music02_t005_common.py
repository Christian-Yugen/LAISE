"""T005 objective signal measurements. No modification to the approved pipeline."""
import json
import math
import subprocess
from pathlib import Path
import numpy as np
from music02_t002 import ROOT,PROJECT,load,dump,db,rms,RATE,BLOCK,_sha256,read_segment,compact,ebur128
from music02_t003 import read,unit
from music02_preview import write24,preview_signal_metrics,cropped_render_metrics,baseline_regressions
from music02_analysis import snapshot
from dearvr_adapter import PLUGIN_PATH,configure_direct_signal,set_pose,interpolate_pose,interpolate_keyframe_value,wrap_azimuth
from pedalboard import load_plugin

OUT=PROJECT/'experiments/M02_T005'
BANDS=[(60,150),(150,500),(500,2000),(2000,6000),(6000,12000),(12000,20000)]
AZ=[0,30,-30,60,-60,90,-90,120,-120,150,-150,180]
EL=[-45,-20,0,20,45,60]
DIST=[.35,.5,.75,1.,1.5,2.,3.]
FRAMES=11884801
WEIGHTS=dict(spatial_discriminability=.25,clarity=.20,orbit_integrity=.15,front_back=.10,elevation=.10,
    transient_preservation=.10,peak_safety=.05,mono_stability=.05)

def fftstats(a,nfft=2048):
    a=np.asarray(a,dtype=np.float64)
    if a.shape[1]<nfft:a=np.pad(a,((0,0),(0,nfft-a.shape[1])))
    windows=np.lib.stride_tricks.sliding_window_view(a,nfft,axis=1)[:,::nfft//2,:]
    z=np.fft.rfft(windows*np.hanning(nfft),axis=-1)
    power=np.mean(np.abs(z)**2,axis=1);cross=np.mean(z[0]*np.conj(z[1]),axis=0)
    return power,cross,np.fft.rfftfreq(nfft,1/RATE)

def features(a):
    a=np.asarray(a,dtype=np.float64);p,c,f=fftstats(a)
    eps=1e-24;coh=np.clip(np.abs(c)**2/np.maximum(p[0]*p[1],eps),0,1)
    ild=[];phase=[];coherence=[];band_energy=[];contrast=[]
    for lo,hi in BANDS:
        use=(f>=lo)&(f<hi);left,right=np.sum(p[:,use],axis=1)
        ild.append(float(np.clip(10*np.log10((left+eps)/(right+eps)),-60,60)))
        weight=np.sqrt(p[0,use]*p[1,use])*coh[use]
        vector=np.sum(weight*np.exp(1j*np.angle(c[use])))
        phase.append(float(np.angle(vector)));coherence.append(float(np.average(coh[use],weights=np.maximum(p[:,use].sum(axis=0),eps))))
        band_energy.append(float(left+right))
        contrast.append(float(10*np.log10((left/max(p[0].sum(),eps)+eps)/(right/max(p[1].sum(),eps)+eps))))
    gcc=np.fft.irfft(c/np.maximum(np.abs(c),eps),n=2048)
    lags=np.arange(-48,49);values=gcc[lags%2048];lag=int(lags[np.argmax(values)])
    # Parabolic sub-sample GCC-PHAT estimate, bounded to +/-1ms.
    i=lag%2048;den=gcc[(i-1)%2048]-2*gcc[i]+gcc[(i+1)%2048]
    delta=0 if abs(den)<1e-15 else float(np.clip(.5*(gcc[(i-1)%2048]-gcc[(i+1)%2048])/den,-.5,.5))
    itd=(lag+delta)*1e6/RATE
    mid=(a[0]+a[1])*.5;side=(a[0]-a[1])*.5
    rr=rms(a);lr=np.sqrt(np.mean(a*a,axis=1));total=np.array(band_energy)
    centroid=[float(np.sum(f*p[ch])/max(np.sum(p[ch]),eps)) for ch in range(2)]
    corr=float(np.corrcoef(a)[0,1]) if min(lr)>1e-12 else 0.
    vector=np.r_[ild,np.cos(phase),np.sin(phase),itd,np.clip(db(rms(side)/max(rms(mid),1e-15)),-60,60),contrast]
    return dict(vector=vector.tolist(),ild_global_db=db(lr[0]/max(lr[1],1e-15)),ild_band_db=ild,itd_us=float(itd),
        itd_definition='GCC-PHAT L*conj(R), positive lag means left delayed; +/-1ms search, parabolic interpolation',
        cross_correlation_lr=corr,coherence_by_band=coherence,phase_relationship_rad=phase,
        spectral_difference_lr_db=contrast,energy_centroid_hz_lr=centroid,interaural_spectral_contrast_db=contrast,
        side_mid_db=db(rms(side)/max(rms(mid),1e-15)),binaural_difference_rms_dbfs=db(rms(a[0]-a[1])),
        objective_width=float(rms(side)**2/max(rms(side)**2+rms(mid)**2,1e-24)),
        band_energy=total.tolist(),band_distribution=(total/max(total.sum(),eps)).tolist(),rms_dbfs=db(rr),
        crest_db=db(np.max(np.abs(a))/max(rr,1e-15)),mono_fold_db=db(rms(mid)/max(rr,1e-15)),
        active_bands=(total>=max(float(total.max())*.001,eps)).tolist())

def direction(az):
    cosine=math.cos(math.radians(az))
    return 'lateral' if abs(cosine)<.15 else ('front' if cosine>0 else 'rear')

def elevation_band(el):return 'low' if el<-10 else ('high' if el>10 else 'ear')

def classifier(library):
    models=library['position_models'];train=np.array([m['features']['vector'] for m in models])
    scale=np.array(library['feature_scale']);scale=np.maximum(scale,1e-6)
    return models,train,scale

def classify(feature,library):
    models,train,scale=classifier(library);v=np.array(feature['vector'])
    active=np.array(feature['active_bands'],bool)
    mask=np.r_[active,active,active,True,True,active]
    distance=np.sqrt(np.mean(((train[:,mask]-v[mask])/scale[mask])**2,axis=1));order=np.argsort(distance)
    best=models[int(order[0])];second=float(distance[order[1]])
    confidence=float(np.clip((second-distance[order[0]])/max(second,1e-12),0,1))*float(active.mean())
    return dict(azimuth_deg=best['azimuth_deg'],elevation_deg=best['elevation_deg'],front_rear=direction(best['azimuth_deg']),
        elevation_band=elevation_band(best['elevation_deg']),confidence=confidence,coverage=float(active.mean()),
        feature_distance=float(distance[order[0]]),alternatives=[dict(azimuth_deg=models[int(i)]['azimuth_deg'],
            elevation_deg=models[int(i)]['elevation_deg'],distance=float(distance[i])) for i in order[:3]])

def intended_distance(feature,az,el,library):
    models,train,scale=classifier(library)
    nearest=min(range(len(models)),key=lambda i:math.degrees(math.acos(float(np.clip(np.dot(unit(az,el),unit(models[i]['azimuth_deg'],models[i]['elevation_deg'])),-1,1)))))
    mask=np.r_[feature['active_bands'],feature['active_bands'],feature['active_bands'],True,True,feature['active_bands']].astype(bool)
    return float(np.sqrt(np.mean(((np.array(feature['vector'])[mask]-train[nearest,mask])/scale[mask])**2)))

def feature_distance(a,b,library):
    scale=np.array(library['feature_scale']);mask=np.r_[np.array(a['active_bands'])&np.array(b['active_bands'])]*1
    mask=np.r_[mask,mask,mask,True,True,mask].astype(bool)
    return float(np.sqrt(np.mean(((np.array(a['vector'])[mask]-np.array(b['vector'])[mask])/scale[mask])**2)))

def envelope(a,hop=4800):
    n=a.shape[1]//hop
    return np.sqrt(np.mean(a[:,:n*hop].astype(np.float64).reshape(2,n,hop)**2,axis=(0,2)))

def transient_proxy(dry,wet,latency_samples=512):
    if latency_samples:
        wet=wet[:,latency_samples:];dry=dry[:,:wet.shape[1]]
    d=envelope(dry,480);w=envelope(wet,480);n=min(len(d),len(w));d,w=d[:n],w[:n]
    dn=np.maximum(0,np.diff(d,prepend=d[0]));wn=np.maximum(0,np.diff(w,prepend=w[0]))
    if dn.max()<1e-10:return dict(score=100.,events=0,onset_envelope_correlation=None,median_attack_crest_delta_db=0.)
    indices=np.argsort(dn)[-max(3,min(50,int(n*.05))):];indices=indices[dn[indices]>dn.max()*.15]
    correlation=float(np.corrcoef(dn,wn)[0,1]) if wn.std()>0 else 0.
    crests=[]
    for i in indices:
        start=int(i)*480;end=min(start+960,dry.shape[1],wet.shape[1]);body=min(start+9600,dry.shape[1],wet.shape[1])
        dc=db(np.max(np.abs(dry[:,start:end]))/max(rms(dry[:,start:body]),1e-15))
        wc=db(np.max(np.abs(wet[:,start:end]))/max(rms(wet[:,start:body]),1e-15));crests.append(wc-dc)
    delta=float(np.median(crests)) if crests else 0.
    return dict(score=float(np.clip(100*(.7*max(correlation,0)+.3*math.exp(-abs(delta)/6)),0,100)),events=len(crests),
        onset_envelope_correlation=correlation,median_attack_crest_delta_db=delta,analysis_common_latency_removed_samples=latency_samples)

def ff(command):
    result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    return result

def read_any(path):
    result=ff(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-acodec','pcm_f32le','-ac','2','-ar','48000','-'])
    return np.frombuffer(result.stdout,dtype='<f4').reshape(-1,2).T.copy()

def write_float(path,a):
    assert not path.exists();path.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-f','f32le','-ar','48000','-ac','2','-i','pipe:0','-c:a','pcm_f32le',str(path)],
        input=np.asarray(a.T,dtype='<f4').tobytes(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)

def file_metrics(path):
    return dict(path=str(path),sha256=_sha256(path),signal=preview_signal_metrics(path),loudness=ebur128(path))

def init():
    assert not OUT.exists(),'Preserve all old experiments; a fresh T005 namespace is required.'
    before=snapshot(PROJECT);tukana=snapshot(ROOT/'projects/tukana');OUT.mkdir(parents=True)
    dump(OUT/'reports/music02_integrity_before.json',before);dump(OUT/'reports/tukana_integrity_before.json',tukana)
    regressions=baseline_regressions(load(PROJECT/'analysis/stem_import_manifest.json'))
    dump(OUT/'reports/baseline_regressions.json',regressions)
    dump(OUT/'reports/scoring_protocol.json',dict(weights=WEIGHTS,locked_before_candidate_measurement=True,
        gains_excluded_from_spatial_feature_vector=True,scope='Actual comparative preview plus full-song input/scene section diagnostics; final full spatial output is independently revalidated.',
        epistemic_limit='System-specific technical discriminability proxies, not human perceptual probabilities or universal localization proof.'))
    print('M02-T005 namespace initialized; protected prior artifacts',flush=True)

if __name__=='__main__':init()
