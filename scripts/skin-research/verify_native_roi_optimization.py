"""Exact fields against frozen Git source, streamed one source, measured RSS."""
import os
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[key]='1'
import json,sys,time,types,subprocess,hashlib
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-camera-scope-20261013';OUT.mkdir(exist_ok=True);sys.path.insert(0,str(ROOT/'services/core-api'))
signature=hashlib.sha256((ROOT/'services/core-api/native_flake_support.py').read_bytes()+(ROOT/'services/core-api/material_component_features.py').read_bytes()).hexdigest()
checkpoint=OUT/'roi-parity-progress.json';progress=json.loads(checkpoint.read_text('utf8')) if checkpoint.exists() else {'signature':signature,'rows':[]};assert progress['signature']==signature
rows=progress['rows'];completed={(r['control'],r['factor']) for r in rows}
with HeavyJobLease('CD-native-ROI-exact-parity',peak_mib=500,minimum_available_mib=1200) as lease:
    import cv2,numpy as np
    import native_flake_support as F,material_component_features as M
    cv2.setNumThreads(1)
    old=types.ModuleType('frozen_proposal');exec(subprocess.check_output(['git','show','ed3cd37dd59a300e5071c403ce1e3788197ccd58:services/core-api/native_flake_support.py'],cwd=ROOT).decode('utf8'),old.__dict__)
    old_m=types.ModuleType('frozen_geometry');exec(subprocess.check_output(['git','show','ed3cd37dd59a300e5071c403ce1e3788197ccd58:services/core-api/material_component_features.py'],cwd=ROOT).decode('utf8'),old_m.__dict__)
    # Small fixed material crops, source positions unchanged. No full photo pool.
    controls=json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json').read_text('utf8'))['controls']
    for c in controls:
        lease.check();source=cv2.imread(c['sourcePath']);x,y,w,h=c['roi'];x0=max(0,x-64);y0=max(0,y-64);image=source[y0:min(source.shape[0],y+h+64),x0:min(source.shape[1],x+w+64)];del source
        for factor in [1.,.5]:
            if (c['controlIndex'],factor) in completed:continue
            im=image if factor==1 else cv2.resize(image,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA);metric=min(c.get('referenceSpan',640)/640,1)*factor
            before=old.proposal_tile(im,metric,pixel_density=factor,check=lease.check);after=F.proposal_tile(im,metric,pixel_density=factor,check=lease.check);assert np.array_equal(before,after)
            # Eligibility is not a label: arbitrary source-coordinate anatomy
            # stand-in verifies holes/core clipping; optical hit scope unchanged.
            yy,xx=np.mgrid[:im.shape[0],:im.shape[1]];eligible=((xx-im.shape[1]/2)**2/(im.shape[1]*.4)**2+(yy-im.shape[0]/2)**2/(im.shape[0]*.4)**2)<1
            t=time.monotonic();a,meta_a=old.native_field(im,metric,eligible,check=lease.check,pixel_density=factor);old_s=time.monotonic()-t;t=time.monotonic();b,meta_b=F.native_field(im,metric,eligible,check=lease.check,pixel_density=factor);new_s=time.monotonic()-t;assert np.array_equal(a,b)
            labels_a,g_a=old_m.describe(im,b,metric);labels_b,g_b=M.describe(im,b,metric);assert np.array_equal(labels_a,labels_b) and g_a==g_b
            rows.append(dict(source=c['sourceSHA256'],control=c['controlIndex'],factor=factor,sourceOrigin=[x0,y0],fieldByteExact=True,componentFeaturesExact=True,beforeSeconds=old_s,afterSeconds=new_s,work=meta_b));print(json.dumps({k:v for k,v in rows[-1].items() if k not in ['work','source']}),flush=True)
            checkpoint.write_text(json.dumps(dict(signature=signature,rows=rows,resource=lease.receipt()),indent=2),'utf8')
        del image
    resource=lease.receipt()
receipt=dict(rows=rows,resource=resource,sourceDownsampleForPerformance=False,controlledHalfOnly=True,originalProposalThresholdsChanged=False)
(OUT/'roi-exact-parity.json').write_text(json.dumps(receipt,indent=2),'utf8')
