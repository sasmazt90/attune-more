exec(open('rules.py').read().split("out={}")[0])
O=SC['oily_models+shine']; Dd=SC['dry_models+flake']
rows=[r for r in face if r['type'] in('oily','dry','normal') and r['set']!='ka1tj']
def dec(r,To,Td,mode):
  o,d=O(r),Dd(r); io,id_=o>=To,d>=Td
  if io and id_:
    if mode=='oily_first': return 'oily'
    return 'oily' if o/To>=d/Td else 'dry'
  return 'oily' if io else ('dry' if id_ else 'normal')
def ev(rr,To,Td,mode):
  y=[r['type'] for r in rr]; p=[dec(r,To,Td,mode) for r in rr]; out={}
  for c in ('oily','dry','normal'):
    tp=sum(a==c and b==c for a,b in zip(y,p)); fp=sum(a!=c and b==c for a,b in zip(y,p)); fn=sum(a==c and b!=c for a,b in zip(y,p))
    P=tp/max(tp+fp,1); R=tp/max(tp+fn,1); out[c]=dict(P=round(P,3),R=round(R,3),F1=round(2*P*R/max(P+R,1e-9),3),n=tp+fn)
  out['macroF1']=round(np.mean([out[c]['F1'] for c in ('oily','dry','normal')]),3); return out
fit=[r for r in rows if not r['test']]; te=[r for r in rows if r['test']]
best=max(((ev(fit,To,Td,m)['macroF1'],To,Td,m) for To in np.arange(0.15,0.55,0.025) for Td in np.arange(0.05,0.4,0.025) for m in ('oily_first','ratio')))
_,To,Td,m=best; print('chosen',round(To,3),round(Td,3),m,'fit',ev(fit,To,Td,m)); print('TEST',ev(te,To,Td,m))
import collections
for s in sorted({r['set'] for r in te}): print(' ',s,ev([r for r in te if r['set']==s],To,Td,m))
json.dump(dict(To=float(To),Td=float(Td),mode=m,fit=ev(fit,To,Td,m),test=ev(te,To,Td,m)),open('three_results.json','w'),indent=1)
