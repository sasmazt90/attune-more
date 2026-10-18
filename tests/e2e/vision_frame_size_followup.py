"""Two focused production UI checks; controlled ASR/camera/audio, not physical acceptance.
Random target selection is deterministic; replies still use the real page/session/render chain.
Normal user history is never touched. Run before/after the production change.
"""
import ast, base64, json, math, sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path.cwd();OUT=ROOT/'audit-results/vision-frame-size-20261009';OUT.mkdir(parents=True,exist_ok=True)
PHASE=sys.argv[1] if len(sys.argv)>1 else 'after'
tree=ast.parse((ROOT/'tests/e2e/vision_feedback.py').read_text('utf8'))
BOOT=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BOOT' for t in n.targets))
BOOT+="""
let selection=0;
crypto.getRandomValues=array=>{const first=selection===0,index=selection++%2===0?(first?27:26):16;array[0]=Math.floor((index+.25)/(first?40:39)*4294967296);return array;};
"""
PATHS={'M20 90V10H55C90 10 90 50 55 50H20':'P','M80 10H20V90M20 50H70':'F'}
def capture(page,name,full=False):
    if full: page.screenshot(path=str(OUT/name),full_page=True)
    else:
        session=page.context.new_cdp_session(page)
        result=session.send('Page.captureScreenshot',{'format':'png','fromSurface':True,'captureBeyondViewport':False});session.detach()
        (OUT/name).write_bytes(base64.b64decode(result['data']))
def active(page):
    page.wait_for_function("document.querySelector('[data-vision-stage]')?.dataset.visionStage==='listening'&&probe.current&&!probe.current.aborted&&document.querySelector('[data-letter-optotype]')",timeout=15000)
def target(page):
    return page.locator('[data-letter-optotype]').evaluate("e=>({id:document.querySelector('[data-vision-trial]').dataset.visionTrial,path:e.querySelector('path').getAttribute('d'),transform:e.querySelector('g').getAttribute('transform'),svg:e.getBoundingClientRect().toJSON(),pathBounds:e.querySelector('path').getBoundingClientRect().toJSON(),stroke:Number.parseFloat(getComputedStyle(e.querySelector('path')).strokeWidth)*e.getBoundingClientRect().width/116})")
def frames(page):
    return page.evaluate("({camera:document.querySelector('[data-camera-preview]').getBoundingClientRect().toJSON(),letter:document.querySelector('[data-letter-area]').getBoundingClientRect().toJSON(),video:document.querySelector('[data-vision-camera]').getBoundingClientRect().toJSON(),crop:JSON.parse(document.querySelector('[data-camera-preview]').dataset.previewCrop),width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.body).zoom})")
def respond(page,correct=True):
    import re
    old=target(page);letter=PATHS[old['path']];rotation=int(re.search(r'rotate\((\d+)\)',old['transform'])[1])
    direction={0:'düz',90:'sağa yatmış',180:'baş aşağı',270:'sola yatmış'}[rotation]+(' ve aynalı' if 'scale(-1' in old['transform'] else '')
    page.evaluate('(text)=>probe.current.emit(text)',(letter if correct else ('F' if letter=='P' else 'P'))+' '+direction)
    try:page.wait_for_function('(id)=>document.querySelector("[data-vision-trial]")?.dataset.visionTrial!==id',arg=old['id'])
    except Exception:
        capture(page,'response-timeout.png',True)
        (OUT/'response-timeout.json').write_text(json.dumps(dict(old=old,answer=(letter if correct else ('F' if letter=='P' else 'P'))+' '+direction,diagnostic=page.evaluate('({stage:document.querySelector("[data-vision-stage]")?.dataset,body:document.body.innerText,evidence:document.querySelector("canvas")?.dataset,recognitions:probe.recognitions.map(r=>({aborted:r.aborted,results:r.results})),calls:probe.calls})')),indent=2),'utf8')
        raise
    if page.locator('[data-vision-stage]').get_attribute('data-vision-stage')=='result':return old,None
    active(page)
    return old,target(page)

