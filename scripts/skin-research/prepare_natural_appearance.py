"""Public copyright-holder photographic sources, local analysis only.
Descriptions are not adopted as diagnoses or appearance labels.
"""
from pathlib import Path
import urllib.request,urllib.parse,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/natural-extra';OUT.mkdir(parents=True,exist_ok=True)
titles=['Seborrhoeic dermatitis example.jpg','Seborrhoeic dermatitis example2.jpg','Seborrhoeic dermatitis head.jpg','Dermatitis of eyelids.jpg','Old Lao man with big chin and wrinkles (cropped).jpg']
if '--confounders' in sys.argv:
 OUT=OUT.parent/'natural-confounders';OUT.mkdir(parents=True,exist_ok=True)
 titles=['Acne vulgaris on a very oily skin.jpg','Isabelle Faust B 09-2012.jpg','Seborrhoeic dermatitis new photo for helping in diagnosis.jpg','Face portrait (Unsplash).jpg','Поры на лице человека.jpg']
def read(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AttuneLocalAppearanceResearch/1.0 (copyright review, no identity linking)'}),timeout=45) as r:return r.read()
rows=[]
for i,title in enumerate(titles):
 url='https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode(dict(action='query',format='json',titles='File:'+title,prop='imageinfo',iiprop='url|size|sha1|extmetadata'))
 try:
  data=json.loads(read(url));info=next(iter(data['query']['pages'].values()))['imageinfo'][0];meta=info['extmetadata'];license=meta['LicenseShortName']['value'];assert license in ['CC BY 2.0','CC BY 3.0','CC BY 4.0','CC BY-SA 3.0','CC0','CC BY-SA 4.0','CC BY-SA 2.0'],license
  raw=read(info['url']);path=OUT/(str(i)+'.jpg');path.write_bytes(raw);rows.append(dict(title=title,path=str(path.relative_to(ROOT)),metadata=data,sha256=hashlib.sha256(raw).hexdigest(),license=license,source=info['descriptionurl'],copyrightHolderMetadata=True,identityLinking=False,diagnosticLabelAdopted=False))
 except Exception as e:rows.append(dict(title=title,failure=str(e)))
 (OUT/'rights.json').write_text(json.dumps(rows,indent=2),'utf8')
print(json.dumps([{k:r.get(k) for k in ('title','license','failure')} for r in rows],indent=2))
