"""Application-owned single-request transport for the pinned SDK wire contract.
No endpoint discovery/fallback, global patch, background Future or network retry.
"""
import http.client,json,math,os,socket,time
from pathlib import Path
from urllib.parse import urlencode,urlsplit

MODEL_ID='skin-type-axavj/1'
ENDPOINT='https://serverless.roboflow.com/'+MODEL_ID
CLASSES=('normal','dry','oily','combination')
CONFIG_PATH=Path(__file__).parent/'models/skin-type-hosted.json'

class HostedTransportError(Exception):
    def __init__(self,reason):super().__init__(reason);self.reason=reason

class BoundedHTTPTransport:
    def __init__(self,connect_timeout=3.,read_timeout=15.,*,loopback_test_url=None):
        self.connect_timeout=connect_timeout;self.read_timeout=read_timeout
        self.target=ENDPOINT
        if loopback_test_url is not None:
            p=urlsplit(loopback_test_url)
            if p.scheme!='http' or p.hostname not in ('127.0.0.1','localhost') or p.path!='/'+MODEL_ID:raise ValueError('TEST_ENDPOINT_NOT_LOOPBACK')
            self.target=loopback_test_url

    def execute(self,request):
        if request.url!=ENDPOINT or request.payload is not None or 'api_key' in (request.parameters or {}):raise HostedTransportError('HOSTED_REQUEST_CONTRACT')
        headers=dict(request.headers or {})
        if not headers.get('Authorization','').startswith('Bearer '):raise HostedTransportError('HOSTED_REQUEST_CONTRACT')
        headers['Accept-Encoding']='identity'
        body=request.data.encode('ascii') if isinstance(request.data,str) else request.data
        if not isinstance(body,bytes) or len(body)>3*1024**2:raise HostedTransportError('HOSTED_IMAGE_LIMIT')
        target=urlsplit(self.target);path=target.path+'?'+urlencode(request.parameters or {},doseq=True)
        kind=http.client.HTTPSConnection if target.scheme=='https' else http.client.HTTPConnection
        connection=kind(target.hostname,target.port,timeout=self.connect_timeout)
        started=time.monotonic();deadline=started+self.connect_timeout+self.read_timeout
        try:
            connection.connect();sock=connection.sock
            sock.settimeout(min(self.read_timeout,max(.001,deadline-time.monotonic())))
            connection.request('POST',path,body=body,headers=headers)
            response=connection.getresponse()
            if response.status!=200:
                code={401:'HOSTED_AUTH_FAILED',403:'HOSTED_AUTH_FAILED',429:'HOSTED_RATE_LIMIT_EXCEEDED',404:'HOSTED_MODEL_NOT_FOUND'}.get(response.status,'HOSTED_CALL_FAILED')
                raise HostedTransportError(code)
            length=response.getheader('Content-Length')
            if length is not None and (not length.isdigit() or int(length)>65536):raise HostedTransportError('HOSTED_RESPONSE_LIMIT')
            chunks=[];size=0
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise HostedTransportError('HOSTED_TIMEOUT')
                sock.settimeout(min(self.read_timeout,remaining))
                chunk=response.read1(min(4096,65537-size))
                if not chunk:break
                size+=len(chunk)
                if size>65536:raise HostedTransportError('HOSTED_RESPONSE_LIMIT')
                chunks.append(chunk)
                if response.isclosed():break
            # SDK consumes the response JSON after this owned socket is closed.
            from requests import Response
            result=Response();result.status_code=200;result._content=b''.join(chunks);result.headers=dict(response.getheaders())
            return result
        except HostedTransportError:raise
        except (TimeoutError,socket.timeout):raise HostedTransportError('HOSTED_TIMEOUT') from None
        except (OSError,http.client.HTTPException):raise HostedTransportError('HOSTED_NETWORK_ERROR') from None
        finally:connection.close()

