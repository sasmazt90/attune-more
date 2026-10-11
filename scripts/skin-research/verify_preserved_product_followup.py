"""Read-only normal shortcut/source/build proof plus one licensed FRONT API.

Does not edit browser history, records, camera, microphone, voice or app state.
Does not restart owned services or close any Chrome window.
"""
import hashlib,json,subprocess,urllib.request
from pathlib import Path
import psutil,pythoncom
from win32com.shell import shell
from diagnose_followup import NEW,write
from prepare_focused_data import ROOT
HOME=Path(r'C:\Users\PC\Desktop\YENİ İŞ\Applications\7. TOGG\.launcher')
def get(url):
    with urllib.request.urlopen(url,timeout=8) as r:return r.read()
def main():
    old=json.loads((ROOT/'audit-results/all-health-20261010/delivery.json').read_text());build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip();assert build==old['buildId']
    files=old['committedSourcesMatch']
    for file in files:
        actual=(ROOT/file).read_bytes();expected=subprocess.check_output(['git','show',old['sha']+':'+file],cwd=ROOT)
        # Match canonical Git text while retaining the existing CRLF files.
        if Path(file).suffix.lower() in ['.py','.pyw','.tsx','.ts','.css','.json','.md','.txt']:
            actual=actual.replace(b'\r\n',b'\n');expected=expected.replace(b'\r\n',b'\n')
        assert actual==expected,file
    link=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink);link.QueryInterface(pythoncom.IID_IPersistFile).Load(str(HOME.parent/'TOGG Başlat.lnk'));assert Path(link.GetArguments().strip('"')).samefile(HOME/'start_togg.pyw')
    session=json.loads((HOME/'session.json').read_text());assert session['status']=='running';assert Path(psutil.Process(session['frontend_pid']).cwd()).resolve()==ROOT/'apps/vehicle-app';assert str(ROOT/'services/core-api').lower() in ' '.join(psutil.Process(session['backend_pid']).cmdline()).lower()
    get('http://127.0.0.1:3000/skin')
    # Every currently served chunk must be the preserved build's bytes.
    chunk_checks={}
    for url in old['servedChunksMatch']:
        path=ROOT/'apps/vehicle-app/.next'/url.removeprefix('/_next/');chunk_checks[url]=hashlib.sha256(get('http://127.0.0.1:3000'+url)).hexdigest()==hashlib.sha256(path.read_bytes()).hexdigest()
    assert all(chunk_checks.values());health=json.loads(get('http://127.0.0.1:8000/api/health'))
    snapshot=dict(buildId=build,frontendSourceCommit=old['sha'],branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),shortcutTargetMatches=True,normalFrontendOwned=True,normalBackendOwned=True,sourceBytesPreserved=True,servedChunksMatch=chunk_checks,normalHistoryWritten=False,paidCalls=0,physicalAcceptance=False,health=health)
    for index in [0,1,3,5]:
        payload=json.loads((ROOT/f'audit-results/all-health-20261010/natural-skin/{index}-payload-private.json').read_text());payload['processingConsent']=True
        req=urllib.request.Request('http://127.0.0.1:8000/api/local-health/skin',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=60) as r:result=json.loads(r.read())
        write(f'product/front-{index}-actual-api.json',result);snapshot.setdefault('samples',[]).append(dict(index=index,source='previously licensed NASA FRONT portrait' if index<2 else 'previously exposed same-person licensed video frame; not separate person or high-detail three-pose acceptance',captureId=payload['photoId'],skinType=result['general']['skinType'],measurements=result['general']['measurements'],modelDiagnostics=result.get('modelDiagnostics'),actualNormalAPI=True,independentFinal=False))
    write('product/preserved-delivery.json',snapshot);print(json.dumps(dict(buildId=build,sourcePreserved=True,normalAPI=True,measurements=[[(v['id'],v['value'],v['quality']) for v in s['measurements']] for s in snapshot['samples']]),indent=2),flush=True)
if __name__=='__main__':main()
