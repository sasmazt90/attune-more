from vehicle_controls import toggle_vehicle, vehicle_status
"""Keyless UI evidence for cockpit provenance, Care limits and selected print.

--before only captures observations of the unchanged starting product; it is
never an acceptance result. Keyless synthetic generation fixture conversation creates the record.
Permission/network denial is controlled; no successful sensor/provider is faked.
"""
import argparse, json, os, subprocess, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('--before', action='store_true')
parser.add_argument('--output', default='audit-results/uat-truthfulness')
args = parser.parse_args()
assert not os.getenv('OPENAI_API_KEY') and os.getenv('ATTUNE_LOAD_LOCAL_ENV') == '0'
OUT = Path(args.output); OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://localhost:3000'; API = 'http://localhost:8000'
results = []; screens = []
INIT = '''window.captureAttempts=0;window.printCalls=0;
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
if(SR)SR.prototype.start=()=>{window.captureAttempts++;throw new DOMException('Controlled denied microphone','NotAllowedError')};
navigator.mediaDevices.getUserMedia=()=>{window.captureAttempts++;return Promise.reject(new DOMException('Controlled denied media','NotAllowedError'))};'''

def snap(page, name):
    if not page.get_by_role('dialog').count(): page.evaluate('scrollTo(0,0)')
    page.screenshot(path=str(OUT/(name+'.png')), full_page=not page.get_by_role('dialog').count(), animations='disabled')
    screens.append({'file':name+'.png', 'viewport':page.viewport_size, 'route':page.url, 'openedForReview':False})

