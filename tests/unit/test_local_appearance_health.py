"""Engineering and confounder tests, not clinical/hardware acceptance."""
import base64,hashlib,json,sys
from pathlib import Path
import cv2,numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from appearance_analysis import decode_photo,analyze_skin,contour_geometry
from dental_analysis import calculus_candidates,dental_quality,contours_and_alignment


def photo(image):
 ok,raw=cv2.imencode('.png',image);assert ok
 rgba=cv2.cvtColor(image,cv2.COLOR_BGR2RGBA)
 return 'data:image/png;base64,'+base64.b64encode(raw).decode(),hashlib.sha256(rgba.tobytes()).hexdigest()


def landmarks():
 p=[dict(x=.5,y=.5,z=0.) for _ in range(478)]
 for index,x,y in [(33,.3,.4),(263,.7,.4),(234,.2,.5),(454,.8,.5),(10,.5,.15),(152,.5,.85),(61,.4,.65),(291,.6,.65),(13,.5,.65),(14,.5,.66),(78,.4,.65),(308,.6,.65)]:p[index]=dict(x=x,y=y,z=0.)
 return p


def skin_input(image):
 url,digest=photo(image);p=landmarks();h,w=image.shape[:2]
 mesh={'points':[{'x':.3*w,'y':.18*h},{'x':.7*w,'y':.18*h},{'x':.7*w,'y':.30*h},{'x':.3*w,'y':.30*h}],'edges':[[0,1],[1,2],[2,3],[3,0],[0,2]]}
 return dict(photo=url,photoId=digest,landmarks=p,temporal=[p,p,p],meshes={r:mesh for r in ['forehead','rightCheek','leftCheek','nose','chin','periorbital']},exclusions=[],pose='FRONT',qualityValid=True,conditions=dict(yaw=0.,pitch=0.,roll=0.,scaleRatio=.6,avgLuminance=145.,blurScore=50.))


def test_decode_hash_and_source_unchanged():
 image=np.full((400,500,3),(100,130,175),np.uint8);before=image.copy();payload=skin_input(image);decoded,digest=decode_photo(payload['photo'])
 assert np.array_equal(image,decoded) and digest==payload['photoId']
 result=analyze_skin(payload)
 assert np.array_equal(image,before) and result['photoId']==digest
 assert set(result['measurements'])==set(payload['meshes'])
 for region,rows in result['measurements'].items():
  ids={r['id'] for r in rows};assert 'dry' in ids
  assert ({'dark','bags','lines'} if region=='periorbital' else {'oil','acne'})<=ids
  assert all(r['type'] in ('appearance_proxy','longitudinal_measurement') for r in rows)
  for item in rows:
   required={'value','unit','methodVersion','modelVersion','modelHash','quality','uncertainty','region','localMap','evaluatedArea','captureConditions','limitationCode','referenceId'}
   assert required<=item.keys()
   if item['localMap']:
    descriptor=item['localMap'];layer=result['maps'][descriptor['key']]
    assert descriptor['photoId']==layer['photoId']==digest and descriptor['region']==region and descriptor['criterion']==item['id']
    assert descriptor['coordinateSpace']=='source-pixels'
    assert 'data:image' not in json.dumps(item) # No pixel/mask payload in numeric measurements.
 assert next(r for r in result['measurements']['forehead'] if r['id']=='oil')['value']==0 # matte, no forced fill
 with pytest.raises(ValueError):analyze_skin({**payload,'photoId':'0'*64})


def test_bad_quality_and_clipping_are_not_healthy_zero():
 image=np.full((400,500,3),(100,130,175),np.uint8);payload=skin_input(image)
 result=analyze_skin({**payload,'qualityValid':False})
 assert all(r['value'] is None for rows in result['measurements'].values() for r in rows)
 assert not result['maps']
 glare=skin_input(np.full_like(image,255));result=analyze_skin(glare)
 assert all(r['value'] is None for rows in result['measurements'].values() for r in rows)
 small=skin_input(cv2.resize(image,(160,128)));result=analyze_skin(small)
 assert all(r['value'] is None and r['limitationCode']=='INSUFFICIENT_SOURCE_DETAIL' for rows in result['measurements'].values() for r in rows if r['id']=='dry')


