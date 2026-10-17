"""Signal/temporal contracts and real artifact integrity; no renderer integration."""
from pathlib import Path
import copy,json,sys,unittest
import numpy as np
V=Path(__file__).resolve().parents[1];sys.path.insert(0,str(V/'tools'))
from musical_gestures import features,repetition,roll_groups,energy_trend,trajectory,analyze_source,validate,canonical,sha256,SOURCE_CLASSES

def role():
 return {'keyframes':[{'time_seconds':0,'azimuth_deg_unwrapped':0,'elevation_deg':0},
                      {'time_seconds':2,'azimuth_deg_unwrapped':40,'elevation_deg':10}],
         'distance_keyframes':[{'time_seconds':0,'distance_m':1},{'time_seconds':2,'distance_m':2}]}
def tone(seconds=3,scale=.1):
 time=np.arange(round(seconds*16000))/16000;return scale*np.sin(2*np.pi*440*time)
class SignalContracts(unittest.TestCase):
 def test_features_are_deterministic(self):
  a=features(tone());b=features(tone())
  for key in a:np.testing.assert_array_equal(a[key],b[key])
 def test_stereo_antiphase_preserves_energy(self):
  x=tone();f=features(np.column_stack([x,-x]));self.assertGreater(float(np.median(f['rms'])),.06)
 def test_intensity_remains_absolute_and_scales_with_signal(self):
  a=features(tone(scale=.02));b=features(tone(scale=.08))
  np.testing.assert_allclose(b['rms'],a['rms']*4,atol=1e-12)
 def test_periodic_sequence(self):
  kind,confidence,evidence=repetition([10,10.5,11,11.5]);self.assertEqual(kind,'REPEATED_PULSE_SEQUENCE');self.assertGreater(confidence,.8);self.assertAlmostEqual(evidence['rateHz'],2)
 def test_short_repeated_pulse(self):self.assertEqual(repetition([1,1.5])[0],'REPEATED_PULSE')
 def test_acceleration(self):self.assertEqual(repetition([0,.8,1.4,1.8,2.05])[0],'ACCELERATING_SEQUENCE')
 def test_deceleration(self):self.assertEqual(repetition([0,.25,.65,1.25,2.05])[0],'DECELERATING_SEQUENCE')
 def test_dense_roll_preserves_hits(self):
  kind,confidence,evidence=repetition(np.arange(12)*.09);self.assertEqual(kind,'TREMOLO_OR_ROLL');self.assertEqual(evidence['attackCount'],12);self.assertLess(confidence,1)
 def test_local_roll_is_not_hidden_by_surrounding_slow_attacks(self):
  times=[0,.5,1]+[2+i*.09 for i in range(10)]+[4,4.5]
  found=roll_groups([{'time':t,'index':i} for i,t in enumerate(times)])
  self.assertEqual(len(found),1);self.assertEqual(len(found[0][0]),10)
 def test_dense_legacy_cues_on_unmodulated_tone_do_not_become_roll(self):
  attacks=[{'index':i,'time':.5+i*.09,'amplitude':.1} for i in range(12)]
  gestures,_,_=analyze_source('bass',features(tone()),attacks,role(),3)
  self.assertNotIn('TREMOLO_OR_ROLL',[g['gestureType'] for g in gestures])
 def test_crescendo_and_decrescendo(self):
  self.assertEqual(energy_trend(np.linspace(.01,.1,100),.02)[0],'CRESCENDO')
  self.assertEqual(energy_trend(np.linspace(.1,.01,100),.02)[0],'DECRESCENDO')
 def test_small_fluctuations_not_a_trend(self):self.assertIsNone(energy_trend(.1+.003*np.sin(np.arange(100)),.02))
 def test_sustain_and_impulse_are_different_evidence(self):
  f=features(tone());g,_,_=analyze_source('woodwinds',f,[{'index':1,'time':.1,'amplitude':.1}],role(),3)
  self.assertIn('SUSTAINED_TONE',[x['gestureType'] for x in g])
  t=np.arange(48000)/16000;x=np.where(t>=.5,np.exp(-np.maximum(0,t-.5)/.025)*np.sin(2*np.pi*220*t)*.2,0)
  g,_,_=analyze_source('percussion',features(x),[{'index':2,'time':.5,'amplitude':.1}],role(),3)
  self.assertIn('IMPULSE',[x['gestureType'] for x in g])
 def test_same_time_different_stems_do_not_merge(self):
  f=features(tone());a=[{'index':0,'time':.1,'amplitude':.1},{'index':1,'time':.6,'amplitude':.1}]
  for source in ['drums','woodwinds']:
   gestures,relations,_=analyze_source(source,f,a,role(),3)
   self.assertTrue(all(g['source']==source for g in gestures));self.assertTrue(any(r['relation']=='containsAttack' for r in relations))
 def test_trajectory_preserves_unwrapped_angles_and_last_boundary_key(self):
  r=role();r['keyframes']=[{'time_seconds':0,'azimuth_deg_unwrapped':350,'elevation_deg':0},{'time_seconds':1,'azimuth_deg_unwrapped':360,'elevation_deg':0},{'time_seconds':1,'azimuth_deg_unwrapped':370,'elevation_deg':0},{'time_seconds':2,'azimuth_deg_unwrapped':390,'elevation_deg':0}]
  rows=trajectory(r,0,1,2);self.assertEqual([p['azimuth'] for p in rows if p['time']==1],[370]);self.assertEqual(rows[-1]['azimuth'],390);self.assertTrue(all(abs(p['x'])<=.8 and abs(p['z'])<=.8 for p in rows))

