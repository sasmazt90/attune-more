"""Read public repository metadata as evidence, never execute downloaded code.
No tokens, model providers, weight deserialization, private data or uploads.
Pinned text snapshots and advertised LFS hashes are kept in ignored audit output.
"""
import concurrent.futures,datetime,hashlib,json,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/skin-expanded-20261008/sources'
HF=[('models',x) for x in ['mufasabrownie/glowlytics-skin-models','imfarzanansari/skintelligent-acne','dima806/skin_types_image_detection','afscomercial/dermatologic','charuka0/acne-multilabel-classifier','will702/acne-cv-models']]+[('spaces','RihemXX/Acnes')]
GH=['CISLAB-web/SGAUnet','kosekei/skin_TDA','NVlabs/ffhq-dataset','aicip/ACNE04','ipazc/mtcnn','DurtyDhiana/skin-scan']

def fetch(url,dest):
 dest.parent.mkdir(parents=True,exist_ok=True)
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'TOGG-local-public-source-review','Accept':'application/json' if '/api/' in url or 'api.github' in url else '*/*'})
  with urllib.request.urlopen(req,timeout=30) as response:data=response.read(4*1024*1024+1)
  assert len(data)<=4*1024*1024,'bounded text evidence only'
  dest.write_bytes(data)
  return {'url':url,'status':'read','file':str(dest.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 except Exception as error:return {'url':url,'status':'unavailable','error':str(error),'file':str(dest.relative_to(ROOT))}

def hf(job):
 kind,repo=job;folder=OUT/('hf-'+repo.replace('/','--'));row={'id':repo,'provider':'huggingface','kind':kind,'url':'https://huggingface.co/'+('spaces/' if kind=='spaces' else '')+repo}
 meta=fetch('https://huggingface.co/api/'+kind+'/'+repo+'?blobs=true',folder/'metadata.json');row['metadata']=meta
 if meta['status']!='read':return row
 info=json.loads((folder/'metadata.json').read_text('utf8'));rev=info['sha'];row.update(revision=rev,advertisedLicense=info.get('cardData',{}).get('license'),cardData=info.get('cardData'),files=info.get('siblings',[]),texts=[])
 for f in info.get('siblings',[]):
  name=f['rfilename']
  if name in ['README.md','LICENSE','LICENSE.txt','config.json','preprocessor_config.json','trainer_state.json','requirements.txt','app.py'] or name.endswith('Evaluation_Summary(42dim).txt'):
   prefix='spaces/' if kind=='spaces' else ''
   row['texts'].append(fetch('https://huggingface.co/'+prefix+repo+'/resolve/'+rev+'/'+urllib.parse.quote(name),folder/name))
 return row

def github(repo):
 folder=OUT/('gh-'+repo.replace('/','--'));row={'id':repo,'provider':'github','url':'https://github.com/'+repo}
 meta=fetch('https://api.github.com/repos/'+repo,folder/'metadata.json');row['metadata']=meta
 if meta['status']!='read':return row
 info=json.loads((folder/'metadata.json').read_text('utf8'));row['advertisedLicense']=info.get('license')
 commit=fetch('https://api.github.com/repos/'+repo+'/commits/'+info['default_branch'],folder/'commit.json')
 if commit['status']!='read':row['commitError']=commit;return row
 rev=json.loads((folder/'commit.json').read_text('utf8'))['sha'];row['revision']=rev
 tree=fetch('https://api.github.com/repos/'+repo+'/git/trees/'+rev+'?recursive=1',folder/'tree.json');row['treeEvidence']=tree
 if tree['status']!='read':return row
 files=json.loads((folder/'tree.json').read_text('utf8'));row['files']=files['tree'];row['treeTruncated']=files.get('truncated',False);row['texts']=[]
 for f in files['tree']:
  name=f['path']
  if f['type']=='blob' and (Path(name).name.lower() in ['readme.md','license','license.txt','license.md','copying','notice'] or (repo=='CISLAB-web/SGAUnet' and name.endswith('.py'))):
   row['texts'].append(fetch('https://raw.githubusercontent.com/'+repo+'/'+rev+'/'+urllib.parse.quote(name),folder/name))
 return row

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(hf,HF))+list(pool.map(github,GH))
 searches=[]
 for kind in ['models','datasets','spaces']:
  for query in ['acne','skin dryness','skin hydration','skin sagging','specular skin']:
   url='https://huggingface.co/api/'+kind+'?search='+urllib.parse.quote(query)+'&limit=30&full=true';searches.append(fetch(url,OUT/('search-hf-'+kind+'-'+query.replace(' ','-')+'.json')))
 for query in ['acne','skin hydration','skin dryness','face sagging']:
  url='https://gitlab.com/api/v4/projects?search='+urllib.parse.quote(query)+'&simple=true&per_page=30';searches.append(fetch(url,OUT/('search-gitlab-'+query.replace(' ','-')+'.json')))
 for query in ['acne dataset','facial skin moisture','skin flaking','facial sagging']:
  url='https://zenodo.org/api/records?q='+urllib.parse.quote(query)+'&size=20';searches.append(fetch(url,OUT/('search-zenodo-'+query.replace(' ','-')+'.json')))
 gitlab=fetch('https://gitlab.com/api/v4/projects/'+urllib.parse.quote('Jayesh-Hyalij/Skin-Acne-Identification',safe=''),OUT/'gitlab-requested-project.json');searches.append(gitlab)
 proof={'checkedAtUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hfCliVersion':'0.36.0: models info unsupported; public REST fallback','repositories':rows,'officialSearchEvidence':searches,'weightsExecuted':False,'privatePhotosUploaded':False}
 (OUT/'source-inventory.json').write_text(json.dumps(proof,indent=2),'utf8')
 for row in rows:print(json.dumps({k:row.get(k) for k in ['id','revision','advertisedLicense']}),flush=True)
 print(json.dumps({'searches':len(searches),'read':sum(r['status']=='read' for r in searches),'unavailable':[{'url':r['url'],'error':r['error']} for r in searches if r['status']!='read']}),flush=True)
if __name__=='__main__':main()
