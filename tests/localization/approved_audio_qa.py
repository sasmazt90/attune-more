"""Finite Linux Cloud audio acceptance. Actual browser media, no physical capture.

Uses a keyless isolated QA backend and bundles unchanged production dispatch
functions into the test page; no product hooks or fake successful media events.
"""
import argparse
import json
import platform
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

p=argparse.ArgumentParser()
p.add_argument('--base-url',default='http://127.0.0.1:3300')
p.add_argument('--api-url',default='http://127.0.0.1:8101')
p.add_argument('--bundle',required=True)
p.add_argument('--output',required=True)
p.add_argument('--chrome',required=True)
p.add_argument('--lifecycle-only',action='store_true',help='Recheck lifecycle/failure cases without repeating completed codec/module playback checks')
a=p.parse_args()
assert platform.system()=='Linux','Cloud-only assessment'
out=Path(a.output);assert not out.exists(),'Preserve existing evidence';out.mkdir();(out/'screenshots').mkdir()
allowed={(urlsplit(u).hostname,urlsplit(u).port) for u in (a.base_url,a.api_url)}
assert all(h in ('localhost','127.0.0.1') for h,_ in allowed)
results=[]
def record(check,value):
    results.append({'check':check,**value});(out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=a.chrome,headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--mute-audio'])
    context=browser.new_context(viewport={'width':1440,'height':1000})
    context.add_init_script("window.__captureAttempts=0;if(navigator.mediaDevices)navigator.mediaDevices.getUserMedia=()=>{window.__captureAttempts++;return Promise.reject(Error('Physical capture outside Cloud QA'));};")
    blocked=[]
    def route(r):
        u=urlsplit(r.request.url)
        if u.scheme in ('blob','data') or (u.hostname,u.port) in allowed:r.continue_()
        else:blocked.append(r.request.url);r.abort('blockedbyclient')
    context.route('**/*',route)
    page=context.new_page();page.set_default_timeout(20000);page.set_default_navigation_timeout(30000)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    page.goto(a.base_url);page.wait_for_function("!document.querySelector('#attune-language').disabled")
    page.add_script_tag(path=a.bundle)
    if not a.lifecycle_only:
        decoded=page.evaluate('''async()=>{
          const audio=new Audio(),context=new AudioContext(),rows=[];
          for(const clip of ApprovedAudioQA.audio.approvedAudio.recordings){
            const r=await fetch(clip.url),bytes=await r.arrayBuffer(),hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
            const buffer=await context.decodeAudioData(bytes.slice(0));
            rows.push({id:clip.recordingId,status:r.ok&&bytes.byteLength===clip.bytes&&hash===clip.sha256&&buffer.duration>0?'PASS':'FAIL',bytes:bytes.byteLength,sha256:hash,httpMime:r.headers.get('content-type'),declaredMime:clip.mimeType,canPlay:audio.canPlayType(clip.mimeType),duration:buffer.duration,channels:buffer.numberOfChannels,sampleRate:buffer.sampleRate});
          }await context.close();return rows;
        }''')
        (out/'browser-decode.json').write_text(json.dumps(decoded,indent=2))
        assert len(decoded)==194 and all(r['status']=='PASS' and r['canPlay'] and r['httpMime'].split(';')[0]=='audio/mp4' for r in decoded)
        record('194 actual browser fetch/hash/decode',{'status':'PASS','files':194})
        choices={'skin':'skin-neutral','dental':'dental-front','mental':'mental-entry','hearing':'hearing-tone'}
        for language in ('tr','en','de'):
            page.locator('#attune-language').select_option(language)
            for module in ('skin','dental','vision','hearing','mental'):
                page.goto(a.base_url+'/'+module,wait_until='domcontentloaded')
                page.wait_for_function('(lang)=>document.documentElement.lang===lang',arg=language)
                dialog=page.get_by_role('dialog').filter(has=page.get_by_role('button',name={'tr':'İzin ver ve devam et','en':'Allow and continue','de':'Erlauben und fortfahren'}[language],exact=True))
                if dialog.count():
                    for box in dialog.get_by_role('checkbox').all():box.check()
                    dialog.get_by_role('button',name={'tr':'İzin ver ve devam et','en':'Allow and continue','de':'Erlauben und fortfahren'}[language],exact=True).click()
                page.mouse.click(12,12)
                page.evaluate("window.dispatchEvent(new Event('attune-guidance-cancel'))")
                page.add_script_tag(path=a.bundle)
                result=page.evaluate('''async({language,module,id})=>{
                  const q=ApprovedAudioQA,events=[];const observed=e=>events.push(e.detail);window.addEventListener('attune-guidance-event',observed);
                  const event=module==='vision'?'vision:next1':'guidance:'+id,clip=q.audio.approvedClip(language,module,event);
                  let passed;if(module==='vision')passed=await q.playback.playFixedSpeech(new Audio(),clip,new AbortController().signal,()=>true,stage=>events.push({event:stage,recordingId:clip.recordingId}),true);
                  else passed=await q.guidance.speakGuidance('browser-evidence',id,true);
                  window.removeEventListener('attune-guidance-event',observed);
                  return {status:passed&&events.some(e=>e.event==='playing')&&events.some(e=>e.event==='ended')?'PASS':'FAIL',language,module,event,recordingId:clip.recordingId,voice:clip.voice,voiceLocale:clip.voiceLocale,applicationLocale:clip.applicationLocale,events};
                }''',{'language':language,'module':module,'id':choices.get(module)})
                screenshot=f'{language}-{module}.png';page.screenshot(path=str(out/'screenshots'/screenshot),full_page=True);result['screenshot']='screenshots/'+screenshot
                record('actual module recording playback',result);assert result['status']=='PASS',result
    # Exercise actual browser cancellation with long clips: no fabricated events.
    page.goto(a.base_url+'/mental');page.add_script_tag(path=a.bundle)
    for mode in ('abort','mute','language','navigation','background'):
        page.evaluate("ApprovedAudioQA.core.setLanguage('en')")
        page.wait_for_function("document.documentElement.lang==='en'")
        page.wait_for_timeout(150) # React's locale-cancellation effect must settle before a new utterance.
        page.evaluate("window.dispatchEvent(new Event('attune-guidance-cancel'));window.__cancelEvents=[];window.addEventListener('attune-guidance-event',e=>window.__cancelEvents.push(e.detail));window.__play=ApprovedAudioQA.guidance.speakGuidance('cancel-qa','mental-entry',true);undefined")
        page.wait_for_function("window.__cancelEvents.some(e=>e.event==='playing')")
        if mode=='abort':page.evaluate("ApprovedAudioQA.guidance.cancelGuidance()")
        elif mode=='mute':page.evaluate("ApprovedAudioQA.guidance.muteGuidance(true)")
        elif mode=='language':page.evaluate("ApprovedAudioQA.core.setLanguage('de')")
        elif mode=='navigation':page.evaluate("history.pushState({},'','/privacy')")
        else:
            other=context.new_page();other.goto(a.base_url+'/privacy');other.bring_to_front()
            if not page.evaluate('document.hidden'):
                other.close();record('actual background cancellation',{'status':'UNVERIFIED','reason':'Headless Chrome does not expose hidden state for this tab'});page.evaluate('ApprovedAudioQA.guidance.cancelGuidance()');continue
        value=page.evaluate("async()=>({played:await window.__play,events:window.__cancelEvents})")
        assert value['played'] is False and not any(e['event']=='ended' for e in value['events'])
        record('actual '+mode+' cancellation',{'status':'PASS',**value})
        if mode=='mute':page.evaluate("ApprovedAudioQA.guidance.muteGuidance(false)")
        if mode=='navigation':page.evaluate("history.replaceState({},'','/mental')")
        if mode=='background':other.close();page.bring_to_front()
    record('browser errors and capture boundary',{'status':'PASS' if not errors and not blocked and page.evaluate('window.__captureAttempts')==0 else 'FAIL','errors':errors,'blockedExternalRequests':blocked,'captureAttempts':page.evaluate('window.__captureAttempts')})
    assert not errors and not blocked
    browser.close()
print(json.dumps({'checks':len(results),'failed':[r for r in results if r['status']=='FAIL'],'unverified':[r for r in results if r['status']=='UNVERIFIED']}))
