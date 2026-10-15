from pathlib import Path
from playwright.sync_api import sync_playwright
import json

out = Path('visualizer/validation-stem-sync')
out.mkdir(exist_ok=True)
helpers = r'''
window.__cueAudit = [];
window.__cuesReady = () => cueTimeline !== null;
window.__cuesInRange = range => cueTimeline.events.filter(e=>e.time>=range[0] && e.time<=range[1]);
const measuredExciteAt = rippleField.exciteAt.bind(rippleField);
rippleField.exciteAt = (x,z,strength,width) => {
  const cue = cueTimeline.events[cueTimeline.index-1];
  window.__cueAudit.push({time:cue.time,source:cue.source,x,z,strength,
    playerTime:audio.currentTime,delay:audio.currentTime-cue.time});
  measuredExciteAt(x,z,strength,width);
};
window.__syncStats = () => {
  scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
  let minX=1,maxX=-1,minY=1,maxY=-1,minHeight=0,maxHeight=0;
  for(let i=0;i<positions.count;i++) {
    const v=new THREE.Vector3().fromBufferAttribute(positions,i);
    minHeight=Math.min(minHeight,v.y);maxHeight=Math.max(maxHeight,v.y);
    v.applyMatrix4(terrain.matrixWorld).project(camera);
    minX=Math.min(minX,v.x);maxX=Math.max(maxX,v.x);
    minY=Math.min(minY,v.y);maxY=Math.max(maxY,v.y);
  }
  return {playerTime:audio.currentTime,paused:audio.paused,error:audio.error?.message,
    cueError:cueLoadError?.message,impulses:rippleField.impulseCount,
    emitted:cueTimeline?.emittedCount,nextIndex:cueTimeline?.index,
    camera:camera.position.toArray(),pose:terrainRig.rotation.toArray(),zoom:camera.zoom,
    minHeight,maxHeight,bounds:{minX,maxX,minY,maxY},energy:energyLabel.textContent};
};
'''

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome',headless=True,
        args=['--autoplay-policy=no-user-gesture-required'])
    context = browser.new_context(viewport={'width':1920,'height':960},device_scale_factor=1,
        record_video_dir=str(out/'recording'),record_video_size={'width':1280,'height':640})
    page = context.new_page()
    errors = []
    page.on('pageerror',lambda e:errors.append(str(e)))
    def instrument(route):
        response = route.fetch()
        route.fulfill(response=response,body=response.text()+helpers)
    page.route('**/src/main.js*',instrument)
    page.goto('http://localhost:5173',wait_until='networkidle')
    page.wait_for_function('window.__cuesReady && window.__cuesReady()')
    results = {'idle':page.evaluate('window.__syncStats()')}
    assert results['idle']['impulses']==0
    results['clips'] = []
    for start in [46,200]:
        page.evaluate('time => {audio.currentTime=time;window.__cueAudit=[];}',start)
        page.wait_for_timeout(200)
        page.locator('#startButton').click()
        samples=[]
        for i in range(20):
            page.wait_for_timeout(200)
            samples.append(page.evaluate('window.__syncStats()'))
            if i in [5,15]:page.screenshot(path=str(out/f'clip-{start}-{i}.png'))
        page.locator('#startButton').click()
        page.wait_for_timeout(200)
        audit=page.evaluate('window.__cueAudit')
        end=page.evaluate('audio.currentTime')
        expected=page.evaluate('range => window.__cuesInRange(range)',[start,end])
        assert [(e['time'],e['source']) for e in audit]==[(e['time'],e['source']) for e in expected], (start,len(audit),len(expected))
        for actual,reference in zip(audit,expected):
            assert actual['strength']==reference['strength']
            assert actual['x']==reference['x'] and actual['z']==reference['z']
            assert -0.000001<=actual['delay']<0.3,actual
        assert len({e['source'] for e in audit})>=3
        pauseCount=len(audit)
        page.wait_for_timeout(500)
        assert page.evaluate('window.__cueAudit.length')==pauseCount
        for sample in samples:
            assert sample['impulses']==sample['emitted']
            assert sample['camera']==results['idle']['camera'] and sample['pose']==results['idle']['pose']
            assert sample['error'] is None and sample['cueError'] is None
            assert max(abs(v) for v in sample['bounds'].values())<0.995,sample
        results['clips'].append({'start':start,'end':end,'samples':samples,'audit':audit,
            'maxDelayMs':max(e['delay'] for e in audit)*1000,
            'sources':sorted({e['source'] for e in audit})})
    page.evaluate('audio.currentTime=0')
    page.wait_for_timeout(200)
    results['reset']=page.evaluate('window.__syncStats()')
    assert results['reset']['impulses']==0 and results['reset']['maxHeight']==0
    assert not errors,errors
    results['errors']=errors
    (out/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    video=page.video
    context.close()
    video.save_as(str(out/'stem-sync-preview.webm'))
    browser.close()
    print(json.dumps({'checks':'passed','clips':[{'start':c['start'],'hits':len(c['audit']),
        'sources':c['sources'],'maxPresentationDelayMs':round(c['maxDelayMs'],2)} for c in results['clips']],
        'errors':errors},indent=2))
