from pathlib import Path
import hashlib, json, os, re, subprocess, urllib.request
import psutil, pythoncom
from win32com.shell import shell

root = Path.cwd()
home = Path(r'C:\Users\PC\Desktop\YENİ İŞ\Applications\7. TOGG')
link = pythoncom.CoCreateInstance(shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink)
link.QueryInterface(pythoncom.IID_IPersistFile).Load(str(home / 'TOGG Başlat.lnk'))
target = link.GetPath(shell.SLGP_RAWPATH)[0]
argument = link.GetArguments().strip('"')
launcher = home / '.launcher/start_togg.pyw'
session = json.loads((home / '.launcher/session.json').read_text())
build = (root / 'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
def fetch(url):
    with urllib.request.urlopen(url, timeout=10) as response: return response.read()
def digest(data): return hashlib.sha256(data).hexdigest()

chunks = {}
for route in ['/', '/vision', '/skin', '/dental', '/hearing', '/profile', '/mental', '/privacy']:
    html = fetch('http://127.0.0.1:3000' + route).decode()
    for path in re.findall(r'<script[^>]+src="([^"]+)"', html):
        if path.startswith('/_next/static/'):
            chunks[path] = digest(fetch('http://127.0.0.1:3000' + path)) == digest((root / 'apps/vehicle-app/.next' / path.removeprefix('/_next/').split('?')[0]).read_bytes())
sources = {}
for path in subprocess.check_output(['git','ls-files','apps/vehicle-app/src','services/core-api','scripts/windows-launcher'],text=True).splitlines():
    committed = subprocess.check_output(['git', 'show', 'HEAD:' + path])
    sources[path] = committed.replace(b'\r\n', b'\n') == (root / path).read_bytes().replace(b'\r\n', b'\n')

# Installation substitutes only ROOT because the launcher lives outside the checkout.
expected_launcher = (root / 'scripts/windows-launcher/start_togg.pyw').read_text('utf8').replace('ROOT = Path(__file__).resolve().parents[2]', 'ROOT = Path(' + repr(str(root)) + ')')

proof = {'sha': sha, 'buildId': build, 'shortcutTarget': target, 'launcherIdentity': os.path.samefile(argument, launcher), 'launcherMatchesInstalledRootSource': launcher.read_text('utf8') == expected_launcher, 'session': session, 'frontendRootMatches': os.path.samefile(psutil.Process(session['frontend_pid']).cwd(), root / 'apps/vehicle-app'), 'normalBrowserOwned': session['status'] == 'running' and not session.get('verification') and any(session['profile'] in arg for arg in psutil.Process(session['browser_pid']).cmdline()), 'buildManifestMatches': fetch('http://127.0.0.1:3000/_next/static/' + build + '/_buildManifest.js') == (root / 'apps/vehicle-app/.next/static' / build / '_buildManifest.js').read_bytes(), 'servedChunksMatch': chunks, 'committedSourcesMatch': sources, 'sourcePredatesBuild': all((root / path).stat().st_mtime <= (root / 'apps/vehicle-app/.next/BUILD_ID').stat().st_mtime for path in sources)}

assets={}
guidance=json.loads(fetch('http://127.0.0.1:3000/audio/guidance/manifest.json'))
bank=json.loads(fetch('http://127.0.0.1:3000/audio/hearing-bank/manifest.json'))
for key,entry in guidance['entries'].items():
    expected='tr-TR-EmelNeural' if key.startswith('mental') else 'tr-TR-AhmetNeural'
    assert entry['voice']==expected and entry['rate']=='-10%' and entry['pitch']=='-10Hz'
for entry in [*guidance['entries'].values(),*bank['digits'],bank['noise']]:
    url=entry['url'];raw=fetch('http://127.0.0.1:3000'+url)
    assets[url]={'sha256':digest(raw),'matchesManifest':digest(raw)==entry['sha256'],'matchesDisk':raw==(root/'apps/vehicle-app/public'/url.lstrip('/')).read_bytes()}
assert all(v['matchesManifest'] and v['matchesDisk'] for v in assets.values())
for folder in ('audio/vision-speech','mediapipe'):
    manifest=json.loads(fetch('http://127.0.0.1:3000/'+folder+'/manifest.json'))
    entries=manifest['files'] if folder=='mediapipe' else manifest['entries'].values()
    for entry in entries:
        path=entry['path'] if folder=='mediapipe' else entry['file']
        url='/'+folder+'/'+path;raw=fetch('http://127.0.0.1:3000'+url)
        assets[url]={'sha256':digest(raw),'matchesManifest':digest(raw)==entry['sha256'],'matchesDisk':raw==(root/'apps/vehicle-app/public'/folder/path).read_bytes()}
        assert assets[url]['matchesManifest'] and assets[url]['matchesDisk']
        if folder=='audio/vision-speech':assert (entry['voice'],entry['rate'],entry['pitch'])==('tr-TR-AhmetNeural','-10%','-10Hz')
model=root/'services/core-api/models/dental-yolox-s.onnx';model_manifest=json.loads((model.with_suffix('.json')).read_text('utf8'))
assert digest(model.read_bytes())==model_manifest['modelHash']
face_url='https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
face_hash=digest(fetch('http://127.0.0.1:3000/mediapipe/models/face_landmarker.task'));assert face_hash==digest((root/'audit-results/skin-capabilities-20261008/scin/face_landmarker.task').read_bytes())
assert psutil.Process(session['backend_pid']).create_time()>=max((root/p).stat().st_mtime for p in sources if p.startswith('services/core-api/'))
extra={'assets':assets,'guidanceManifestHash':digest(fetch('http://127.0.0.1:3000/audio/guidance/manifest.json')),'bankManifestHash':digest(fetch('http://127.0.0.1:3000/audio/hearing-bank/manifest.json')),'dentalModelSHA256':model_manifest['modelHash'],'dentalThreshold':model_manifest['confidenceThreshold'],'faceModelSHA256':face_hash,'faceModelURL':face_url,'backendStartedAfterSourceEdits':True}
skin_manifest=root/'services/core-api/models/skin-focused.json'
if skin_manifest.exists():
    registry=json.loads(skin_manifest.read_text('utf8'));skin_models={}
    for task,entry in registry['models'].items():
        accepted=bool(entry['accepted']);file=root/'services/core-api/models'/entry['file'] if accepted else None
        if accepted:assert file and digest(file.read_bytes())==entry['sha256']
        else:assert entry['file'] is None,'Rejected research weight cannot be an installed product model'
        skin_models[task]={'accepted':accepted,'modelSHA256':entry['sha256'],'file':entry['file'],'installedHashMatches':bool(file and digest(file.read_bytes())==entry['sha256']) if accepted else None}
    extra.update(skinRegistrySHA256=digest(skin_manifest.read_bytes()),skinModels=skin_models)

proof.update(extra)
out = root / 'audit-results/all-health-20261010/delivery.json'
out.write_text(json.dumps(proof, ensure_ascii=False, indent=2), 'utf8')
print(json.dumps({k:proof[k] for k in ['sha','buildId','normalBrowserOwned','buildManifestMatches','sourcePredatesBuild','backendStartedAfterSourceEdits']},ensure_ascii=True))
assert all(proof[key] for key in ['launcherIdentity','launcherMatchesInstalledRootSource','frontendRootMatches','normalBrowserOwned','buildManifestMatches','sourcePredatesBuild'])
assert chunks and all(chunks.values())
assert sources and all(sources.values())
