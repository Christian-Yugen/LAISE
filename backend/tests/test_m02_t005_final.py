"""Final M02-T005 hashes, probe grid, full-song outputs and automated selection regression."""
import json
import sys
import wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend/spatial'))
from music02_t005_common import OUT,PROJECT,load,_sha256

def main():
    p=OUT/'reports';library=load(p/'probe_library_native256.json')
    expected={(a,e,d) for a in library['azimuths'] for e in library['elevations'] for d in library['distances_m']}
    records=library['records'];assert len(records)==504
    assert {(r['azimuth_deg'],r['elevation_deg'],r['distance_m']) for r in records}==expected
    for r in records:
        path=Path(r['path']);assert path.is_file() and _sha256(path)==r['sha256']
        with wave.open(str(path)) as w:assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(2,3,48000,48000)
    selection=load(p/'objective_selection_final.json');scores=selection['scores']
    assert selection['selected_variant']=='T004'
    assert all(scores['T004']['score']>scores[k]['score'] for k in ('T001','T002','T002_ORIGINAL_LEAD','T003'))
    full=load(p/'full_render_validation.json');assert full['status']=='PASS' and all(full['checks'].values())
    assert full['frames']==11884801 and full['duration_seconds']==247.60002083333333
    orbit=load(p/'full_spatial_supplement.json');assert orbit['status']=='PASS'
    assert orbit['actual_orbit']['ild_progression_correlation_against_same_content_static_probes']>.8
    assert len(orbit['onset_collisions_by_section'])==9
    for role,r in full['source_reports'].items():
        item=r['delivery'];path=Path(item['path']);assert _sha256(path)==item['sha256'] and item['signal']['frames']==11884801
    master=load(p/'mastering_validation.json');assert master['selected_master']=='C' and master['refined_product_created']
    decision=load(p/'technical_final_decision.json')
    assert decision['status']=='TECHNICAL_FINAL_PASS_WITH_AAC_SPATIAL_DEGRADATION_DISCLOSED'
    assert decision['historical_mastering_report_status']=='FAIL'
    assert decision['historical_AAC_gate'] is False and decision['AAC_score_loss_points']>0
    final=master['final_artifacts'];assert _sha256(Path(final['wav']['path']))==final['wav']['sha256']
    assert _sha256(Path(final['aac']['path']))==final['aac']['sha256']
    assert _sha256(Path(final['dry']['path']))==final['dry']['sha256']
    assert final['wav']['signal']['frames']==final['dry']['signal']['frames']==11884801
    assert final['wav']['signal']['finite'] and final['wav']['signal']['sample_peak']<1
    assert final['wav']['loudness']['true_peak_dbtp']<=-1.5
    for field in ('wav','dry'):
        with wave.open(final[field]['path']) as w:assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(2,3,48000,11884801)
    integrity=load(p/'music02_integrity_before.json');tukana=load(p/'tukana_integrity_before.json')
    for root,records in ((PROJECT,integrity),(ROOT/'projects/tukana',tukana)):
        for rel,item in records.items():
            f=root/rel;assert f.is_file() and f.stat().st_size==item['size'] and f.stat().st_mtime_ns==item['mtime_ns'] and _sha256(f)==item['sha256']
    md=OUT/'M02_FINAL_AUTOMATED_VALIDATION.md';assert md.is_file()
    text=md.read_text(encoding='utf-8')
    for needle in ('T005 validada tecnicamente','T004 foi selecionada automaticamente','does not claim universal human perception','AAC spatial-signature score falls materially','247.600020833'):
        assert needle in text,needle
    assert '98.58; the AAC 256 kb/s round-trip score is 88.56, a loss of **10.02 points**' in text
    assert '(98,58 → 88,56)' in text
    result=dict(test_id='M02-T005-FINAL-REGRESSION',status='PASS',probes_verified=504,
        music02_preservation_verified=len(integrity),tukana_preservation_verified=len(tukana),
        roles_and_full_frames=11,selected_spatial_candidate='T004',selected_master='C',
        AAC_spatial_loss_reported=decision['AAC_score_loss_points'],
        no_universal_perception_claim=True)
    out=OUT/'reports/M02_T005_final_regression.json'
    if out.exists():
        # A matching prior regression is evidence to preserve, never replace.
        assert load(out)==result
    else:out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(result)

if __name__=='__main__':main()
