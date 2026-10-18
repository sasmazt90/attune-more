"""Focused production ASR callback -> score -> size -> DOM proof.
Controlled camera/ASR/audio; this is not physical microphone acceptance.
The deterministic target picker changes selection only, never score or size.
"""
import ast, base64, json, math, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path.cwd()
OUT = ROOT / (sys.argv[2] if len(sys.argv) > 2 else 'audit-results/vision-half-size-20261009')
OUT.mkdir(parents=True, exist_ok=True)
PHASE = sys.argv[1] if len(sys.argv) > 1 else 'after'
tree = ast.parse((ROOT / 'tests/e2e/vision_feedback.py').read_text('utf8'))
BOOT = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'BOOT' for t in n.targets))
BOOT += """
sessionStorage.setItem('attune_vision_size_diagnostics','1');
probe.sizeDiagnostics=[];
window.addEventListener('attune-vision-size-diagnostic',e=>probe.sizeDiagnostics.push(e.detail));
let selection=0;
crypto.getRandomValues=array=>{const first=selection===0,index=selection++%2===0?(first?27:26):16;array[0]=Math.floor((index+.25)/(first?40:39)*4294967296);return array;};
"""
PATHS = {'M20 90V10H55C90 10 90 50 55 50H20': 'P', 'M80 10H20V90M20 50H70': 'F'}

def active(page):
    try:
        page.wait_for_function("document.querySelector('[data-vision-stage]')?.dataset.visionStage==='listening'&&probe.current&&!probe.current.aborted&&document.querySelector('[data-letter-optotype]')", timeout=15000)
    except Exception:
        capture(page, 'failure.png')
        (OUT/'failure-state.json').write_text(json.dumps(page.evaluate("({stage:document.querySelector('[data-vision-stage]')?.dataset.visionStage,body:document.body.innerText,calls:probe.calls,diagnostics:probe.sizeDiagnostics,recognition:probe.current?.aborted,evidence:document.querySelector('canvas')?.dataset})"),indent=2), 'utf8')
        raise

def target(page):
    return page.locator('[data-letter-optotype]').evaluate("""e=>{
      const styles=n=>{const s=getComputedStyle(n);return {tag:n.tagName,width:s.width,height:s.height,transform:s.transform,zoom:s.zoom,flexGrow:s.flexGrow,alignSelf:s.alignSelf}};
      const ancestors=[];for(let n=e;n;n=n.parentElement)ancestors.push(styles(n));
      return {id:document.querySelector('[data-vision-trial]').dataset.visionTrial,path:e.querySelector('path').getAttribute('d'),transform:e.querySelector('g').getAttribute('transform'),svg:e.getBoundingClientRect().toJSON(),pathBounds:e.querySelector('path').getBoundingClientRect().toJSON(),stroke:parseFloat(getComputedStyle(e.querySelector('path')).strokeWidth)*e.getBoundingClientRect().width/116,viewBox:e.getAttribute('viewBox'),ancestors,outerHTML:e.outerHTML};
    }""")

def frames(page):
    return page.evaluate("({camera:document.querySelector('[data-camera-preview]').getBoundingClientRect().toJSON(),letter:document.querySelector('[data-letter-area]').getBoundingClientRect().toJSON(),width:innerWidth,scrollWidth:document.documentElement.scrollWidth,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.body).zoom})")

def emit_parts(page, parts, expect_change=True):
    old = target(page)
    for i, phrase in enumerate(parts):
        page.evaluate('text=>probe.current.emit(text)', phrase)
        if i < len(parts)-1:
            page.wait_for_timeout(80)
            assert target(page)['id'] == old['id'], 'Partial answer must not advance'
    if expect_change:
        page.wait_for_function('id=>document.querySelector("[data-vision-trial]")?.dataset.visionTrial!==id', arg=old['id'], timeout=5000)
        active(page)
    else:
        page.wait_for_timeout(80)
        assert target(page)['id'] == old['id']
    return old, target(page)

def literal(page, correct=True):
    t = target(page)
    letter = PATHS[t['path']]
    rotation = int(re.search(r'rotate\((\d+)\)', t['transform'])[1])
    direction = {0:'düz',90:'sağa yatmış',180:'baş aşağı',270:'sola yatmış'}[rotation]
    if 'scale(-1' in t['transform']: direction += ' ve aynalı'
    if not correct: letter = 'F' if letter == 'P' else 'P'
    return emit_parts(page, [letter+' '+direction])

