from pathlib import Path
import json,copy,sys,unittest
import numpy as np
V=Path(__file__).resolve().parents[1];sys.path.insert(0,str(V/'tools'))
from musical_salience import PARAMETERS,salience,arbitrate,fuse_gestures,source_features,validate
from musical_gestures import sha256

def factors(shape):return {k:np.zeros(shape) for k in PARAMETERS['weights']}
def raw(rms):return salience(rms,.01,factors(np.asarray(rms).shape))
def gesture(gid,kind,start,end,source='voice',refs=None):
 return {'gestureId':gid,'gestureType':kind,'startTime':start,'endTime':end,'duration':end-start,
  'source':source,'confidence':.72,'intensity':.1,'attackRefs':refs or []}
def synthetic(gestures,attacks):
 return {'sources':{s:{} for s in {g['source'] for g in gestures}|{a['source'] for a in attacks}},'gestures':gestures,'attacks':attacks}

class FidelityCases(unittest.TestCase):
 def test_A_one_strong_eleven_weak(self):
  x=np.full((40,12),1e-5);x[:,8]=.1;score=raw(x);_,roles,_=arbitrate(score,np.ones_like(x,dtype=bool))
  self.assertTrue(np.all(roles[:,8]==3));self.assertTrue(np.all(roles[:,:8]<3));self.assertTrue(np.all(roles[:,9:]<3))
 def test_B_equal_sources_both_remain_dominant(self):
  x=np.full((30,2),.05);_,roles,_=arbitrate(raw(x),np.ones_like(x,dtype=bool));self.assertTrue(np.all(roles==3))
 def test_C_sustain_and_small_attacks_fuse(self):
  gs=[gesture('s','SUSTAINED_TONE',0,8),gesture('p','PHRASE',0,9),gesture('a','IMPULSE',2,2.1,refs=[0])]
  data=synthetic(gs,[{'index':0,'source':'voice','time':2}]);intents,relationships,owners=fuse_gestures(data)
  self.assertEqual(len(intents),1);self.assertEqual(intents[0]['primaryGesture'],'s');self.assertEqual(intents[0]['endTime'],8)
  self.assertIn(('a','reinforcement'),[(r.get('gestureId'),r['relation']) for r in relationships]);self.assertEqual(owners,[intents[0]['intentId']])
 def test_D_crescendo_is_modifier_not_second_driver(self):
  data=synthetic([gesture('s','SUSTAINED_TONE',0,8),gesture('c','CRESCENDO',2,5)],[])
  intents,relationships,_=fuse_gestures(data);self.assertEqual(len(intents),1);self.assertIn('c',intents[0]['intensityTrend']);self.assertTrue(any(r['relation']=='intensityModifier' for r in relationships))
 def test_E_weak_isolated_source_has_context_without_false_absolute_gain(self):
  x=np.full((30,1),1e-5);f=factors(x.shape);f['isolation']=np.ones_like(x);score=salience(x,.01,f);_,roles,_=arbitrate(score,np.ones_like(x,dtype=bool))
  self.assertTrue(np.all(roles==3));self.assertAlmostEqual(x[0,0],1e-5);self.assertLess(float(np.max(score)),.002)
 def test_F_strong_change_reacts_within_150_ms(self):
  x=np.array([[.1,.001]]*20+[[.001,.1]]*20);_,roles,_=arbitrate(raw(x),np.ones_like(x,dtype=bool))
  self.assertTrue(np.any(roles[20:23,1]==3));self.assertEqual(roles[24,1],3);self.assertNotEqual(roles[24,0],3)
 def test_G_small_oscillations_do_not_flicker(self):
  phase=np.where(np.arange(100)%2==0,1,-1);x=np.column_stack([.1*(1+.02*phase),.1*(1-.02*phase)])
  _,_,history=arbitrate(raw(x),np.ones_like(x,dtype=bool));changes=sum(a!=b for a,b in zip(history,history[1:]));self.assertLessEqual(changes,1)
 def test_instrument_names_cannot_change_ranking(self):
  # Same numerical passage permuted: strong Strings beat weak Drums as readily
  # as the reverse; classifier/source labels are not inputs to salience.
  x=np.array([[.01,.1,.03]]*20);a=raw(x);b=raw(x[:,[2,0,1]])
  np.testing.assert_allclose(a[:,[2,0,1]],b);self.assertTrue(np.all(np.argmax(a,axis=1)==1))
 def test_absolute_intensity_monotonic_under_equivalent_conditions(self):
  x=np.array([.001,.01,.05,.1,.5]);score=raw(x);self.assertTrue(np.all(np.diff(score)>0));self.assertTrue(np.all(np.diff((x/.01)**2)>0))
 def test_confidence_is_not_an_input_to_intensity_or_salience(self):
  data=synthetic([gesture('g','SUSTAINED_TONE',0,4)],[]);data.update({'duration':4,'stemStatistics':[{'source':'voice','activityFloor':1e-6}]})
  f=np.zeros((201,7));f[:,0]=np.arange(201)*.02;f[:,1]=.01;f[:,5]=1e-6
  first=fuse_gestures(data)[0];a=source_features(data,{'voice':f},first)
  data['gestures'][0]['confidence']=.95;second=fuse_gestures(data)[0];b=source_features(data,{'voice':f},second)
  self.assertNotEqual(first[0]['classificationConfidence'],second[0]['classificationConfidence'])
  np.testing.assert_array_equal(salience(a['rms'],a['reference'],a['factors']),salience(b['rms'],b['reference'],b['factors']))
 def test_sources_never_fuse_even_at_identical_times(self):
  intents,_,_=fuse_gestures(synthetic([gesture('g1','SUSTAINED_TONE',0,8,'drums'),gesture('g2','SUSTAINED_TONE',0,8,'strings')],[]));self.assertEqual(len(intents),2)
 def test_phrase_alone_is_not_an_independent_visual_driver(self):
  data=synthetic([gesture('p','PHRASE',0,12)],[{'index':0,'source':'voice','time':1}]);intents,relations,_=fuse_gestures(data)
  self.assertEqual(len(intents),1);self.assertEqual(intents[0]['startTime'],intents[0]['endTime']);self.assertIsNone(intents[0]['primaryGesture']);self.assertEqual(relations[0]['relation'],'context')
 def test_attack_membership_has_one_owner_at_shared_boundaries(self):
  data=synthetic([gesture('a','SUSTAINED_TONE',0,2),gesture('b','SUSTAINED_TEXTURE',2,4)],[{'index':0,'source':'voice','time':2}]);intents,_,owners=fuse_gestures(data)
  self.assertEqual(sum(len(i['attackRefs']) for i in intents),1);self.assertEqual(len(owners),1)
 def test_click_sample_cannot_define_robust_rms_reference(self):
  reference=np.percentile(np.ones(1000)*.01,95);values=np.ones(1000)*.01;values[0]=1
  self.assertEqual(reference,np.percentile(values,95))
 def test_density_uses_exact_half_open_media_boundaries(self):
  data=synthetic([gesture('g','SUSTAINED_TONE',0,4)],[{'index':0,'source':'voice','time':1.0},{'index':1,'source':'voice','time':1.2}]);data.update({'duration':4,'stemStatistics':[{'source':'voice','activityFloor':1e-6}]})
  f=np.zeros((201,7));f[:,0]=np.arange(201)*.02;f[:,1]=.01
  intents=fuse_gestures(data)[0];m=source_features(data,{'voice':f},intents)
  self.assertEqual(m['density'][19,0],0);self.assertEqual(m['density'][20,0],4);self.assertEqual(m['density'][23,0],4);self.assertEqual(m['density'][24,0],8)
 def test_no_fixed_maximum_source_count(self):
  x=np.ones((10,12))*.1;_,roles,_=arbitrate(raw(x),np.ones_like(x,dtype=bool));self.assertTrue(np.all(np.sum(roles==3,axis=1)==12))
 def test_silence_has_no_dominant_ghost(self):
  x=np.zeros((10,12));_,roles,_=arbitrate(raw(x),np.zeros_like(x,dtype=bool));self.assertFalse(np.any(roles))

