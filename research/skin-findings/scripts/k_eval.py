"""Compare regional v3 decisions on the new K- profiles with the generation sheet (expected values)."""
import json,re,collections,sys,numpy as np,openpyxl
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0,f'{S}/repo/claude-skin/services/core-api')
from regional_skin_v3 import Decider,tone_group,skin_type_from_regions
dec=Decider(json.load(open(f'{S}/repo/claude-skin/services/core-api/models/regional-skin-v3/params.json')))
wb=openpyxl.load_workbook('/mnt/user-data/uploads/Customer Profiles/dermatolojik_karakter_profilleri.xlsx',data_only=True)
EXP={}
RMAP={'alın':'forehead','burun':'nose','sağ yanak':'rightCheek','sol yanak':'leftCheek','çene':'chin'}
TMAP={'normal':'normal','kuru':'dry','yağlı':'oily'}
for kid,txt in list(wb.active.iter_rows(values_only=True))[1:]:
  t=txt.lower().replace('\xa0',' ').replace('◦',';').replace('▪',';'); e=dict(regions={},overall=None,sens=False,sensRegions=set(),fst=None)
  m=re.search(r'fitzpatrick\)?:\s*(vi|v|iv|iii|ii|i)\b',t) or re.search(r'ten tonu:\s*(vi|v|iv|iii|ii|i)\b',t)
  if m: e['fst']=m.group(1).upper()
  m=re.search(r'bölge bazında cilt tipi:(.*?)•',t+'•')
  if m:
    for part in m.group(1).split(';'):
      if ':' in part:
        rn,v=[x.strip() for x in part.split(':',1)]
        if rn in RMAP and v in TMAP: e['regions'][RMAP[rn]]=TMAP[v]
  m=re.search(r'cilt tipi:\s*(normal|kuru|yağlı|karma)',t)
  if m and not e['regions']: e['overall']=m.group(1)
  for key in ('kızarıklık','rozasea','egzama / atopik','sedef'):
    m=re.search(re.escape(key)+r':\s*([^•;]*)',t)
    if m and not m.group(1).strip().startswith('yok'):
      e['sens']=True
      for rn,app in RMAP.items():
        if rn in m.group(1): e['sensRegions'].add(app)
      if 'sağ ve sol yanak' in m.group(1): e['sensRegions']|={'rightCheek','leftCheek'}
      if 'cilt geneli' in m.group(1): e['sensRegions']|=set(RMAP.values())
  m=re.search(r'hassasiyet/durum:\s*([^,]*(?:,[^:]*)?)bulgular',t)
  if m and m.group(1).strip().strip(',').strip()!='yok': e['sens']=True
  EXP[kid]=e
I={it['id']:it for it in json.load(open(f'{S}/rf/items_k.json'))+json.load(open(f'{S}/rf/items_k4.json'))}; F=json.load(open(f'{S}/rf/feats2_k.json'))+json.load(open(f'{S}/rf/feats2_k4.json'))
by=collections.defaultdict(dict)
for r in F: by[r['id']][r['region']]=r
subs=collections.defaultdict(list)
for i,it in I.items(): subs[re.match(r'(K-\d+)',it['key']).group(1)].append(i)
def name(regs):
  st=[v for v in regs.values()]
  if 'oily' in st and any(s in('dry','normal') for s in st): return 'karma'
  if st and all(s=='oily' for s in st): return 'yağlı'
  if 'dry' in st: return 'kuru'
  return 'normal'
TR={'combination':'karma','oily':'yağlı','dry':'kuru','normal':'normal'}
rows=[]; reg_ok=collections.Counter(); reg_n=collections.Counter(); conf=collections.Counter()
for kid,e in sorted(EXP.items()):
  if kid not in subs: continue
  ids=subs[kid]; front=min(ids,key=lambda i:abs(I[i]['yaw'])); pos=[i for i in ids if I[i]['yaw']>10.5]; neg=[i for i in ids if I[i]['yaw']<-10.5]
  src={'forehead':(front,'forehead'),'nose':(front,'nose'),'chin':(front,'chin'),'rightCheek':(pos[0] if pos else front,'cheek_imgL'),'leftCheek':(neg[0] if neg else front,'cheek_imgR')}
  reg={}
  for app,(i,rn) in src.items():
    r=by[i].get(rn); tone=tone_group(r['f']['ita']) if r else 'light'
    reg[app]=dict(dec.region(r['f'] if r else None,rn,tone),tone=tone)
  t=skin_type_from_regions(reg); ours=TR.get(t['value'],'belirsiz'); ours_s=t['sensitive']
  exp_name=name(e['regions']) if e['regions'] else e['overall']
  for app,ex in e['regions'].items():
    got=reg[app]['state']
    if got=='unmeasured': continue
    reg_n[(e['fst'],ex)]+=1; reg_ok[(e['fst'],ex)]+=got==ex; conf[(ex,got)]+=1
  sens_reg_hits=sum(reg[a]['sensitive'] for a in e['sensRegions']) if e['sensRegions'] else None
  rows.append((kid,e['fst'],exp_name,ours,e['sens'],ours_s,' '.join(f"{a[:2]}:{reg[a]['state'][:3]}{'+S' if reg[a]['sensitive'] else ''}" for a in reg),reg[ 'forehead']['tone']))
print(f"{'id':6s} FST  beklenen   bizim      hassas(b/biz)  bölgeler")
for r in rows: print(f"{r[0]:6s} {str(r[1]):4s} {str(r[2]):10s} {r[3]:10s} {str(r[4])[0]}/{str(r[5])[0]}  {'✓' if r[2]==r[3] else '✗'}{'✓' if r[4]==r[5] else '✗'}  {r[6]}  ton={r[7]}")
n=len(rows); print('\nkişi bazında cilt tipi doğru:',sum(r[2]==r[3] for r in rows),'/',n,' | hassas doğru:',sum(r[4]==r[5] for r in rows),'/',n)
print('bölge bazında (beklenen→bizim):',dict(conf))
for ex in ('oily','dry','normal'):
  tot=sum(v for (f,e2),v in reg_n.items() if e2==ex); ok=sum(v for (f,e2),v in reg_ok.items() if e2==ex)
  print(f"  beklenen {ex:6s}: {ok}/{tot} doğru")
light={'I','II','III'};
for grp,fs in (('açık-orta (I-III)',{'I','II','III'}),('esmer (IV)',{'IV'}),('koyu (V-VI)',{'V','VI'})):
  tot=sum(v for (f,e2),v in reg_n.items() if f in fs); ok=sum(v for (f,e2),v in reg_ok.items() if f in fs)
  print(f"  {grp}: {ok}/{tot}")
