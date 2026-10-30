"""Admitted dryness identity, atomic replacement and source-bound expression."""
import copy,sys,asyncio,time
from pathlib import Path
import pytest,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import product_dryness as D,skin_expression as E
from native_material_budget import NativeRequestStopped

def observation(photo='a'):
 return dict(photoId=photo,version=E.VERSION,scores={k:.01 for k in E.REQUIRED})

def test_expression_requires_complete_source_bound_finite_support():
 obs=observation()
 assert E.reason(obs,'a',.01,-.12,.4) is None
 assert E.reason(None,'a',.01,-.12,.4)=='EXPRESSION_SMILE'
 assert E.reason(None,'a',.01,0,.4)=='EXPRESSION_SUPPORT_UNAVAILABLE'
 for changed in [dict(photoId='b'),dict(version='future'),dict(scores={}),dict(scores={**obs['scores'],'jawOpen':float('nan')}),dict(scores={**obs['scores'],'jawOpen':True})]:
  with pytest.raises(ValueError):E.validate({**obs,**changed},'a')
 for name,expected in [('jawOpen','OPEN_MOUTH'),('mouthSmileLeft','SMILE'),('mouthFrownLeft','FROWN'),('cheekPuff','CHEEK_PUFF'),('mouthPressLeft','MOUTH_PRESS'),('mouthPucker','PUCKER')]:
  o=observation();o['scores'][name]=.8
  assert E.reason(o,'a',.01,-.12,.3)=='EXPRESSION_'+expected
 assert E.reason(observation(),'a',.11,0,.4)=='EXPRESSION_OPEN_MOUTH'
 broad=observation();broad['scores']['mouthSmileLeft']=.8
 assert E.reason(broad,'a',.01,-.12,.42)=='EXPRESSION_SMILE'
 broad=observation();broad['scores'].update(mouthPucker=.8,mouthFunnel=.3)
 assert E.reason(broad,'a',.01,-.12,.42)=='EXPRESSION_PUCKER'
 broad['scores']['mouthFunnel']=.07
 assert E.reason(broad,'a',.01,-.12,.42) is None

def test_head_asset_tampering_fails_without_fallback(tmp_path,monkeypatch):
 import shutil
 for p in D.BASE.iterdir():shutil.copyfile(p,tmp_path/p.name)
 (tmp_path/'head.json').write_text('{}')
 monkeypatch.setattr(D,'BASE',tmp_path);monkeypatch.setattr(D,'_runtime',None)
 with pytest.raises(D.DrynessModelUnavailable):D.runtime(lambda:None)
 assert D._runtime is None

def test_replace_has_one_support_and_unavailable_is_not_zero():
 def row(region,value):return dict(id='dry',region=region,value=value,quality='valid' if value is not None else 'insufficient',limitationCode=None if value is not None else 'CAPTURE_QUALITY',normalizationVersion='old',methodVersion='appearance-cv-6',modelHash=None,components={},evaluatedArea={},localMap=None)
 old=dict(photoId='a',sourceWidth=100,sourceHeight=100,measurements={'chin':[row('chin',5),dict(id='tone',value=3,quality='valid',limitationCode=None,normalizationVersion='tone-v1',methodVersion='appearance-cv-6',modelHash=None,evaluatedArea={},localMap=None)]},maps={'chin:dry':{'old':True},'chin:tone':{'criterion':'tone','region':'chin'}},general={'measurements':[row('overview',6)]})
 native=dict(photoId='a',sourceWidth=100,sourceHeight=100,measurements={'chin':row('chin',None)},maps={},general=row('overview',None),nativeMetadata={})
 from skin_measurement_contract import attach_result_receipts
 old=attach_result_receipts(old)
 actual=D.replace_dryness(copy.deepcopy(old),native,'identity')
 assert actual['measurements']['chin'][0]['value'] is None and actual['general']['measurements'][0]['value'] is None
 assert 'chin:dry' not in actual['maps'] and actual['measurements']['chin'][1]==old['measurements']['chin'][1]
 assert actual['general']['measurements'][0]['normalizationVersion']==D.NORMALIZATION
 native['general']=None
 with pytest.raises(ValueError,match='OVERVIEW_SCOPE_MISMATCH'):D.replace_dryness(old,native,'id')
 assert old['general']['measurements'][0]['value']==6
 native['photoId']='b'
 with pytest.raises(ValueError):D.replace_dryness(old,native,'id')
 assert old['measurements']['chin'][0]['value']==5

@pytest.mark.parametrize('reason,status',[('disconnect',409),('deadline',504)])
def test_normal_router_reaps_native_process_before_unlock(monkeypatch,reason,status):
 import local_health as L
 from local_native_process import NativeAnalysisProcess
 from fastapi import HTTPException
 monkeypatch.setattr(L,'parked',lambda:True);monkeypatch.setattr(L,'skin_geometry',lambda _:None)
 async def payload(_):return {}
 monkeypatch.setattr(L,'payload',payload)
 async def run():
  service=NativeAnalysisProcess();started=asyncio.Event();processes=[]
  monkeypatch.setattr(L,'native_analysis',service)
  async def work(*_):
   service.process=await asyncio.create_subprocess_exec(getattr(sys,'_base_executable',sys.executable),'-c','import time;time.sleep(60)')
   processes.append(service.process);started.set();await service.process.wait()
  service.exchange=work
  original=service.run
  async def bounded(op,value,request,permitted,seconds):return await original(op,value,request,permitted,.3)
  service.run=bounded
  class Request:
   async def receive(self):
    await started.wait()
    if reason=='disconnect':return {'type':'http.disconnect'}
    await asyncio.Future()
  L._busy=asyncio.Lock()
  task=asyncio.create_task(L.skin(Request()))
  await started.wait();assert L._busy.locked()
  with pytest.raises(HTTPException) as e:await task
  assert e.value.status_code==status and not L._busy.locked()
  assert processes[0].returncode is not None and service.process is None
 asyncio.run(run())
