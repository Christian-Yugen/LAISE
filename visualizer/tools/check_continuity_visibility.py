"""Probe actual headless visibility support; never override document.hidden."""
import json,time
from playwright.sync_api import sync_playwright
from validate_playback_continuity import setup,OUT
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True,args=['--mute-audio'])
 page,errors=setup(browser)
 page.evaluate('window.__visibility=[];document.addEventListener("visibilitychange",()=>window.__visibility.push({state:document.visibilityState,time:document.querySelector("audio").currentTime}))')
 page.locator('#startButton').click();page.wait_for_timeout(500)
 initial=page.evaluate('window.__state()')
 other=browser.new_page();other.goto('about:blank');other.bring_to_front()
 visibility=page.evaluate('document.visibilityState')
 cdp=page.context.new_cdp_session(page)
 cdp.send('Page.setWebLifecycleState',{'state':'frozen'});time.sleep(1.5)
 cdp.send('Page.setWebLifecycleState',{'state':'active'});page.bring_to_front();page.wait_for_timeout(500)
 page.evaluate('document.querySelector("audio").pause()');page.wait_for_timeout(100)
 final=page.evaluate('window.__state()');audit=page.evaluate('window.__audit');events=page.evaluate('window.__visibility')
 cues=page.evaluate('fetch("/audio/tukana-stem-cues.json").then(r=>r.json()).then(d=>d.events)')
 expected=[i for i,c in enumerate(cues) if c['time']<=final['simulationTime']]
 actual=[r['cueIndex'] for r in audit['records']]
 result={'pass':True,'initial':initial,'final':final,'actualBackgroundVisibility':visibility,'visibilityEvents':events,
 'hiddenSupported':visibility=='hidden' or any(e['state']=='hidden' for e in events),'method':'second foreground tab plus CDP frozen/active lifecycle; no visibility property overrides','audit':audit,'errors':errors}
 (OUT/'visibility-lifecycle.json').write_text(json.dumps(result,indent=2))
 assert expected==actual and not audit['resets'] and not errors,(expected,actual,audit['resets'],errors)
 print(json.dumps({k:v for k,v in result.items() if k!='audit'}))
 browser.close()
