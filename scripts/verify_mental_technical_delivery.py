"""Read-only final identity check. No conversation, summary or TTS generation."""
import hashlib,json,re,subprocess,urllib.request
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/mental-technical-closeout-20261017'
def sha(data):return hashlib.sha256(data).hexdigest()
def read(p):return json.loads(p.read_text('utf-8-sig'))
def get(url):
 with urllib.request.urlopen(url,timeout=15) as r:return r.read()
def main():
 build=read(OUT/'build-receipt.json');rows=[]
 for file in build['files']:
  path=ROOT/file['path'];assert sha(path.read_bytes())==file['sha256'],file['path']
  if '.next/static/' in file['path'].replace('\\','/'):
   url='http://127.0.0.1:3307/_next/'+path.relative_to(ROOT/'apps/vehicle-app/.next').as_posix();raw=get(url);assert sha(raw)==file['sha256']
   assert not re.search(rb'sk-[A-Za-z0-9_-]{30,}',raw),'Unexpected credential-shaped bundle data'
   assert b'CONTROLLED_PROVIDER_SEAM' not in raw and b'noncredential-test-fixture' not in raw
   rows.append(dict(path=file['path'],sha256=sha(raw),bytes=len(raw)))
 html=get('http://127.0.0.1:3307/mental').decode();scripts=re.findall(r'<script[^>]+src="([^\"]+)"',html)
 assert scripts and all(any(f['path'].replace('\\','/').endswith(url.split('?')[0].replace('/_next/','.next/')) for f in build['files']) for url in scripts)
 assets=[]
 for file in read(OUT/'local-assets.json'):
  path=ROOT/file['path'];assert sha(path.read_bytes())==file['sha256']
  if path.suffix=='.mp3' and file['sha256'] in ('92f143f29631a1deb3555adbcd551a03218f21c4f7eb81946dba2ca5df2ea943','ecf987d8da58d5f83488da5ae6e899010966d2d0a6745f223283cbf6629a57d1'):
   raw=get('http://127.0.0.1:3307/'+path.relative_to(ROOT/'apps/vehicle-app/public').as_posix());assert sha(raw)==file['sha256'];assets.append(file)
 assert len(assets)==2
 start=read(OUT/'start.json');protected=[]
 for directory,expected in start['protected'].items():
  head=subprocess.check_output(['git','-C',directory,'rev-parse','HEAD'],text=True).strip();status=subprocess.check_output(['git','-C',directory,'status','--short'],text=True).strip()
  assert head==expected['head'] and status==expected['status'].strip(),directory
  protected.append(dict(checkout=directory,head=head,statusUnchanged=True))
 for relative,digest in start['sourceTaskFiles'].items():assert sha((ROOT.parent/'attune-live-test'/relative).read_bytes())==digest
 for relative in ('apps/vehicle-app/src/app/mental/page.tsx','services/core-api/mental_provider.py','services/core-api/openai_client.py','services/core-api/tts_profiles.py','services/core-api/vision_speech.py'):
  before=subprocess.check_output(['git','show',start['startCommit']+':'+relative]).decode().replace('\r\n','\n');assert (ROOT/relative).read_text('utf8')==before,relative
 provider=json.loads(get('http://127.0.0.1:8307/api/mental/provider-status'));assert provider['isLiveLLM'] and provider['providerName']=='LIVE_OPENAI (gpt-4o-mini)'
 try:get('http://127.0.0.1:8307/__test__/ledger');raise AssertionError('Fixture route still present')
 except urllib.error.HTTPError as error:assert error.code==404
 backend=json.loads(get('http://127.0.0.1:8307/api/mental/sessions'));assert backend==[],'Unexpected isolated backend records'
 old=read(OUT/'controller-build-receipt.json');old_files={r['path']:r['sha256'] for r in old['files']};controller='apps\\vehicle-app\\src\\utils\\useMentalConversation.ts';assert old_files[controller]==next(r['sha256'] for r in build['files'] if r['path']==controller)
 value=dict(timeUTC=datetime.now(timezone.utc).isoformat(),BUILD_ID=build['BUILD_ID'],controllerEvidenceBuild=old['BUILD_ID'],identicalControllerSource=True,servedJavaScript=rows,existingEmelBank=assets,provider=provider,protected=protected,productionTestRoutesAbsent=True,backendStoredRecords=len(backend),physicalUserAcceptance=False)
 tmp=OUT/'served-protection.tmp';tmp.write_text(json.dumps(value,indent=2),'utf8');tmp.replace(OUT/'served-protection-receipt.json');print('VERIFIED',build['BUILD_ID'],len(rows),'JS, 2 Emel assets, 5 protected checkouts; no generated requests')
if __name__=='__main__':main()
