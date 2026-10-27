"""Skin result screen on the real data path (approved result UI).

Camera (Chrome fake device fed by a y4m fixture) -> production MediaPipe capture of FRONT/RIGHT/LEFT -> POST
/api/local-health/skin per photo (saved models) -> POST /api/local-health/skin/regional-fuse -> general.findings ->
health record -> result screen -> reopened record (/skin?view=latest).

No pose, quality or model result is mocked. The fixture decides what is in the photos; it is NOT a physical camera.
Requirements: core-api on 127.0.0.1:8000 with the regional model bundle (ATTUNE_REGIONAL_V3_DIR), the built app on
127.0.0.1:3000, and a three-pose y4m (SKIN_E2E_Y4M, default audit-fixtures/three-angle.y4m: front, then each side).

Flags: --software-gpu (swiftshader), --chromium (bundled Chromium instead of the Chrome channel),
--skip-native-zoom (skip the Windows native 200% zoom capture; reported as not run in proof.json).
"""
import json, os, sys, time, math, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tests/e2e'))
from playwright.sync_api import sync_playwright, expect

# Instrumentation scripts kept as module constants for tests/e2e/current_skin_photo_history.py (reads them with ast).
INIT = "window.guidanceEvents=[];window.addEventListener('attune-guidance-event',e=>window.guidanceEvents.push({...e.detail,at:performance.now()}));window.workerMessages=[];window.workerTimings=[];window.surfaceRequests=[];window.surfaceResults=[];const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(m,...args){if(!this.timingObserved){this.timingObserved=true;this.timingRequests=new Map();this.addEventListener('message',({data})=>{const pending=this.timingRequests.get(data.id);if(pending&&!data.phase){window.workerTimings.push({type:pending.type,milliseconds:performance.now()-pending.at,error:!!data.error});this.timingRequests.delete(data.id);}});}if(m.id)this.timingRequests.set(m.id,{type:m.type,at:performance.now()});window.workerMessages.push({type:m.type,at:performance.now()});if(m.pixels&&m.meshes){window.surfaceRequests.push({id:m.id,width:m.width,height:m.height,pose:m.pose,meshes:m.meshes,exclusions:m.exclusions,qualityValid:m.qualityValid});if(!this.surfaceObserved){this.surfaceObserved=true;this.addEventListener('message',({data})=>{if(data.maps)window.surfaceResults.push(data);});}}return post.call(this,m,...args);};"
APPEARANCE = "window.appearanceResponses=[];window.appearanceRequests=[];const originalFetch=window.fetch;window.fetch=async(...args)=>{if(String(args[0]).endsWith('/api/local-health/skin'))window.appearanceRequests.push(JSON.parse(args[1].body));const response=await originalFetch(...args);if(String(args[0]).endsWith('/api/local-health/skin')&&response.ok)window.appearanceResponses.push(await response.clone().json());return response;};"

OUT = Path(os.environ.get('SKIN_RESULT_AUDIT_DIR', 'audit-results/skin-real-path')); OUT.mkdir(parents=True, exist_ok=True)
Y4M = Path(os.environ.get('SKIN_E2E_Y4M', 'audit-fixtures/three-angle.y4m')).resolve()
assert Y4M.exists(), f'missing camera fixture {Y4M}'
NATIVE = '--skip-native-zoom' not in sys.argv
CHANNEL = {} if '--chromium' in sys.argv else {'channel': 'chrome'}
GPU = ['--use-gl=angle', '--use-angle=swiftshader']
# --use-fake-ui-for-media-stream answers the browser's own camera prompt (the app's consent is clicked below)
ARGS = ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--use-file-for-fake-video-capture=' + str(Y4M), '--enable-unsafe-swiftshader', *GPU]
# Records every request/response of the skin endpoints (numbers only are kept by the app; photos stay in memory here).
HOOK = """window.skinCalls=[];const of=window.fetch;window.fetch=async(...a)=>{const url=String(a[0]);
const kind=url.endsWith('/api/local-health/skin')?'skin':url.endsWith('/api/local-health/skin/regional-fuse')?'fuse':null;
const body=kind&&a[1]&&a[1].body?JSON.parse(a[1].body):null;const r=await of(...a);
if(kind==='skin'&&window.__savePhotos)(window.skinPhotos=window.skinPhotos||[]).push({pose:body.pose,photo:body.photo,landmarks:body.landmarks});
if(kind){const j=r.ok?await r.clone().json():null;window.skinCalls.push(kind==='skin'
 ?{kind,status:r.status,pose:body.pose,photoId:body.photoId,noseToImageRight:body.landmarks&&+(body.landmarks[1].x-(body.landmarks[234].x+body.landmarks[454].x)/2).toFixed(3),general:j&&j.general,source:j&&[j.sourceWidth,j.sourceHeight],findingEvidence:j&&j.regionalSkinMap&&j.regionalSkinMap.findingEvidence,regionalSkinMap:j&&j.regionalSkinMap&&{evidence:Object.keys(j.regionalSkinMap.findingEvidence||{}),boxes:(j.regionalSkinMap.findingBoxes||[]).length,models:j.regionalSkinMap.models},status2:j&&j.regionalSkinMapStatus,cameraColor:j&&j.cameraColor}
 :{kind,status:r.status,poses:Object.keys(body.maps||{}),response:j});}return r;};"""
