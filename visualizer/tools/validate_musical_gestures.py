"""Quantitative V1.3A sanity/provenance/spatial audit, no runtime integration."""
from pathlib import Path
import json,subprocess
from musical_gestures import validate,sha256,canonical
from build_audio_cues import floor_position
V=Path(__file__).resolve().parents[1];OUT=V/'reports/v1_3a-musical-gesture-intelligence'
def main():
 d=json.loads((V/'public/audio/tukana-musical-gestures-v1.json').read_text(encoding='utf-8'));cues=json.loads((V/'public/audio/tukana-stem-cues.json').read_text())
 assert validate(d,cues)
 base=json.loads((V/'reports/LAISE_VISUALIZER_V1_2_APPROVED_BASELINE.json').read_text())
 for path,digest in base['hashes'].items():assert sha256(V/path)==digest,path
 protected=subprocess.check_output(['git','diff','LAISE_VISUALIZER_V1_2_APPROVED','--','visualizer/src','visualizer/index.html','visualizer/public/audio/tukana-stem-cues.json','visualizer/public/audio/tukana-visualizer-manifest.json'],text=True)
 assert not protected
 assert sha256(V/'tools/musical_gestures.py')==d['sourceHashes']['analyzer']
 assert sha256(V/'tools/build_musical_gestures.py')==d['sourceHashes']['builder']
 automation=V.parent/d['spatialTrajectoryReference']['manifest'];assert sha256(automation)==d['sourceHashes']['t007Automation']
 roles={r['source_id']:r for r in json.loads(automation.read_text())['roles']}
 checked=0;maxerror=0
 for g in d['gestures']:
  for point in g['trajectory']:
   actual=floor_position(roles[g['source']],point['time'])
   for key,expected in zip(['x','z','azimuth','elevation','distance'],actual):
    error=abs(point[key]-expected);maxerror=max(maxerror,error);assert error<2e-5,(g['gestureId'],point,key,error)
   checked+=1
 grouped={i for g in d['gestures'] if g['gestureType']=='PHRASE' for i in g['attackRefs']};assert grouped==set(range(10282))
 # Relationship classes are intentionally separate; all identities are source-local.
 for source,item in d['sources'].items():assert sha256(V.parent/item['file'])==item['sha256'],source
 result={'pass':True,'sources':len(d['sources']),'preservedAttacks':len(d['attacks']),
  'gestures':len(d['gestures']),'relationships':len(d['relationships']),
  'trajectorySamplesChecked':checked,'spatialTolerance':2e-5,'maximumSpatialError':maxerror,
  'allAttacksGrouped':True,'protectedV12HashesMatch':True,'runtimeDiffVsApprovedTag':'empty',
  'jsonSha256':sha256(V/'public/audio/tukana-musical-gestures-v1.json')}
 (OUT/'sanity-checks.json').write_bytes(canonical(result));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