def test_geometry_roll_scale_invariance_and_expression_gate():
 p=landmarks();conditions=dict(yaw=0.,pitch=0.,sourceWidth=1000,sourceHeight=1000)
 for i in [172,136,150,379,365,397]:p[i]={'x':.3+i%3*.1,'y':.75,'z':0}
 first,_=contour_geometry(p,'chin',conditions,[p,p,p]);assert first is not None
 angle=.11;rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
 transformed=[]
 for v in p:
  q=(np.array([v['x'],v['y']])-.5)@rotation*.7+.5;transformed.append(dict(x=float(q[0]),y=float(q[1]),z=0))
 second,_=contour_geometry(transformed,'chin',conditions,[transformed]*3)
 assert np.allclose(first['features'],second['features'],atol=1e-6)
 opened=[dict(v) for v in p];opened[14]['y']=.75
 assert contour_geometry(opened,'chin',conditions,[opened]*3)[1]=='POSE_OR_EXPRESSION_INCOMPATIBLE'
 assert contour_geometry(p,'chin',{**conditions,'yaw':.8},[p]*3)[0] is None
 assert contour_geometry(p,'chin',conditions,[p])[1]=='TEMPORAL_SUPPORT_MISSING'


def test_uniform_yellow_is_not_accumulation():
 image=np.full((200,300,3),(120,190,210),np.uint8);tooth=np.zeros((200,300),bool);tooth[70:130,50:250]=True;gum=np.zeros_like(tooth);gum[60:70,50:250]=True
 candidates,area=calculus_candidates(image,tooth,gum)
 assert area>0 and not candidates
 # Saliva white and pink gum aren't calculus even at the same boundary.
 for color in [(255,255,255),(80,80,180)]:
  candidates,_=calculus_candidates(np.full_like(image,color),tooth,gum);assert not candidates


def test_duplicate_frames_cannot_supply_multiview_support():
 from dental_analysis import analyze_dental
 with pytest.raises(ValueError,match='DUPLICATE_CAPTURE'):
  analyze_dental({'captures':[{'photoId':'same','pose':'FRONT'},{'photoId':'same','pose':'RIGHT'}]})
 with pytest.raises(ValueError,match='DUPLICATE_VIEW'):
  analyze_dental({'captures':[{'photoId':'one','pose':'FRONT'},{'photoId':'two','pose':'FRONT'}]})


def test_invalid_dental_photo_has_explicit_null_results_not_healthy_zero(monkeypatch):
 import dental_analysis as dental
 def forbidden(*args):raise AssertionError('Bad capture must not run a detector')
 monkeypatch.setattr(dental,'model_candidates',forbidden)
 url,digest=photo(np.zeros((400,500,3),np.uint8))
 result=dental.analyze_dental({'captures':[dict(photo=url,photoId=digest,pose='FRONT',landmarks=landmarks())]})
 view=result['views'][0];assert not view['quality']['valid']
 for key in ('caries','accumulation','alignment'):
  assert view[key]['value'] is None and view[key]['quality']=='insufficient'
  assert view[key]['limitationCode']=='CAPTURE_QUALITY' and view[key]['methodVersion']
 assert not view['caries']['candidates'] and not view['alignment']['contours']


def test_corrupt_model_hash_is_technical_failure_before_model_decode(monkeypatch,tmp_path):
 import dental_analysis as dental
 models=tmp_path/'models';models.mkdir()
 (models/'dental-yolox-s.onnx').write_bytes(b'invalid-test-artifact-never-decoded')
 (models/'dental-yolox-s.json').write_text(json.dumps({'modelHash':'0'*64}),'utf8')
 monkeypatch.setattr(dental,'ROOT',tmp_path);monkeypatch.setattr(dental,'_session',None)
 image=np.full((30,30,3),150,np.uint8);mouth=np.ones((30,30),bool)
 with pytest.raises(dental.DentalModelError,match='MODEL_HASH_MISMATCH'):dental.model_candidates(image,mouth)


