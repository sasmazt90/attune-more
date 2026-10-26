import json,numpy as np,collections
exec(open('rules.py').read().split("out={}")[0])
sc=SC['oily_models+shine']; rows,yl,_=TASKS['oily']; te=[r for r in rows if r['test']]
fp=[r for r in te if sc(r)>=0.25 and yl(r)==0]
c=collections.Counter()
for r in fp:
  g=r['gt']; ok=max(g.get('oily',0),g.get('Oily',0),g.get('Yagli Cilt',0))
  c[(r['set'],'partialOilyGT' if ok>0 else ('imgHasOily' if any(k in r['classes'] for k in('oily','Oily','Yagli Cilt')) else 'noOily'))]+=1
print('OILY FP breakdown',sorted(c.items()))
sc=SC['sens_mean']; rows,yl,_=TASKS['sens']; te=[r for r in rows if r['test']]
fp=[r for r in te if sc(r)>=0.425 and yl(r)==0]; c=collections.Counter()
for r in fp:
  g=r['gt']; ks=[k for k,v in g.items() if v>0]
  c[(r['set'],'partialRedGT' if g.get('Redness',0)>0 or g.get('Rozasea',0)>0 else ('inflamOther:'+','.join(sorted(set(ks)&{'Egzema','Sedef ve Dokuntu','Akne','Ucuk'})) if set(ks)&{'Egzema','Sedef ve Dokuntu','Akne','Ucuk'} else 'none'))]+=1
print('SENS FP breakdown',sorted(c.items()))
json.dump([dict(id=r['id'],region=r['region'],set=r['set']) for r in fp],open('sens_fp.json','w'))
