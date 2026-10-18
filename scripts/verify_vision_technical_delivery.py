"""Read-only loopback byte identity and protected checkout verification."""
import hashlib,json,re,subprocess,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'cdc-progress/vision-technical-closeout-20261017'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def get(url,data=None):
    request=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'} if data else {})
    with urllib.request.urlopen(request,timeout=15) as response:
        return response.read(),dict(response.headers)
def atomic(name,value):
    p=OUT/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf8');t.replace(p)
def main():
    receipt=json.loads((OUT/'build-receipt.json').read_text('utf-8-sig'))
    rows=[]
    for file in receipt['files']:
        path=ROOT/file['path'];assert digest(path.read_bytes())==file['sha256'],file['path']
        relative=path.relative_to(ROOT/'apps/vehicle-app')
        if relative.parts[:2]==('.next','static'):
            url='http://127.0.0.1:3306/_next/'+Path(*relative.parts[1:]).as_posix()
            raw,_=get(url);assert digest(raw)==file['sha256'],url
            rows.append(dict(path=file['path'],sha256=digest(raw),bytes=len(raw)))
    html,_=get('http://127.0.0.1:3306/vision')
    script_urls=re.findall(r'<script[^>]+src="([^\"]+)"',html.decode())
    assert script_urls and all(any(p['path'].replace('\\','/').endswith(u.split('?')[0].replace('/_next/','.next/')) for p in receipt['files']) for u in script_urls)
    asset_rows=[]
    for file in json.loads((OUT/'local-assets.json').read_text('utf-8-sig')):
        path=ROOT/file['path'];assert digest(path.read_bytes())==file['sha256'],file['path']
        if path.suffix=='.task':
            url='http://127.0.0.1:3306/'+path.relative_to(ROOT/'apps/vehicle-app/public').as_posix()
            raw,_=get(url);assert digest(raw)==file['sha256'];asset_rows.append(dict(path=file['path'],sha256=digest(raw),bytes=len(raw)))
    bank=json.loads((ROOT/'apps/vehicle-app/public/audio/vision-speech/manifest.json').read_text())
    voice=[]
    # Verify the existing bank first: this route must never reach voice generation.
    for code,entry in bank['entries'].items():
        raw=(ROOT/'apps/vehicle-app/public/audio/vision-speech'/entry['file']).read_bytes()
        assert digest(raw)==entry['sha256'] and len(raw)==entry['bytes']
    for code in ('prepare','right','left','first'):
        raw,headers=get('http://127.0.0.1:8306/api/vision/speech',json.dumps(dict(text=code,cloudConsent=True)).encode())
        normalized={k.lower():v for k,v in headers.items()}
        assert digest(raw)==bank['entries'][code]['sha256']
        assert normalized['x-tts-source']=='verified-fixed-cache'
        assert (normalized['x-tts-voice'],normalized['x-tts-rate'],normalized['x-tts-pitch'])==('tr-TR-AhmetNeural','-10%','-10Hz')
        voice.append(dict(code=code,bytes=len(raw),sha256=digest(raw),source=normalized['x-tts-source']))
    start=json.loads((OUT/'start.json').read_text('utf-8-sig'));protected=[]
    for directory,expected in start['protected'].items():
        head=subprocess.check_output(['git','-C',directory,'rev-parse','HEAD'],text=True).strip()
        status=subprocess.check_output(['git','-C',directory,'status','--short'],text=True).strip()
        assert head==expected['head'] and status==expected['status'].strip(),directory
        protected.append(dict(checkout=directory,head=head,statusUnchanged=True))
    for relative,sha in start['sourceTaskFiles'].items():assert digest((ROOT.parent/'attune-live-test'/relative).read_bytes())==sha
    value=dict(timeUTC=datetime.now(timezone.utc).isoformat(),BUILD_ID=receipt['BUILD_ID'],sourceAndServedJavaScript=rows,models=asset_rows,voice=voice,protected=protected,physicalUserAcceptance=False)
    atomic('served-protection-receipt.json',value)
    print('VERIFIED',receipt['BUILD_ID'],len(rows),'served JS files; 2 models; 4 bank responses; 4 protected checkouts')
if __name__=='__main__':main()
