"""First-ever native encoder request for a newly selected actual photo bitmap."""
import json,time,threading,hashlib
from pathlib import Path
import httpx,uvicorn
from verify_native_api_budget import app,events,ROOT,OUT
probe_path=OUT/'new-photo/00312529-probe.json';probe=json.loads(probe_path.read_text('utf8'));s=probe['snapshot']
assert probe['realMediaPipe'] and probe['poseCaptureCompleted'] and probe['quality']['isValid'] and probe['supportedAngles']
payload=dict(processingConsent=True,hostedProcessingConsent=False,photo=s['dataUrl'],photoId=s['photoId'],pose=s['angle'],meshes=s['meshes'],exclusions=s['exclusions'],landmarks=s['landmarks'],qualityValid=True,conditions=probe['conditions'],temporal=[s['landmarks']]*3)
path=OUT/'new-photo/00312529-payload.json';path.write_text(json.dumps(payload),'utf8')
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=18011,log_level='error'));thread=threading.Thread(target=server.run,daemon=True);thread.start();deadline=time.monotonic()+15
while not server.started:
    if time.monotonic()>deadline:raise RuntimeError('Isolated HTTP host failed')
    time.sleep(.05)
client=httpx.Client(timeout=50);data=json.dumps(payload).encode();start=time.monotonic();response=client.post('http://127.0.0.1:18011/api/local-health/skin',content=data,headers={'Content-Type':'application/json'});seconds=time.monotonic()-start;actual=response.json()
if response.status_code==200:(OUT/'new-photo/00312529-native-result.json').write_text(json.dumps(actual),'utf8')
receipt=dict(source='00312529',sourceSHA256=json.loads((OUT/'new-photo-selection.json').read_text('utf8'))[0]['sha256'],photoId=payload['photoId'],payloadSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),realBrowserMediaPipe=True,automaticCapture=True,newSourceNeverPreviouslyEncoderBenchmarked=True,firstRequestNoPhotoCache=True,actualHTTP=True,isolatedResearchNativeAnalyzer=True,normalProductEnabled=False,status=response.status_code,seconds=seconds,worker=events[-1],stages=events[-1].get('profile'),classifier=actual.get('nativeMetadata'),scores={k:v['value'] for k,v in actual.get('measurements',{}).items()},detail=actual.get('detail'))
(OUT/'new-photo-request.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True);client.close();server.should_exit=True;thread.join(10);assert not thread.is_alive()
