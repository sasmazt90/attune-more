exec(open('rules.py').read().split("out={}")[0])
for tn,sc in [('oily','oily_models+shine'),('dry','dry_models+flake'),('sens','sens_mean')]:
  rows,yl,_=TASKS[tn]
  for part in ('fit','test'):
    rr=[r for r in rows if (r['test'] if part=='test' else not r['test'])]; y=np.array([yl(r) for r in rr]); s=np.array([SC[sc](r) for r in rr])
    print(tn,part,' '.join(f"{t}:P{prf(y,(s>=t).astype(int))['P']}/R{prf(y,(s>=t).astype(int))['R']}" for t in (0.1,0.15,0.2,0.25,0.3,0.35,0.4,0.45,0.5)))
# dry vs oily conflict: dry-labelled regions that score oily and vice versa
rows=[r for r in face if r['type'] in ('dry','oily') and r['set']!='ka1tj']
import collections; c=collections.Counter()
for r in rows:
  o=SC['oily_models+shine'](r)>=0.25; d=SC['dry_models+flake'](r)>=0.1
  c[(r['type'],'O' if o else '-','D' if d else '-')]+=1
print(sorted(c.items()))
