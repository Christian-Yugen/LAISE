"""M02-T001 analysis. Audio is read only; all outputs are MUSIC 02 metadata."""
from pathlib import Path
import json
import math
import numpy as np
from stem_importer import ROLES, import_folder, iter_blocks, _sha256
from musical_analyzer import build_musical_map, estimate_bpm, _onset_envelope

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'projects/music_02'
ROLES_M02 = (*ROLES, 'brass')

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

def snapshot(folder):
    return {str(p.relative_to(folder)): dict(size=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns,
        sha256=_sha256(p)) for p in sorted(folder.rglob('*')) if p.is_file()}

def envelope(path):
    result=[]
    for block in iter_blocks(path,4800):
        result.append(float(np.sqrt(np.mean(block.astype(np.float64)**2))))
    return np.array(result)

def merged_regions(regions, gap=0.5):
    result=[]
    for r in regions:
        if result and r['start_seconds']-result[-1]['end_seconds'] <= gap:
            result[-1]['end_seconds']=r['end_seconds']
        else: result.append(dict(r))
    return result

def spectral_content(path):
    powers=[]; crossings=[]
    frequencies=np.fft.rfftfreq(4800,1/48000)
    for block in iter_blocks(path,4800):
        mono=block.mean(axis=1)
        if np.sqrt(np.mean(mono.astype(np.float64)**2)) < 0.002 or len(mono)!=4800: continue
        spectrum=np.abs(np.fft.rfft(mono*np.hanning(len(mono))))**2
        total=max(float(spectrum.sum()),1e-20)
        powers.append([float(np.sum(spectrum*frequencies)/total),
                       float(spectrum[frequencies<250].sum()/total),
                       float(spectrum[(frequencies>=250)&(frequencies<4000)].sum()/total),
                       float(spectrum[frequencies>=4000].sum()/total)])
        crossings.append(float(np.mean(np.diff(np.signbit(mono)))))
    if not powers: return dict(status='NO_ACTIVE_WINDOWS')
    values=np.median(powers,axis=0)
    return dict(active_windows=len(powers), median_spectral_centroid_hz=float(values[0]),
        median_band_energy_fractions=dict(below_250hz=float(values[1]), from_250_to_4000hz=float(values[2]), above_4000hz=float(values[3])),
        median_zero_crossing_rate=float(np.median(crossings)),
        instrument_identity='UNCONFIRMED_WITHOUT_LISTENING', classification_confidence=0.0,
        reason='Spectral/activity descriptors are not sufficient to name an instrument in a separated Other stem.')

