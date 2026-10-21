"""Cloud browser fault injection, narrow voice UI and isolated backend safety.

Injected HTTP faults are labelled fixtures. Media success is never fabricated.
Only the task-owned loopback DEMO backend is changed, then restored to parked.
"""
import argparse,json,platform
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser()
for key in ('base-url','api-url','bundle','output','chrome'):p.add_argument('--'+key,required=True)
a=p.parse_args();assert platform.system()=='Linux'
out=Path(a.output);assert not out.exists();out.mkdir();results=[]
allowed={(urlsplit(u).hostname,urlsplit(u).port) for u in (a.base_url,a.api_url)}
assert all(h in ('localhost','127.0.0.1') for h,_ in allowed)
def record(row):
    results.append(row);(out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=a.chrome,headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--mute-audio'])
    c=b.new_context(viewport={'width':375,'height':844});errors=[];blocked=[]
    c.add_init_script("window.__captureAttempts=0;if(navigator.mediaDevices)navigator.mediaDevices.getUserMedia=()=>{window.__captureAttempts++;return Promise.reject(Error('Capture prohibited'));};")
    def route(r):
        u=urlsplit(r.request.url)
        if u.scheme in ('blob','data') or (u.hostname,u.port) in allowed:r.continue_()
        else:blocked.append(r.request.url);r.abort('blockedbyclient')
    c.route('**/*',route);page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(15000)
    page.goto(a.base_url);page.wait_for_function("!document.querySelector('#attune-language').disabled")
    # Snapshot actual storage after normal app initialization; no health record injection.
    before=page.evaluate("Object.fromEntries(Object.entries(localStorage).filter(([k])=>k!=='attune.language.v1'))")
    for language,names in [('tr',['Emel','Ahmet']),('en',['Ada','Andrew']),('de',['Katja','Stefan'])]:
        page.locator('#attune-language').select_option(language);page.wait_for_function('(lang)=>document.documentElement.lang===lang',arg=language)
        page.locator('[data-language-selector] button').click();dialog=page.get_by_role('dialog');dialog.wait_for()
        text=dialog.inner_text();assert all(name in text for name in names)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        screenshot=language+'-voice-assignments-375.png';page.screenshot(path=str(out/screenshot),full_page=True)
        page.keyboard.press('Escape')
        after=page.evaluate("Object.fromEntries(Object.entries(localStorage).filter(([k])=>k!=='attune.language.v1'))")
        assert before==after
        record({'check':'narrow approved voice inventory and storage preservation','language':language,'status':'PASS','screenshot':screenshot})
        try:
            r=c.request.post(a.api_url+'/api/vehicle/speed',data={'speedKmH':30});assert r.ok
            page.wait_for_function("document.querySelector('#attune-language').disabled")
            denial=c.request.post(a.api_url+'/api/mental/speech?language='+language,data={'text':'Neutral QA','cloudConsent':True})
            assert denial.status==409
            record({'check':'isolated DEMO backend moving locks','language':language,'status':'PASS','speechStatus':denial.status,'physicalVehicleEvidence':False})
        finally:
            assert c.request.post(a.api_url+'/api/vehicle/speed',data={'speedKmH':0}).ok
            page.wait_for_function("!document.querySelector('#attune-language').disabled")
    page.locator('#attune-language').select_option('en');page.goto(a.base_url+'/skin');page.add_script_tag(path=a.bundle)
    page.evaluate("window.dispatchEvent(new Event('attune-guidance-cancel'))")
    clip=page.evaluate("ApprovedAudioQA.audio.approvedClip('en','skin','guidance:skin-front')")
    for mode in ('missing','size','hash'):
        def fault(r,mode=mode):
            r.fulfill(status=404 if mode=='missing' else 200,body=b'not found' if mode=='missing' else (b'x' if mode=='size' else b'\x00'*clip['bytes']),content_type='audio/mp4')
        page.route('**'+clip['url'],fault)
        result=page.evaluate("async()=>{const events=[];const fn=e=>events.push(e.detail);window.addEventListener('attune-voice-unavailable',fn);const played=await ApprovedAudioQA.guidance.speakGuidance('fault-qa','skin-front',true);window.removeEventListener('attune-voice-unavailable',fn);return {played,events}}")
        page.unroute('**'+clip['url'],fault)
        assert result['played'] is False and result['events']
        record({'check':'actual dispatch rejects '+mode+' HTTP fixture','status':'PASS',**result})
    record({'check':'capture and unexpected runtime errors','status':'PASS' if not errors and not blocked and page.evaluate('window.__captureAttempts')==0 else 'FAIL','errors':errors,'blockedExternalRequests':blocked,'captureAttempts':page.evaluate('window.__captureAttempts')})
    assert not errors and not blocked
    b.close()
print(json.dumps({'checks':len(results),'failed':[r for r in results if r['status']!='PASS']}))
