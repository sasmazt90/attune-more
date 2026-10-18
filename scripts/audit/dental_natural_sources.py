"""Natural rights-recorded photos through actual production upload API.
No clinical labels or inference from detector confidence. Private local pixels.
"""
from pathlib import Path
import base64,json,hashlib,urllib.request,time,io
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'audit-results/followup-closure-20261010/dental-sources'
OUT=ROOT/'audit-results/all-health-20261010/dental-natural';OUT.mkdir(parents=True,exist_ok=True)
manifest=json.loads((SOURCE/'complete-manifest.json').read_text());rows=[]
for item in manifest:
 path=SOURCE/f"{item['id']}.jpg";assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sourceSHA256']
 start=time.monotonic();body=json.dumps({'processingConsent':True,'photo':'data:image/jpeg;base64,'+base64.b64encode(path.read_bytes()).decode()}).encode()
 row=dict(id=item['id'],name=item['name'],sourceSHA256=item['sourceSHA256'],natural=True,clinicalGroundTruth=False)
 try:
  response=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/api/local-health/dental-upload',data=body,headers={'Content-Type':'application/json'}),timeout=120)
  result=json.load(response);(OUT/f"{item['id']}-result-private.json").write_text(json.dumps(result),'utf8');view=result['views'][0];row.update(status='MEASURED',seconds=time.monotonic()-start,caries=view['caries'],accumulation=view['accumulation'],alignment=view['alignment'],quality=view['quality'])
  im=Image.open(io.BytesIO(base64.b64decode(result['normalizedPhoto'].split(',')[1]))).convert('RGB');scale=min(1,1000/im.width);im=im.resize((int(im.width*scale),int(im.height*scale)));d=ImageDraw.Draw(im)
  for key,color in [('caries','magenta'),('accumulation','cyan')]:
   for c in view[key]['candidates']:
    box=c.get('box') or c.get('bbox') or c.get('bounds')
    if isinstance(box,dict):box=[box['x'],box['y'],box['x']+box['width'],box['y']+box['height']]
    if box:d.rectangle([v*scale for v in box],outline=color,width=2)
  im.save(OUT/f"{item['id']}-review.png")
 except urllib.error.HTTPError as e:row.update(status='REJECTED',http=e.code,reason=e.read().decode()[:1500])
 except Exception as e:row.update(status='ERROR',reason=str(e))
 rows.append(row);(OUT/'measurements-private.json').write_text(json.dumps(rows,indent=2),'utf8');print(json.dumps({k:row[k] for k in ['id','status']},ensure_ascii=True),flush=True)
print('Natural evidence collected; positive/negative visual assessment remains separate.')
