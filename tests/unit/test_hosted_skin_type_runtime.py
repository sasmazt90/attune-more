"""Actual loopback HTTP and consent gates; no paid/network provider calls."""
import json,sys,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import hosted_skin_type as H

class Server:
 def __init__(self,status=200,delay=0,dribble=False):
  self.calls=[];owner=self
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_POST(self):
    body=self.rfile.read(int(self.headers.get('Content-Length',0)));owner.calls.append(dict(path=self.path,header=self.headers.get('Authorization'),body=body))
    time.sleep(delay);payload=json.dumps(dict(top='normal',confidence=.93)).encode()
    try:
     self.send_response(status);self.send_header('Content-Length',str(len(payload)));self.end_headers()
     if dribble:
      for byte in payload:self.wfile.write(bytes([byte]));self.wfile.flush();time.sleep(.025)
     else:self.wfile.write(payload)
    except (BrokenPipeError,ConnectionError):pass
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def __enter__(self):return self
 def __exit__(self,*args):self.server.shutdown();self.server.server_close()
 def client(self,read=.3):return H.get_inference_client('unit-test-not-a-credential',H.BoundedHTTPTransport(.2,read,loopback_test_url=f'http://127.0.0.1:{self.server.server_port}/'+H.MODEL_ID))

def test_wire_contract_header_only_and_one_call():
 with Server() as s:
  result=s.client().infer(np.zeros((32,32,3),np.uint8),model_id=H.MODEL_ID)
 assert result['top']=='normal' and len(s.calls)==1
 call=s.calls[0];assert call['header']=='Bearer unit-test-not-a-credential' and 'api_key' not in call['path']
 assert 'disable_active_learning=True' in call['path'] and call['body'].startswith(b'/9j/')

@pytest.mark.parametrize('status',[401,403,429,503,504,302])
def test_status_never_retries_or_falls_back(status):
 with Server(status=status) as s:
  with pytest.raises(H.HostedTransportError):s.client().infer(np.zeros((32,32,3),np.uint8),model_id=H.MODEL_ID)
 assert len(s.calls)==1

def test_real_socket_read_timeout_and_dribble_deadline():
 for delay,dribble in [(.4,False),(0,True)]:
  with Server(delay=delay,dribble=dribble) as s:
   started=time.monotonic()
   with pytest.raises(H.HostedTransportError,match='HOSTED_TIMEOUT'):s.client(read=.1).infer(np.zeros((32,32,3),np.uint8),model_id=H.MODEL_ID)
   assert time.monotonic()-started<.7
  assert len(s.calls)==1

def test_permission_revocation_is_checked_before_any_client(monkeypatch):
 monkeypatch.setenv('ATTUNE_ROBOFLOW_API_KEY','not-a-real-key')
 monkeypatch.setattr(H,'get_inference_client',lambda *a,**k:pytest.fail('No consent must never construct network client'))
 for consent in [False,None,'true',1]:assert H.infer_hosted_type(np.zeros((30,30,3),np.uint8),consent)['limitationCode']=='HOSTED_INFERENCE_PERMISSION_DENIED'

@pytest.mark.parametrize('label',H.CLASSES)
def test_four_classes_keep_provider_identity_without_fabricated_hash(label):
 r=H.parse_hosted_type_response(dict(top=label,confidence=.9));assert r['value']==label and r['modelHash'] is None and r['providerModelId']==H.MODEL_ID

@pytest.mark.parametrize('response',[dict(top='other',confidence=.9),dict(top='normal',confidence=float('nan')),dict(predictions=[{'class':'normal','confidence':.9},{'class':'other','confidence':.1}]),dict(top='dry',confidence=.9,predictions=[{'class':'normal','confidence':.9}]),dict(predictions={'dry':.7,'normal':.7})])
def test_invalid_response_cannot_be_a_class(response):assert H.parse_hosted_type_response(response) is None

def test_resolved_provider_identity_is_checked_without_inventing_weights():
 assert H.parse_hosted_type_response(dict(top='normal',confidence=.9,resolved_model={'model_id':'other/1'})) is None
 r=H.parse_hosted_type_response(dict(top='normal',confidence=.9,resolved_model={'model_id':H.MODEL_ID,'model_package_id':'recorded-package'}))
 assert r['providerModelPackageId']=='recorded-package' and r['modelHash'] is None

def test_degrees_remain_independent_of_hosted_failure(monkeypatch):
 import skin_models as M
 class Session:
  def run(self,*args):return [np.array([[3.]],np.float32)]
 monkeypatch.setattr(M,'load',lambda:dict(sessions={'degrees':dict(session=Session(),loadMs=0,metadata=dict(sha256='a'*64,version='preserved',targets=['redness'],acceptedTargets=['redness']))}))
 monkeypatch.setattr(M,'infer_hosted_type',lambda *args:H.unavailable('HOSTED_TIMEOUT'))
 p=[dict(x=.2+(i%2)*.6,y=.2+(i%3)*.2) for i in range(468)];result=M.infer(np.zeros((320,320,3),np.uint8),p,True,True)
 assert result['degrees']['redness']['value']==60 and result['skinType']['value'] is None