def analyze():
    for name in ('analysis','spatial_scenes','spatial_stems','renders','reports'):
        (PROJECT/name).mkdir(parents=True,exist_ok=True)
    # Full immutable-project evidence before any MUSIC 02 processing.
    baseline=snapshot(ROOT/'projects/tukana')
    dump(PROJECT/'reports/tukana_integrity_before.json',baseline)
    manifest=import_folder(PROJECT/'stems_original',PROJECT/'analysis/stem_import_manifest.json',required_roles=ROLES_M02)
    assert manifest['status']=='PASS' and manifest['stem_count']==11
    assert set(manifest['stems'])==set(ROLES_M02)
    for r in manifest['stems'].values():
        w=r['wav']; assert (w['sample_rate'],w['bits_per_sample'],w['channels'],w['frames'])==(48000,16,2,11884801)
        assert not r['internal_format']['resampling_required']
    mapping=build_musical_map(manifest,PROJECT/'analysis/musical_map.json')
    mapping['project']='music_02'; mapping['test_id']='M02-T001'
    matrix=np.vstack([envelope(r['path']) for r in manifest['stems'].values()])
    roles=list(manifest['stems']); n=matrix.shape[1]
    normalized=matrix/np.maximum(matrix.max(axis=1,keepdims=True),1e-12)
    active=matrix>=0.001
    density=active.sum(axis=0)
    # Two-second context either side: changes of texture, not individual hits.
    width=20
    smooth=np.array([np.convolve(row,np.ones(width)/width,mode='same') for row in normalized])
    novelty=np.zeros(n)
    novelty[width:-width]=np.mean(np.abs(smooth[:,2*width:]-smooth[:,:-2*width]),axis=0)
    density_change=np.zeros(n)
    density_smooth=np.convolve(density,np.ones(width)/width,mode='same')
    density_change[width:-width]=np.abs(density_smooth[2*width:]-density_smooth[:-2*width])/11
    novelty+=0.25*density_change
    candidates=[i for i in range(50,n-25) if novelty[i]>=novelty[i-1] and novelty[i]>novelty[i+1]
                and novelty[i]>=np.quantile(novelty,0.85)]
    selected=[]
    for i in sorted(candidates,key=lambda x:novelty[x],reverse=True):
        if all(abs(i-j)>=80 for j in selected): selected.append(i)
        if len(selected)>=round(mapping['duration_seconds']/30): break
    selected.sort()
    transitions=[]
    for i in selected:
        changes=np.abs(smooth[:,min(n-1,i+20)]-smooth[:,max(0,i-20)])
        dominant=[roles[j] for j in np.argsort(changes)[::-1][:4]]
        transitions.append(dict(time_seconds=i/10,confidence=float(novelty[i]/max(novelty.max(),1e-12)),
            reason='Change in 2-second smoothed role energy and active-role density',dominant_roles=dominant,
            density_before=float(np.mean(density[max(0,i-20):i])),density_after=float(np.mean(density[i:i+20]))))
    boundaries=[0]+[t['time_seconds'] for t in transitions]+[mapping['duration_seconds']]
    sections=[]
    for index,(start,end) in enumerate(zip(boundaries,boundaries[1:]),1):
        a=round(start*10);b=min(n,max(a+1,round(end*10)))
        sections.append(dict(section_id=f'm02_section_{index:02}',label='intro_candidate' if index==1 else
            ('outro_candidate' if index==len(boundaries)-1 else 'texture_section_candidate'),
            start_seconds=start,end_seconds=end,mean_active_roles=float(density[a:b].mean()),
            dominant_roles=[roles[j] for j in np.argsort(normalized[:,a:b].mean(axis=1))[::-1][:4]],
            confidence=0.6,human_review_required=True))
    mapping['transitions']=transitions;mapping['sections']=sections
    mapping['structural_method']='role-energy/density novelty; provisional boundaries; no external timestamps used as detection inputs'
    mapping['bpm']['independent_stem_estimates']={role:estimate_bpm([manifest['stems'][role]['path']]) for role in ('drums','percussion')}
    mapping['bpm']['confidence_interpretation']='Normalized autocorrelation contrast, not a calibrated probability; beat/downbeat phase requires listening.'
    lag=mapping['bpm']['beat_period_seconds']*48000/1024
    mapping['bpm']['lag_quantization_interval_bpm']=[60*(48000/1024)/(lag+0.5),60*(48000/1024)/(lag-0.5)]
    mapping['meter']['bar_zero_status']='Beat phase inferred; downbeat/bar phase unconfirmed'
    for role,r in manifest['stems'].items():
        onset=_onset_envelope(r['path']); level=float(np.quantile(onset,0.93))
        indices=[i for i in range(1,len(onset)-1) if onset[i]>=onset[i-1] and onset[i]>onset[i+1] and onset[i]>=max(level,0.01)]
        chosen=[]
        for i in sorted(indices,key=lambda i:onset[i],reverse=True):
            if all(abs(i-j)>=5 for j in chosen): chosen.append(i)
        mapping['stem_events'][role]['onsets']=[dict(time_seconds=i*1024/48000,strength=float(onset[i]),confidence=0.65) for i in sorted(chosen)]
        mapping['stem_events'][role]['phrases']=merged_regions(r['metrics']['active_regions'])
    # Safe common pre-render attenuation based on an upper bound, including all stems.
    bound=sum(r['metrics']['peak'] for r in manifest['stems'].values())
    common=min(1,10**(-12/20)/max(bound,1e-12))
    gain=dict(policy='common attenuation before dearVR; no limiter; exact sum measured separately',
        sum_of_individual_peak_upper_bound=bound,common_input_gain=common,common_input_gain_db=20*math.log10(common),
        worst_case_dry_sum_peak_dbfs=-12.0,target_output_peak_dbfs=-6.0)
    # Measure actual aligned full dry sum without writing or changing originals.
    streams=[iter_blocks(r['path']) for r in manifest['stems'].values()]; peak=squares=samples=0
    for blocks in zip(*streams):
        summed=np.sum(np.stack(blocks).astype(np.float64),axis=0)
        peak=max(peak,float(np.max(np.abs(summed))));squares+=float(np.sum(summed*summed));samples+=summed.size
    gain['measured_unity_sum_peak_dbfs']=20*math.log10(max(peak,1e-12));gain['measured_unity_sum_rms_dbfs']=20*math.log10(max(math.sqrt(squares/samples),1e-12))
    gain['pre_staged_sum_peak_dbfs']=gain['measured_unity_sum_peak_dbfs']+gain['common_input_gain_db']
    dump(PROJECT/'analysis/gain_staging.json',gain)
    mapping['density_changes']=[dict(time_seconds=i/10,active_roles=int(density[i])) for i in range(0,n,10)]
    # Rank thirty-second excerpts by participation and proximity to structural events.
    choices=[]
    for start in range(0,math.floor(mapping['duration_seconds']-30)+1):
        a=start*10;b=(start+30)*10
        fractions=active[:,a:b].mean(axis=1)
        participants=int(np.count_nonzero(fractions>0.01))
        brass=float(fractions[roles.index('brass')])
        score=participants*100+brass*20+float(density[a:b].mean())+5*sum(start<t['time_seconds']<start+30 for t in transitions)
        choices.append(dict(start_seconds=start,duration_seconds=30,score=score,participating_roles=participants,
            brass_active_fraction=brass,role_active_fractions={role:float(fractions[j]) for j,role in enumerate(roles)}))
    choices.sort(key=lambda x:x['score'],reverse=True)
    preliminary=next(c for c in choices if c['start_seconds']==200)
    best=choices[0]
    # Prefer the requested audition interval when complete and within 1% of best.
    selected_preview=preliminary if preliminary['participating_roles']==11 and preliminary['score']>=best['score']*0.99 else best
    mapping['preview_selection']=dict(selected=selected_preview,external_candidate_200_230=preliminary,
        best_computed_candidate=best,reason='Complete role coverage and Brass events; prefer 200-230 only if within 1% of best computed score')
    brass=mapping['stem_events']['brass']
    brass['function_hypothesis']='Intermittent accent/answer phrases, to verify by listening'
    brass['function_confidence']=0.55
    brass['total_active_seconds']=sum(r['end_seconds']-r['start_seconds'] for r in manifest['stems']['brass']['metrics']['active_regions'])
    brass['full_song_active_fraction']=brass['total_active_seconds']/mapping['duration_seconds']
    other=spectral_content(manifest['stems']['other']['path'])
    other['spatial_policy']='Stable conservative location pending human content identification; no content-specific motion'
    dump(PROJECT/'analysis/other_content_analysis.json',other)
    dump(PROJECT/'analysis/brass_analysis.json',brass)
    mapping['external_structure_comparison']=[dict(external_time_seconds=t,nearest_detected_seconds=min(transitions,key=lambda x:abs(x['time_seconds']-t))['time_seconds'])
        for t in (35,116,134,178.5,205.5,219,243)]
    dump(PROJECT/'analysis/musical_map.json',mapping)
    print(json.dumps(dict(test_id='M02-T001',stem_count=11,bpm=mapping['bpm'],transitions=transitions,
        preview=mapping['preview_selection'],gain=gain,brass_phrases=brass['phrases'],other=other),indent=2),flush=True)
    return manifest,mapping,gain

if __name__=='__main__': analyze()
