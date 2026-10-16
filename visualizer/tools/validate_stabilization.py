"""Controlled V1.1R1 evidence. Requires Vite :5173, Chrome and Playwright."""
import argparse
import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "reports/v1_1r1-evidence"
SNAPSHOT = "V1_PRE_STABILIZATION_20261015_235716"
EXPOSE = r"""
window.__v11 = {
  ready: cueReady,
  sample: () => ({duration: audio.duration, label: durationLabel.textContent,
    paused: audio.paused, time: audio.currentTime, energy: energyLabel.textContent,
    bloom: bloom.strength, particleY: particles.position.y,
    maxHeight: Math.max(...rippleField.heights.map(Math.abs)),
    impulses: rippleField.impulseCount, cueError: String(cueLoadError || ''),
    camera: camera.position.toArray(), zoom: camera.zoom,
    pose: terrainRig.rotation.toArray(), scale: terrainRig.scale.toArray()}),
  musical: () => {
    rippleField.reset(); cueTimeline.seek(46);
    for(let i=1;i<=240;i++) cueTimeline.step(46+i/120,true,
      c=>rippleField.exciteAt(c.x,c.z,c.strength,c.width),s=>rippleField.advance(s));
    for(let i=0;i<positions.count;i++) positions.array[i*3+1]=TERRAIN.maxHeight*Math.tanh(rippleField.heights[i]/TERRAIN.maxHeight);
    positions.needsUpdate=true; composer.render();
    return Array.from(positions.array);
  }
};
"""


def instrument(page, controlled=False, baseline=False):
    if controlled:
        page.add_init_script("""let seed=12345; window.__resetParticleSeed=()=>{seed=12345}; Math.random=()=>((seed=(1664525*seed+1013904223)>>>0)/4294967296);
          window.requestAnimationFrame=()=>0;""")
    def route_main(route):
        response = route.fetch(url=f"http://localhost:5173/backups/{SNAPSHOT}/src/main.js") if baseline else route.fetch()
        text = response.text()
        if controlled:
            text = text.replace("const clock = new THREE.Clock();", "const clock = {getElapsedTime:()=>2};")
            # Three.js UUID allocation also consumes Math.random; removing two lights
            # changes that consumption. Seed particles at their own creation boundary.
            text = text.replace("const particleCount =", "window.__resetParticleSeed();\nconst particleCount =")
        route.fulfill(response=response, body=text + EXPOSE)
    page.route("**/src/main.js*", route_main)


def capture(browser, phase):
    page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    instrument(page, controlled=True, baseline=phase == "before")
    if phase == "before":
        baseline_html = OUT.parents[1] / f"backups/{SNAPSHOT}/index.html"
        page.route("http://localhost:5173/", lambda route: route.fulfill(status=200, content_type="text/html", body=baseline_html.read_text(encoding="utf-8-sig")))
    page.goto("http://localhost:5173", wait_until="networkidle")
    page.wait_for_function("window.__v11 && document.querySelector('audio').readyState>=1")
    page.evaluate("window.__v11.ready")
    page.screenshot(path=str(OUT / f"{phase}-idle-full.png"))
    state = page.evaluate("window.__v11.sample()")
    page.add_style_tag(content="#app > :not(canvas) { visibility:hidden !important; }")
    page.screenshot(path=str(OUT / f"{phase}-idle-scene.png"))
    vertices = page.evaluate("window.__v11.musical()")
    state["musicalPositionsSha256"] = hashlib.sha256(json.dumps(vertices).encode()).hexdigest()
    page.screenshot(path=str(OUT / f"{phase}-musical-scene.png"))
    page.close()
    return state


def playback(browser, fail_manifest=False):
    page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    errors = []
    console_errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    instrument(page)
    if fail_manifest:
        page.route("**/audio/tukana-visualizer-manifest.json", lambda route: route.fulfill(status=503, body="Unavailable"))
    page.goto("http://localhost:5173", wait_until="networkidle")
    page.wait_for_function("window.__v11 && document.querySelector('audio').readyState>=1")
    page.evaluate("window.__v11.ready")
    if fail_manifest:
        page.wait_for_function("document.querySelector('#deliveryStatus').textContent==='UNAVAILABLE'")
    else:
        page.wait_for_function("document.querySelector('#integratedLufs').textContent==='-16.90'")
    states = {"before": page.evaluate("window.__v11.sample()")}
    page.locator("#startButton").click()
    page.wait_for_function("document.querySelector('audio').currentTime>0.4")
    states["playing"] = page.evaluate("window.__v11.sample()")
    page.locator("#startButton").click()
    states["paused"] = page.evaluate("window.__v11.sample()")
    page.locator("#timeline").click(position={"x": 100, "y": 1})
    page.wait_for_function("document.querySelector('audio').currentTime>10 && !document.querySelector('audio').seeking")
    states["seek"] = page.evaluate("window.__v11.sample()")
    page.locator("#startButton").click()
    page.wait_for_function("!document.querySelector('audio').paused")
    page.wait_for_timeout(1800)
    states["resumed"] = page.evaluate("window.__v11.sample()")
    assert all(s["label"] == "05:30" for s in states.values()), states
    assert not states["playing"]["paused"] and states["paused"]["paused"]
    assert states["resumed"]["impulses"] > 0 and states["resumed"]["maxHeight"] > 0
    assert states["resumed"]["bloom"] > .45 and states["resumed"]["particleY"] > 0
    assert all(s["camera"] == states["before"]["camera"] and s["pose"] == states["before"]["pose"] for s in states.values())
    assert not errors, errors
    states["pageErrors"] = errors
    states["consoleErrors"] = console_errors
    if fail_manifest:
        assert any("LAISE technical metadata unavailable" in error for error in console_errors)
    page.close()
    return states


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["before", "after"])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--mute-audio"])
        result = {"controlled": capture(browser, args.phase)}
        if args.phase == "after":
            result["playback"] = playback(browser)
            result["manifestFailurePlayback"] = playback(browser, fail_manifest=True)
            comparator = browser.new_page()
            import base64
            for scene in ("idle", "musical"):
                images = ["data:image/png;base64," + base64.b64encode((OUT / f"{phase}-{scene}-scene.png").read_bytes()).decode() for phase in ("before", "after")]
                result[f"{scene}PixelIdentical"] = comparator.evaluate("""async urls => {
                  const pixels = await Promise.all(urls.map(async url => {
                    const image = new Image(); image.src=url; await image.decode();
                    const canvas=document.createElement('canvas'); canvas.width=image.width; canvas.height=image.height;
                    const ctx=canvas.getContext('2d'); ctx.drawImage(image,0,0);
                    return ctx.getImageData(0,0,canvas.width,canvas.height).data;
                  }));
                  return pixels[0].length===pixels[1].length && pixels[0].every((v,i)=>v===pixels[1][i]);
                }""", images)
                assert result[f"{scene}PixelIdentical"], f"Visual regression: {scene}"
            comparator.close()
            before = json.loads((OUT / "before.json").read_text())["controlled"]
            assert before["musicalPositionsSha256"] == result["controlled"]["musicalPositionsSha256"]
        (OUT / f"{args.phase}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        browser.close()