class ArtifactContracts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((V/'public/audio/tukana-musical-gestures-v1.json').read_text(encoding='utf-8'))
  cls.cues=json.loads((V/'public/audio/tukana-stem-cues.json').read_text(encoding='utf-8'))
 def test_schema_all_sanity_checks(self):self.assertTrue(validate(self.data,self.cues))
 def test_duplicate_gesture_id_rejected(self):
  d=copy.deepcopy(self.data);d['gestures'][1]['gestureId']=d['gestures'][0]['gestureId']
  with self.assertRaises(AssertionError):validate(d,self.cues)
 def test_temporal_disorder_rejected(self):
  d=copy.deepcopy(self.data);d['gestures'].reverse()
  with self.assertRaises(AssertionError):validate(d,self.cues)
 def test_cross_source_attack_reference_rejected(self):
  d=copy.deepcopy(self.data);g=next(g for g in d['gestures'] if g['attackRefs'])
  g['source']=next(s for s in SOURCE_CLASSES if s!=g['source'])
  with self.assertRaises(AssertionError):validate(d,self.cues)
 def test_confidence_out_of_range_rejected(self):
  d=copy.deepcopy(self.data);d['gestures'][0]['confidence']=1.01
  with self.assertRaises(AssertionError):validate(d,self.cues)
 def test_orphan_attack_reference_rejected(self):
  d=copy.deepcopy(self.data);d['gestures'][0]['attackRefs'].append(10282)
  with self.assertRaises(AssertionError):validate(d,self.cues)
 def test_nonfinite_feature_rejected(self):
  d=copy.deepcopy(self.data);d['gestures'][0]['features']['spectralFlux']=float('nan')
  with self.assertRaises(ValueError):validate(d,self.cues)
 def test_all_existing_attacks_preserved_and_grouped(self):
  self.assertEqual(len(self.data['attacks']),10282)
  grouped={i for g in self.data['gestures'] if g['gestureType']=='PHRASE' for i in g['attackRefs']}
  self.assertEqual(grouped,set(range(10282)))
 def test_confidence_has_evidence_not_false_certainty(self):
  self.assertTrue(all(0<g['confidence']<1 and g['evidence'] for g in self.data['gestures']))
  self.assertEqual(self.data['taxonomy']['TRANSITION']['count'],0)
 def test_source_hashes_match_real_inputs(self):
  d=self.data
  self.assertEqual(sha256(V/'public/audio/tukana-stem-cues.json'),d['sourceHashes']['cueDataset'])
  self.assertEqual(sha256(V.parent/d['spatialTrajectoryReference']['manifest']),d['sourceHashes']['t007Automation'])
  for source,item in d['sources'].items():self.assertEqual(sha256(V.parent/item['file']),item['sha256'],source)
 def test_no_nan_infinity_and_serialization_is_stable(self):self.assertEqual(canonical(self.data),canonical(json.loads(canonical(self.data))))
 def test_intensity_differences_between_stems_are_not_equalized(self):
  values=[s['rawSampleRms'] for s in self.data['sources'].values()]
  self.assertGreater(max(values)/min(values),1.5)
 def test_runtime_has_no_gesture_consumer(self):
  self.assertIsNone(self.data['metadata']['runtimeConsumer'])
  self.assertNotIn('tukana-musical-gestures', (V/'src/main.js').read_text(encoding='utf-8-sig'))
if __name__=='__main__':unittest.main()
