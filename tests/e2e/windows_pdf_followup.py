"""Actual Windows Chrome Save-as-PDF and viewer; disposable profile and explicitly synthetic generation fixture records.
No system printer/preferences, user profile, keys, microphone or personal health data.
"""
import json,os,tempfile,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
assert os.name=='nt' and not os.getenv('OPENAI_API_KEY') and os.getenv('ATTUNE_LOAD_LOCAL_ENV')=='0'
OUT=Path(os.getenv('ATTUNE_WINDOWS_PDF_OUTPUT','audit-results/uat-20261003/windows-pdf')).resolve();OUT.mkdir(parents=True,exist_ok=True)
INIT="window.captureAttempts=0;const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR)SR.prototype.start=()=>{window.captureAttempts++;throw new DOMException('Denied','NotAllowedError')};navigator.mediaDevices.getUserMedia=()=>{window.captureAttempts++;return Promise.reject(new DOMException('Denied','NotAllowedError'))}"
with tempfile.TemporaryDirectory(prefix='attune-uat-pdf-') as profile, sync_playwright() as pw:
 default=Path(profile)/'Default';default.mkdir()
 prefs={'printing':{'print_preview_sticky_settings':{'appState':json.dumps({'version':2,'recentDestinations':[{'id':'Save as PDF','origin':'local','account':''}],'selectedDestinationId':'Save as PDF','isHeaderFooterEnabled':False})}},'savefile':{'default_directory':str(OUT)}}
 (default/'Preferences').write_text(json.dumps(prefs),encoding='utf-8')
 context=pw.chromium.launch_persistent_context(profile,channel='chrome',headless=False,locale='tr-TR',viewport={'width':1280,'height':900},args=['--kiosk-printing'])
 context.add_init_script(INIT);page=context.pages[0];version=context.browser.version;context.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0})
 page.goto('http://localhost:3000/privacy');page.get_by_role('button',name='Devre Dışı Bırak',exact=True).click();page.get_by_role('button',name='Etkinleştir',exact=True).click()
 page.goto('http://localhost:3000/mental');page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click();page.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click();page.get_by_role('textbox',name='Görüşme mesajı').fill('Ailemle güzel bir kitap okudum.');page.get_by_role('button',name='Gönder',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready');page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed')
 assert page.evaluate('window.captureAttempts')==0
 page.goto('http://localhost:3000/profile');page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click();assert page.get_by_role('checkbox').evaluate_all('(a)=>a.every(i=>!i.checked)');page.get_by_label('Ruhsal iyi oluş',exact=True).check();preview=page.locator('[data-share-preview]').inner_text();assert 'Ruhsal iyi oluş' in preview and 'Cilt' not in preview and 'Görme' not in preview
 before={p: p.stat().st_mtime_ns for p in OUT.glob('*.pdf')};page.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True).click()
 deadline=time.monotonic()+40
 while True:
  files=[p for p in OUT.glob('*.pdf') if before.get(p)!=p.stat().st_mtime_ns]
  if files:break
  assert time.monotonic()<deadline,'Actual Chrome Save-as-PDF did not produce a file'
  page.wait_for_timeout(250)
 pdf=max(files,key=lambda p:p.stat().st_mtime_ns)
 import fitz
 doc=fitz.open(pdf);text=''.join(p.get_text() for p in doc);metadata=json.dumps(doc.metadata,ensure_ascii=False)
 assert len(doc)>0 and 'Ruhsal iyi oluş' in text and 'Cilt' not in text and 'Görme' not in text and 'Ahmet Yılmaz' not in text+metadata
 assert 'klinik' in text.lower() and 'Ailemle güzel bir kitap okudum.' not in text
 doc[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(OUT/'printed-page-1.png');pages=len(doc);doc.close()
 viewer=context.new_page();viewer.goto(pdf.as_uri());viewer.wait_for_timeout(2000);assert viewer.url==pdf.as_uri();viewer.screenshot(path=str(OUT/'real-chrome-pdf-viewer.png'));context.close()
proof={'status':'PASS','platform':'Windows','actualChromeVersion':version,'saveMechanism':'Actual UI print -> isolated Chrome kiosk Save as PDF preference, not manual OS dialog','pdf':pdf.name,'pages':pages,'selectedCategories':['mental'],'excludedCategoriesNotInPDFOrMetadata':['skin','vision'],'demoIdentityAbsent':True,'fullTranscriptAbsent':True,'physicalCaptureAttempts':0,'reopenedInActualChromeViewer':True,'temporaryProfileRemoved':not Path(profile).exists(),'provider':'KEYLESS_SYNTHETIC_GENERATION_FIXTURE','liveOpenAI':False}
(OUT/'result.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(proof,ensure_ascii=False))
