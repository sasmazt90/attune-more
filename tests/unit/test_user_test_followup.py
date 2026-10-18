"""Presentation/semantic-mask/initial-baseline regressions; no paid provider."""
import json, subprocess, sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from conversation_control import conversation_control

def run(tmp_path,code):
 bootstrap="""
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const dir=JSON.parse(fs.readFileSync(0,'utf8')).dir;
const Module=require('module'),original=Module._resolveFilename;
Module._resolveFilename=function(request,parent,...rest){if(request==='@mediapipe/tasks-vision')return original.call(this,request,{paths:module.paths},...rest);return original.call(this,request,parent,...rest)};
const load=require('./tests/unit/ts_source_loader.cjs')(dir);
load('skinAnalyzer');load('skinMultiAngle');const M=load('skinMesh'),S=load('skinSnapshot'),P=load('visionPreparation');
"""+code
 result=subprocess.run(['node','-e',bootstrap],cwd=ROOT,input=json.dumps({'dir':str(tmp_path).replace('\\','/')}),capture_output=True,text=True,encoding='utf-8')
 assert result.returncode==0,result.stdout+result.stderr

@pytest.mark.parametrize('id',['forehead','rightCheek','leftCheek','nose','periorbital','chin'])
def test_explicit_anatomical_graphs(tmp_path,id):
 run(tmp_path,"""
const id="""+json.dumps(id)+""",g=M.SKIN_GRAPHS[id],l=Array.from({length:478},(_,i)=>({x:i/1000,y:(i%70)/100}));
const mesh=M.buildSkinMesh(id,l,640,480);assert(mesh.edges.length>=20);assert(mesh.major.length>=2);assert(mesh.excluded.length>=2);
assert.equal(mesh.points.length,g.indices.length);mesh.points.forEach((p,i)=>{assert.equal(p.x,l[g.indices[i]].x*640);assert.equal(p.y,l[g.indices[i]].y*480)});
assert(mesh.edges.every(([a,b])=>a!==b&&a>=0&&b>=0&&a<mesh.points.length&&b<mesh.points.length));
if(id==='periorbital')assert(mesh.edges.every(([a,b])=>(a<16&&b<16)||(a>=16&&b>=16)),'Eyes may never connect over nose/iris');
assert.equal(S.snapshotAngleForRegion('rightCheek',true),'LEFT');assert.equal(S.snapshotAngleForRegion('leftCheek',true),'RIGHT');
assert.notDeepEqual(M.SKIN_GRAPHS.rightCheek.indices,M.SKIN_GRAPHS.leftCheek.indices);
""")

def test_semantic_head_keeps_original_face_holes_excludes_body_background(tmp_path):
 run(tmp_path,"""
const l=Array.from({length:478},()=>({x:.5,y:.5}));l[10]={x:.5,y:.25};l[151]={x:.5,y:.35};l[152]={x:.5,y:.7};l[148]={x:.4,y:.65};l[377]={x:.6,y:.65};
const categories=new Uint8Array(32*32);for(let y=7;y<24;y++)for(let x=9;x<23;x++)categories[y*32+x]=y<10?1:3;
for(let y=24;y<32;y++)for(let x=13;x<19;x++)categories[y*32+x]=2;
categories[15*32+15]=5; // enclosed eye pixel: kept, not recoloured/reconstructed
const result=S.headAlpha({width:32,height:32,categories,elapsedMs:1},{landmarks:l},64,64);
assert.equal(result.alpha[30*64+30],255);assert.equal(result.alpha[60*64+30],0);assert.equal(result.alpha[0],0);assert(result.bounds.height<64);
assert.throws(()=>S.headAlpha({width:32,height:32,categories:new Uint8Array(1024),elapsedMs:1},{landmarks:l},64,64));
const edge=structuredClone(l);edge[10].y=.001;assert.throws(()=>S.assertCompleteFace({landmarks:edge},640,480),/INCOMPLETE_HEAD_FRAME/);
""")

@pytest.mark.parametrize('kind,expected', [('initial','preparing'),('near','recede'),('far','approach'),('dark','light'),('bright','bright'),('blur','blur'),('turned','pose'),('stale','camera'),('outside','framing'),('valid','ready')])
def test_measured_initial_and_locked_guidance(tmp_path,kind,expected):
 run(tmp_path,"""
const c={observedAt:1000,cameraLive:true,modelActive:true,faceCount:1,positionValid:true,relativeScaleChange:0};
const e={width:640,height:480,alignment:{box:{x:150,y:70,width:300,height:330},yaw:0,pitch:0,roll:0,scaleRatio:.4},quality:{isValid:true,status:'OPTIMAL'}};
const kind="""+json.dumps(kind)+""";
if(kind==='initial'){c.relativeScaleChange=null;c.positionValid=false;}
if(kind==='near')c.relativeScaleChange=.081;if(kind==='far')c.relativeScaleChange=-.081;
if(kind==='dark'){e.quality.status='TOO_DARK';e.quality.isValid=false;}if(kind==='bright'){e.quality.status='TOO_BRIGHT';e.quality.isValid=false;}
if(kind==='blur'){e.quality.status='BLURRY';e.quality.isValid=false;}if(kind==='turned')e.alignment.yaw=.3;
if(kind==='stale')c.observedAt=0;if(kind==='outside')e.alignment.box.x=-2;
assert.equal(P.visionPreparationCode(c,e,1100),"""+json.dumps(expected)+""");assert(!P.PREPARATION_TEXT.preparing.includes('dönün'));
""")

