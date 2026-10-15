from pathlib import Path
from playwright.sync_api import sync_playwright
import json

out = Path('visualizer/validation-reflections')
out.mkdir(exist_ok=True)

# Instrument only the served module. No debug globals are added to production.
helpers = r'''
window.__manualRipple = false;
window.__singleRipple = (source = 0) => {
  window.__manualRipple = true;
  rippleField.reset();
  rippleField.excite(source, 1);
};
window.__crossingRipples = () => {
  window.__manualRipple = true;
  rippleField.reset(); rippleField.excite(0, 0.7); rippleField.excite(5, 0.6);
};
window.__waveStep = delta => rippleField.advance(delta);
window.__waveStats = () => {
  scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
  let minX=1,maxX=-1,minY=1,maxY=-1,minHeight=0,maxHeight=0,edgeHeight=0;
  let peak=-Infinity,peakRadius=0;
  for(let i=0;i<positions.count;i++) {
    const v=new THREE.Vector3().fromBufferAttribute(positions,i);
    minHeight=Math.min(minHeight,v.y); maxHeight=Math.max(maxHeight,v.y);
    if(i % (SEG_X+1) === 0 || i % (SEG_X+1) === SEG_X || i < SEG_X+1 || i >= SEG_Z*(SEG_X+1)) edgeHeight=Math.max(edgeHeight,Math.abs(v.y));
    if(rippleField.heights[i]>peak) {
      peak=rippleField.heights[i];
      peakRadius=Math.hypot(basePositions[i*3],basePositions[i*3+2]);
    }
    v.applyMatrix4(terrain.matrixWorld).project(camera);
    minX=Math.min(minX,v.x);maxX=Math.max(maxX,v.x);
    minY=Math.min(minY,v.y);maxY=Math.max(maxY,v.y);
  }
  return {bounds:{minX,maxX,minY,maxY},minHeight,maxHeight,edgeHeight,peakRadius,
    impulseCount:rippleField.impulseCount,simulationTime:rippleField.time,
    centerHeight:rippleField.heights[Math.floor(SEG_Z/2)*(SEG_X+1)+Math.floor(SEG_X/2)],
    camera:camera.position.toArray(),zoom:camera.zoom,pose:terrainRig.rotation.toArray(),
    audio:{paused:audio.paused,time:audio.currentTime,duration:audio.duration,error:audio.error?.message},
    energy:energyLabel.textContent};
};
'''

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True,
        args=['--autoplay-policy=no-user-gesture-required'])
    context = browser.new_context(viewport={'width':1920,'height':960}, device_scale_factor=1,
        record_video_dir=str(out/'recording'), record_video_size={'width':1280,'height':640})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))

    def instrument(route):
        response = route.fetch()
        source = response.text().replace('  updateSoundWaves(delta);', '  if (!window.__manualRipple) updateSoundWaves(delta);')
        source = source.replace('  rippleField.advance(delta);', '  if (!window.__manualRipple) rippleField.advance(delta);')
        route.fulfill(response=response, body=source + helpers)

    page.route('**/src/main.js*', instrument)
    page.goto('http://localhost:5173', wait_until='networkidle')
    page.wait_for_timeout(500)
    results = {'idle':page.evaluate('window.__waveStats()')}
    assert results['idle']['maxHeight'] == 0 and results['idle']['minHeight'] == 0
    page.screenshot(path=str(out/'idle.png'))

    page.locator('#startButton').click()
    page.evaluate('document.querySelector("audio").currentTime=12')
    page.wait_for_timeout(400)
    results['music'] = []
    for i in range(24):
        page.wait_for_timeout(200)
        state = page.evaluate('window.__waveStats()')
        results['music'].append(state)
        if i in [3,11,19]:
            page.screenshot(path=str(out/f'music-{i:02}.png'))
    assert results['music'][-1]['impulseCount'] > 0
    assert any(s['minHeight'] < -0.03 and s['maxHeight'] > 0.1 for s in results['music'])
    assert results['music'][-1]['audio']['time'] > 12
    page.locator('#startButton').click()
    page.wait_for_timeout(600)
    results['pause'] = page.evaluate('window.__waveStats()')
    assert results['pause']['audio']['paused']

    # Reproduce one drop at known simulation times, independently of rendering speed.
    page.evaluate('window.__singleRipple()')
    results['singleImpulse'] = []
    elapsed = 0
    for stage, target in enumerate([0.15,0.4,0.7,1.1,1.7,2.1,3.0,4.0,4.6]):
        while elapsed < target - 1e-7:
            step = min(0.1, target-elapsed)
            page.evaluate('delta => window.__waveStep(delta)', step)
            elapsed += step
        page.wait_for_timeout(150)
        results['singleImpulse'].append(page.evaluate('window.__waveStats()'))
        page.screenshot(path=str(out/f'impulse-{stage+1:02}.png'))
    assert results['singleImpulse'][0]['peakRadius'] < 0.3
    assert results['singleImpulse'][3]['peakRadius'] > 2

    assert max(s['edgeHeight'] for s in results['singleImpulse']) > 0.1
    assert abs(results['singleImpulse'][7]['centerHeight']) > 0.05

    page.evaluate('window.__singleRipple(4)')
    for _ in range(2): page.evaluate('window.__waveStep(0.075)')
    page.wait_for_timeout(150)
    results['straight'] = page.evaluate('window.__waveStats()')
    page.screenshot(path=str(out/'straight-wave.png'))
    page.evaluate('window.__crossingRipples()')
    for _ in range(12): page.evaluate('window.__waveStep(0.1)')
    page.wait_for_timeout(150)
    results['crossing'] = page.evaluate('window.__waveStats()')
    page.screenshot(path=str(out/'crossing-waves.png'))

    for _ in range(200):
        page.evaluate('window.__waveStep(0.1)')
    page.wait_for_timeout(150)
    results['settled'] = page.evaluate('window.__waveStats()')
    assert max(abs(results['settled']['minHeight']),results['settled']['maxHeight']) < 0.005

    # Seeking clears wave history. Resume the ordinary simulation for playback checks.
    page.evaluate('window.__manualRipple=false; document.querySelector("audio").currentTime=46')
    page.wait_for_timeout(250)
    results['seek'] = page.evaluate('window.__waveStats()')
    assert results['seek']['maxHeight'] == 0 and results['seek']['minHeight'] == 0

    page.locator('#startButton').click()
    results['responsive'] = []
    for width,height in [(1366,768),(768,1024),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        page.wait_for_timeout(650)
        results['responsive'].append(page.evaluate('window.__waveStats()'))
    for state in [results['idle'],*results['music'],*results['singleImpulse'],results['straight'],results['crossing'],*results['responsive']]:
        assert max(abs(v) for v in state['bounds'].values()) < 0.99, state
        assert state['edgeHeight'] <= 2.8, state
        assert state['minHeight'] >= -2.8 and state['maxHeight'] <= 2.8
    for state in results['music']:
        assert state['camera'] == results['idle']['camera']
        assert state['pose'] == results['idle']['pose']
        assert state['zoom'] == results['idle']['zoom']
        assert state['audio']['error'] is None
    results['errors'] = errors
    assert not errors, errors
    (out/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    video = page.video
    context.close()
    video.save_as(str(out/'waves-preview.webm'))
    browser.close()
    print(json.dumps({'checks':'passed', 'impulses':results['music'][-1]['impulseCount'],
        'musicHeights':[min(s['minHeight'] for s in results['music']),max(s['maxHeight'] for s in results['music'])],
        'radii':[round(s['peakRadius'],2) for s in results['singleImpulse']],
        'edgeMotion':max(s['edgeHeight'] for s in results['singleImpulse']),
        'reflectedCenterHeight':results['singleImpulse'][7]['centerHeight'],
        'settledHeight':results['settled']['maxHeight'], 'errors':errors},indent=2))
