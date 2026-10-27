"""Spearman between blind visual severity ratings (1-3) of positives and candidate indices."""
import json, collections, numpy as np
from scipy.stats import spearmanr
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
R=json.load(open(f'{S}/rate/ratings.json')); K=json.load(open(f'{S}/rate/key.json'))
D=json.load(open(f'{S}/rf/dino_logit_index.json'))
F=json.load(open(f'{S}/rf/severity_feats.json')); by=collections.defaultdict(dict)
for k,v in F.items(): kid,p=k.split('|'); by[kid][p]=v
DC=json.load(open(f'{S}/rf/darkcircle.json')); SG=json.load(open(f'{S}/rf/sag_geo.json'))
def fr(name):
    def g(k):
        f=by.get(k,{}).get('front',{}); v=[f.get(f'{name}_{s}') for s in 'LR']; v=[x for x in v if x is not None and np.isfinite(x)]
        return np.mean(v) if v else None
    return g
def single(name): return lambda k: by.get(k,{}).get('front',{}).get(name)
def akne(k):
    f=by.get(k,{}).get('front',{}); v=[f.get(n) for n in ('pig_frac_L','pig_frac_R','pig_frac_chin')]; v=[x for x in v if x is not None]
    return np.mean(v) if v else None
def dc(i,nm='corr'): return lambda k: DC.get(k,{}).get(nm,[None]*4)[i]
def dcE(k):
    c=DC.get(k,{}).get('corr'); return None if c is None else float(np.hypot(c[0],np.hypot(c[2],c[3])))
def sg(n): return lambda k: SG.get(k,{}).get('f',{}).get(n)
def dino(n): return lambda k: D[n].get(k)
C={'torba':[('DINOv2',dino('Göz altı torbası')),('profil ham',fr('bag_raw')),('profil düz.',fr('bag_corr')),('oluk eğimi',fr('bag_raw_slope'))],
 'morluk':[('DINOv2',dino('Göz altı morluğu')),('dL düz.',dc(0)),('da',dc(2)),('db',dc(3)),('dE düz.',dcE),('dL ham',dc(0,'raw'))],
 'kapak':[('DINOv2',dino('Göz kapağı düşüklüğü')),('aperture',sg('aperture')),('brow_lid',sg('brow_lid')),('crease_lid',sg('crease_lid'))],
 'kaz':[('DINOv2',dino('Kaz ayakları')),('çizgi gücü',fr('crow'))],
 'alin':[('DINOv2',dino('Alın çizgileri')),('fore_h',single('fore_h')),('fore_h_p90',single('fore_h_p90')),('fore_any',single('fore_any'))],
 'akneizi':[('DINOv2',dino('Akne izi')),('pigment alanı',akne),('leke sayısı',fr('pig_blobs'))],
 'ucuk':[('DINOv2',dino('Dudakta uçuk'))]}
out={}
for f,cands in C.items():
    r=np.array(R[f]); ks=K[f]; print(f'\n{f}: n={len(r)} dağılım={np.bincount(r,minlength=4)[1:].tolist()}')
    for nm,g in cands:
        v=[g(k) for k in ks]; m=np.array([x is not None and np.isfinite(x) for x in v])
        if m.sum()<8: print(f'  {nm:14s} n={m.sum()} yetersiz'); continue
        vv=np.array([x for x,o in zip(v,m) if o],float); rho=spearmanr(r[m],vv).correlation
        # bootstrap CI
        rng=np.random.default_rng(0); bs=[]
        for _ in range(500):
            i=rng.integers(0,m.sum(),m.sum()); 
            if len(set(r[m][i]))>1: bs.append(spearmanr(r[m][i],vv[i]).correlation)
        print(f'  {nm:14s} n={m.sum():2d} rho={rho:+.2f}  [%{5}-95: {np.nanpercentile(bs,5):+.2f}, {np.nanpercentile(bs,95):+.2f}]')