@pytest.mark.parametrize('invalid',['nonfinite','shape'])
def test_invalid_inference_output_cannot_become_valid_zero(monkeypatch,tmp_path,invalid):
 import dental_analysis as dental
 models=tmp_path/'models';models.mkdir();(models/'dental-yolox-s.onnx').touch();(models/'dental-yolox-s.json').touch()
 class Session:
  def run(self,*args):
   raw=np.zeros((1,3,7 if invalid=='nonfinite' else 8),np.float32)
   if invalid=='nonfinite':raw[0,0,4]=np.nan
   return [raw]
 monkeypatch.setattr(dental,'ROOT',tmp_path);monkeypatch.setattr(dental,'_session',Session())
 monkeypatch.setattr(dental,'_manifest',{'inputSize':320,'classes':['D','d'],'confidenceThreshold':.2})
 with pytest.raises(dental.DentalModelError,match='INVALID_MODEL_OUTPUT'):
  dental.model_candidates(np.full((30,30,3),150,np.uint8),np.ones((30,30),bool))


def test_no_synthetic_teeth_contours():
 image=np.full((200,300,3),80,np.uint8);tooth=np.zeros((200,300),bool);p=np.zeros((478,2),np.float32);p[13]=[150,80];p[14]=[150,120];p[78]=[40,100];p[308]=[260,100]
 contours,metrics,reason=contours_and_alignment(image,tooth,tooth,p)
 assert not contours and metrics is None and reason=='TOOTH_BOUNDARIES_UNRELIABLE'


def test_png_dimensions_bounded_before_decoder():
 raw=b'\x89PNG\r\n\x1a\n'+b'\0'*8+(50000).to_bytes(4,'big')+(50000).to_bytes(4,'big')
 with pytest.raises(ValueError,match='PHOTO_LIMIT'):decode_photo('data:image/png;base64,'+base64.b64encode(raw).decode())


def test_structured_deposit_and_two_visible_tooth_rows():
 # Controlled engineering shapes prove positive execution, not dental accuracy.
 image=np.full((200,300,3),80,np.uint8);tooth=np.zeros((200,300),np.uint8)
 for y in (70,130):
  for x in (70,150,230):
   cv2.ellipse(image,(x,y),(20,28),0,0,360,(205,215,220),-1)
   cv2.ellipse(tooth,(x,y),(20,28),0,0,360,1,-1)
 p=np.zeros((478,2),np.float32);p[13]=[150,85];p[14]=[150,115];p[78]=[35,100];p[308]=[265,100]
 contours,metrics,reason=contours_and_alignment(image,tooth.astype(bool),tooth.astype(bool),p)
 assert reason is None and len(contours)==6
 assert all(metrics[r]['quality']=='valid' and metrics[r]['contourCount']==3 and metrics[r]['value']<1 for r in ('upper','lower'))
 assert all(metrics[r]['projectedContourOverlapRatio']==0 for r in ('upper','lower'))
 image=np.full((200,300,3),(170,190,210),np.uint8);tooth=np.zeros((200,300),bool);tooth[70:130,50:250]=True;gum=np.zeros_like(tooth);gum[60:70,50:250]=True
 for y in range(71,75):
  for x in range(115,130):image[y,x]=(85+(x%2)*30,145+(x%2)*40,205+(x%2)*20)
 candidates,area=calculus_candidates(image,tooth,gum)
 assert candidates and all(c['bounds']['y']<80 and c['areaPixels']<area for c in candidates)


def test_visible_outline_projection_overlap_preserves_scale_and_row_rotation():
 from dental_analysis import projected_contour_overlap
 outlines=[dict(points=[[x,0],[x+20,0],[x+20,10],[x,10]]) for x in (0,15,40)]
 assert projected_contour_overlap(outlines,[1.,0.])==pytest.approx(.125)
 theta=.4;rotation=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
 transformed=[dict(points=(np.asarray(item['points'])@rotation.T*3+[70,100]).tolist()) for item in outlines]
 assert projected_contour_overlap(transformed,rotation@np.array([1.,0.]))==pytest.approx(.125)


