"""Actual local MediaPipe + browser fake camera negative paths, no model stubs.
No physical-camera, eyelid/hand/object detection accuracy claim.
"""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=os.getenv('VISION_TEST_URL','http://127.0.0.1:3306')
SEED="localStorage.setItem('attune_health_processing_v1',JSON.stringify({version:1,services:{vision:{permissions:['local','speech']}}}));localStorage.setItem('attune_privacy_microphone_allowed','true');"
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=os.getenv('CHROME_PATH') or None,channel=None if os.getenv('CHROME_PATH') else 'chrome',headless=True,args=['--use-fake-device-for-media-stream','--autoplay-policy=no-user-gesture-required','--enable-unsafe-swiftshader','--no-sandbox'])
    try:
        context=browser.new_context(permissions=['camera']);context.add_init_script(SEED+"window.streams=[];const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...args)=>{const s=await gum(...args);streams.push(s);return s;};")
        p=context.new_page();p.goto(BASE+'/vision');p.get_by_role('button',name='Başlat',exact=True).click()
        p.wait_for_function("()=>!!document.querySelector('canvas')?.dataset.visionEvidence",timeout=90000)
        evidence=p.evaluate("JSON.parse(document.querySelector('canvas').dataset.visionEvidence)")
        assert evidence['conditions']['faceCount']==0
        assert evidence['conditions']['right']['state']=='uncertain' and evidence['conditions']['left']['state']=='uncertain'
        assert p.locator('[data-letter-optotype]').count()==0
        p.evaluate("streams[0].getTracks().forEach(t=>t.stop())")
        p.wait_for_function("()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='idle'",timeout=15000)
        assert p.evaluate("localStorage.getItem('togg_health_latest_vision')")==None
        denied=browser.new_context();denied.add_init_script(SEED);q=denied.new_page();q.goto(BASE+'/vision')
        denied.new_cdp_session(q).send('Browser.setPermission',{'permission':{'name':'camera'},'setting':'denied','origin':BASE})
        q.get_by_role('button',name='Başlat',exact=True).click();q.locator('p[role=alert]').wait_for();assert q.locator('[data-letter-optotype]').count()==0
        result={'kind':'native fake-device browser capture; unchanged local MediaPipe worker/weights; no face in test pattern','delegate':evidence['delegate'],'faceCount':0,'eyes':['uncertain','uncertain'],'nativeCameraPermissionDenied':True,'trackDisconnectionCleanup':True,'physicalUserAcceptance':False}
        path=Path('docs/vision-evidence/native-camera.json');path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:browser.close()