proof=[];errors=[]
with sync_playwright() as pw:
    surfaces=[('desktop',1,1920)] if PHASE=='before' else [('desktop',1,1920),('narrow',1,750),('native200',2,1920)]
    for name,zoom,width in surfaces:
        profile=OUT/(PHASE+'-'+name+'-profile');prefs=profile/'Default';prefs.mkdir(parents=True,exist_ok=True)
        (prefs/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(zoom)/math.log(1.2)}}}),'utf8')
        context=pw.chromium.launch_persistent_context(str(profile),channel='chrome',headless=False,no_viewport=True,args=[f'--window-size={width},1080','--window-position=0,0'])
        context.add_init_script(BOOT);page=context.pages[0];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:3000/vision');page.get_by_role('button',name='Başlat',exact=True).click();active(page)
        if PHASE=='after':page.wait_for_function("document.querySelector('[data-vision-camera]').getBoundingClientRect().width>=document.querySelector('[data-camera-preview]').getBoundingClientRect().width",timeout=5000)
        initial=target(page);layout=frames(page);capture(page,f'{PHASE}-{name}-start.png');capture(page,f'{PHASE}-{name}-full.png',True)
        page.locator('[data-letter-area]').screenshot(path=str(OUT/f'{PHASE}-{name}-letter-initial.png'))
        if PHASE=='after':
            assert abs(layout['camera']['width']-layout['letter']['width'])<.1 and abs(layout['camera']['height']-layout['letter']['height'])<.1,layout
            if name=='desktop': assert abs(layout['camera']['y']-layout['letter']['y'])<.1,layout
            assert layout['scrollWidth']<=layout['width']+1,layout
            assert abs(layout['video']['width']/layout['video']['height']-4/3)<.001,layout
            assert layout['video']['width']>=layout['camera']['width'] and layout['video']['height']>=layout['camera']['height'],layout
            page.evaluate('probe.mouth=true');page.wait_for_timeout(180);changed=frames(page)
            assert changed['camera']['width']==layout['camera']['width'] and changed['camera']['height']==layout['camera']['height']
        renders=[initial];answers=[]
        for index in range(6):
            previous,current=respond(page);answers.append(previous);renders.append(current)
            if PHASE=='after': assert abs(current['svg']['width']-120*.5**((index+1)//2))<.02,(index,current)
        smaller=target(page);assert smaller['path']==initial['path'] and smaller['transform']==initial['transform']
        capture(page,f'{PHASE}-{name}-six-correct.png');capture(page,f'{PHASE}-{name}-six-correct-full.png',True)
        page.locator('[data-letter-area]').screenshot(path=str(OUT/f'{PHASE}-{name}-letter-smaller.png'))
        if PHASE=='after':
            resized=frames(page)
            assert all(resized[frame][dimension]==layout[frame][dimension] for frame in ['camera','letter'] for dimension in ['width','height'])
            assert abs(smaller['pathBounds']['width']/initial['pathBounds']['width']-.5**3)<.001
            assert abs(smaller['pathBounds']['height']/initial['pathBounds']['height']-.5**3)<.001
            assert abs(smaller['stroke']/initial['stroke']-.5**3)<.001
            page.get_by_role('button',name='Duraklat',exact=True).click();page.get_by_role('button',name='Devam et',exact=True).click();active(page);assert abs(target(page)['svg']['width']-smaller['svg']['width'])<.01
            page.evaluate("probe.current.emit('tekrar')");page.wait_for_timeout(100);assert target(page)['svg']['width']==smaller['svg']['width']
            # One wrong leaves size; two wrong undo precisely one .50 step.
            old,one=respond(page,False);answers.append(old);assert abs(one['svg']['width']-old['svg']['width'])<.01
            old,two=respond(page,False);answers.append(old);assert abs(two['svg']['width']-old['svg']['width']/.5)<.02
            wrongSizes=[one['svg']['width'],two['svg']['width']]
            # Opposite answers reset the streak, not the size.
            old,c1=respond(page);answers.append(old);old,w1=respond(page,False);answers.append(old);old,c2=respond(page);answers.append(old)
            assert all(abs(t['svg']['width']-two['svg']['width'])<.02 for t in [c1,w1,c2])
            # Last right-eye response then changes eye, returning to the start.
            old,_=respond(page);answers.append(old);assert abs(target(page)['svg']['width']-120)<.01
            if name=='desktop':
                # Complete this isolated session only to compare stored pre-response
                # geometry with the actual DOM. No normal profile is accessed.
                for _ in range(12):old,_=respond(page);answers.append(old)
                expect(page.get_by_role('dialog',name='Görme bildirimi')).to_be_visible();page.get_by_role('button',name='Tamam',exact=True).click()
                record=page.evaluate("JSON.parse(localStorage.getItem('togg_health_vision_history'))[0]")
                trials=[t for t in record['trials'] if t['valid']];assert len(trials)==len(answers)==24
                assert record['methodVersion']=='mirror-x-then-rotate-two-up-two-down-step50-min15-v4'
                for t,render in zip(trials,answers):
                    assert abs(t['renderedGeometry']['viewportWidthCssPx']-render['svg']['width'])<.01
                    assert abs(t['sizePx']-render['svg']['width'])<.02
                (OUT/'after-record.json').write_text(json.dumps(record,indent=2),'utf8')
                page.get_by_role('button',name='Yeni görev',exact=True).click()
            else:
                page.get_by_role('button',name='Bitir',exact=True).scroll_into_view_if_needed();page.get_by_role('button',name='Bitir',exact=True).click();page.get_by_role('button',name='Tamam',exact=True).click()
                assert page.evaluate("!localStorage.getItem('togg_health_vision_history')")
            # Reopen same page to verify all six rows/buttons are reachable without clipping.
            page.get_by_role('button',name='Başlat',exact=True).click();active(page)
            for locator in [page.locator('[data-camera-preparation]'),page.get_by_role('button',name='Bitir',exact=True)]:
                locator.scroll_into_view_if_needed();expect(locator).to_be_visible()
            page.locator('[data-camera-preparation]').scroll_into_view_if_needed();capture(page,f'{PHASE}-{name}-controls.png')
            page.get_by_role('button',name='Bitir',exact=True).scroll_into_view_if_needed();capture(page,f'{PHASE}-{name}-buttons.png')
        else: wrongSizes=[]
        proof.append({'surface':name,'frames':layout,'sixCorrectRenders':renders,'sameShape':{'start':initial,'afterSix':smaller},'wrongSizes':wrongSizes})
        context.close()
assert not errors,errors
(OUT/(PHASE+'-proof.json')).write_text(json.dumps({'build':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'controlled':True,'physicalAcceptance':False,'proof':proof},indent=2),'utf8')
print(json.dumps([{'surface':p['surface'],'camera':[p['frames']['camera']['width'],p['frames']['camera']['height']],'letter':[p['frames']['letter']['width'],p['frames']['letter']['height']],'sixCorrectSizes':[r['svg']['width'] for r in p['sixCorrectRenders']],'wrongSizes':p['wrongSizes']} for p in proof]))
