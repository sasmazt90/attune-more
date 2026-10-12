"""Bounded real two-source product chain using the actual frozen winner.
Reuses the established source selection without overwriting its saved diagnosis.
"""
import json
from pathlib import Path
from expanded_sources import ROOT,OUT

source=ROOT/'scripts/skin-research/complete_front_filter_control.py'
code=source.read_text('utf8')
old="snap=json.loads((d/'start.json').read_text())['phaseSnapshots']['negative-yolox'];"
new="selected_model=json.loads((d/'frozen-detector-selection.json').read_text())['selected']['model'];snap=dict(snapshot=str(Path(selected_model['folder'])/'model.safetensors'),modelSHA256=selected_model['sha256']);"
assert old in code;code=code.replace(old,new).replace('front-filter-selection.json','selected-detector-product-selection.json').replace('front-filter-control.json','selected-detector-product-chain.json')
old="results.append(dict(sha256=r['sha256'],modelSHA256=snap['modelSHA256'],"
new="stage=d/'selected-detector-product-staging';stage.mkdir(exist_ok=True);(stage/(r['sha256'][:12]+'.json')).write_text(json.dumps(dict(dataUrl=photo,photoId=capture,width=im.shape[1],height=im.shape[0],angle='FRONT',meshes=mesh['meshes'],exclusions=[],maps=analysis['maps'],rows={k:next(v for v in rows if v['id']=='acne') for k,rows in analysis['measurements'].items() if k!='periorbital'}|{'overview':next(v for v in analysis['general']['measurements'] if v['id']=='acne')})),'utf8');results.append(dict(sha256=r['sha256'],modelSHA256=snap['modelSHA256'],"
assert old in code;code=code.replace(old,new)
exec(compile(code,str(source),'exec'),{'__name__':'__main__','__file__':str(source)})
