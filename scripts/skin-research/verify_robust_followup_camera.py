"""New natural, expression-confounded source through the real automatic product flow.

Local camera encoding only; no pose transform, mocked SDK, fake API or hosted call.
The isolated profile owns its records; normal user records are never read/written.
"""
import argparse, base64, hashlib, json, math, time, urllib.request
from pathlib import Path
import cv2
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();choice=parser.add_mutually_exclusive_group();choice.add_argument('--census-index',type=int);choice.add_argument('--flaking-index',type=int);parser.add_argument('--attempt',type=int,default=1);args=parser.parse_args()
DATA=ROOT/'audit-results/dry-sag-robust-followup-20261013'
OUT=ROOT/'output/playwright/dry-sag-robust-followup-20261013';OUT.mkdir(parents=True,exist_ok=True)
PROFILE=OUT/'automatic-front-profile'
row=next(r for r in json.loads((DATA/'additional-sag-selection.json').read_text('utf-8-sig')) if r['sha256'].startswith('55ec00b8'))
if args.census_index is not None or args.flaking_index is not None:
    census=ROOT/'audit-results/dry-sag-source-census-20261013'
    row=json.loads((census/('contour-selection.json' if args.census_index is not None else 'dry-label-selection.json')).read_text('utf8'))[args.census_index if args.census_index is not None else args.flaking_index]
    DATA=census/'product'/row['sha256'][:8];DATA.mkdir(parents=True,exist_ok=True)
    OUT=ROOT/'output/playwright/dry-sag-source-census-20261013'/row['sha256'][:8];OUT.mkdir(parents=True,exist_ok=True)
    PROFILE=OUT/'automatic-front-profile'
if args.attempt>1:
    DATA=DATA/('attempt-'+str(args.attempt));DATA.mkdir(parents=True,exist_ok=True)
    OUT=OUT/('attempt-'+str(args.attempt));OUT.mkdir(parents=True,exist_ok=True)
    PROFILE=OUT/'automatic-front-profile'
prefix=row['sha256'][:8]
source=Path(row['absolutePath']);assert hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256']
image=cv2.imread(str(source));height,width=image.shape[:2];assert width%2==0 and height%2==0
camera=DATA/(prefix+'-camera.y4m')
with camera.open('wb') as stream:
    stream.write(f'YUV4MPEG2 W{width} H{height} F5:1 Ip A1:1 C420jpeg\n'.encode())
    yuv=cv2.cvtColor(image,cv2.COLOR_BGR2YUV_I420).tobytes()
    for _ in range(20):stream.write(b'FRAME\n');stream.write(yuv)
bundle=(ROOT/'.runtime/periorbital-v5-browser-support/utilities.js').read_text('utf8')
labels=dict(tone='Ton eşitsizliği',oil='Yağlı görünüm',redness='Kızarıklık eğilimi',acne='Sivilce görünümü',sag='Sarkma',dry='Cilt kuruluğu',dark='Göz altı morluğu',bags='Göz altı torbaları',lines='Kaz ayakları')
overview={**labels,'sag':'Sarkma görünümü','dry':'Cilt kuruluğu görünümü'}
views=['overview','forehead','rightCheek','leftCheek','nose','chin','periorbital']
errors=[];trace=[]
deadline=time.monotonic()+45
while True:
    try:
        for port,path in [(3000,'/privacy'),(8000,'/api/vehicle/state')]:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}'+path,timeout=3) as r:assert r.status==200
        break
    except (OSError,AssertionError):
        if time.monotonic()>deadline:raise
        time.sleep(.5)
