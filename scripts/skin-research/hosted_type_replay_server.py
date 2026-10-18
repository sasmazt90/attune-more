"""Isolated backend/loopback provider for recorded-response browser acceptance.
Never contacts Roboflow, changes normal config, or loads the real credential.
Replayed labels test routing/UI/history, not accuracy of the fixture subject.
"""
import base64,hashlib,json,os,sys,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
os.environ['ATTUNE_LOAD_LOCAL_ENV']='0';os.environ['ATTUNE_ROBOFLOW_API_KEY']='local-contract-test-token';os.environ.pop('ROBOFLOW_API_KEY',None)
import hosted_skin_type as H
import cv2,numpy as np

records=json.loads((ROOT.parent/'attune-antigravity-skin/audit-results/skin-type-access-probe.json').read_text('utf8'))
responses={r['true_class']:r['raw_response'] for r in records if r.get('success') and r.get('model_id')==H.MODEL_ID}
assert set(responses)==set(H.CLASSES)
state={'mode':'normal','calls':[]}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,value,status=200):
  raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers()
  try:self.wfile.write(raw)
  except (BrokenPipeError,ConnectionError):pass
 def do_GET(self):self.send({'mode':state['mode'],'calls':state['calls'],'newLiveHostedRequests':0})
 def do_POST(self):
  body=self.rfile.read(int(self.headers.get('Content-Length',0)))
  if self.path=='/control':
   mode=json.loads(body)['mode'];assert mode in (*H.CLASSES,'401','429','timeout','slow');state['mode']=mode;self.send({'mode':mode});return
  assert self.path.startswith('/'+H.MODEL_ID+'?') and 'api_key' not in self.path
  assert self.headers.get('Authorization')=='Bearer local-contract-test-token'
  raw=base64.b64decode(body);photo=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR);assert photo is not None
  mode=state['mode'];state['calls'].append({'mode':mode,'cropJPEG_SHA256':hashlib.sha256(raw).hexdigest(),'cropSize':[photo.shape[1],photo.shape[0]],'headerAuthentication':True,'oneRequest':True})
  if mode in ('401','429'):self.send({'message':'contract-test failure'},int(mode));return
  if mode=='timeout':time.sleep(16);self.send(responses['normal']);return
  if mode=='slow':time.sleep(2);self.send(responses['normal']);return
  self.send(responses[mode])

provider=ThreadingHTTPServer(('127.0.0.1',0),Handler);provider.daemon_threads=True;threading.Thread(target=provider.serve_forever,daemon=True).start()
original=H.get_inference_client
H.get_inference_client=lambda key:original(key,H.BoundedHTTPTransport(loopback_test_url=f'http://127.0.0.1:{provider.server_port}/'+H.MODEL_ID))
import main,uvicorn
output=ROOT/'audit-results/skin-type-integration-20261012';output.mkdir(exist_ok=True,parents=True)
(output/'replay-server.json').write_text(json.dumps({'backendPort':8103,'providerPort':provider.server_port,'pid':os.getpid(),'recordedResponseSourceCommit':'8b9db4649148d421c4495c657e76273a6f1cd006','recordedResponseSourceSHA256':hashlib.sha256((ROOT.parent/'attune-antigravity-skin/audit-results/skin-type-access-probe.json').read_bytes()).hexdigest(),'liveHostedCalls':0,'realCredentialLoaded':False}),encoding='utf8')
server=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=8103,log_level='warning'))
def stop():sys.stdin.buffer.readline();server.should_exit=True
threading.Thread(target=stop,daemon=True).start()
try:server.run()
finally:provider.shutdown();provider.server_close()
