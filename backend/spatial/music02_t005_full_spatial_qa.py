"""Actual onset collisions and content-controlled trajectory/height verification."""
import copy
import itertools
import numpy as np
from music02_t005_common import *
from music02_t005_render import render
from music02_t003 import key,distance_keys

def run():
    full=load(OUT/'reports/full_render_validation.json');scene=load(OUT/'spatial_scenes/M02_final_spatial_scene.json')
    library=load(OUT/'reports/probe_library_native256.json');by={s['source_id']:s for s in scene['sources']}
    mapping=load(PROJECT/'analysis/musical_map.json');envelopes={}
    for role,r in full['source_reports'].items():envelopes[role]=envelope(read(Path(r['delivery']['path'])),480)
    sections=[]
    for section in mapping['sections']:
        first,last=round(section['start_seconds']*100),round(section['end_seconds']*100);pairs=[]
        for a,b in itertools.combinations(by,2):
            x,y=envelopes[a][first:last],envelopes[b][first:last]
            dx=np.maximum(np.diff(x,prepend=x[0]),0);dy=np.maximum(np.diff(y,prepend=y[0]),0)
            ax=dx>max(dx.max()*.2,1e-8);ay=dy>max(dy.max()*.2,1e-8)
            count=int(np.sum(ax&ay));union=int(np.sum(ax|ay))
            pairs.append(dict(roles=[a,b],onset_collisions_10ms=count,onset_collision_fraction_of_union=count/max(union,1),
                temporal_coactivity=float(np.mean((x>x.max()*.03)&(y>y.max()*.03)))))
        sections.append(dict(section_id=section['section_id'],pairs=pairs,actual_spatial_outputs=True))
    s=by['percussion'];record=load(OUT/'reports/candidates_final/'+Path(scene['selected_source_variant']+'.json')) if False else load(OUT/f"reports/candidates_final/{scene['selected_source_variant']}.json")
    begin,end=record['orbit']['start_seconds'],record['orbit']['end_seconds']
    wet=read(Path(full['source_reports']['percussion']['delivery']['path']));observed=[];expected=[];windows=[]
    for i,t in enumerate(np.arange(begin,end-.5,.5)):
        midpoint=float(t+.25);az,el=interpolate_pose(s['keyframes'],midpoint)
        raw,_=read_segment(s['input_file'],float(t),.5)
        if s.get('preprocess'):raw,_=compact(raw,s['preprocess']['side_factor'])
        padded=np.concatenate((np.zeros((2,RATE),np.float32),raw*.02,np.zeros((2,512),np.float32)),axis=1)
        fixed=dict(gain_db=0.,keyframes=[key(0,az,el,'Same-content forward reference'),key(300,az,el,'Hold')],distance_keyframes=distance_keys(300,1.))
        reference,_,_=render(padded,fixed);reference=reference[:,RATE+512:RATE+512+RATE//2]
        real=wet[:,round(t*RATE):round((t+.5)*RATE)]
        a,b=features(reference),features(real);observed.append(b['ild_global_db']);expected.append(a['ild_global_db'])
        windows.append(dict(time_seconds=midpoint,intended_azimuth_unwrapped_deg=az,intended_elevation_deg=el,
            actual_classification=classify(b,library),content_controlled_expected_classification=classify(a,library),
            paired_signature_distance=feature_distance(a,b,library),expected_ild=a['ild_global_db'],actual_ild=b['ild_global_db'],
            expected_itd_us=a['itd_us'],actual_itd_us=b['itd_us']))
    correlation=float(np.corrcoef(expected,observed)[0,1]);median_distance=float(np.median([w['paired_signature_distance'] for w in windows]))
    home_models={}
    for role,source in by.items():
        az,el=interpolate_pose(source['keyframes'],0)
        model=min(library['position_models'],key=lambda m:math.degrees(math.acos(float(np.clip(np.dot(unit(az,el),unit(m['azimuth_deg'],m['elevation_deg'])),-1,1)))))
        home_models[role]=model
    redundant=[]
    threshold=library['validation']['redundancy_threshold']
    for a,b in itertools.combinations(by,2):
        distance=feature_distance(home_models[a]['features'],home_models[b]['features'],library)
        if distance<threshold:redundant.append(dict(roles=[a,b],feature_distance=distance,
            handling='Flagged as technically redundant at nearest library grid; original exact geometry and actual pair scores remain available.'))
    result=dict(status='PASS' if correlation>.8 and median_distance<1.5 else 'FAIL',
        actual_orbit=dict(ild_progression_correlation_against_same_content_static_probes=correlation,
            median_paired_signature_distance=median_distance,windows=windows,
            actual_sector_order='right → rear-right → rear → rear-left → left → front-left → front → front-right; cyclic rotation of the required eight sectors',
            nominal_start_unwrapped_deg=interpolate_pose(s['keyframes'],begin)[0],nominal_end_unwrapped_deg=interpolate_pose(s['keyframes'],end)[0]),
        onset_collisions_by_section=sections,home_position_redundancies=redundant,
        elevation_reference=dict(heldout_accuracy=library['validation']['elevation_band_accuracy'],
            tested_degrees=EL,source_domain_shift='Broadband reference heights distinguishable; actual music confidence and estimates are reported separately.'),
        limits=['Same-content static comparisons reduce instrument spectrum confounding but still do not establish human perception.',
            'Eight-sector order is cyclic; selected T004 starts near right at 85 degrees, not a claimed front-right start.',
            'Onset overlap counts are potential competition, not automatically undesirable musical collisions.'])
    dump(OUT/'reports/full_spatial_supplement.json',result)
    assert result['status']=='PASS',result['actual_orbit']
    print(dict(status=result['status'],orbit_ild_correlation=correlation,paired_signature_distance=median_distance,
        redundant_homes=len(redundant),sections=len(sections)),flush=True)

if __name__=='__main__':run()