with sync_playwright() as pw:
    context=pw.chromium.launch_persistent_context(str(PROFILE),channel='chrome',headless=False,viewport=dict(width=1600,height=1000),permissions=['camera'],args=['--window-size=1600,1000','--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(camera),'--enable-unsafe-swiftshader'])
    context.add_init_script("window.__skinRequests=[];window.__skinResponses=[];const orig=window.fetch;window.fetch=async(...a)=>{const skin=String(a[0]).endsWith('/api/local-health/skin');if(skin)window.__skinRequests.push(JSON.parse(a[1].body));const r=await orig(...a);if(skin&&r.ok)window.__skinResponses.push(await r.clone().json());return r;};")
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:3000/privacy');expect(page.get_by_label('Cilt tipi için yüz fotoğrafımın Roboflow tarafından işlenmesine izin ver',exact=True)).not_to_be_checked()
    for text in ['Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla','Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla']:
        control=page.get_by_label(text,exact=True)
        if not control.is_checked():control.click()
        expect(control).to_be_enabled();expect(control).to_be_checked()
    page.wait_for_function("localStorage.getItem('attune_privacy_skin_photos_allowed')==='true' && localStorage.getItem('attune_privacy_skin_save_allowed')==='true'")
    page.goto('http://127.0.0.1:3000/skin');page.bring_to_front()
    page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click();page.get_by_label('Üç açılı tarama',exact=True).uncheck();page.get_by_role('button',name='Bilgi penceresini kapat',exact=True).click()
    page.get_by_role('button',name='Analizi Başlat',exact=True).click();started=time.monotonic()
    while not page.get_by_text('Cilt Analizi Tamamlandı',exact=True).count() and time.monotonic()-started<120:
        page.wait_for_timeout(2000)
        trace.append(dict(seconds=time.monotonic()-started,text=page.locator('main').inner_text(),canvas=page.evaluate('({...document.querySelector("canvas")?.dataset})')))
        (OUT/'trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2),'utf8')
    completed=page.get_by_text('Cilt Analizi Tamamlandı',exact=True).is_visible()
    if not completed:
        page.screenshot(path=str(OUT/'incomplete-scan.png'),full_page=True)
        (OUT/'camera-receipt.json').write_text(json.dumps(dict(sourceSHA256=row['sha256'],automaticScanCompleted=completed,trace=trace,pageErrors=errors),ensure_ascii=False,indent=2),'utf8')
        context.close();raise RuntimeError('Automatic scan did not complete; no pose/quality override applied')
    requests=page.evaluate('window.__skinRequests');responses=page.evaluate('window.__skinResponses');record=page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
    assert len(requests)==len(responses)==1 and record['usedMediaPipe']
    assert not any(r.get('hostedProcessingConsent') for r in requests)
    p=requests[0];response=responses[0]
    (DATA/(prefix+'-automatic-payload.json')).write_text(json.dumps(p,ensure_ascii=False),'utf8')
    (DATA/(prefix+'-automatic-api.json')).write_text(json.dumps(response,ensure_ascii=False),'utf8')
    def check_views(root,history):
        receipts=[]
        for view in views:
            attribute='data-skin-record-indicator' if history else 'data-skin-indicator'
            cards=root.locator('['+attribute+']');ids=cards.evaluate_all('(els)=>els.map(e=>e.dataset.skinRecordIndicator||e.dataset.skinIndicator)');wanted=overview if view=='overview' else labels
            actual=[]
            for ident in ids:
                card=root.locator('['+attribute+'="'+ident+'"]')
                text=card.locator('h4').inner_text() if history else card.locator(':scope > div').first.inner_text()
                assert text==wanted[ident],(view,ident,text)
                actual.append(dict(id=ident,text=text,expected=wanted[ident],matches=text==wanted[ident]))
            for ident in ('dry','sag'):
                if ident not in ids:continue
                card=root.locator('['+attribute+'="'+ident+'"]');card.click()
                layer=response['maps'].get(view+':'+ident)
                fill=root.locator('[data-skin-local-fill="'+ident+'"]')
                if layer:
                    expect(fill).to_be_visible();paint=fill.locator('image').first
                    fields={k:abs(float(paint.get_attribute(k))-layer[k]*(layer['step'] if k in ('width','height') else 1))<1e-7 for k in ('x','y','width','height')}
                    assert all(fields.values()) and fill.get_attribute('data-map-photo')==p['photoId']
                else:assert fill.count()==0,(view,ident,'Unavailable map must not be fabricated')
            if 'tone' in ids:
                root.locator('['+attribute+'="tone"]').click();assert root.locator('[data-skin-local-fill="sag"]').count()==0
            receipts.append(dict(view=view,labels=actual,photoId=p['photoId']))
            root.get_by_role('button',name='Sonraki Bölge',exact=True).click();assert root.locator('[data-skin-local-fill]').count()==0
        return receipts
    result_views=check_views(page,False);page.screenshot(path=str(OUT/'actual-result-overview.png'),full_page=True)
    page.goto('http://127.0.0.1:3000/profile');before=page.evaluate('localStorage.getItem("togg_health_skin_history")')
    page.locator('[data-record-id="'+record['id']+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);expect(dialog.locator('[data-skin-snapshot]')).to_be_visible(timeout=15000)
    history_views=check_views(dialog,True);page.screenshot(path=str(OUT/'actual-history-overview.png'),full_page=True)
    assert before==page.evaluate('localStorage.getItem("togg_health_skin_history")')
    page.set_viewport_size(dict(width=720,height=900));assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/'actual-history-narrow.png'),full_page=True);context.close()
    prefs=PROFILE/'Default/Preferences';settings=json.loads(prefs.read_text('utf8'));settings.setdefault('partition',{})['default_zoom_level']={'x':math.log(2)/math.log(1.2)};prefs.write_text(json.dumps(settings),'utf8')
    context=pw.chromium.launch_persistent_context(str(PROFILE),channel='chrome',headless=False,viewport=None,no_viewport=True,args=['--window-size=1600,1000','--enable-unsafe-swiftshader']);page=context.new_page();page.goto('http://127.0.0.1:3000/profile')
    page.locator('[data-record-id="'+record['id']+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);expect(dialog.locator('[data-skin-snapshot]')).to_be_visible()
    geometry=page.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,zoom:getComputedStyle(document.documentElement).zoom,scroll:document.documentElement.scrollWidth})')
    zoom_ok=geometry['dpr']>=2 and geometry['innerWidth']<geometry['outerWidth']*.65 and geometry['zoom']=='1' and geometry['scroll']<=geometry['innerWidth'];assert zoom_ok
    page.bring_to_front();cdp=context.new_cdp_session(page);(OUT/'actual-history-native200.png').write_bytes(base64.b64decode(cdp.send('Page.captureScreenshot',{'format':'png','fromSurface':False,'captureBeyondViewport':False})['data']))
    sag_card=dialog.locator('[data-skin-record-indicator="sag"]');page.wait_for_timeout(600)
    dialog.evaluate('el=>{const c=el.querySelector("[data-skin-record-indicator=sag]");el.scrollTop+=c.getBoundingClientRect().top-el.getBoundingClientRect().top-(el.clientHeight-c.clientHeight)/2}');page.wait_for_timeout(600);expect(sag_card).to_be_visible()
    card_bounds=sag_card.evaluate('el=>{const r=el.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:innerHeight}}');assert card_bounds['top']>=0 and card_bounds['bottom']<=card_bounds['height']
    sag_text=sag_card.inner_text();general_sag=next(v for v in response['general']['measurements'] if v['id']=='sag')
    if general_sag['value'] is None:assert '—' in sag_text and '0%' not in sag_text
    (OUT/'actual-history-sag-native200.png').write_bytes(base64.b64decode(cdp.send('Page.captureScreenshot',{'format':'png','fromSurface':False,'captureBeyondViewport':False})['data']))
    unchanged=before==page.evaluate('localStorage.getItem("togg_health_skin_history")');assert unchanged
    target=[]
    for region,values in [*response['measurements'].items(),('overview',response['general']['measurements'])]:
        for v in values:
            if v['id'] in ('dry','sag'):target.append(dict(region=region,id=v['id'],value=v['value'],quality=v['quality'],reason=v['limitationCode'],normalizationVersion=v['normalizationVersion'],mapPresent=region+':'+v['id'] in response['maps']))
    receipt=dict(sourceSHA256=row['sha256'],cameraSHA256=hashlib.sha256(camera.read_bytes()).hexdigest(),capturePixelSHA256=p['photoId'],buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip(),automaticScanCompleted=completed,realMediaPipe=record['usedMediaPipe'],pose=p['pose'],conditions=p['conditions'],qualityValid=p['qualityValid'],requestCount=len(requests),responseCount=len(responses),sourceMatches=p['photoId']==response['photoId'],targets=target,resultViews=result_views,historyViews=history_views,historyBytesUnchanged=unchanged,real200Percent=geometry,real200Accepted=zoom_ok,pageErrors=errors,recordId=record['id'],hostedCalls=sum(bool(r.get('hostedProcessingConsent')) for r in requests))
    assert not errors and receipt['sourceMatches']
    (OUT/'camera-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8');context.close()
    print(json.dumps({k:receipt[k] for k in ('automaticScanCompleted','realMediaPipe','sourceMatches','targets','historyBytesUnchanged','real200Accepted','hostedCalls')}))
