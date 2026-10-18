"""Separate ASR finals through the production controller; controlled, not physical acceptance."""
import ast, base64, json, sys,os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path.cwd();OUT=ROOT/'audit-results/feedback-four-modules-20261009/vision-memory';OUT.mkdir(parents=True,exist_ok=True)
PHASE=sys.argv[1] if len(sys.argv)>1 else 'after'
tree=ast.parse((ROOT/'tests/e2e/vision_feedback.py').read_text('utf8'))
BOOT=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BOOT' for t in n.targets))
BOOT=BOOT.replace('confidence:.99','confidence:this.confidence??.99')
BOOT=BOOT.replace('{transcript:text,confidence:this.confidence??.99}', 'Object.create({transcript:text,confidence:this.confidence??.99})')
BOOT+="""
sessionStorage.setItem('attune_vision_size_diagnostics','1');probe.sizeDiagnostics=[];
window.addEventListener('attune-vision-size-diagnostic',e=>probe.sizeDiagnostics.push(e.detail));
crypto.getRandomValues=a=>{a[0]=Math.floor(27.25/40*4294967296);return a;};
"""

def capture(p,name):
    p.bring_to_front()
    # Keep the actual glyph and existing response fields visible; capture one
    # native viewport, avoiding compositor gaps in repeated full-page captures.
    p.evaluate("""()=>{const e=document.querySelector('[data-letter-optotype]');if(e){const b=e.getBoundingClientRect(),h=document.querySelector('[data-cockpit-header]').getBoundingClientRect().bottom;window.scrollBy(0,b.top+b.height/2-(Math.max(0,h)+innerHeight)/2)}}""")
    p.wait_for_timeout(100)
    cdp=p.context.new_cdp_session(p);r=cdp.send('Page.captureScreenshot',{'format':'png','fromSurface':True,'captureBeyondViewport':False});cdp.detach();(OUT/name).write_bytes(base64.b64decode(r['data']))
def active(p):
    try:p.wait_for_function("document.querySelector('[data-vision-stage]')?.dataset.visionStage==='listening'&&probe.current&&!probe.current.aborted&&document.querySelector('[data-letter-optotype]')",timeout=15000)
    except Exception:
        (OUT/'failure-state.json').write_text(json.dumps({'state':state(p),'body':p.locator('body').inner_text(),'recognitions':p.evaluate('probe.recognitions.map(r=>({aborted:r.aborted,results:r.results,confidence:r.confidence}))')},ensure_ascii=False,indent=2),'utf8');capture(p,'failure.png');raise
def target(p):return p.locator('[data-vision-trial]').get_attribute('data-vision-trial')
def state(p):
    return p.evaluate("({id:document.querySelector('[data-vision-trial]').dataset.visionTrial,stage:document.querySelector('[data-vision-stage]').dataset.visionStage,heard:[...document.querySelectorAll('p')].map(e=>e.innerText).find(t=>t.startsWith('Duyulan:'))||'',notice:document.querySelector('[data-vision-answer-notice]')?.innerText,parsed:JSON.parse(document.querySelector('canvas').dataset.visionAnswer||'null'),diagnostics:probe.sizeDiagnostics,calls:probe.calls.map(c=>c.code),size:document.querySelector('[data-letter-optotype]')?.getBoundingClientRect().width})")
def emit(p,text,confidence=.99):p.evaluate('({text,confidence})=>{probe.current.confidence=confidence;probe.current.emit(text)}',{'text':text,'confidence':confidence})
def followup(p,code):
    p.wait_for_function('code=>probe.calls.at(-1)?.code===code&&probe.audios.at(-1)?.paused===false',arg=code,timeout=6000)
def changed(p,old):p.wait_for_function('id=>document.querySelector("[data-vision-trial]").dataset.visionTrial!==id',arg=old,timeout=5000);active(p)
def stop(p):
    p.get_by_role('button',name='Bitir',exact=True).scroll_into_view_if_needed();p.get_by_role('button',name='Bitir',exact=True).click();p.get_by_role('button',name='Tamam',exact=True).click()
    assert p.evaluate("!localStorage.getItem('togg_health_vision_history')")