def capture(page, name):
    cdp = page.context.new_cdp_session(page)
    shot = cdp.send('Page.captureScreenshot', {'format':'png','fromSurface':True,'captureBeyondViewport':False})
    cdp.detach()
    (OUT/name).write_bytes(base64.b64decode(shot['data']))

proof = []
errors = []
with sync_playwright() as pw:
    for name, zoom in [('desktop',1)] if PHASE == 'before' else [('desktop',1),('native200',2)]:
        profile = OUT/(PHASE+'-'+name+'-profile')
        prefs = profile/'Default'
        prefs.mkdir(parents=True, exist_ok=True)
        (prefs/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(zoom)/math.log(1.2)}}}), 'utf8')
        context = pw.chromium.launch_persistent_context(str(profile), channel='chrome', headless=False, no_viewport=True, args=['--window-size=1920,1080','--window-position=0,0'])
        context.add_init_script(BOOT)
        page = context.pages[0]
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto('http://127.0.0.1:3000/vision')
        page.get_by_role('button', name='Başlat', exact=True).click()
        active(page)
        first = target(page)
        layout = frames(page)
        capture(page, PHASE+'-'+name+'-initial.png')
        assert abs(layout['camera']['width']-layout['letter']['width']) < .1
        assert abs(layout['camera']['height']-layout['letter']['height']) < .1
        assert layout['scrollWidth'] <= layout['width']+1
        # Genuine final-callback phrases, including direction-first / letter-first fragments.
        variants = [
            ['P sağa yatmış ve aynalı'],
            ['düz fasulye'],
            ['sağa yatmış ve aynalı', "Pırasanın P'si"],
            ["Fasulyenin F'si", 'normal'],
            ['aynalı ve sağa dönük pırasa'],
            ['efe düz'],
        ]
        renders = [first]
        for i, parts in enumerate(variants):
            if PHASE == 'after' and i == 1:
                emit_parts(page, ['Harf alanına bakın. Harfi ve yönünü istediğiniz sırada söyleyin.'], False)
                page.evaluate("probe.fault='uncertain'")
                page.wait_for_timeout(120)
                page.evaluate('probe.fault=null')
                page.wait_for_timeout(180)
                assert target(page)['id'] == renders[-1]['id']
                assert len(page.evaluate('probe.sizeDiagnostics')) == 1
            old, new = emit_parts(page, parts)
            renders.append(new)
            if PHASE == 'after':
                assert abs(new['svg']['width']-120*.5**((i+1)//2)) < .01, (i,new)
                diags = page.evaluate('probe.sizeDiagnostics')
                assert len(diags) == i+1 and diags[-1]['combinedCorrect'] is True, diags
        same = [renders[i] for i in [0,2,4,6]]
        assert all(t['path'] == first['path'] and t['transform'] == first['transform'] for t in same)
        for i, t in enumerate(same):
            factor = (.7 if PHASE == 'before' else .5)**i
            for dimension in ['width','height']:
                assert abs(t['pathBounds'][dimension]/first['pathBounds'][dimension]-factor) < .001
            assert abs(t['stroke']/first['stroke']-factor) < .001
            assert t['viewBox'] == '-8 -8 116 116'
            assert all(s['transform']=='none' and s['zoom']=='1' for s in t['ancestors']), t['ancestors']
        capture(page, PHASE+'-'+name+'-six-correct.png')
        if PHASE == 'after':
            later = frames(page)
            assert all(later[f][d] == layout[f][d] for f in ['camera','letter'] for d in ['width','height'])
            # At the minimum, even another full correct pair must keep 15.
            for _ in range(2):
                _, new = literal(page)
                assert new['svg']['width'] == 15
            # A single wrong orientation must advance but not enlarge; two valid
            # wrong answers (including not-visible) enlarge one step, not reset.
            t = target(page)
            wrong_direction = 'P düz' if PATHS[t['path']] == 'P' else 'F baş aşağı'
            _, one = emit_parts(page, [wrong_direction])
            _, two = emit_parts(page, ['göremiyorum'])
            assert one['svg']['width'] == 15 and two['svg']['width'] == 30
            diags = page.evaluate('probe.sizeDiagnostics')
            assert diags[-2]['letterCorrect'] is True and diags[-2]['orientationCorrect'] is False
            assert diags[-1]['combinedCorrect'] is False
            # Repeat/pause carry the first correct in a pair; a real eye switch resets.
            _, new = literal(page)
            assert new['svg']['width'] == 30
            emit_parts(page, ['tekrar'], False)
            page.get_by_role('button', name='Duraklat', exact=True).click()
            page.get_by_role('button', name='Devam et', exact=True).click()
            active(page)
            assert target(page)['svg']['width'] == 30
            _, new = literal(page)
            assert new['svg']['width'] == 120
            diagnostics = page.evaluate('probe.sizeDiagnostics')
            assert len(diagnostics) == 12
            assert diagnostics[-1]['before']['correctStreak'] == 1
            assert diagnostics[-1]['after']['sizePx'] == 120
        else: diagnostics = []
        # One native browser screenshot of unchanged SVG snapshots from actual
        # production renders; no image editing or individual image enlargement.
        if PHASE == 'after' and name == 'desktop':
            comparison = context.new_page()
            comparison.set_content('<html><body style="margin:0;background:#070d15;color:white;font:16px Arial"><h2 style="margin:24px">Aynı P · aynı yön ve aynalama · aynı tarayıcı zoom’u</h2><p style="margin:24px">Kontrollü ASR callback → puanlama → production SVG. Fiziksel mikrofon kabulü değildir.</p><div style="display:flex;gap:24px;margin:24px">'+''.join('<section><h3>'+label+'</h3><div data-proof-frame style="width:480px;height:288px;background:black;display:flex;align-items:center;justify-content:center;border:1px solid #586274">'+t['outerHTML']+'</div></section>' for label,t in [('İlk harf · 120 × 120 CSS px',same[0]),('İki tam doğru sonrası · 60 × 60 CSS px',same[1])])+'</div></body></html>')
            capture(comparison, 'same-shape-side-by-side.png')
            comparison.close()
        page.get_by_role('button', name='Bitir', exact=True).scroll_into_view_if_needed()
        page.get_by_role('button', name='Bitir', exact=True).click()
        page.get_by_role('button', name='Tamam', exact=True).click()
        assert page.evaluate("!localStorage.getItem('togg_health_vision_history')")
        equivalent = None
        if PHASE == 'after':
            # E has exact horizontal symmetry. Mirrored upright E and an
            # unmirrored upside-down E are visually identical, so this full
            # answer must be correct through the production callback too.
            page.evaluate("""()=>{let n=0;probe.sizeDiagnostics=[];crypto.getRandomValues=a=>{const first=n++===0,index=first?13:12;a[0]=Math.floor((index+.25)/(first?40:39)*4294967296);return a;}}""")
            page.get_by_role('button', name='Başlat', exact=True).click()
            active(page)
            eq_start = target(page)
            assert eq_start['path'] == 'M80 10H20V90H80M20 50H70'
            assert 'rotate(0) scale(-1 1)' in eq_start['transform']
            emit_parts(page, ['baş aşağı elma'])
            emit_parts(page, ['E düz'])
            equivalent = page.evaluate('probe.sizeDiagnostics')
            assert len(equivalent) == 2 and all(d['combinedCorrect'] is True for d in equivalent)
            assert target(page)['svg']['width'] == 60
            page.get_by_role('button', name='Bitir', exact=True).scroll_into_view_if_needed()
            page.get_by_role('button', name='Bitir', exact=True).click()
            page.get_by_role('button', name='Tamam', exact=True).click()
            assert page.evaluate("!localStorage.getItem('togg_health_vision_history')")
        proof.append({'surface':name,'frames':layout,'renders':renders,'sameShape':same,'diagnostics':diagnostics,'equivalentTransform':equivalent})
        context.close()
assert not errors, errors
(OUT/(PHASE+'-proof.json')).write_text(json.dumps({'buildId':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'controlled':True,'physicalMicrophoneAcceptance':False,'proof':proof}, indent=2), 'utf8')
print(json.dumps([{'surface':p['surface'],'widths':[t['svg']['width'] for t in p['renders']],'heights':[t['svg']['height'] for t in p['renders']],'diagnostics':len(p['diagnostics'])} for p in proof]))
