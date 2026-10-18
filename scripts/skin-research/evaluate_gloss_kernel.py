"""Execute the pinned MIT object-gloss kernel, without MATLAB or pickle.

This is a kernel-response reproduction on ORIGINAL TRAINING-domain renders.
It is expressly not an independent model test, a skin map or a sebum estimate.
The repository publishes the kernel but not the complete inference bias/state.
Only our affine response calibration is fitted on the calibration partition.
"""
import concurrent.futures,csv,hashlib,io,json,time
from pathlib import Path
import cv2,numpy as np,requests,scipy.io
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/skin-expanded-20261008/gloss'
REV='884485d02f73d1a9aa079d3355dc4c774d36c994'
BASE=f'https://raw.githubusercontent.com/takuma929/gloss_tinynetworks/{REV}/'
FILES=['LICENSE','data/humanlabel.csv','data/networks/human_onelayer_kernelN1_trainedby3888imgs/kernel.mat']

def download(name):
    path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        response=requests.get(BASE+name,timeout=60);response.raise_for_status()
        assert len(response.content)<2_000_000
        path.write_bytes(response.content)
    return {'path':name,'url':BASE+name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def metrics(y,p):
    return {'MAE':float(np.abs(y-p).mean()),'RMSE':float(np.sqrt(np.mean((y-p)**2))),
            'bias':float(np.mean(p-y)),'PearsonR':float(np.corrcoef(y,p)[0,1]) if np.std(p)>0 else None}

def main():
    OUT.mkdir(parents=True,exist_ok=True);started=time.perf_counter()
    provenance=[download(n) for n in FILES]
    assert provenance[0]['sha256']=='ed28f8499e137e21b36414cd22dea40a09bea8c9a84c420c1f1cd61227cfafa4'
    # Freeze selection and partition before inspecting responses; no threshold search.
    ids=np.arange(1,3889,27);cal=np.arange(len(ids))%2==0;test=~cal
    protocol={'ids':ids.tolist(),'calibration':'even selection indices','evaluation':'odd selection indices',
              'seed':20261008,'independentModelTest':False,'reason':'author kernel was trained on all 3888 renders',
              'target':'human object-gloss perceptual response; not patient skin','unit':'paper human response units'}
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2),'utf8')
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        provenance+=list(pool.map(download,[f'data/imgs/imgs3888_bg_png/img{i}.png' for i in ids]))
    kernel=scipy.io.loadmat(OUT/FILES[2])['kernel'].astype('float32')
    assert kernel.shape==(15,15,3) and np.isfinite(kernel).all()
    labels=list(csv.DictReader((OUT/'data/humanlabel.csv').open(encoding='utf8')))
    by_id={int(row['imgN']):float(row['humanresponse']) for row in labels}
    assert len(by_id)==3888
    truth=np.array([by_id[int(i)] for i in ids])
    features=[];timings=[];rows=[]
    for i in ids:
        source=np.array(Image.open(OUT/f'data/imgs/imgs3888_bg_png/img{i}.png').convert('RGB'))
        assert source.shape==(224,224,3),source.shape
        im=source.astype('float32')/255.;t=time.perf_counter()
        # MATLAB flips the saved kernel before conv2: OpenCV cross-correlation
        # against the saved kernel therefore yields the same valid response.
        activation=sum(cv2.filter2D(im[:,:,c],cv2.CV_32F,kernel[:,:,c],borderType=cv2.BORDER_CONSTANT)[7:-7,7:-7] for c in range(3))
        response=float(activation.max());timings.append((time.perf_counter()-t)*1000)
        v=im.max(2);s=(v-im.min(2))/np.maximum(v,1e-6)
        luminance=im@np.array([.299,.587,.114]);mean=float(luminance.mean())
        # Explicit simple control, not the product's anatomical skin denominator.
        hsvArea=float(np.mean((v>.6)&(s<.42)))
        features.append([response,mean,hsvArea]);rows.append({'imageId':int(i),'kernelMaxResponse':response,'meanLuminance':mean,'simpleHSVArea':hsvArea,'humanResponse':float(truth[len(rows)])})
    features=np.array(features);comparison={}
    for j,name in enumerate(['learned-kernel-response','mean-luminance-control','HSV-area-control']):
        design=np.c_[features[cal,j],np.ones(cal.sum())];coef=np.linalg.lstsq(design,truth[cal],rcond=None)[0]
        pred=features[test,j]*coef[0]+coef[1]
        comparison[name]={'calibrationCoefficients':coef.tolist(),'evaluation':metrics(truth[test],pred)}
    report={**protocol,'revision':REV,'selectedImages':len(ids),'calibrationImages':int(cal.sum()),'evaluationImages':int(test.sum()),
            'ordinaryProductAccepted':False,'sourcePixelsModified':False,'localMapValidated':False,'weightFormat':'numeric MAT, scipy loadmat; no executable remote code',
            'kernelParameters':int(kernel.size),'weightBytes':provenance[2]['bytes'],'comparison':comparison,
            'runtime':{'totalSecondsIncludingDownloads':time.perf_counter()-started,'firstInferenceMs':timings[0],'warmMedianMs':float(np.median(timings[1:])),'warmP95Ms':float(np.percentile(timings[1:],95)),
                       'knownActivationAndRGBBytes':int(210*210*4+224*224*3*4),'processPeakMemoryMeasured':False},
            'missing':['complete original network bias/inference state','independent held-out training-disjoint kernel test','skin expert reflection masks','physical cross-camera light/repeat captures'],
            'provenance':provenance,'rows':rows}
    (OUT/'report.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['rows','provenance']}))

if __name__=='__main__':main()