def test_source_mouth_crop_has_actual_origin_and_preserves_colors():
 from dental_analysis import prepare_model_input
 image=np.full((500,700,3),(30,50,70),np.uint8);image[300:400,350:550]=(110,160,190)
 mouth=np.zeros(image.shape[:2],bool);mouth[300:400,350:550]=True
 tensor,ratio,origin=prepare_model_input(image,mouth,320)
 assert tensor.shape==(1,3,320,320) and origin==(320,270)
 assert ratio==320/260 and np.array_equal(tensor[0,:,int(60*ratio),int(60*ratio)],np.array([110,160,190]))
 assert np.array_equal(image[320,400],np.array([110,160,190]))
 with pytest.raises(ValueError,match='VISIBLE_MOUTH_MISSING'):prepare_model_input(image,np.zeros_like(mouth),320)


def test_dental_sharpness_cannot_come_from_background_edges():
 from dental_analysis import mouth_geometry,dental_quality
 points=[dict(x=.5,y=.5) for _ in range(478)]
 coordinates={78:(.2,.5),81:(.3,.3),82:(.4,.3),13:(.5,.3),312:(.6,.3),311:(.7,.3),308:(.8,.5),402:(.7,.7),317:(.6,.7),14:(.5,.7),87:(.4,.7),178:(.3,.7)}
 for index,(x,y) in coordinates.items():points[index]=dict(x=x,y=y)
 shape=(200,300,3);mouth,*_=mouth_geometry(points,shape)
 gray=((np.indices(shape[:2]).sum(axis=0)%2)*255).astype(np.uint8);image=np.repeat(gray[:,:,None],3,axis=2);image[mouth]=150
 quality=dental_quality(image,points)
 assert quality['sharpness']==0 and 'BLURRY' in quality['reasons']
 image[mouth]=(80,80,190);quality=dental_quality(image,points)
 assert 'TONGUE_OCCLUSION' in quality['reasons'] and not quality['valid']


def test_t_zone_uses_forehead_and_nose_without_chin_or_forehead_fill():
 image=np.full((400,500,3),(100,130,175),np.uint8);payload=skin_input(image)
 def mesh(x0,y0,x1,y1):return {'points':[{'x':x0,'y':y0},{'x':x1,'y':y0},{'x':x1,'y':y1},{'x':x0,'y':y1}],'edges':[[0,1],[1,2],[2,3],[3,0],[0,2]]}
 payload['meshes']['forehead']=mesh(160,70,340,120);payload['meshes']['nose']=mesh(220,160,280,240);payload['meshes']['chin']=mesh(170,270,330,310)
 image[70:120,160:340]=(90,120,195);payload['photo'],payload['photoId']=photo(image)
 result=analyze_skin(payload);area=result['measurements']['nose'][0]['evaluatedArea']
 assert area['foreheadSourcePixels']>area['noseSourcePixels']>0 and area['chinSourcePixels']==0
 layer=result['maps']['nose:redness'];assert layer['y']>=150 and layer['y']+layer['height']*layer['step']<250
 modified=image.copy();modified[270:310,170:330]=(30,30,230);other={**payload};other['photo'],other['photoId']=photo(modified)
 r2=analyze_skin(other);assert result['measurements']['nose'][1]['value']==r2['measurements']['nose'][1]['value']