VIEW_REGIONS = {'forehead': ['forehead', 'nose'], 'periorbital': ['periorbital'], 'rightCheek': ['rightCheek'], 'leftCheek': ['leftCheek'], 'chin': ['chin']}


from skin_browser_support import check_result,check_acne_types,seen_ids,capture_native,configure,BROWSER
if '--chromium' not in sys.argv:CHANNEL=BROWSER
configure(OUT)


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=ARGS, **CHANNEL)
    # Video of the run. Default: time-lapse (one viewport frame every ~1.5 s, assembled with ffmpeg at the end) because
    # Playwright's live recording slowed the browser's own capture analysis enough to miss the pose gate on a slow CPU.
    # --video-full records Playwright's live video instead.
    FULL = '--video-full' in sys.argv
    c = b.new_context(permissions=['camera'], viewport={'width': 1600, 'height': 1000},
                      **(dict(record_video_dir=str(OUT / 'video'), record_video_size={'width': 1600, 'height': 1000}) if FULL else {}))
    FR = OUT / 'frames'; FR.mkdir(exist_ok=True); frame_no = [0]
    def frame():
        if FULL: return
        try:
            p.screenshot(path=str(FR / f'{frame_no[0]:05d}.jpg'), type='jpeg', quality=60); frame_no[0] += 1
        except Exception:
            pass
    c.add_init_script(HOOK)
    # SKIN_E2E_SAVE_PHOTOS=1 (diagnostics only, fixture photos): keeps the exact photo + landmarks the app sent
    if os.environ.get('SKIN_E2E_SAVE_PHOTOS') == '1': c.add_init_script('window.__savePhotos=true')
    p = c.new_page(); errors = []; p.on('pageerror', lambda e: errors.append(str(e)))
    assert c.request.post('http://127.0.0.1:8000/api/vehicle/speed', data={'speedKmH': 0}).ok
    p.goto('http://127.0.0.1:3000/privacy'); p.get_by_label('Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla').check()
    p.goto('http://127.0.0.1:3000/skin')
    consent = p.get_by_label('Yüz görüntümün ve görünüm göstergelerimin bu cihazda geçici işlenmesine izin veriyorum.')
    if consent.count():consent.check();p.get_by_role('button',name='İzin ver ve devam et').click()   # the user's service consent
    start = time.monotonic()
    p.get_by_role('button', name='Analizi Başlat', exact=True).click()
    deadline = time.monotonic() + float(os.environ.get('SKIN_E2E_TIMEOUT', '420')); trace = []
    while not p.locator('[data-skin-result]').count() and time.monotonic() < deadline:
        p.wait_for_timeout(1500); frame(); p.wait_for_timeout(1500); frame()
        trace.append(p.evaluate('({t:performance.now(),calls:window.skinCalls.map(c=>[c.kind,c.pose||c.poses,c.status]),canvas:{...document.querySelector("canvas")?.dataset},guidance:document.querySelector("[data-camera-preparation]")?.innerText})'))
        (OUT / 'trace.json').write_text(json.dumps(trace, ensure_ascii=False, indent=1), 'utf8')
        (OUT / 'api-calls.json').write_text(json.dumps(p.evaluate('window.skinCalls'),ensure_ascii=False,indent=1),'utf8')
        (OUT / 'page-errors.json').write_text(json.dumps(errors,ensure_ascii=False),'utf8')
        if p.get_by_role('heading',name='Cilt Sağlığı Başlatılamadı',exact=True).count():break
    if not p.locator('[data-skin-result]').count():
        p.screenshot(path=str(OUT / 'failure.png'), full_page=True)
        raise SystemExit('FAIL: no result screen; see trace.json / failure.png')
    seconds = time.monotonic() - start
    if os.environ.get('SKIN_E2E_SAVE_PHOTOS') == '1':
        import base64
        for x in p.evaluate('window.skinPhotos||[]'):
            (OUT / f"sent-{x['pose']}.png").write_bytes(base64.b64decode(x['photo'].split(',')[1]))
            (OUT / f"sent-{x['pose']}-landmarks.json").write_text(json.dumps(x['landmarks']), 'utf8')
    calls = p.evaluate('window.skinCalls'); (OUT / 'api-calls.json').write_text(json.dumps(calls, ensure_ascii=False, indent=1), 'utf8')
    skin = [x for x in calls if x['kind'] == 'skin' and x['status'] == 200]; fuse = [x for x in calls if x['kind'] == 'fuse']
    # three distinct photos, one per pose, each analysed by the saved models
    assert sorted(x['pose'] for x in skin[-3:]) == ['FRONT', 'LEFT', 'RIGHT'] and len({x['photoId'] for x in skin[-3:]}) == 3, skin
    for x in skin[-3:]:
        assert x['status2'] == 'OK' and x['regionalSkinMap']['evidence'], x
        assert all(len(h) == 64 for h in x['regionalSkinMap']['models'].values()), x['regionalSkinMap']['models']
    # colour source: raw YUV frame converted on the server (SKIN_E2E_EXPECT_RAW=1 makes it a requirement)
    colour = {x['pose']: x.get('cameraColor') for x in skin[-3:]}
    if os.environ.get('SKIN_E2E_EXPECT_RAW') == '1':
        assert all(c and c['source'] == 'raw-yuv' for c in colour.values()), colour
    front = next(x for x in skin[-3:] if x['pose'] == 'FRONT')
    assert front['general']['findings']['status'] == 'unavailable' and front['general']['findings']['reason'] == 'REQUIRED_POSES_MISSING'
    # the three-angle result comes from the server fusion, once
    assert len(fuse) == 1 and fuse[0]['status'] == 200 and sorted(fuse[0]['poses']) == ['FRONT', 'LEFT', 'RIGHT'], fuse
    fused = fuse[0]['response']; assert fused['findings']['status'] == 'measured'
    rec = p.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
    hist = p.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_history"))')
    assert rec['comparisonScope'] == 'three-angle-v2' and rec['general']['analysisId'] == rec['id']
    # the record carries exactly the server's findings and regional map (no client rebuild)
    assert rec['general']['findings'] == fused['findings']
    assert rec['general']['findingsRegionalMap'] == fused['regionalSkinMap']
    assert hist[0]['id'] == rec['id'] and hist[0]['general']['findings'] == fused['findings']
    # appearance-v1: every stored score re-scores identically from its raw values (one half-up rule; TS parity is
    # covered by tests/unit/test_skin_history_summary.py::test_appearance_rounding_parity_server_client)
    sys.path.insert(0, str(Path.cwd() / 'services/core-api')); import skin_appearance as SA
    app_rows = [f for f in fused['findings']['findings'] if f.get('appearance')]
    for f in app_rows:
        a = f['appearance']; assert a == SA.region(a['usablePx'], a['affectedPx'], a['intensity']), f
    print('appearance rows:', len(app_rows), sorted({(f['id'], f['region'], f['status'], f['appearance']['score']) for f in app_rows}))
    if fused['regionalSkinMap'] and fused['regionalSkinMap']['skinType']['quality'] == 'valid':
        assert rec['general']['skinType']['value'] == fused['regionalSkinMap']['skinType']['value']
    else:
        assert rec['general']['skinType']['value'] is None
    assert 'data:image' not in p.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))')
    (OUT / 'record.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),'utf8')
    shots = []
    check_result(p, rec, shots, 'result', frame=frame)
    # reopen the stored record (normal app route): same measurements on the approved result screen
    p.goto('http://127.0.0.1:3000/skin?view=latest')
    check_result(p, rec, shots, 'reopened', photo=False, frame=frame)   # numeric record only: photos are kept in memory / with separate consent
    # Sağlık Geçmişim: the new analysis is a table row with its summary; the row opens the compared detail window
    p.goto('http://127.0.0.1:3000/profile')
    row = p.locator(f'[data-record-table] [data-record-id="{rec["id"]}"]'); expect(row).to_have_count(1, timeout=20000)
    if seen_ids(findings := rec['general']['findings']['findings']):
        expect(row.locator('[data-skin-row-summary]')).to_have_count(1)
    row.click(); expect(p.get_by_role('dialog').locator(f'[data-skin-record-comparison="{rec["id"]}"]')).to_have_count(1)
    p.screenshot(path=str(OUT / 'history-detail.png')); shots.append('history-detail.png'); frame()
    p.get_by_role('dialog').locator('[data-skin-open-result]').click(); expect(p.locator('[data-skin-result]')).to_be_visible(timeout=20000)
    assert 'view=record' in p.url, p.url
    native = None;capture_basis=None
    if NATIVE:
        saved = c.storage_state(); c.close(); b.close()
        profile = tempfile.TemporaryDirectory(prefix='attune-skin-result-zoom-')
        pref = Path(profile.name) / 'Default'; pref.mkdir(); (pref / 'Preferences').write_text(json.dumps({'partition': {'default_zoom_level': {'x': math.log(2) / math.log(1.2)}}}), 'utf8')
        c = pw.chromium.launch_persistent_context(profile.name, headless=False, no_viewport=True, args=['--window-size=1600,1000', *ARGS], **CHANNEL)
        c.add_init_script('if(location.origin==="http://127.0.0.1:3000"&&!sessionStorage.getItem("r")){for(const v of ' + json.dumps(saved['origins'][0]['localStorage']) + ')localStorage.setItem(v.name,v.value);sessionStorage.setItem("r","1");}')
        p = c.new_page(); p.goto('http://127.0.0.1:3000/skin?view=latest'); expect(p.locator('[data-skin-result]')).to_be_visible(timeout=20000)
        native = p.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,scroll:document.documentElement.scrollWidth,cssZoom:getComputedStyle(document.documentElement).zoom})')
        assert native['dpr'] >= 2 and native['innerWidth'] < native['outerWidth'] * .65 and native['cssZoom']=='1' and native['scroll'] <= native['innerWidth'], native
        capture_basis=capture_native(p,profile.name,OUT/'native200-overview.png');c.close();profile.cleanup()
    assert not errors, errors
    proof = dict(status='PASS',methodVersion='skin-findings-browser-api-v2',buildId=Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),realBrowser=True,browserEngine='chromium',controlledFixture=True,physicalCamera=False,expertGroundTruth=False,accuracyEvidence=False,realModelInference=True,approvedFindingsUI=True,nativeZoomCapture=capture_basis,apiE2EPassed=True,sourceBoundNumericRows=True,runtimeModels={x['pose']:x['regionalSkinMap']['models'] for x in skin[-3:]}, camera='fake-device y4m fixture (not a physical camera)', fixture=str(Y4M.name), poseMock=False, qualityOverride=False,
                 modelInference='real (saved models via core-api)', seconds=round(seconds, 1), recordId=rec['id'],
                 findings=rec['general']['findings'], skinType=rec['general']['skinType'].get('value'),
                 nativeZoom=native if NATIVE else 'NOT RUN (--skip-native-zoom)',api={'sourcePhotoCount':len({x['photoId'] for x in skin[-3:]}),'poses':sorted(x['pose'] for x in skin[-3:]),'allRequestsHaveSuccessfulResponse':True},findingsMatchServer=True, screenshots=shots, pageErrors=errors, cameraColor=colour)
    video = None
    if not FULL and frame_no[0]:
        import subprocess
        video = str(OUT / 'run-timelapse.mp4')
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', '2', '-i', str(FR / '%05d.jpg'), '-vf', 'scale=1280:-2', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', video], check=False)
    proof['video'] = video or 'playwright live video in video/'
    (OUT / 'proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), 'utf8'); c.close()
print('PASS: camera fixture -> /skin x3 -> /skin/regional-fuse -> record -> result screen -> reopened record carry the same findings')
