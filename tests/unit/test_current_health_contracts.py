"""Current-photo engineering tests; no clinical or physical acceptance claims."""
import base64,hashlib,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
import cv2,numpy as np,pytest
from PIL import Image,ImageOps
from dental_upload import decode_upload,UploadError,LIMITS,analyze_upload
from instant_appearance import curve_profile,boundary_support,instant_proxy
from care_provider import available_window_match
from test_local_appearance_health import landmarks,skin_input
from appearance_analysis import analyze_skin
ROOT=Path(__file__).resolve().parents[2]

def encoded(image,fmt='PNG',exif=None):
 b=io.BytesIO();image.save(b,format=fmt,**({'exif':exif} if exif else {}));return 'data:image/ignored;base64,'+base64.b64encode(b.getvalue()).decode()

@pytest.mark.parametrize('fmt',['PNG','JPEG','WEBP'])
def test_magic_decode_actual_formats_and_full_source(fmt):
 im=Image.fromarray(np.full((96,144,3),(172,128,102),'uint8'))
 image,digest,normalized,meta=decode_upload(encoded(im,fmt))
 assert image.shape==(96,144,3) and meta['originalFormat']==fmt and meta['exifNormalized']
 assert hashlib.sha256(cv2.cvtColor(image,cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()==digest
 assert meta['sourceWidth']==144 and normalized.startswith('data:image/png;base64,')

def test_exif_same_oriented_pixels_and_limits(monkeypatch):
 im=Image.fromarray(np.random.default_rng(4).integers(50,180,(96,144,3),dtype=np.uint8));exif=Image.Exif();exif[274]=6
 data=encoded(im,'JPEG',exif)
 image,_,_,_=decode_upload(data)
 raw=base64.b64decode(data.split(',')[1]);expected=np.array(ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB'))
 assert image.shape==(144,96,3) and np.array_equal(image[:,:,::-1],expected)
 for raw in [b'<svg>bad</svg>',b'RIFFxxxxWAVE',b'\xff\xd8\xffbroken']:
  with pytest.raises(UploadError):decode_upload('data:image/png;base64,'+base64.b64encode(raw).decode())
 monkeypatch.setitem(LIMITS,'maxPixels',100)
 with pytest.raises(UploadError,match='PIXEL_LIMIT'):decode_upload(data)

def test_actual_current_skin_determinism_quality_not_historical_refs():
 im=np.full((400,500,3),(100,130,175),np.uint8);payload=skin_input(im)
 first=analyze_skin(payload);second=analyze_skin({**payload,'historicalReference':{'corrupt':'ignored'}})
 # Runtime timings describe execution, not deterministic appearance values.
 def without_timings(value):
  if isinstance(value,dict):return {k:without_timings(v) for k,v in value.items() if k not in {'loadMs','inferenceMs'}}
  if isinstance(value,list):return [without_timings(v) for v in value]
  return value
 assert without_timings(first)==without_timings(second) and first['methodVersion']=='appearance-cv-6'
 for rows in first['measurements'].values():
  assert all(r['referenceId'] is None and r['type']=='appearance_proxy' for r in rows)
 invalid=analyze_skin({**payload,'qualityValid':False})
 assert all(r['value'] is None for rows in invalid['measurements'].values() for r in rows)

def test_real_pixel_profile_positive_color_negative_and_boundary_joint():
 h,w=180,320;gray=np.full((h,w),.6,np.float32);mask=np.ones_like(gray,bool)
 guide=np.array([[40,70],[100,82],[160,86],[220,82],[280,70]],np.float32)
 for x in range(40,281):
  y=np.interp(x,guide[:,0],guide[:,1])+12
  gray[:,x]-=.12*np.exp(-((np.arange(h)-y)/.9)**2)
 q=curve_profile(gray,mask,guide,np.array([0.,1.]),np.arange(3,25),320)
 assert q['strength']>0 and q['edge']>0 and q['continuity']>.2
 dark=np.full_like(gray,.25)
 negative=curve_profile(dark,mask,guide,np.array([0.,1.]),np.arange(3,25),320)
 assert negative['strength']==0 and negative['edge']==0 # Dark color alone is never bags.
 boundary=np.full_like(gray,.2)
 for x in range(w):boundary[:int(120+5*np.sin(x/9)),x]=.6
 measured=boundary_support(boundary,mask,[[20,120],[150,120],[300,120]],320)
 assert measured['value']>0 and measured['coverage']==1
 assert boundary_support(np.full_like(gray,.6),mask,[[20,120],[300,120]],320)['value']==0

def test_expression_shadow_low_detail_null_not_zero():
 p=landmarks();gray=np.full((400,500),.6,np.float32);mask=np.ones_like(gray,bool)
 conditions={'yaw':0,'pitch':0}
 for mod,code in [({'yaw':.8},'HEAD_ANGLE_UNSUPPORTED'),({'pitch':.4},'HEAD_ANGLE_UNSUPPORTED')]:
  v=instant_proxy(gray,mask,p,'chin',{**conditions,**mod},1,(0,0),(400,500));assert v[0] is None and v[-1]==code
 opened=[dict(v) for v in p];opened[14]['y']=.75
 assert instant_proxy(gray,mask,opened,'chin',conditions,1,(0,0),(400,500))[0] is None
 assert instant_proxy(gray,np.zeros_like(mask),p,'chin',conditions,1,(0,0),(400,500))[0] is None
 assert instant_proxy(gray,mask,p,'periorbital',conditions,1,(0,0),(400,500))[-1]=='SQUINT_OR_EYE_OCCLUSION'

def test_availability_timezone_duration_and_missing_source():
 windows=[{'start':'2026-10-09T09:00','end':'2026-10-09T10:00'}]
 assert available_window_match('2026-10-09T07:10:00Z',windows,45,'Europe/Berlin') is True
 assert available_window_match('2026-10-09T07:30:00Z',windows,45,'Europe/Berlin') is False
 assert available_window_match(None,windows,45,'Europe/Berlin') is None
 assert available_window_match('2026-10-09T07:10:00Z',[],45,'Europe/Berlin') is None

@pytest.mark.parametrize('bite_confirmation',[None,False,True])
def test_upload_exact_trained_model_positive_and_source_coords(bite_confirmation):
 path=ROOT/'audit-results/current-health-20261009/public-positive.json'
 if not path.exists():pytest.skip('Licensed local public source unavailable; production proof requires it')
 info=json.loads(path.read_text('utf8'));raw=Path(info['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==info['sourceSHA256']
 result=analyze_upload({'photo':'data:image/jpeg;base64,'+base64.b64encode(raw).decode(),'biteConfirmed':bite_confirmation})
 view=result['views'][0];assert view['sourceType']=='upload' and not view['quality']['fullFaceRequired'] and not view['quality']['motionGateApplied']
 assert view['pose']=='FRONT' and result['methodVersion']=='dental-visible-upload-v3'
 assert view['caries']['modelHash']=='eafaca8139e4447b1aa64375156aa47764affd91cf0594392b896ea78463bf03' and view['caries']['value']>0
 for c in view['caries']['candidates']:
  b=c['bounds'];assert 0<=b['x']<view['sourceWidth'] and 0<=b['y']<view['sourceHeight'] and b['x']+b['width']<=view['sourceWidth'] and b['y']+b['height']<=view['sourceHeight']
 assert view['accumulation']['viewSupport']==1 and view['alignment']['value'] is None


def engineering_face():
 p=[dict(x=.5,y=.5,z=0.) for _ in range(478)]
 for i,x,y in [(234,0,150),(454,320,150),(33,40,70),(263,280,70),(133,110,70),(362,210,70),(159,75,64),(145,75,82),(386,245,64),(374,245,82),(144,45,80),(153,90,83),(154,105,80),(373,275,80),(380,230,83),(381,215,80),(61,110,165),(291,210,165),(13,160,165),(14,160,168),(98,130,112),(205,122,125),(206,119,138),(216,113,152),(132,25,150),(58,35,180),(172,60,205),(136,85,222),(150,125,236)]:p[i]=dict(x=x/320,y=y/280,z=0.)
 return p

def test_complete_current_proxy_positive_and_independent_negative_support():
 p=engineering_face();mask=np.ones((280,320),bool);base=np.full(mask.shape,.6,np.float32)
 yy,xx=np.indices(mask.shape)
 bags=base.copy()
 for ids in ([144,145,153,154,133],[362,381,380,374,373]):
  pts=np.array([[p[i]['x']*320,p[i]['y']*280] for i in ids]);ys=np.interp(np.arange(320),pts[:,0],pts[:,1])+12
  bags-=.12*np.exp(-((yy-ys[None,:])/.9)**2)*((xx>=pts[:,0].min())&(xx<=pts[:,0].max()))
 value,parts,signal,lines,code=instant_proxy(bags,mask,p,'periorbital',{'yaw':0,'pitch':0},1,(0,0),mask.shape)
 assert code is None and value>0 and len(parts['sides'])==2 and signal.max()>0 and lines
 assert instant_proxy(base,mask,p,'periorbital',{'yaw':0,'pitch':0},1,(0,0),mask.shape)[0]==0
 # Sag needs both an independently tracked jaw boundary and an actual local fold.
 guide=np.array([[p[i]['x']*320,p[i]['y']*280] for i in [132,58,172,136,150]])
 y_boundary=np.interp(np.arange(320),guide[:,0],guide[:,1])+5*np.sin(np.arange(320)/5)
 boundary=base.copy();boundary[yy>y_boundary[None,:]]=.2
 fold=base.copy();f=np.array([[p[i]['x']*320,p[i]['y']*280] for i in [98,205,206,216,61]])
 x_fold=np.interp(np.arange(280),f[:,1],f[:,0])+5
 fold-=.12*np.exp(-((xx-x_fold[:,None])/.9)**2)*((yy>=f[:,1].min())&(yy<=f[:,1].max()))
 both=boundary+(fold-base)
 args=(mask,p,'rightCheek',{'yaw':0,'pitch':0},1,(0,0),mask.shape)
 measured=instant_proxy(both,*args)
 assert measured[-1] is None and measured[0]>0 and measured[2].max()>0 and measured[3]
 assert instant_proxy(fold,*args)[0]==0 and instant_proxy(boundary,*args)[0]==0
 # Real unsupported samples are null, not a healthy zero.
 glasses=base.copy();glasses[90:94,40:120]=.05
 assert instant_proxy(glasses,mask,p,'periorbital',{'yaw':0,'pitch':0},1,(0,0),mask.shape)[0] is None
 beard=np.ones_like(mask)
 assert instant_proxy(both,*args,hair=beard)[0] is None
 shade=np.tile(np.linspace(.15,.9,320,dtype=np.float32),(280,1))
 # The broad photo slope is small across this local jaw/fold ROI.
 assert instant_proxy(shade,*args)[-1] is None
 local_shade=np.tile(np.clip(.15+.75*(np.arange(320)-20)/145,.15,.9).astype(np.float32),(280,1))
 assert instant_proxy(local_shade,*args)[-1]=='HARD_DIRECTIONAL_SHADOW'


def test_provider_date_is_read_not_invented_or_user_timezone():
 from care_provider import verified_source_slot_time
 class SourceNode:
  def __init__(self,attrs):self.attrs=attrs
  def get_attribute(self,key):return self.attrs.get(key)
  def query_selector(self,selector):return None
 assert verified_source_slot_time(SourceNode({'data-start':'2026-10-09T09:30'}))=='2026-10-09T09:30:00+03:00'
 assert verified_source_slot_time(SourceNode({'datetime':'2026-10-09T07:30:00Z'}))=='2026-10-09T07:30:00+00:00'
 for value in ['09:30','2026-10-09','tomorrow 9','2026-99-09T09:30']:
  assert verified_source_slot_time(SourceNode({'datetime':value})) is None
 with pytest.raises(ValueError):available_window_match(None,[{'start':'bad','end':'bad'}],45,'Europe/Berlin')
 assert available_window_match('09:30',[{'start':'2026-10-09T09:00','end':'2026-10-09T10:00'}],45,'Europe/Berlin') is None