proof=[]
with sync_playwright() as pw:
    c=pw.chromium.launch_persistent_context(str(OUT/(PHASE+'-profile')),channel='chrome',headless=False,no_viewport=True,args=['--window-size=1920,1080','--window-position=0,0']);c.add_init_script(BOOT);p=c.pages[0]
    modes=['followup','low-confidence','sensor-recovery'] if PHASE=='before' else ['followup','low-confidence','sensor-recovery','letter-first','e-down','single','e-sentence','mirror-parts','correction','asr-restart','tts-ended','interim-duplicate','pause-resume']
    if os.getenv('VISION_MEMORY_MODES'):modes=os.environ['VISION_MEMORY_MODES'].split(',')
    for mode in modes:
        p.goto('http://127.0.0.1:3000/vision')
        if mode in ['e-down','e-sentence','mirror-parts']:
            p.evaluate('index=>{crypto.getRandomValues=a=>{a[0]=Math.floor((index+.25)/40*4294967296);return a}}',29 if mode=='mirror-parts' else 13)
        p.get_by_role('button',name='Başlat',exact=True).click();active(p);old=target(p)
        start=state(p)
        first_text='E' if mode=='e-down' else 'P' if mode=='letter-first' else 'baş aşağı' if mode=='mirror-parts' else 'sağa yatmış ve aynalı P veya E' if mode=='correction' else 'sağa yatmış ve aynalı'
        if mode in ['single','e-sentence']:
            first=start;capture(p,PHASE+'-'+mode+'-first.png');emit(p,'Aşağı dönük E harfi' if mode=='e-sentence' else 'sağa yatmış ve aynalı P');changed(p,old);second=state(p)
            assert len(second['diagnostics'])==1 and second['diagnostics'][0]['combinedCorrect'] is True
            proof.append({'mode':mode,'first':first,'second':second,'advanced':True});capture(p,PHASE+'-'+mode+'-second.png');stop(p);continue
        if mode=='interim-duplicate':
            p.evaluate('text=>probe.current.emit(text,false)',first_text);p.wait_for_timeout(80);assert not state(p)['heard']
        emit(p,first_text,.35 if mode=='low-confidence' else .99)
        followup(p,'orientation' if mode in ['letter-first','e-down'] else 'letter')
        first=state(p);capture(p,PHASE+'-'+mode+'-first.png')
        if mode=='interim-duplicate':
            p.evaluate('text=>probe.current.emit(text,true,true)',first_text);p.wait_for_timeout(80);assert state(p)['heard']==first['heard']
        if mode=='sensor-recovery':
            p.evaluate("probe.fault='uncertain'");p.wait_for_function("document.querySelector('[data-vision-stage]').dataset.visionStage==='condition-paused'",timeout=5000);p.wait_for_timeout(150);p.evaluate('probe.fault=null');active(p);old=target(p)
        if mode=='pause-resume':
            p.get_by_role('button',name='Duraklat',exact=True).click();p.get_by_role('button',name='Devam et',exact=True).click();active(p);old=target(p)
        if mode=='asr-restart':
            p.evaluate('()=>{probe.old=probe.current;probe.oldCallback=probe.current.onresult;probe.current.onend()}')
            p.wait_for_function('probe.current!==probe.old&&!probe.current.aborted');active(p)
            assert state(p)['heard']==first['heard']
            p.evaluate("probe.oldCallback({resultIndex:0,results:[Object.assign([{transcript:'düz E',confidence:1}],{isFinal:true})]})")
            p.wait_for_timeout(80);assert state(p)['heard']==first['heard']
        if mode=='tts-ended':
            p.wait_for_function('probe.audios.at(-1).paused===true',timeout=10000);assert state(p)['heard']==first['heard']
        intermediate=None
        if mode=='mirror-parts':
            emit(p,'aynalı');followup(p,'letter');intermediate=state(p);capture(p,PHASE+'-'+mode+'-second-fragment.png')
            assert 'baş aşağı · aynalı' in intermediate['heard'] and 'baş aşağı ve aynalı' in intermediate['notice']
        if mode=='followup':assert p.evaluate('probe.audios.at(-1).paused===false')
        second_text='Aşağı dönük' if mode=='e-down' else 'sağa yatmış ve aynalı' if mode=='letter-first' else 'P değil F' if mode=='correction' else "Pırasanın P'si"
        # Capture stale callback identity before accepting the complete answer.
        p.evaluate('()=>{probe.previous=probe.current;probe.previousCallback=probe.current.onresult}')
        emit(p,second_text);p.wait_for_timeout(200);second=state(p);capture(p,PHASE+'-'+mode+'-second.png')
        if PHASE=='after':
            if mode=='low-confidence':
                assert target(p)==old and len(second['diagnostics'])==0
                followup(p,'orientation');assert 'Yalnız yön' in state(p)['notice']
                emit(p,'sağa yatmış ve aynalı');p.wait_for_timeout(200);second=state(p)
            changed(p,old);assert len(second['diagnostics'])==1 and second['diagnostics'][0]['combinedCorrect'] is (mode!='correction'),second
            d=second['diagnostics'][0];assert d['parsed']['transform']['rotation']==(180 if mode in ['e-down','mirror-parts'] else 90) and d['parsed']['transform']['mirrored'] is (mode!='e-down')
            assert d['fragmentCount']==(3 if mode in ['mirror-parts','low-confidence'] else 2)
            assert second['heard']=='' and not second['notice']
            new_id=target(p)
            p.evaluate("probe.previousCallback({resultIndex:99,results:Object.assign(Array(99).fill(null).concat([Object.assign([{transcript:'düz E',confidence:1}],{isFinal:true})]),{})})")
            p.wait_for_timeout(100);assert target(p)==new_id and len(state(p)['diagnostics'])==1 and state(p)['heard']==''
            # New target must not inherit the former rotation; its bare letter
            # is incomplete, not a second immediately scored response.
            emit(p,'P');p.wait_for_timeout(100);assert target(p)==new_id and len(state(p)['diagnostics'])==1
            assert 'Yalnız yön' in state(p)['notice']
        proof.append({'mode':mode,'first':first,'second':second,'intermediate':intermediate,'advanced':second['id']!=old})
        stop(p)
    c.close()
(OUT/(PHASE+'-proof.json')).write_text(json.dumps({'build':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'controlled':True,'physicalMicrophoneAcceptance':False,'proof':proof},indent=2),'utf8')
print(json.dumps([{'mode':x['mode'],'advanced':x['advanced'],'notice':x['second']['notice']} for x in proof],ensure_ascii=False))