@pytest.mark.parametrize('text,action',[('Dönerim belki','clarify'),('Sonra gelirim','clarify'),('Ara verelim mi?','clarify'),('Görüşmeyi duraklat','pause'),('Lütfen ara ver','pause'),('Biraz ara vermek istiyorum','pause')])
def test_control_never_infers_emotion(text,action):
 result=conversation_control(text);assert result['sessionAction']==action;assert result['providerType']=='CONVERSATION_CONTROL';assert 'dinlenmek istiyorsun' not in result['reply']

def test_normal_content_not_a_control_and_crisis_precedes_control(monkeypatch):
 assert conversation_control('Yeni bir kitap okudum.') is None
 import main
 from fastapi.testclient import TestClient
 monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False)
 monkeypatch.setattr(main,'get_active_mental_provider',lambda:pytest.fail('Control must not dispatch a paid provider'))
 client=TestClient(main.app)
 assert client.post('/api/mental/converse',json={'userMessage':'Görüşmeyi duraklat','cloudConsent':True}).json()['sessionAction']=='pause'
 result=client.post('/api/mental/converse',json={'userMessage':'Kendime zarar vermek istiyorum. Görüşmeyi duraklat','cloudConsent':True}).json()
 assert result['isCrisis'] and result['providerType']=='CRISIS_SAFETY_GUARD' and 'sessionAction' not in result


def test_edge_alpha_transition_is_narrow_and_face_interior_opaque(tmp_path):
 run(tmp_path,"""
const l=Array.from({length:478},()=>({x:.5,y:.5}));l[10]={x:.5,y:.25};l[151]={x:.5,y:.35};l[152]={x:.5,y:.7};l[148]={x:.4,y:.65};l[377]={x:.6,y:.65};
const categories=new Uint8Array(1024),confidence=new Float32Array(1024);for(let y=7;y<24;y++)for(let x=9;x<23;x++){categories[y*32+x]=y<10?1:3;confidence[y*32+x]=.95;}
const {alpha}=S.headAlpha({width:32,height:32,categories,confidence,elapsedMs:1},{landmarks:l},128,128);
assert(alpha.some(a=>a>0&&a<255));assert.equal(alpha[64*128+64],255);assert.equal(alpha[0],0);assert.equal(alpha[120*128+64],0);
""")


def test_real_speech_boundary_nfc_and_single_provider_iterator(monkeypatch):
 import asyncio,unicodedata,time,vision_speech
 from tts_profiles import MENTAL_WELLBEING_TTS_PROFILE
 calls=[]
 class Provider:
  def __init__(self,text,voice,rate,pitch,*,connect_timeout,receive_timeout):
   assert connect_timeout==5 and receive_timeout==15
   calls.append((text,voice,rate,pitch))
  async def stream(self):
   for data in (b'audio-1',b'audio-2',b'audio-3'):yield {'type':'audio','data':data}
 monkeypatch.setattr(vision_speech.edge_tts,'Communicate',Provider)
 monkeypatch.setattr(vision_speech,'_catalogue',(time.monotonic(),frozenset([MENTAL_WELLBEING_TTS_PROFILE.voice])))
 async def exercise():
  reply=await vision_speech.mental_response(unicodedata.normalize('NFD','Türkçe ses denemesidir. İyi günler.'),lambda:False)
  result=b''.join([chunk async for chunk in reply.body_iterator]);assert result==b'audio-1audio-2audio-3'
 asyncio.run(exercise())
 assert len(calls)==1 and unicodedata.is_normalized('NFC',calls[0][0]);assert calls[0][1:]==('tr-TR-EmelNeural','-10%','-10Hz')


