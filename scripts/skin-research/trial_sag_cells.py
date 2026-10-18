"""Single bounded closed-cell/target-center trial, production source untouched."""
import importlib.util,itertools,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
from load_dry_sag_baseline import load_baseline
A,IA,_=load_baseline()
OUT=ROOT/'audit-results/dry-sag-product-20261013';FROZEN=ROOT/'.runtime/dry-sag-baseline-20261013'
code=(FROZEN/'instant_appearance.py').read_text('utf8')
code=code.replace("profile=curve_profile(gray,skin,p[indices],direction,offsets,native_width,center_support=eligible) if region=='periorbital' else curve_profile(gray,skin,p[indices],direction,offsets,native_width)","profile=curve_profile(gray,skin,p[indices],direction,offsets,native_width,center_support=eligible)")
code=code.replace("joint = float(np.mean(q['values'] * edge_gate)) * continuity_gate * boundary_gate","visible=q['observedSamples'];joint = float(np.mean((q['values'] * edge_gate)[visible])) * continuity_gate * boundary_gate if visible.any() else 0.")
code=code.replace("[98,205,206,216,61]","[100,142,203,206]").replace("[61,186,172,136]","[206,212,202]")
code=code.replace("[327,425,426,436,291]","[329,371,423,426]").replace("[291,410,397,365]","[426,432,422]")
code=code.replace("elif region=='chin':paths=[('lower-right',[206,212,202]),('lower-left',[426,432,422])];offsets=np.arange(-10,11);direction=horizontal", "elif region=='chin':paths=[('mental',[201,200,421])];offsets=np.arange(-10,11);direction=vertical")
namespace={};exec(compile(code,str(FROZEN/'target-center-trial.py'),'exec'),namespace)
def cells(mesh):
 edges={tuple(sorted(e)) for e in mesh['edges']};neighbors={i:set() for i in range(len(mesh['points']))}
 for a,b in edges:neighbors[a].add(b);neighbors[b].add(a)
 found={};p=np.asarray([[v['x'],v['y']] for v in mesh['points']],np.float32)
 for a,b in itertools.combinations(neighbors,2):
  if (a,b) in edges:continue
  for c,d in itertools.combinations(sorted(neighbors[a]&neighbors[b]),2):
   if tuple(sorted((c,d))) in edges:continue
   cell=[a,c,b,d]
   if cv2.isContourConvex(p[cell]):found[tuple(sorted(cell))]=cell
 return list(found.values())
rows=[]
for prefix in ['515cc548','05619d0a','e0ee9f0c','5bd42346','d3e8bb60']:
 p=json.loads((OUT/(prefix+'-payload.json')).read_text('utf8'));proxy=A.instant_proxy;captured=[]
 def trial(*args,**kw):
  if args[3] not in ('rightCheek','leftCheek','chin'):return proxy(*args,**kw)
  gray,eligible,pts,region,conditions,scale,origin,shape,hair,context,clipped,exposed=args;mask=A.polygon_mask(gray.shape,p['meshes'][region],scale,origin).astype('uint8')
  cc=cells(p['meshes'][region])
  for cell in cc:
   coords=np.asarray([[(p['meshes'][region]['points'][i]['x']-origin[0])*scale,(p['meshes'][region]['points'][i]['y']-origin[1])*scale] for i in cell],np.int32);cv2.fillPoly(mask,[coords],1)
  target=(mask>0)&context&~hair;result=namespace['instant_proxy'](gray,target,*args[2:],**kw);captured.append(dict(region=region,cells=len(cc),oldTarget=int(eligible.sum()),newTarget=int(target.sum()),value=result[0],reason=result[-1],sides=result[1].get('sides')));return result
 A.instant_proxy=trial
 try:r=A.analyze_skin(p)
 finally:A.instant_proxy=proxy
 row=dict(source=prefix,regions=captured,overview=next(v for v in r['general']['measurements'] if v['id']=='sag')['value']);rows.append(row);print(json.dumps(row),flush=True)
(OUT/'sag-guide-trial.json').write_text(json.dumps(rows,indent=2),'utf8')
