from pathlib import Path
import json,sys,unittest
import numpy as np
V=Path(__file__).resolve().parents[1];sys.path.insert(0,str(V/'tools'))
from causal_eligibility_audit import audit
from musical_salience import source_features,arbitrate
class FullTrackCausality(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((V/'public/audio/tukana-musical-gestures-v1.json').read_text(encoding='utf-8'))
  cls.result=json.loads((V/'public/audio/tukana-musical-visual-intents-v1.json').read_text(encoding='utf-8'))
  cls.audit=audit(cls.result,cls.data)
 def test_no_unowned_arbitration_salience(self):self.assertEqual(self.audit['metrics']['inactiveSourceWithArbitrationSalience'],0)
 def test_no_unowned_supporting_role(self):self.assertEqual(self.audit['metrics']['inactiveSourceWithSupportingRole'],0)
 def test_no_unowned_secondary_role(self):self.assertEqual(self.audit['metrics']['inactiveSourceWithSecondaryRole'],0)
 def test_no_unowned_dominant_role(self):self.assertEqual(self.audit['metrics']['inactiveSourceWithDominantRole'],0)
 def test_zero_intents_implies_zero_dominants(self):self.assertEqual(self.audit['metrics']['zeroIntentFramesWithDominant'],0)
 def test_all_dominants_have_complete_causal_chain(self):self.assertEqual(self.audit['metrics']['orphanDominants'],0)
 def test_active_lists_match_actual_interval_intersections(self):self.assertEqual(self.audit['metrics']['activeIntentListMismatch'],0)
 def test_329_90_no_owner_no_dominant(self):
  f=self.result['frames'][6598];self.assertEqual(f['startTime'],329.9);self.assertEqual(f['activeIntentIds'],[]);self.assertEqual(f['dominantCount'],0)
  self.assertTrue(all(row[4]==row[5]==row[9]==0 for row in f['values']))
 def test_329_95_only_backing_vocals_can_arbitrate(self):
  f=self.result['frames'][6599];self.assertEqual(f['activeIntentIds'],['backing_vocals:i00068'])
  for source,row in zip(self.result['sourceOrder'],f['values']):
   if source!='backing_vocals':self.assertEqual((row[4],row[5],row[9]),(0,0,0))
 def test_calibration_weights_and_intensity_measurements_unchanged(self):
  old=json.loads((V/'reports/v1_3br1-causal-eligibility/before/public/audio/tukana-musical-visual-intents-v1.json').read_text(encoding='utf-8'))
  self.assertEqual(self.result['calibration'],old['calibration']);self.assertEqual(self.result['analysisParameters'],old['analysisParameters'])
  for a,b in zip(old['frames'],self.result['frames']):
   for ra,rb in zip(a['values'],b['values']):
    self.assertEqual([ra[k] for k in [0,1,2,3,6,7,8]],[rb[k] for k in [0,1,2,3,6,7,8]])
 def test_topology_attack_owners_and_gesture_refs_unchanged(self):
  old=json.loads((V/'reports/v1_3br1-causal-eligibility/before/public/audio/tukana-musical-visual-intents-v1.json').read_text(encoding='utf-8'))
  self.assertEqual(len(self.result['intents']),505);self.assertEqual(self.result['attackOwners'],old['attackOwners']);self.assertEqual(self.result['relationships'],old['relationships'])
  for a,b in zip(old['intents'],self.result['intents']):
   for key in ['intentId','startTime','endTime','primaryGesture','gestureRefs','attackRefs','absoluteIntensity','visualEnergyCandidate']:self.assertEqual(a[key],b[key])

class GateAndRelease(unittest.TestCase):
 def test_measured_audio_without_intent_is_ineligible(self):
  data={'sources':{'stem':{}},'duration':1,'attacks':[],'stemStatistics':[{'source':'stem','activityFloor':1e-6}]}
  f=np.zeros((51,7));f[:,0]=np.arange(51)*.02;f[:,1]=.1
  m=source_features(data,{'stem':f},[]);self.assertFalse(np.any(m['eligible']));self.assertTrue(np.all(m['rms']>0))
 def test_release_cannot_keep_or_reactivate_unowned_source(self):
  raw=np.ones((20,2));eligible=np.ones_like(raw,dtype=bool);eligible[5:,0]=False
  score,roles,_=arbitrate(raw,eligible);self.assertTrue(np.all(score[5:,0]==0));self.assertTrue(np.all(roles[5:,0]==0))
 def test_returning_cause_restarts_filter_without_residual_priority(self):
  raw=np.full((8,1),100.);eligible=np.array([[True],[True],[False],[False],[True],[True],[False],[False]])
  score,roles,_=arbitrate(raw,eligible);self.assertEqual(score[0,0],score[4,0]);self.assertTrue(np.all(score[[2,3,6,7]]==0));self.assertTrue(np.all(roles[[2,3,6,7]]==0))
if __name__=='__main__':unittest.main()
