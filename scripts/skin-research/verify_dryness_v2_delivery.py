"""Read-only live shortcut/source/build/served-asset proof; no user record access."""
import hashlib,json,re,urllib.request,subprocess
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dryness-integration-v2-20261014'
LAUNCH=Path('C:/Users/PC/Desktop/YENİ İŞ/Applications/7. TOGG/.launcher')
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:3000'+path,timeout=20) as r:return r.read()
state=json.loads((LAUNCH/'session.json').read_text('utf8'))
assert state['status']=='running' and state['verification'] is False
build_receipt=OUT/'build-existing-receipt.json';frozen_receipt=ROOT/'.runtime/skin-dry-calibrated-v2-clips-20261014/source-receipt.json'
assert build_receipt.stat().st_mtime>=frozen_receipt.stat().st_mtime
assert all(r['exitCode']==0 for r in json.loads(build_receipt.read_text('utf8'))['rows'])
processes={}
for name in ['launcher','frontend','backend','browser']:
    p=psutil.Process(state[name+'_pid']);cwd=Path(p.cwd()).resolve();args=p.cmdline()
    if name in ['frontend','backend']:assert cwd.is_relative_to(ROOT)
    if name=='browser':assert any(str(Path(state['profile'])).lower() in a.lower() for a in args)
    processes[name]=dict(pid=p.pid,processStarted=p.create_time(),workspace=str(cwd),executable=p.exe())
snapshot=json.loads((ROOT/'.runtime/skin-dry-calibrated-v2-clips-20261014/source-receipt.json').read_text('utf-8-sig'))
assert all(sha(ROOT/p)==h for p,h in snapshot.items())
build_id=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip()
assert build_id!='9DheD3msEFSOMhjMp-kK8'
assets={};pages={}
for page in ['/','/skin','/profile']:
    html=get(page).decode('utf8');scripts=set(re.findall(r'<script[^>]+src="([^"?]+)',html))
    for src in scripts:
        if not src.startswith('/_next/static/'):continue
        body=get(src);expected=ROOT/'apps/vehicle-app/.next'/src.removeprefix('/_next/')
        actual=hashlib.sha256(body).hexdigest();assert actual==sha(expected)
        assets[src]=actual
    pages[page]=dict(status=200,scripts=len(scripts),htmlSHA256=hashlib.sha256(html.encode()).hexdigest())
manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/guidance/manifest.json').read_text('utf8'))
# Verify the selected asset itself, not just a manifest URL.
clip='f1f50c0d6ded53ca4d20fc867a017b36c44741e1e68b4f6cf889da3f266bfa63.mp3'
audio=hashlib.sha256(get('/audio/guidance/'+clip)).hexdigest()
assert audio==sha(ROOT/'apps/vehicle-app/public/audio/guidance'/clip)=='46767d988f4712377ef3ea3bf42cbf3b82be28d35c0a37e5dd93225e6c73410a'
sources={p:sha(ROOT/p) for p in ['services/core-api/requirements.txt','services/core-api/product_dryness.py','services/core-api/material_component_features.py','services/core-api/native_dry_path.py','services/core-api/native_flake_support.py','services/core-api/skin_expression.py','services/core-api/models/dryness-calibrated-v3/config.json','services/core-api/models/dryness-calibrated-v3/head.json','services/core-api/models/dryness-calibrated-v3/encoder.onnx','services/core-api/models/dryness-calibrated-v3/encoder-parity.json','services/core-api/local_health.py','services/core-api/appearance_analysis.py','services/core-api/instant_appearance.py','services/core-api/contour_appearance.py','services/core-api/skin_eyewear.py','services/core-api/models/skin-eyewear-framefind-v1.onnx','services/core-api/models/skin-focused.json']}
assert all((ROOT/name).stat().st_mtime<=processes['backend']['processStarted'] for name in sources if name.endswith('.py'))
assert sources['services/core-api/models/skin-eyewear-framefind-v1.onnx']=='66f75c686974a04bf956d0ed6411315309afcabd36c400edec743953adafccb9'
browser_path=OUT/'eyewear-product-browser.json'
browser=json.loads(browser_path.read_text('utf8')) if browser_path.exists() else None
if browser:assert browser['buildId']==build_id
normal=json.loads((OUT/'normal-shortcut-cold-result.json').read_text('utf8'))
assert all(row['captureConditions']['skinEyewearModelHash']==sources['services/core-api/models/skin-eyewear-framefind-v1.onnx'] for rows in normal['measurements'].values() for row in rows)
assert normal['drynessRuntime']['headSHA256']==sources['services/core-api/models/dryness-calibrated-v3/head.json']=='7f13c7cb4eb65a3fb44abf062563ee3aff605a6ef9ff3271c5e32e206fedb8e1'
assert normal['drynessRuntime']['encoderSHA256']==sources['services/core-api/models/dryness-calibrated-v3/encoder.onnx']=='a93e5445326c8071cd4d013b6fde494d9054dd4842dacf97028ceaefc9eb1987'
geometry_path=OUT/'history-source-geometry.json'
geometry=json.loads(geometry_path.read_text('utf8')) if geometry_path.exists() else None
if browser:
    assert geometry and geometry['photoId']==browser['actualPhotoId'] and geometry['actualMapSourceCoordinates']==geometry['expectedAPISourceCoordinates']
receipt=dict(buildId=build_id,normalShortcutState=state,processes=processes,shortcutSHA256=sha(LAUNCH.parent/'TOGG Başlat.lnk'),launcherScriptSHA256=sha(LAUNCH/'start_togg.pyw'),buildReceiptSHA256=sha(build_receipt),frozenSourceReceiptSHA256=sha(frozen_receipt),frozenFrontendFiles=len(snapshot),sourceHashes=sources,servedJavascriptSHA256=assets,pages=pages,skinStartAudioSHA256=audio,actualBrowserReceiptSHA256=sha(browser_path) if browser else None,browserAcceptancePassed=bool(browser and geometry),historyGeometryReceiptSHA256=sha(geometry_path) if geometry else None,normalLoadedDrynessRuntime=normal['drynessRuntime'],userRecordsRead=False,verificationProfileUsedForTestRecords=True)
(OUT/'normal-shortcut-delivery.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(browserAcceptancePassed=bool(browser and geometry),buildId=build_id,servedJavascriptFiles=len(assets),normalShortcut=True,sourceFilesMatched=len(snapshot),audioMatched=True,modelMatched=True)))
