"""Supplement section band analysis with time-resolved coactivity, without changing audio."""
import numpy as np
from pathlib import Path
from music02_t004 import OUT,load,dump,read_segment,read,rms,db,RATE,BLOCK,cropped_render_metrics

def run():
    scene=load(OUT/'spatial_scenes/M02_T004_scene.json')
    report=load(OUT/'reports/masking_clarity.json');envelopes={}
    for s in scene['sources']:
        a,_=read_segment(s['input_file'],200,30)
        # 100ms linked stereo RMS, constant inherited role gain; no EQ or audio edits.
        a=a.astype(np.float64)*10**(float(s.get('gain_db',0))/20)
        envelopes[s['source_id']]=np.sqrt(np.mean(a.reshape(2,300,4800)**2,axis=(0,2)))
    times=200+np.arange(300)*.1
    for section in report['sections']:
        featured=section['featured']
        if featured is None:continue
        use=(times>=section['start_seconds'])&(times<section['end_seconds'])
        ref=envelopes[featured][use];ref_active=ref>=max(np.max(envelopes[featured])*10**(-30/20),1e-9)
        for candidate in section['potential_maskers']:
            value=envelopes[candidate['role']][use]
            active=value>=max(np.max(envelopes[candidate['role']])*10**(-30/20),1e-9)
            together=ref_active&active
            candidate['temporal_coactive_fraction_of_featured_active_bins']=float(together.sum()/max(ref_active.sum(),1))
            candidate['temporal_coactive_seconds']=float(together.sum()*.1)
            candidate['rms_envelope_correlation']=float(np.corrcoef(ref,value)[0,1]) if np.std(ref)>0 and np.std(value)>0 else None
            candidate['selected_support_trim_temporally_supported']=candidate['role'] not in section['support_trims_db'] or bool(together.any())
        assert all(c['selected_support_trim_temporally_supported'] for c in section['potential_maskers'])
    report['temporal_method']='100ms stereo RMS bins, active >= own-role preview peak RMS minus 30dB; coactivity measured relative to featured active bins. Correlation and activity are diagnostic, not proof of masking.'
    # Analyse the original full-song section map too; this is read-only analysis, never a full render.
    mapping=load(OUT.parents[1]/'analysis/musical_map.json');full_sections=[]
    bands=report['bands_hz'];freq=np.fft.rfftfreq(4096,1/RATE)
    for section in mapping['sections']:
        a,b=section['start_seconds'],section['end_seconds'];vectors={};levels={};activities={}
        for source in scene['sources']:
            role=source['source_id'];raw,_=read_segment(source['input_file'],a,b-a)
            raw=raw.astype(np.float64)*10**(float(source.get('gain_db',0))/20);levels[role]=db(rms(raw))
            frames=np.lib.stride_tricks.sliding_window_view(raw,4096,axis=1)[:,::2048,:]
            power=np.abs(np.fft.rfft(frames*np.hanning(4096),axis=-1))**2
            vectors[role]=np.array([float(power[:,:,(freq>=lo)&(freq<hi)].sum()) for lo,hi in bands])
            bins=int(np.ceil(raw.shape[1]/4800));padded=np.pad(raw,((0,0),(0,bins*4800-raw.shape[1])))
            envelope=np.sqrt(np.mean(padded.reshape(2,bins,4800)**2,axis=(0,2)))
            activities[role]=envelope>=max(float(np.max(envelope))*10**(-30/20),10**(-70/20))
        pairs=[];roles=list(vectors)
        for i,left in enumerate(roles):
            for right in roles[i+1:]:
                vl,vr=vectors[left],vectors[right]
                overlap=float(np.dot(vl,vr)/max(np.linalg.norm(vl)*np.linalg.norm(vr),1e-20))
                together=activities[left]&activities[right];coactivity=float(together.sum()/max((activities[left]|activities[right]).sum(),1))
                if overlap>.75 and coactivity>.25 and abs(levels[left]-levels[right])<12:
                    pairs.append(dict(roles=[left,right],band_cosine_overlap=overlap,coactive_fraction=coactivity,
                        relative_rms_db=levels[left]-levels[right]))
        full_sections.append(dict(section_id=section['section_id'],label=section['label'],start_seconds=a,end_seconds=b,
            role_rms_dbfs=levels,potential_competing_pairs=pairs,automatic_audio_edits=False))
    report['full_song_read_only_section_analysis']=full_sections
    report['full_song_section_method']='Inherited tentative T001 section map; same STFT bands plus 100ms coactivity; report pairs only when overlap >.75, coactive union fraction >.25 and RMS difference <12dB. Activity floor -70dBFS. No full-song audio processed or exported.'
    # Keep the detailed report and validation embedding consistent; only newly created T004 reports change.
    dump(OUT/'reports/masking_clarity.json',report)
    validation=load(OUT/'reports/M02_T004_validation.json');validation['masking']=report
    validation['checks']['support_trims_temporally_supported']=True
    near=load(OUT/'reports/near_field.json')
    reference=read(Path(near['static_sweep']['matched']['1.5']['path'])).astype(np.float64)
    for record in near['calibration']:
        y=read(Path(record['export']['path'])).astype(np.float64)
        scalar=float(np.sum(y*reference)/max(np.sum(y*y),1e-20))
        record['normalized_waveform_residual_vs_1_5m_db']=db(rms(y*scalar-reference)/max(rms(reference),1e-15))
        record['spectral_band_change_vs_1_5m_db']={k:float(v-near['calibration'][-1]['spectral_distribution'][k]) for k,v in record['spectral_distribution'].items()}
    near['distance_cue_analysis']='Static level-matched waveform residual and band deltas quantify changes remaining after best linked scalar fit. Small residuals indicate gain-dominated control, not verified physical near-field cues.'
    boundaries={policy:cropped_render_metrics(read(Path(entry['path'])),BLOCK,RATE) for policy,entry in near['exports'].items()}
    near['monitor_boundary_metrics']=boundaries
    validation['checks']['near_field_block_continuity']=all(m['max_block_boundary_delta']<=max(.25,m['max_sample_delta']*.8) for m in boundaries.values())
    assert validation['checks']['near_field_block_continuity']
    dump(OUT/'reports/near_field.json',near);validation['near_field']=near
    dump(OUT/'reports/M02_T004_validation.json',validation)
    print('T004 temporal masking analysis: PASS')

if __name__=='__main__':run()