def test_dark_freckles_moles_beard_and_linear_scar_are_not_acne_candidates():
 image=np.full((400,500,3),(100,130,175),np.uint8)
 for x in (180,210,240,270,300):
  cv2.circle(image,(x,95),3,(20,40,60),-1)
  cv2.line(image,(x,80),(x+3,108),(20,25,30),1)
 cv2.line(image,(175,85),(305,85),(70,100,180),2)
 result=analyze_skin(skin_input(image),include_research_features=True)
 rows={r['id']:r for r in result['measurements']['forehead']}
 assert rows['acne']['value']==0 and rows['oil']['value']==0
 assert rows['dry']['value']==0
 assert rows['acne']['components']['bounds']==[]
 image[:]=0;result=analyze_skin(skin_input(image));assert all(r['value'] is None for rows in result['measurements'].values() for r in rows)


@pytest.mark.parametrize('jpeg_quality',[20,35,60,85])
def test_jpeg_noise_pores_and_dark_hair_halos_are_not_flaking(jpeg_quality):
 # Known negative feature field; not a skin diagnosis/accuracy benchmark.
 image=np.full((400,500,3),(100,130,175),np.uint8)
 for x in range(165,336,12):
  for y in range(78,113,12):cv2.circle(image,(x,y),1,(80,105,145),-1)
 for x in (180,210,240,270,300):cv2.line(image,(x,80),(x+3,108),(20,25,30),1)
 image=np.clip(image.astype(float)+np.random.default_rng(8102026).normal(0,2,image.shape),0,255).astype(np.uint8)
 ok,encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,jpeg_quality]);assert ok
 compressed=cv2.imdecode(encoded,cv2.IMREAD_COLOR);before=compressed.copy()
 result=analyze_skin(skin_input(compressed),include_research_features=True);rows={row['id']:row for row in result['measurements']['forehead']}
 assert rows['dry']['quality']=='valid' and rows['dry']['value']==0
 assert rows['acne']['value']==0 and rows['oil']['value']==0 and np.array_equal(before,compressed)


@pytest.mark.parametrize('criterion',['oil','dry','acne'])
def test_controlled_positive_local_signals_execute_without_painting_source(criterion):
 # Feature fixtures only: no expert lesion, oil or physiological dryness label.
 image=np.full((400,500,3),(100,130,175),np.uint8)
 if criterion=='oil':
  y,x=np.indices(image.shape[:2]);weight=np.exp(-((x-250)**2+(y-96)**2)/(2*6**2))[:,:,None]
  image=np.clip(image*(1-weight)+np.array([235,238,240])*weight,0,255).astype(np.uint8)
 elif criterion=='dry':
  for x in (190,220,250,280,310):
   for y in (85,102):cv2.circle(image,(x,y),2,(190,200,220),-1)
 else:cv2.circle(image,(250,95),4,(100,130,230),-1)
 before=image.copy();payload=skin_input(image);result=analyze_skin(payload,include_research_features=criterion=='acne')
 measurement=next(r for r in result['measurements']['forehead'] if r['id']==criterion)
 assert measurement['quality']=='valid' and measurement['value']>0
 assert measurement['type']=='appearance_proxy' and result['photoId']==payload['photoId']
 if criterion=='acne':
  # Offline feature controls check localization, not an accepted detector or
  # a lesion segmentation. The ordinary API keeps rejected acne unavailable.
  assert 'forehead:acne' not in result['maps'] and measurement['localMap'] is None
  assert measurement['components']['candidateCount']==1 and len(measurement['components']['bounds'])==1
  box=measurement['components']['bounds'][0];assert 240<box['x']<260 and 85<box['y']<105
  # Overlapping region supports cannot report the same candidate twice.
  assert sum(r['components'].get('candidateCount',0) for rows in result['measurements'].values() for r in rows if r['id']=='acne')==1
  assert measurement['components']['candidateBoxCoveragePercent']>0
  normal=analyze_skin(payload);unavailable=next(r for r in normal['measurements']['forehead'] if r['id']=='acne')
  assert unavailable['value'] is None and unavailable['status']=='unavailable'
 else:
  layer=result['maps']['forehead:'+criterion];overlay,_=decode_photo(layer['dataUrl'])
  assert layer['photoId']==payload['photoId'] and layer['colorMapping']=='cyan-fixed-100-v1'
  assert layer['sampleCount']>0
 assert np.array_equal(before,image)