def test_short_neck_uses_only_actual_body_skin_and_preserves_face(tmp_path):
 run(tmp_path,"""
const l=Array.from({length:478},()=>({x:.5,y:.5}));l[10]={x:.5,y:.25};l[151]={x:.5,y:.35};l[152]={x:.5,y:.7};l[148]={x:.4,y:.65};l[377]={x:.6,y:.65};l[172]={x:.35,y:.6};l[397]={x:.65,y:.6};
const categories=new Uint8Array(1024),confidence=new Float32Array(1024).fill(.95),neckConfidence=new Float32Array(1024).fill(.95);
for(let y=7;y<23;y++)for(let x=9;x<23;x++)categories[y*32+x]=y<10?1:3;
for(let y=23;y<32;y++)for(let x=12;x<20;x++)categories[y*32+x]=y<27?2:4;
const {alpha}=S.headAlpha({width:32,height:32,categories,confidence,neckConfidence,elapsedMs:1},{landmarks:l},64,64);
assert.equal(alpha[30*64+30],255);assert(alpha[47*64+30]>0);assert.equal(alpha[60*64+30],0);assert.equal(alpha[47*64+5],0);
""")


def test_cheek_rows_do_not_skip_anatomy_or_draw_non_node_crossings(tmp_path):
 run(tmp_path,"""
const rows=Array.from({length:24},(_,i)=>Math.floor(i/4));
for(const id of ['rightCheek','leftCheek']){const g=M.SKIN_GRAPHS[id];assert.equal(g.indices.length,24);assert(g.edges.length>=35);assert(g.edges.every(([a,b])=>Math.abs(rows[a]-rows[b])<=1));}
const lm=Array.from({length:478},()=>({x:0,y:0})),alpha=new Uint8Array(10000).fill(255);
const graph={points:[{x:20,y:20},{x:80,y:80},{x:20,y:80},{x:80,y:20}],edges:[[0,1],[2,3]],major:[0,2],boundary:[],excluded:['occluded-cheek']};
const supported=M.supportedSkinMesh(graph,lm,100,100,alpha);assert.equal(supported.edges.length,1,'Non-node cheek crossing cannot reach the render');assert.equal(supported.points.length,2);
""")


def test_source_color_guides_alpha_without_modifying_face_pixels(tmp_path):
 run(tmp_path,"""
const R=load('skinMatte'),w=64,h=64,rgba=new Uint8ClampedArray(w*h*4),alpha=new Uint8Array(w*h);
for(let y=0;y<h;y++)for(let x=0;x<w;x++){const i=y*w+x;rgba[i*4]=x<32?220:20;rgba[i*4+1]=70;rgba[i*4+2]=x<32?20:220;rgba[i*4+3]=255;alpha[i]=x<28?255:x>35?0:128;}
const before=new Uint8ClampedArray(rgba),m=R.refineSkinMatte(rgba,alpha,w,h,32);
assert.deepEqual(rgba,before,'Refinement cannot change source RGB');
assert.equal(m.alpha[32*w+20],255);assert.equal(m.alpha[32*w+45],0);
assert(m.alpha[32*w+30]>160,'Real foreground colour must sharpen the uncertain semantic boundary');
assert(m.alpha[32*w+34]<100,'Real background colour must remove an uncertain fringe');
assert(m.alpha[32*w+31]-m.alpha[32*w+32]>60,'Guide must create a source-aligned colour boundary, not just blur the prior');
assert(m.elapsedMs>=0 && m.workingBytes<1000000);
""")


def test_native_sized_masks_compact_to_true_semantic_grid(tmp_path):
 run(tmp_path,"""
const w=1024,h=1024,c=new Uint8Array(w*h).fill(3),hair=new Float32Array(w*h),face=new Float32Array(w*h).fill(.9),neck=new Float32Array(w*h);
const mask=S.compactSkinMask(w,h,c,hair,face,neck);
assert.equal(mask.width,256);assert.equal(mask.height,256);assert.equal(mask.categories.length,65536);assert(mask.confidence.every(v=>Math.abs(v-.9)<1e-6));
assert.equal(mask.categories.byteLength+mask.confidence.byteLength+mask.faceConfidence.byteLength+mask.neckConfidence.byteLength,851968);
""")


def test_nostril_opening_blocks_upper_void_but_keeps_surrounding_skin(tmp_path):
 run(tmp_path,"""
const lm=Array.from({length:478},()=>({x:0,y:0}));
for(const [id,x,y] of [[48,.3,.35],[1,.55,.32],[19,.55,.55],[97,.5,.65],[98,.32,.65],[64,.28,.5],[99,.36,.63],[278,.7,.35],[326,.6,.65],[327,.78,.65],[294,.82,.5]])lm[id]={x,y};
const input={points:[{x:15,y:45},{x:60,y:45},{x:15,y:20},{x:85,y:20}],edges:[[0,1],[2,3]],major:[],boundary:[],excluded:[]};
const output=M.supportedSkinMesh(input,lm,100,100,new Uint8Array(10000).fill(255));
assert.equal(output.edges.length,1,'The opening above the old tiny lower triangle is not visible skin');
assert(output.points.every(p=>p.y===20),'Surrounding supported skin remains connected');
assert.equal(input.edges.length,2,'Filtering cannot mutate the source graph');
""")
