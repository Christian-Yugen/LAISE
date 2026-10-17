"""Numeric, reviewable results of required synthetic fidelity cases A-G."""
from pathlib import Path
import json
import numpy as np
from musical_salience import PARAMETERS,salience,arbitrate,fuse_gestures
OUT=Path(__file__).resolve().parents[1]/'reports/v1_3b-musical-salience-arbitration'
def evaluate(x,isolation=False):
 factors={k:np.zeros_like(x) for k in PARAMETERS['weights']}
 if isolation:factors['isolation']=np.ones_like(x)
 scores=salience(x,.01,factors);smooth,roles,history=arbitrate(scores,np.ones_like(x,dtype=bool));return scores,smooth,roles,history
def fixture(kind):
 sustain={'gestureId':'s','gestureType':'SUSTAINED_TONE','source':'source','startTime':0,'endTime':8,'duration':8,'confidence':.72,'intensity':.1,'attackRefs':[0]}
 modifier={'gestureId':'m','gestureType':kind,'source':'source','startTime':2,'endTime':3,'duration':1,'confidence':.95,'intensity':.01,'attackRefs':[0]}
 return {'sources':{'source':{}},'gestures':[sustain,modifier],'attacks':[{'index':0,'source':'source','time':2}]}
def main():
 rows=[]
 x=np.full((40,12),1e-5);x[:,8]=.1;_,_,roles,_=evaluate(x);ok=bool(np.all(roles[:,8]==3) and np.all(np.sum(roles==3,axis=1)==1));rows.append({'case':'A','pass':ok,'dominantSourceIndex':8,'dominantCount':1,'strongAbsoluteRms':.1,'weakAbsoluteRms':1e-5})
 _,_,roles,_=evaluate(np.full((30,2),.05));rows.append({'case':'B','pass':bool(np.all(roles==3)),'bothEqualSourcesDominant':True})
 for label,kind,relation in [('C','IMPULSE','reinforcement'),('D','CRESCENDO','intensityModifier')]:
  intents,relations,owners=fuse_gestures(fixture(kind));ok=len(intents)==1 and intents[0]['primaryGesture']=='s' and any(r['relation']==relation for r in relations)
  rows.append({'case':label,'pass':ok,'intentCount':len(intents),'sustainDuration':intents[0]['endTime']-intents[0]['startTime'],'modifierRelation':relation,'ownedAttacks':len(owners)})
 x=np.full((30,1),1e-5);score,_,roles,_=evaluate(x,True);rows.append({'case':'E','pass':bool(np.all(roles==3) and np.max(score)<.002),'absoluteRms':1e-5,'localContextIntensity':1,'maximumRawSalience':float(np.max(score))})
 x=np.array([[.1,.001]]*20+[[.001,.1]]*20);_,_,roles,_=evaluate(x);indices=np.flatnonzero(roles[20:,1]==3);latency=float(indices[0]*.05) if len(indices) else None
 rows.append({'case':'F','pass':latency is not None and latency<=.15,'changeLatencySeconds':latency,'maximumAllowedSeconds':.15})
 phase=np.where(np.arange(100)%2==0,1,-1);x=np.column_stack([.1*(1+.02*phase),.1*(1-.02*phase)]);_,_,_,history=evaluate(x);changes=sum(a!=b for a,b in zip(history,history[1:]));rows.append({'case':'G','pass':changes<=1,'dominanceSetChanges':changes,'frames':100,'relativeOscillation':.02})
 result={'pass':all(r['pass'] for r in rows),'cases':rows};OUT.mkdir(exist_ok=True);(OUT/'synthetic-cases.json').write_text(json.dumps(result,indent=2));assert result['pass'],result;print(json.dumps(result,indent=2))
if __name__=='__main__':main()
