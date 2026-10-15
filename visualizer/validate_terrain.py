from pathlib import Path
from playwright.sync_api import sync_playwright
import json
out=Path('visualizer/validation-tilt'); out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
    page=browser.new_page(viewport={'width':1920,'height':960},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda e: errors.append(str(e)))
    def expose(route):
        response=route.fetch()
        route.fulfill(response=response,body=response.text()+'''\nwindow.__terrainCheck = () => {
          scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
          let minX=1,maxX=-1,minY=1,maxY=-1,maxHeight=0,edgeHeight=0;
          for(let i=0;i<positions.count;i++) {
            const v=new THREE.Vector3().fromBufferAttribute(positions,i);
            maxHeight=Math.max(maxHeight,v.y);
            if(i % (SEG_X+1) === 0 || i % (SEG_X+1) === SEG_X || i < SEG_X+1 || i >= SEG_Z*(SEG_X+1)) edgeHeight=Math.max(edgeHeight,Math.abs(v.y));
            v.applyMatrix4(terrain.matrixWorld).project(camera);
            minX=Math.min(minX,v.x);maxX=Math.max(maxX,v.x);minY=Math.min(minY,v.y);maxY=Math.max(maxY,v.y);
          }
          const baseCorners = [[-TERRAIN.width/2,-TERRAIN.depth/2],[-TERRAIN.width/2,TERRAIN.depth/2],[TERRAIN.width/2,-TERRAIN.depth/2],[TERRAIN.width/2,TERRAIN.depth/2]].map(([x,z]) =>
            new THREE.Vector3(x,0,z).applyMatrix4(terrain.matrixWorld).project(camera));
          const baseCenter = {
            x:(Math.min(...baseCorners.map(p=>p.x))+Math.max(...baseCorners.map(p=>p.x)))/2,
            y:(Math.min(...baseCorners.map(p=>p.y))+Math.max(...baseCorners.map(p=>p.y)))/2
          };
          return {zoom:camera.zoom,baseCenter,camera:camera.position.toArray(),fov:camera.fov,pose:terrainRig.rotation.toArray(),
            bounds:{minX,maxX,minY,maxY},maxHeight,edgeHeight,
            audio:{paused:audio.paused,time:audio.currentTime,duration:audio.duration,error:audio.error?.message},
            context:audioContext.state,energy:energyLabel.textContent};
        };''')
    page.route('**/src/main.js*',expose)
    page.goto('http://localhost:5173',wait_until='networkidle')
    page.wait_for_timeout(1500)
    results={'idle':page.evaluate('window.__terrainCheck()')}
    page.screenshot(path=str(out/'desktop-idle.png'))
    page.locator('#startButton').click()
    page.wait_for_timeout(500)
    page.evaluate('document.querySelector("audio").currentTime=46')
    page.wait_for_timeout(2500)
    results['playing']=page.evaluate('window.__terrainCheck()')
    page.screenshot(path=str(out/'desktop-playing.png'))
    page.locator('#startButton').click()
    page.wait_for_timeout(700)
    results['paused']=page.evaluate('window.__terrainCheck()')
    for w,h in [(1366,768),(768,1024),(390,844)]:
        page.set_viewport_size({'width':w,'height':h});page.wait_for_timeout(350)
        results[f'{w}x{h}']=page.evaluate('window.__terrainCheck()')
    results['errors']=errors
    for key, result in results.items():
        if key == 'errors': continue
        assert result['baseCenter']['x'] > 0 and abs(result['baseCenter']['y']) < 1e-6, (key,result)
        assert max(abs(v) for v in result['bounds'].values()) < 0.981, (key,result)
        assert result['edgeHeight'] <= 2.8, (key,result)
    assert not errors, errors
    assert not results['playing']['audio']['paused'] and results['playing']['audio']['time'] > 46
    assert results['paused']['audio']['paused']
    assert results['idle']['camera'] == results['playing']['camera']
    assert results['idle']['pose'] == results['playing']['pose']
    (out/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))
    browser.close()
