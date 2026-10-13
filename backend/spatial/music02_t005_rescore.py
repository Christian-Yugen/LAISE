"""Correct common-latency bias in attack metrics before definitive selection."""
import copy
import hashlib
import numpy as np
from music02_t005_common import *
from music02_t005_selection import candidates
from music02_t005_probes import reference

def run():
    assert not (OUT/'reports/objective_selection_final.json').exists()
    items=candidates();initial=load(OUT/'reports/objective_selection.json');scores={}
    for name,item in items.items():
        prior=load(OUT/f'reports/candidates/{name}.json')
        dry={s['source_id']:read_segment(s['input_file'],200,30)[0] for s in item['scene']['sources']}
        trans={r:transient_proxy(dry[r],item['arrays'][r],latency_samples=512) for r in dry}
        score=float(np.average([trans[r]['score'] for r in ('drums','percussion','brass')],weights=[2,1,1]))
        prior['components']['transient_preservation']=score;prior['actual_preview']['transient_by_role']=trans
        prior['actual_preview']['components']['transient_preservation']=score
        prior['score']=float(sum(prior['components'][k]*WEIGHTS[k] for k in WEIGHTS))
        prior['latency_metric_revision']=dict(plugin_reported_samples=512,initial_pre_initialization_reported_samples=1024,
            impulse_center_peak_delay_samples=533,common_latency_compensated_for_analysis_only=True,
            historical_audio_modified=False,remaining_21_sample_HRTF_delay_not_removed=True)
        dump(OUT/f'reports/candidates_final/{name}.json',prior)
        scores[name]=dict(score=prior['score'],components=prior['components'])
    winner=max(scores,key=lambda n:(scores[n]['score'],scores[n]['components']['transient_preservation']))
    scene=copy.deepcopy(items[winner]['scene']);scene.update(test_id='M02-T005',selected_source_variant=winner,
        status='AUTOMATICALLY_SELECTED_ARCHITECTURE',human_review='NOT_REQUIRED_BY_USER_T005',common_latency_to_compensate_samples=512)
    dump(OUT/'spatial_scenes/selected_architecture_final.json',scene)
    final=copy.deepcopy(initial);final.update(selected_variant=winner,scores=scores,
        metric_revision='512-frame plugin latency removed from attack comparison. Original candidate reports preserved; no audio changed.',
        initial_selection_report='reports/objective_selection.json',hybrid_created=False)
    dump(OUT/'reports/objective_selection_final.json',final)
    dump(OUT/'reports/reference_provenance.json',dict(mono_reference_float32_sha256=hashlib.sha256(reference()[0].tobytes()).hexdigest(),
        native_reference_library='reports/probe_library_native256.json',batch_reference_excluded=True,seed=5017))
    np.save(OUT/'probes/reference_mono_float32.npy',reference()[0],allow_pickle=False)
    print(json.dumps(final,indent=2),flush=True)

if __name__=='__main__':run()