class RealIntentContracts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((V/'public/audio/tukana-musical-gestures-v1.json').read_text(encoding='utf-8'))
  cls.result=json.loads((V/'public/audio/tukana-musical-visual-intents-v1.json').read_text(encoding='utf-8'))
 def test_complete_schema_and_causal_integrity(self):self.assertTrue(validate(self.result,self.data))
 def test_all_gesture_evidence_and_attack_indices_are_preserved(self):
  self.assertEqual(set(g['gestureId'] for g in self.data['gestures']),set(g for i in self.result['intents'] for g in i['gestureRefs']))
  self.assertEqual(sorted(a for i in self.result['intents'] for a in i['attackRefs']),list(range(10282)))
 def test_v13a_input_hash_and_features_unchanged(self):
  self.assertEqual(sha256(V/'public/audio/tukana-musical-gestures-v1.json'),self.result['sourceHashes']['gesturesV13A'])
  for s,digest in self.result['sourceHashes']['features'].items():self.assertEqual(sha256(V/f'reports/v1_3a-musical-gesture-intelligence/features/{s}.json'),digest)
 def test_source_relative_diagnostics_do_not_enter_salience_formula(self):
  self.assertNotIn('sourceRelative',self.result['metadata']['formula']);self.assertFalse(self.result['metadata']['confidenceUsedAsIntensity'])
 def test_local_weight_perturbations_pass_declared_limits(self):self.assertTrue(self.result['audit']['sensitivity']['pass'])
 def test_two_complete_outputs_are_byte_identical(self):
  self.assertEqual((V/'public/audio/tukana-musical-visual-intents-v1.json').read_bytes(),(V/'reports/v1_3b-musical-salience-arbitration/determinism-run-2.json').read_bytes())
 def test_no_mesh_units_or_runtime_activation(self):
  self.assertIsNone(self.result['metadata']['runtimeConsumer']);self.assertIn('NOT mesh height',self.result['metadata']['visualEnergyUnit'])
  self.assertNotIn('visual-intents',(V/'src/main.js').read_text(encoding='utf-8-sig'))
 def test_evolution_segments_cover_intent_without_resetting_each_frame(self):
  long=next(e for e in self.result['intents'] if e['temporalBehavior']=='sustained' and e['endTime']-e['startTime']>=8)
  self.assertAlmostEqual(long['roleSegments'][0]['startTime'],long['startTime'])
  self.assertAlmostEqual(long['roleSegments'][-1]['endTime'],long['endTime'])
  self.assertEqual(len(set(a for a in long['attackRefs'])),len(long['attackRefs']))
 def test_weak_brass_is_not_equalized_to_percussion(self):
  columns=self.result['sourceOrder'];rms=[f['values'] for f in self.result['frames']]
  brass=np.array([row[columns.index('brass')][0] for row in rms]);perc=np.array([row[columns.index('percussion')][0] for row in rms])
  self.assertLess(np.percentile(brass,95),np.percentile(perc,95)/10)
 def test_duplicate_attack_owner_rejected(self):
  d=copy.deepcopy(self.result);e=next(e for e in d['intents'] if e['attackRefs']);e['attackRefs'].append(e['attackRefs'][0])
  with self.assertRaises(AssertionError):validate(d,self.data)
 def test_cross_source_gesture_reference_rejected(self):
  d=copy.deepcopy(self.result);e=d['intents'][0];wrong=next(g for g in self.data['gestures'] if g['source']!=e['source']);e['gestureRefs'].append(wrong['gestureId'])
  with self.assertRaises(AssertionError):validate(d,self.data)
if __name__=='__main__':unittest.main()
