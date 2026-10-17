"""Independent real-clock runs; test-only module telemetry, no product UI changes."""
from pathlib import Path
import json,time
from playwright.sync_api import sync_playwright
V=Path(__file__).resolve().parents[1]
OUT=V/'reports/v1_2br3b_r1-playback-continuity'
HOOK=r"""
window.__audit={records:[],resets:[],events:[],gaps:[],finished:false};
const audit=window.__audit,step=cueTimeline.step.bind(cueTimeline),reset=rippleField.reset.bind(rippleField);
let previous=null;
cueTimeline.step=(time,playing,emit,advance)=>{
 if(playing&&previous!==null&&time-previous>.1)audit.gaps.push({from:previous,to:time,ms:(time-previous)*1000,visibility:document.visibilityState});
 if(playing)previous=time;
 return step(time,playing,(c,m)=>{audit.records.push(m);emit(c,m)},advance);
};
rippleField.reset=()=>{audit.resets.push({time:audio.currentTime,epoch:cueTimeline.playbackEpoch,seeking:audio.seeking});return reset()};
for(const event of ['waiting','stalled','suspend','playing','canplay','pause','seeking','seeked','ended'])audio.addEventListener(event,()=>audit.events.push({event,time:audio.currentTime,epoch:cueTimeline.playbackEpoch}));
audio.addEventListener('ended',()=>{audit.finished=true});
window.__state=()=>({time:audio.currentTime,ended:audio.ended,finished:audit.finished,error:audio.error?.message??null,
 totalCues:cueTimeline.events.length,appliedCues:audit.records.length,uniqueAppliedCues:new Set(audit.records.map(r=>r.playbackEpoch+':'+r.cueIndex)).size,
 nextCueIndex:cueTimeline.index,simulationTime:cueTimeline.simulationTime,playbackEpoch:cueTimeline.playbackEpoch,
 catchUpCount:cueTimeline.catchUpCount,largestCatchUpMs:cueTimeline.largestCatchUpMs,unexpectedResetCount:audit.resets.filter(r=>!r.seeking).length});
window.__ready=cueReady;
"""
def setup(browser):
 page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
 # Append after cue loading so hooks attach before play.
 def route(r):
  response=r.fetch()
  r.fulfill(response=response,body=response.text()+'\nawait cueReady;\n'+HOOK)
 page.route('**/src/main.js*',route)
 page.goto('http://localhost:5173',wait_until='networkidle')
 page.wait_for_function('window.__state && document.querySelector("audio").readyState>=1')
 return page,errors
def run(browser,index,controlled=False):
 page,errors=setup(browser);page.locator('#startButton').click();last=-1;injected=[];start=time.monotonic()
 while True:
  page.wait_for_timeout(1000);state=page.evaluate('window.__state()')
  bucket=int(state['time']//15)
  if bucket!=last:print(f'RUN {index}: '+json.dumps(state),flush=True);last=bucket
  if controlled:
   for at,ms in [(15,950),(46,1500),(156,950),(200,3000),(325,950)]:
    if state['time']>=at and at not in injected:
     page.evaluate('ms=>{const end=performance.now()+ms;while(performance.now()<end){}}',ms);injected.append(at)
  if state['finished']:break
  assert time.monotonic()-start<480,'playback timeout'
  assert not state['error'],state
 audit=page.evaluate('window.__audit');ids=[r['cueIndex'] for r in audit['records']]
 result={'state':state,'audit':audit,'errors':errors,'controlled':controlled,'injectedAt':injected,
 'duplicateCues':len(ids)-len(set(ids)),'droppedCues':len(set(range(10282))-set(ids))}
 result['pass']=ids==list(range(10282)) and not errors and not state['error'] and not audit['resets'] and state['simulationTime']==330
 (OUT/f'real-run-{index}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 page.close();assert result['pass'],f'RUN {index} FAIL';print(f'RUN {index} PASS: 10282/10282',flush=True)
def controls(browser):
 page,errors=setup(browser);button=page.locator('#startButton');button.click();page.wait_for_timeout(700);button.click();page.wait_for_timeout(100)
 paused=page.evaluate('window.__state()');page.wait_for_timeout(350);assert page.evaluate('window.__state().appliedCues')==paused['appliedCues']
 states=[]
 for target in [120,30,200,329,.01]:
  page.evaluate('t=>{document.querySelector("audio").currentTime=t}',target)
  page.wait_for_function('!document.querySelector("audio").seeking')
  button.click();page.wait_for_timeout(400);button.click();states.append(page.evaluate('window.__state()'))
 page.evaluate('document.querySelector("audio").currentTime=329.8');page.wait_for_function('!document.querySelector("audio").seeking');button.click();page.wait_for_function('window.__state().finished')
 epoch=page.evaluate('window.__state().playbackEpoch');button.click();page.wait_for_timeout(600)
 replay=page.evaluate('window.__state()');assert replay['time']<2 and replay['playbackEpoch']>epoch
 assert not errors
 (OUT/'controls.json').write_text(json.dumps({'pass':True,'states':states,'replay':replay,'errors':errors},indent=2))
 page.close()
if __name__=='__main__':
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='chrome',headless=True,args=['--mute-audio'])
  for i in [1,2,3]:run(browser,i)
  run(browser,4,True)
  controls(browser)
  browser.close()
