"""Audit production Vision DOM in each locale using controlled media inputs.

Native approved audio is played at 4x for this text audit. Camera/model/ASR are
fixtures, not physical acceptance. No production assessment logic is replaced.
"""
import importlib.util
import json
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/vision-localization-evidence'
OUT.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location('conversation', Path(__file__).with_name('vision_conversation.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.OUT = OUT
LANG = os.getenv('VISION_LOCALIZATION_LANGUAGE', 'tr')
assert LANG in ['tr', 'en', 'de']
LABELS = {
    'tr': ('TEST KAMERASI', 'Fiziksel doğrulama değildir'),
    'en': ('SIMULATED CAMERA', 'Not physical validation'),
    'de': ('SIMULIERTE KAMERA', 'Keine physische Prüfung'),
}
BOOT = M.BOOT.replace('CONTROLLED CAMERA', LABELS[LANG][0]).replace('Not physical acceptance', LABELS[LANG][1])
BOOT = BOOT.replace("this.onmessage?.({data:{id:m.id,evidence:", """
 if(fault==='both-closed'){c.right=closed;c.left=closed;}
 if(fault==='stale')c.observedAt-=1000;
 if(['pose','framing','light','bright','blur','approach','distance-unknown'].includes(fault)){c.blocker=fault;c.positionValid=false;}
 if(['light','bright','blur'].includes(fault))c.qualityValid=false;
 this.onmessage?.({data:{id:m.id,evidence:""")
BOOT = BOOT.replace("quality:{status:'GOOD',avgLuminance:120,blurScore:20}", "quality:{status:fault==='light'?'TOO_DARK':fault==='bright'?'TOO_BRIGHT':'GOOD',avgLuminance:120,blurScore:fault==='blur'?0:20}")
EXTRA = """
probe.holdModel=true;
const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(m){
 if(m.type==='initialize'&&probe.failModel){setTimeout(()=>this.onmessage?.({data:{id:m.id,error:'MODEL_FIXTURE_ERROR'}}),0);return;}
 if(m.type==='initialize'&&probe.holdModel){probe.releaseModel=()=>{probe.holdModel=false;post.call(this,m);};return;}
 return post.call(this,m);
};
const camera=navigator.mediaDevices.getUserMedia;
navigator.mediaDevices.getUserMedia=async(...args)=>{if(probe.cameraError)throw new DOMException('simulated camera error',probe.cameraError);return camera(...args);};
const NativeTestAudio=window.Audio;window.Audio=function(...args){const a=new NativeTestAudio(...args);const play=a.play.bind(a);a.play=()=>probe.audioError?Promise.reject(new Error('simulated playback failure')):play();a.addEventListener('playing',()=>a.playbackRate=4);return a;};window.Audio.prototype=NativeTestAudio.prototype;
"""
FOREIGN = {
    'tr': r'\b(?:Waiting|Detected|Right eye|Left eye|We are testing|Overall average score|Letter size|Header|Erkannt|Ausrichtung|Augengesundheit|Buchstabengröße|Rechtes Auge|Linkes Auge)\b',
    'en': r'(?-i:[çğıİşŞ])|\b(?:bekleniyor|göz|Algılanan|Yalnız|aynalı|düz|Toplam|Harf|kaydedilmedi|Erkannt|Ausrichtung|Augengesundheit|Buchstabengröße|Zuhören)\b',
    'de': r'(?-i:[çğıİşŞ])|\b(?:bekleniyor|göz|Algılanan|Yalnız|aynalı|düz|Toplam|Harf|kaydedilmedi|Waiting|Detected|Right eye|Left eye|We are testing|Overall average score|Letter size|Resume)\b',
}
records = []


def audit(page, stage, screenshot=False, full=False):
    text = page.locator('body').inner_text()
    attributes = page.locator('[aria-label],[aria-description],[aria-roledescription],img[alt],[title]').evaluate_all("els=>els.filter(e=>e.getClientRects().length).flatMap(e=>['aria-label','aria-description','aria-roledescription','alt','title'].map(a=>e.getAttribute(a)).filter(Boolean))")
    match = re.search(FOREIGN[LANG], text + '\n' + '\n'.join(attributes), re.IGNORECASE)
    assert not match, (LANG, stage, match.group() if match else '', text)
    assert page.locator('html').get_attribute('lang') == LANG
    assert page.evaluate('document.fonts.status') == 'loaded'
    entry = {'stage': stage, 'status': 'PASS', 'visibleText': text, 'accessibleText': attributes}
    if screenshot:
        name = f'{LANG}-{stage}.png'
        page.screenshot(path=str(OUT / name), full_page=full)
        entry['screenshot'] = name
    records.append(entry)
    print('PASS', LANG, stage, flush=True)


def context(browser, mobile=False, extra=''):
    c = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 844 if mobile else 1000})
    c.add_init_script(M.SEED + BOOT + M.OBSERVE + EXTRA + f"localStorage.setItem('attune.language.v1','{LANG}');" + extra)
    p = c.new_page()
    p.goto(M.BASE + '/vision')
    p.get_by_role('button', name=M.label('Başlat', LANG), exact=True).wait_for()
    return c, p


