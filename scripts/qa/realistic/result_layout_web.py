#!/usr/bin/env python3
"""Measures Skin and Dental result screens with real model output at a chosen viewport.

Runs the real production flow on the WEB host with reference photos replayed as the browser
camera. Reports layout numbers and saves screenshots. Says nothing about analysis accuracy.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import time

from playwright.sync_api import sync_playwright

HOST = 'attune.sasmaz.digital'
QA = Path('/var/lib/attune/qa')
# Layout facts from the rendered page; the same questions the page audit asks.
MEASURE = """()=>{const h=document.querySelector('[data-cockpit-header]'),hr=h?h.getBoundingClientRect():{height:0},sticky=h?['sticky','fixed'].includes(getComputedStyle(h).position):false;
 const usable=innerHeight-(sticky?hr.height:0),total=document.documentElement.scrollHeight;
 const seen=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';};
 const sideways=el=>{for(let n=el.parentElement;n&&n!==document.body;n=n.parentElement){if(['auto','scroll','hidden'].includes(getComputedStyle(n).overflowX))return true;}return false;};
 const over=[...document.querySelectorAll('main *')].filter(el=>seen(el)&&el.getBoundingClientRect().right>innerWidth+1&&!sideways(el)).slice(0,5).map(el=>el.tagName+':'+(el.innerText||'').slice(0,30));
 const small=[...document.querySelectorAll('main button,main a[href],main summary,main select')].filter(seen).filter(el=>{const r=el.getBoundingClientRect();return Math.min(r.width,r.height)<43.5;});
 const tiny=[...document.querySelectorAll('main *')].filter(el=>seen(el)&&[...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&parseFloat(getComputedStyle(el).fontSize)<12).length;
 const heads=[...document.querySelectorAll('main h1,main h2,main h3')].filter(seen).slice(0,14).map(el=>({text:(el.innerText||'').slice(0,44),top:Math.round(el.getBoundingClientRect().top+scrollY)}));
 return {inner:[innerWidth,innerHeight],headerHeight:Math.round(hr.height),sticky,usable,total,viewportLengths:+(total/usable).toFixed(2),overflow:over,smallTargets:small.length,smallSamples:small.slice(0,4).map(el=>(el.innerText||el.getAttribute('aria-label')||'').slice(0,28)),tinyText:tiny,headings:heads};}"""
DIALOG = """()=>{const p=[...document.querySelectorAll('[role=dialog]')].pop();if(!p)return null;const r=p.getBoundingClientRect();
 const close=[...p.querySelectorAll('button')].find(b=>/close|ok|done|cancel/i.test((b.getAttribute('aria-label')||'')+' '+(b.innerText||'')));const c=close?close.getBoundingClientRect():null;
 return {title:p.getAttribute('aria-label'),w:Math.round(r.width),h:Math.round(r.height),sharePct:Math.round(100*r.width*r.height/(innerWidth*innerHeight)),fits:r.top>=-1&&r.bottom<=innerHeight+1,lengths:+(p.scrollHeight/Math.max(1,p.clientHeight)).toFixed(2),closeInView:c?c.top>=r.top-1&&c.bottom<=r.bottom+1:false};}"""


def open_context(playwright, camera, width, height, credentials):
    browser = playwright.chromium.launch(
        executable_path='/usr/bin/google-chrome', headless=True, ignore_default_args=['--mute-audio'],
        args=['--no-sandbox', '--disable-dev-shm-usage', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--use-file-for-fake-video-capture=' + str(camera),
              '--host-resolver-rules=MAP {} 127.0.0.1'.format(HOST), '--autoplay-policy=no-user-gesture-required'])
    context = browser.new_context(http_credentials=credentials, ignore_https_errors=True, viewport={'width': width, 'height': height}, permissions=['camera', 'microphone'])
    page = context.new_page()
    page.set_default_timeout(25000)
    return browser, context, page


def accept_consent(page):
    dialog = page.get_by_role('dialog')
    page.wait_for_timeout(700)
    if dialog.count():
        for box in dialog.get_by_role('checkbox').all():
            box.check()
        dialog.get_by_role('button', name='Allow and continue', exact=True).click()


def enter(page, module):
    page.goto('https://' + HOST, wait_until='networkidle')
    page.locator('#attune-language').select_option('en')
    page.wait_for_function("document.querySelector('[data-vehicle-status]')?.textContent==='PARK'")
    page.get_by_role('button', name='Health Center', exact=True).click()
    page.locator('#health-centre-links a[href="/' + module + '"]').click()
    accept_consent(page)
    page.locator('[data-health-start]').wait_for()


def walk_results(page, report, out, label, scope_selector):
    report['resultTop'] = page.evaluate(MEASURE)
    page.screenshot(path=str(out / (label + '-top.png')))
    total = report['resultTop']['total']
    step = max(200, report['resultTop']['usable'] - 40)
    index = 0
    for y in range(step, total, step):
        page.evaluate('y=>scrollTo(0,y)', y)
        page.wait_for_timeout(250)
        index += 1
        if index <= 8:
            page.screenshot(path=str(out / '{}-scroll{}.png'.format(label, index)))
    page.evaluate('()=>scrollTo(0,0)')
    report['dialogs'] = []
    triggers = page.locator(scope_selector + ' [aria-haspopup="dialog"]:visible')
    for i in range(min(triggers.count(), 10)):
        trigger = page.locator(scope_selector + ' [aria-haspopup="dialog"]:visible').nth(i)
        name = trigger.get_attribute('aria-label') or trigger.inner_text()
        before = page.evaluate('scrollY')
        trigger.click()
        page.wait_for_timeout(300)
        info = page.evaluate(DIALOG) or {}
        info['opener'] = (name or '')[:50]
        if i < 4:
            page.screenshot(path=str(out / '{}-dialog{}.png'.format(label, i)))
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        info['closed'] = not page.locator('[role=dialog]').count()
        info['scrollMoved'] = abs(page.evaluate('scrollY') - before) > 2
        report['dialogs'].append(info)
        if not info['closed']:
            break
    report['expandables'] = []
    items = page.locator(scope_selector + ' details:visible, ' + scope_selector + ' [aria-expanded]:visible')
    for i in range(min(items.count(), 12)):
        item = page.locator(scope_selector + ' details:visible, ' + scope_selector + ' [aria-expanded]:visible').nth(i)
        is_details = item.evaluate('e=>e.tagName==="DETAILS"')
        control = item.locator('summary').first if is_details else item
        text = (control.inner_text() or control.get_attribute('aria-label') or '')[:44]
        control.scroll_into_view_if_needed()
        before = item.evaluate('e=>({h:e.getBoundingClientRect().height,page:document.documentElement.scrollHeight,y:scrollY,top:e.getBoundingClientRect().top})')
        control.click()
        page.wait_for_timeout(300)
        after = item.evaluate('e=>({h:e.getBoundingClientRect().height,page:document.documentElement.scrollHeight,y:scrollY,top:e.getBoundingClientRect().top,bottom:e.getBoundingClientRect().bottom})')
        report['expandables'].append({'text': text, 'kind': 'details' if is_details else 'expanded', 'collapsed': round(before['h']), 'expanded': round(after['h']), 'addedPage': after['page'] - before['page'],
                                      'scrollMoved': round(after['y'] - before['y']), 'shift': round(after['top'] - before['top'])})
        if i < 3:
            page.screenshot(path=str(out / '{}-expanded{}.png'.format(label, i)))
        control.click()
        page.wait_for_timeout(120)


def run_dental(args, credentials, playwright, out):
    report = {'module': 'dental', 'input': 'Male-Dental reference photos', 'boundary': 'Layout with real model output. Not accuracy acceptance.'}
    frames = {k: (QA / (k + '.y4m')).read_bytes() for k in ('FRONT', 'RIGHT', 'LEFT', 'BITE')}
    camera = QA / 'dental-live.y4m'
    camera.write_bytes(frames['FRONT'])
    handle = camera.open('r+b')
    browser, context, page = open_context(playwright, camera, args.width, args.height, credentials)
    try:
        enter(page, 'dental')
        report['prepare'] = page.evaluate(MEASURE)
        page.get_by_role('button', name=re.compile('^start dental scan$', re.I)).click()
        pose = 'FRONT'
        deadline = time.time() + 300
        shot = False
        while time.time() < deadline and not page.locator('[data-dental-result]').count():
            capture = page.locator('[data-dental-capture]')
            if capture.count():
                if not shot:
                    page.wait_for_timeout(1000)
                    page.screenshot(path=str(out / 'dental-capture.png'))
                    report['capture'] = page.evaluate(MEASURE)
                    report['capture']['previewVisiblePct'] = capture.evaluate('e=>{const r=e.getBoundingClientRect();return Math.round(100*Math.max(0,Math.min(r.bottom,innerHeight)-Math.max(r.top,0))/r.height)}')
                    shot = True
                heading = capture.locator('h2').inner_text().lower()
                target = 'BITE' if 'bite' in heading else 'RIGHT' if 'right' in heading else 'LEFT' if 'left' in heading else 'FRONT'
                if target != pose:
                    handle.seek(0)
                    handle.write(frames[target])
                    handle.flush()
                    pose = target
            page.wait_for_timeout(700)
        page.locator('[data-dental-result]').wait_for(timeout=3000)
        page.wait_for_timeout(1500)
        report['measuredViews'] = page.locator('[data-dental-result]').get_attribute('data-dental-measured')
        walk_results(page, report, out, 'dental', '[data-dental-result]')
        record = page.evaluate("localStorage.getItem('attune_dental_history_v1')")
        (out / 'dental-history.json').write_text(record or '[]')
        report['status'] = 'MEASURED'
    except Exception as error:
        report['status'] = 'ERROR'
        report['failure'] = str(error)[:500]
        page.screenshot(path=str(out / 'dental-failure.png'))
        report['pageText'] = page.locator('main').inner_text()[:600]
    finally:
        handle.close()
        browser.close()
    return report


def run_skin(args, credentials, playwright, out):
    report = {'module': 'skin', 'input': args.skin_input, 'boundary': 'Layout and findings with real model output. No ground-truth labels, so not accuracy acceptance.'}
    source = Path(args.skin_input)
    frames = {pose: (source / (args.skin_prefix + name + '.y4m')).read_bytes() for pose, name in (('Front', 'Front'), ('Right', 'Right'), ('Left', 'Left'))}
    camera = QA / 'skin-live.y4m'
    camera.write_bytes(frames['Front'])
    handle = camera.open('r+b')
    browser, context, page = open_context(playwright, camera, args.width, args.height, credentials)
    responses = []

    def response(res):
        if res.url.split('?')[0].endswith('/api/local-health/skin'):
            responses.append(res)
    page.on('response', response)
    try:
        enter(page, 'skin')
        page.get_by_role('button', name=re.compile('^start analysis$', re.I)).click()
        pose = 'Front'
        deadline = time.time() + 480
        while time.time() < deadline and not page.locator('[data-skin-result]').count():
            match = re.search(r'Stage (\d)/3: (Front|Right|Left)', page.locator('main').inner_text())
            if match and match[2] != pose:
                handle.seek(0)
                handle.write(frames[match[2]])
                handle.flush()
                pose = match[2]
            if not report.get('capture') and match and page.locator('[data-camera-preview], video').count():
                page.wait_for_timeout(1500)
                page.screenshot(path=str(out / 'skin-capture.png'))
                report['capture'] = page.evaluate(MEASURE)
            page.wait_for_timeout(700)
        page.locator('[data-skin-result]').wait_for(timeout=3000)
        page.wait_for_timeout(2000)
        walk_results(page, report, out, 'skin', '[data-skin-result]')
        record = page.evaluate("localStorage.getItem('togg_health_skin_history')")
        (out / 'skin-history.json').write_text(record or '[]')
        report['apiStatuses'] = [r.status for r in responses]
        try:
            history = json.loads(record or '[]')
            findings = history[-1].get('general', {}).get('findings') if history else None
            rows = findings.get('findings') if isinstance(findings, dict) else findings
            report['findings'] = [{k: f.get(k) for k in ('id', 'region', 'status', 'count', 'areaPct', 'severity')} for f in (rows or [])]
        except Exception as error:
            report['findingsError'] = str(error)[:200]
        report['status'] = 'MEASURED'
    except Exception as error:
        report['status'] = 'ERROR'
        report['failure'] = str(error)[:500]
        page.screenshot(path=str(out / 'skin-failure.png'))
        report['pageText'] = page.locator('main').inner_text()[:800]
    finally:
        handle.close()
        browser.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--modules', default='dental,skin')
    parser.add_argument('--skin-input', default=str(QA / 'skin-native-input'))
    parser.add_argument('--skin-prefix', default='skin')
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=517)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    credentials = json.loads((QA / 'access.json').read_text())
    with sync_playwright() as playwright:
        access = {'username': credentials['username'], 'password': credentials['password']}
        report = {}
        if 'dental' in args.modules:
            report['dental'] = run_dental(args, access, playwright, args.out)
        if 'skin' in args.modules:
            report['skin'] = run_skin(args, access, playwright, args.out)
    (args.out / 'report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    sys.exit(main())