def get_inference_client(api_key,transport=None):
    from inference_sdk import InferenceConfiguration,InferenceHTTPClient
    class BoundedClient(InferenceHTTPClient):
        def _execute_infer_from_api_request(self,requests_data):
            if len(requests_data)!=1:raise HostedTransportError('HOSTED_REQUEST_CONTRACT')
            return [(transport or BoundedHTTPTransport()).execute(requests_data[0])]
    client=BoundedClient(api_url='https://serverless.roboflow.com',api_key=api_key)
    client.configure(InferenceConfiguration(api_key_transport='header',workflow_run_retries_enabled=False,disable_active_learning=True))
    return client

def unavailable(reason,elapsed=0.):
    return dict(value=None,quality='insufficient',confidence=None,methodVersion='hosted-roboflow-'+MODEL_ID,provider='roboflow',providerModelId=MODEL_ID,inferenceKind='hosted',modelHash=None,limitationCode=reason,inferenceMs=elapsed)

def parse_hosted_type_response(data,model_id=MODEL_ID,elapsed=0.):
    if model_id!=MODEL_ID or not isinstance(data,dict):return None
    resolved=data.get('resolved_model',{})
    if not isinstance(resolved,dict) or resolved.get('model_id',MODEL_ID)!=MODEL_ID:return None
    if data.get('multi_label') or data.get('multilabel') or len(data.get('predicted_classes',[]))>1:return None
    candidates={};predictions=data.get('predictions')
    if isinstance(predictions,dict):predictions=[dict(class_name=c,confidence=(v.get('confidence') if isinstance(v,dict) else v)) for c,v in predictions.items()]
    if predictions is not None:
        if not isinstance(predictions,list) or not 1<=len(predictions)<=4:return None
        for p in predictions:
            if not isinstance(p,dict):return None
            c=str(p.get('class',p.get('class_name',''))).strip().lower();v=p.get('confidence')
            if c not in CLASSES or c in candidates or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1:return None
            candidates[c]=float(v)
    top=data.get('top');conf=data.get('confidence')
    if top is not None:top=str(top).strip().lower()
    if conf is not None and (isinstance(conf,bool) or not isinstance(conf,(int,float)) or not math.isfinite(conf) or not 0<=conf<=1):return None
    if candidates:
        winner=max(candidates,key=candidates.get);support=candidates[winner]
        if sum(candidates.values())>1.35 or sum(v>=.6 for v in candidates.values())>1:return None
        if top is not None and top!=winner or conf is not None and abs(conf-support)>.05:return None
    elif top in CLASSES and conf is not None:winner,support=top,float(conf)
    else:return None
    if support<.5:return unavailable('LOW_MODEL_SUPPORT',elapsed)
    result=unavailable(None,elapsed);result.update(value=winner,confidence=support,quality='valid')
    package=resolved.get('model_package_id')
    if isinstance(package,str) and 0<len(package)<=128:result['providerModelPackageId']=package
    return result

def infer_hosted_type(crop_bgr,processing_consent=False):
    if processing_consent is not True:return unavailable('HOSTED_INFERENCE_PERMISSION_DENIED')
    try:config=json.loads(CONFIG_PATH.read_text('utf8'))
    except (OSError,ValueError):return unavailable('HOSTED_CONFIG_UNAVAILABLE')
    if config.get('enabled') is not True or config.get('modelId')!=MODEL_ID or config.get('classOrder')!=list(CLASSES) or config.get('connectTimeoutSeconds')!=3 or config.get('readTimeoutSeconds')!=15:return unavailable('HOSTED_CONFIG_DISABLED')
    key=os.environ.get('ATTUNE_ROBOFLOW_API_KEY') or os.environ.get('ROBOFLOW_API_KEY')
    if not key:return unavailable('HOSTED_CREDENTIALS_MISSING')
    start=time.perf_counter()
    try:
        data=get_inference_client(key).infer(crop_bgr,model_id=MODEL_ID)
        elapsed=(time.perf_counter()-start)*1000
        return parse_hosted_type_response(data,MODEL_ID,elapsed) or unavailable('HOSTED_INVALID_RESPONSE',elapsed)
    except HostedTransportError as e:return unavailable(e.reason,(time.perf_counter()-start)*1000)
    except ValueError:return unavailable('HOSTED_INVALID_RESPONSE',(time.perf_counter()-start)*1000)
    except Exception:return unavailable('HOSTED_CALL_FAILED',(time.perf_counter()-start)*1000)