def print_style(button):
    return button.evaluate('e=>{const s=getComputedStyle(e);return {background:s.backgroundColor,color:s.color,cursor:s.cursor,shadow:s.boxShadow,disabled:e.disabled}}')

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    for width, height in [(390,844),(820,900),(1280,900)]:
        c = browser.new_context(viewport={'width':width,'height':height}, locale='tr-TR')
        c.add_init_script(INIT); page = c.new_page()
        c.request.post(API+'/api/vehicle/speed',data={'speedKmH':0})
        try:
            page.goto(BASE); expect(vehicle_status(page)).to_contain_text('PARK')
            snap(page,f'cockpit-health-demo-off-{width}')
            if not args.before:
                assert page.locator('[data-vehicle-provenance]').count()==0
                assert page.locator('[data-sensor-status]').count()==0
                assert 'Ahmet Yılmaz' not in page.locator('header').inner_text()
                assert '22 dk varış' not in page.locator('main').inner_text()
                page.get_by_role('button',name='Demo araç durumu hakkında bilgi',exact=True).click()
                expect(page.get_by_role('dialog')).to_contain_text('gerçek araç API/CAN bağlantısına sahip değildir')
                page.keyboard.press('Escape')
                expect(page.locator('[data-cockpit-care]')).to_contain_text('Örnek randevu')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.goto(BASE+'/?demo=1'); snap(page,f'cockpit-health-demo-on-{width}')
            if not args.before:
                assert page.locator('[data-vehicle-provenance]').count()==0
                expect(page.get_by_text('demo veri',exact=True)).to_be_visible()
            page.goto(BASE+'/privacy')
            page.get_by_role('button',name='Erişimi Kapat',exact=True).first.click()
            page.get_by_role('button',name='Erişimi Kapat',exact=True).first.click()
            page.goto(BASE); snap(page,f'cockpit-permissions-denied-{width}')
            if not args.before:
                assert page.locator('[data-sensor-status]').count()==0
                assert page.evaluate('localStorage.getItem("attune_privacy_camera_allowed")')=='false'
                assert page.evaluate('localStorage.getItem("attune_privacy_microphone_allowed")')=='false'
            page.route('**/api/vehicle/state',lambda route:route.abort())
            page.goto(BASE); expect(vehicle_status(page)).to_contain_text('ARAÇ DURUMU BELİRSİZ')
            snap(page,f'cockpit-vehicle-api-outage-{width}')
            if not args.before:
                expect(vehicle_status(page)).to_contain_text('ARAÇ DURUMU BELİRSİZ')
                assert 'Sürüş (0' not in page.locator('main').inner_text()
                assert 'Yalnızca sesli asistan kullanılabilir' not in page.locator('main').inner_text()
            page.unroute('**/api/vehicle/state')
            page.goto(BASE+'/profile'); expect(vehicle_status(page)).to_contain_text('PARK')
            snap(page,f'profile-empty-{width}')
            page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click()
            button=page.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True)
            expect(button).to_be_disabled(); initial=print_style(button)
            button.hover(force=True); page.wait_for_timeout(120); hovered=print_style(button)
            # Invoke DOM click: browser semantics must suppress a disabled button.
            button.evaluate('e=>e.click()'); assert page.locator('iframe[title="Seçilmiş sağlık özeti yazdırma"]').count()==0
            assert page.get_by_role('checkbox').evaluate_all('(a)=>a.every(x=>!x.checked)')
            snap(page,f'profile-empty-share-disabled-{width}')
            if not args.before:
                assert initial['background']==hovered['background'] and initial['color']==hovered['color']
                assert hovered['cursor']=='not-allowed' and hovered['shadow']=='none'
                expect(page.locator('#share-print-status')).to_contain_text('Yazdırmak için en az bir kayıtlı sonucu seçin.')
                assert button.get_attribute('aria-describedby')=='share-print-status'
            page.keyboard.press('Escape')
            # Actual keyless backend and actual UI, written synthetic text; no STT/TTS.
            page.goto(BASE+'/mental'); page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click()
            page.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click()
            page.get_by_role('textbox',name='Görüşme mesajı').fill('Ailemle güzel bir kitap okudum.')
            page.get_by_role('button',name='Gönder',exact=True).click()
            expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready')
            page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click()
            expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed')
            assert page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history")||"[]").length')==1
            page.goto(BASE+'/profile'); snap(page,f'profile-completed-local-{width}')
            page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click()
            button=page.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True)
            expect(button).to_be_disabled()
            page.get_by_label('Ruhsal iyi oluş',exact=True).check(); expect(button).to_be_enabled()
            selected=print_style(button); assert selected['background']!=initial['background'] if not args.before else True
            snap(page,f'profile-selected-mental-{width}')
            # Observe the real generated print DOM, suppress only the OS dialog.
            page.evaluate("HTMLIFrameElement.prototype.__originalContentWindowGetter=Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype,'contentWindow').get;Object.defineProperty(HTMLIFrameElement.prototype,'contentWindow',{get(){const w=this.__originalContentWindowGetter();if(w)w.print=()=>{window.printCalls++};return w}})")
            button.click(); frame=page.locator('iframe[title="Seçilmiş sağlık özeti yazdırma"]')
            expect(frame).to_have_count(1); assert page.evaluate('window.printCalls')==1
            doc=frame.content_frame.locator('html').inner_text(); html=frame.content_frame.locator('html').evaluate('e=>e.outerHTML')
            assert 'Ruhsal iyi oluş' in doc and 'Görme' not in html and 'Cilt' not in html and 'Ahmet Yılmaz' not in html
            assert 'Ailemle güzel bir kitap okudum.' not in html
            c.request.post(API+'/api/vehicle/speed',data={'speedKmH':75})
            expect(button).to_be_disabled(); button.evaluate('e=>e.click()'); assert page.evaluate('window.printCalls')==1
            if not args.before: expect(page.locator('#share-print-status')).to_contain_text('Yazdırma yalnız PARK durumunda kullanılabilir.')
            snap(page,f'profile-driving-disabled-{width}')
            c.request.post(API+'/api/vehicle/speed',data={'speedKmH':0})
            page.route('**/api/care/match',lambda route:route.abort())
            page.goto(BASE+'/care'); expect(page.get_by_role('button',name='RANDEVUYU İNCELE',exact=True)).to_be_visible()
            snap(page,f'care-service-error-{width}')
            if not args.before:
                expect(page.locator('[data-care-limits]')).to_contain_text('Burada randevu oluşturulmaz');page.get_by_role('button',name='Uzman seçenekleri hakkında bilgi',exact=True).click();expect(page.get_by_role('dialog',name='Uzman seçenekleri',exact=True)).to_contain_text('Kişisel takvim ve canlı rota entegrasyonu yoktur');page.keyboard.press('Escape')
                expect(page.get_by_text('Uzman seçeneği',exact=True)).to_be_visible(); assert 'eşleşme puanı' not in page.locator('main').inner_text().lower()
                expect(page.get_by_text('Örnek ulaşım:',exact=False).first).to_be_visible()
                expect(page.get_by_text('Demo takvim',exact=False).last).to_be_visible()
                assert 'Takviminizle Uyumlu' not in page.locator('main').inner_text()
            page.get_by_role('button',name='RANDEVUYU İNCELE',exact=True).click()
            page.get_by_role('checkbox').check(); page.get_by_role('button',name='Onayla ve Devam Et',exact=True).click()
            expect(page.get_by_text('Hekim sisteminde randevu oluşturulmadı',exact=False)).to_be_visible()
            assert page.evaluate('window.captureAttempts')==0
            results.append({'name':f'Truthful cockpit and Care / disabled and selected print at {width}px','status':'OBSERVED' if args.before else 'PASS','captureAttempts':0,'printCalls':1,'emptyDisabledStyle':initial,'selectedStyle':selected})
        except Exception as error:
            results.append({'name':f'{width}px','status':'FAIL','error':str(error),'traceback':traceback.format_exc()})
        finally:
            c.request.post(API+'/api/vehicle/speed',data={'speedKmH':0}); c.close()
    browser.close()
proof={'results':results,'screenshots':screens,'sourceHead':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'productionBuildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'beforeObservationOnly':args.before,'provider':'keyless synthetic generation fixture written input; no OpenAI dispatch','physicalCaptureAttempts':0}
(OUT/'results.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False))
raise SystemExit(any(x['status']=='FAIL' for x in results))