def start(page, preparation=False):
    if preparation:
        audit(page, 'preparation', True)
    page.get_by_role('button', name=M.label('Başlat', LANG), exact=True).click()
    page.wait_for_function('()=>!!probe.releaseModel')
    if preparation:
        audit(page, 'camera-preparation', True)
    page.evaluate('probe.releaseModel()')


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=os.getenv('CHROME_PATH') or None, channel=None if os.getenv('CHROME_PATH') else 'chrome', headless=True, args=['--autoplay-policy=no-user-gesture-required', '--no-sandbox'])
    page = None
    try:
        c, page = context(browser)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        start(page, True)
        page.wait_for_function("()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='eye-instruction'")
        audit(page, 'instruction', True)
        M.ready(page)
        audit(page, 'listening', True)
        v = M.target(page)
        M.expect_partial(page, M.word(v, LANG), 'orientation', [])
        audit(page, 'clarification', True)
        row = M.emit(page, M.orientation(v, LANG))
        audit(page, 'processing', True)
        page.wait_for_function('n=>probe.events.filter(e=>e.combinedCorrect!==undefined).length===n', arg=row['scoreCountBefore'] + 1)
        M.ready(page)
        v = M.target(page)
        M.expect_partial(page, M.orientation(v, LANG), 'letter', [])
        audit(page, 'letter-clarification', True)
        M.finish(page, M.word(v, LANG), [])
        M.ready(page)
        v = M.target(page)
        M.expect_partial(page, {'tr': 'E ters', 'en': 'E reverse', 'de': 'E umgekehrt'}[LANG], 'reverse', [])
        audit(page, 'reverse-clarification', True)
        M.finish(page, M.word(v, LANG) + ' ' + M.orientation(v, LANG), [])
        M.ready(page)
        v = M.target(page)
        M.expect_partial(page, 'blablabla', 'repeat', [])
        audit(page, 'repeat-clarification', True)
        M.finish(page, M.word(v, LANG) + ' ' + M.orientation(v, LANG), [])
        M.ready(page)
        page.evaluate("probe.waitAfter=performance.now();probe.current.onerror({error:'no-speech'})")
        M.next_prompt(page, 'repeat')
        audit(page, 'silence', True)
        M.ready(page)
        # Three native-style errors expose bounded retries and the existing error UI.
        for i in range(3):
            page.evaluate("probe.old=probe.current;probe.current.onerror({error:'network'})")
            if i < 2:
                if i == 0:
                    audit(page, 'reconnecting', True)
                M.ready(page)
        page.wait_for_function("()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='error'")
        audit(page, 'error', True)
        page.get_by_role('button', name=M.label('Tekrar dene', LANG), exact=True).click()
        M.ready(page)
        audit(page, 'retry')
        page.get_by_role('button', name=M.label('Duraklat', LANG), exact=True).click()
        audit(page, 'paused', True)
        page.get_by_role('button', name=M.label('Devam et', LANG), exact=True).click()
        M.ready(page)
        page.evaluate("window.attuneOutputMuted=true;window.dispatchEvent(new Event('attune-guidance-muted'))")
        audit(page, 'muted', True)
        page.evaluate('window.attuneOutputMuted=false')
        page.get_by_role('button', name=M.label('Devam et', LANG), exact=True).click()
        M.ready(page)
        for fault in ['hand', 'object']:
            page.evaluate('fault=>probe.fault=fault', fault)
            page.wait_for_timeout(500)
            audit(page, fault + '-coverage', True)
        for fault in ['both-open', 'both-closed', 'test-covered', 'uncertain', 'no-face', 'pose', 'framing', 'light', 'bright', 'blur', 'near', 'approach', 'distance-unknown', 'stale']:
            page.evaluate('fault=>probe.fault=fault', fault)
            page.wait_for_function("()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='condition-paused'", timeout=10000)
            page.wait_for_timeout(350)
            audit(page, 'condition-' + fault, fault in ['both-open', 'uncertain', 'light', 'stale'])
            page.evaluate('probe.fault=null')
            M.ready(page)
        while M.count(page) < 24:
            before = M.count(page)
            M.ready(page)
            v = M.target(page)
            M.finish(page, M.word(v, LANG) + ' ' + M.orientation(v, LANG), [])
            assert M.count(page) == before + 1
            if M.count(page) == 12:
                page.wait_for_function("()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='eye-instruction'")
                audit(page, 'left-eye-instruction', True)
        page.get_by_role('dialog').wait_for()
        audit(page, 'completion', True)
        page.get_by_role('button', name=M.label('Tamam', LANG), exact=True).click()
        page.locator('[data-letter-result] details').evaluate_all('els=>els.forEach(e=>e.open=true)')
        audit(page, 'results', True, True)
        assert not errors, errors
        page.reload()
        page.get_by_role('button', name=M.label('Sonucu Aç', LANG), exact=True).click()
        audit(page, 'history', True)
        page.get_by_role('button', name=M.label('Sonuç penceresini kapat', LANG), exact=True).click()
        # Corrupt only this isolated browser context's fixture history.
        page.evaluate("localStorage.setItem('togg_health_vision_history','invalid-json');window.dispatchEvent(new Event('attune-records'))")
        page.get_by_text(M.label('Göz Sağlığı: kayıtlar okunamadı; veriler korunuyor.', LANG), exact=True).wait_for()
        audit(page, 'history-error', True)
        c.close()
        # Independent fixtures expose start/capture/model/output permission errors.
        for name, setup in [
            ('permission-error', "localStorage.setItem('attune_privacy_microphone_allowed','false');"),
            ('camera-denied', "probe.cameraError='NotAllowedError';"),
            ('camera-busy', "probe.cameraError='NotReadableError';"),
            ('model-error', 'probe.failModel=true;'),
            ('playback-error', 'probe.audioError=true;probe.holdModel=false;'),
        ]:
            c, page = context(browser, extra=setup)
            page.get_by_role('button', name=M.label('Başlat', LANG), exact=True).click()
            page.locator('[data-vision-stage] [role="alert"]').wait_for(timeout=15000)
            audit(page, name, True)
            c.close()
        c, page = context(browser, mobile=True)
        start(page)
        M.ready(page)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        audit(page, 'mobile', True, True)
        page.evaluate("localStorage.setItem('attune_privacy_microphone_allowed','false');window.dispatchEvent(new Event('attune-privacy'))")
        page.locator('[data-vision-stage] [role="alert"]').wait_for()
        audit(page, 'consent-withdrawal')
        c.close()
        (OUT / f'{LANG}-browser.json').write_text(json.dumps({'status': 'PASS', 'language': LANG, 'kind': 'production UI; simulated camera/model/ASR; native approved audio accelerated 4x for text audit', 'physicalTesting': False, 'stages': records}, ensure_ascii=False, indent=2) + '\n')
    except Exception:
        if page and not page.is_closed():
            page.screenshot(path=str(OUT / f'{LANG}-failure.png'), full_page=True)
        raise
    finally:
        browser.close()
