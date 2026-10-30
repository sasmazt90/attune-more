"""Invalid requests fail before expensive image/mesh allocation; no payload echo."""
import asyncio,copy,sys
from pathlib import Path
import httpx
from fastapi import FastAPI
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
import local_health as health

def request(path,value,park=True,content_type='application/json'):
 app=FastAPI();app.include_router(health.router);previous=health.parked;health.parked=lambda:park
 async def run():
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:return await c.post(path,json=value,headers={'content-type':content_type})
 try:return asyncio.run(run())
 finally:health.parked=previous

def test_park_consent_media_type_and_malformed_geometry():
 assert request('/api/local-health/skin',{},False).status_code==409
 assert request('/api/local-health/skin',{},True,'text/plain').status_code==415
 assert request('/api/local-health/skin',{}).status_code==422
 p={'processingConsent':True,'landmarks':[{'x':.5,'y':.5}]*478,'meshes':{'forehead':{'points':[{'x':1,'y':1}]*3,'edges':[[0,1]]}},'temporal':[],'exclusions':[]}
 for key,value in [('landmarks',[{}]*478),('temporal',[p['landmarks']]*9),('exclusions','invalid'),('meshes',{'forehead':{'points':[{}]*201,'edges':[]}}),('meshes',{'forehead':{'points':[{}]*3,'edges':[[0,True]]}})]:
  result=request('/api/local-health/skin',{**p,key:value});assert result.status_code==422 and result.text=='{"detail":"INVALID_LOCAL_GEOMETRY_OR_PHOTO"}'
 for captures in ([],[{}]*5,[{'pose':'UNKNOWN','landmarks':p['landmarks']}],[{'pose':'FRONT','landmarks':None}]):assert request('/api/local-health/dental',{'processingConsent':True,'captures':captures}).status_code==422

def test_no_cubic_mesh_work_or_dark_hair_glare():
 from test_local_appearance_health import skin_input
 from appearance_analysis import analyze_skin
 import numpy as np
 image=np.full((400,500,3),(100,130,175),np.uint8);image[:55]=0;result=analyze_skin(skin_input(image))
 assert all(v['value'] is not None for v in result['measurements']['forehead'] if v['id'] in ('tone','redness','oil','dry'))
 # This deliberately synthetic mesh has no supported acne search area. It
 # must remain unavailable rather than manufacture a healthy zero.
 acne=next(v for v in result['measurements']['forehead'] if v['id']=='acne')
 assert acne['value'] is None and acne['limitationCode']=='INSUFFICIENT_VISIBLE_AREA'


def test_dental_model_failure_is_503_without_payload_echo(monkeypatch):
 from fastapi import HTTPException
 async def failure(*_):raise HTTPException(503,'LOCAL_MODEL_FAILURE')
 # Native analysis now crosses a process boundary; inject its classified
 # failure at that boundary, never a synthetic successful inference result.
 monkeypatch.setattr(health.native_analysis,'run',failure)
 result=request('/api/local-health/dental',{'processingConsent':True,'captures':[{'pose':pose,'landmarks':[{'x':.5,'y':.5}]*478} for pose in ['FRONT','RIGHT','LEFT','BITE']]})
 assert result.status_code==503 and result.json()=={'detail':'LOCAL_MODEL_FAILURE'}
