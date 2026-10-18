"""Native anatomy/score/source-coordinate verification on actual product inputs.

Staging only: failed material separation prevents normal product selection.
"""
import base64,hashlib,json,sys,time
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-dry-scale-20261013'
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
from native_dry_path import analyze_native_dry
cv2.setNumThreads(1)
def decode(url):return cv2.imdecode(np.frombuffer(base64.b64decode(url.split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)

def main():
    paths=list((ROOT/'audit-results/dry-sag-component-followup-20261013/product').glob('*/*-automatic-payload.json'))
    paths.append(ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json')
    # One already captured high-resolution browser source exercises actual
    # overlapping native tiles. No new population scan or hosted call.
    labels=json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json').read_text('utf8'))
    control=next(c for c in labels['controls'] if c['controlIndex']==15)
    probe_path=ROOT/'audit-results/dry-sag-native-followup-20261013'/(control['sourceSHA256'][:8]+'-probe.json')
    probe=json.loads(probe_path.read_text('utf8'));s=probe['snapshot']
    p=dict(processingConsent=True,hostedProcessingConsent=False,photo=s['dataUrl'],photoId=s['photoId'],pose=s['angle'],meshes=s['meshes'],exclusions=s['exclusions'],landmarks=s['landmarks'],qualityValid=probe['quality']['isValid'],conditions=probe['conditions'],temporal=[s['landmarks']]*3)
    native_path=OUT/(control['sourceSHA256'][:8]+'-native-payload.json');native_path.write_text(json.dumps(p),'utf8');paths.append(native_path)
    rows=[]
    for path in paths:
        payload=json.loads(path.read_text('utf8'));assert not payload['hostedProcessingConsent'];start=time.monotonic();baseline=A.analyze_skin(payload);result=analyze_native_dry(payload)
        bgr,digest=A.decode_photo(payload['photo']);original=bgr.copy();geometry=[];scores=[]
        for region,row in result['measurements'].items():
            old=next(v for v in baseline['measurements'][region] if v['id']=='dry');scores.append(dict(region=region,currentV3=old['value'],nativeStaging=row['value'],nativeReason=row['limitationCode'],acceptedPixels=row['components']['acceptedMaterialSourcePixels'],eligiblePixels=row['evaluatedArea']['sourcePixels']))
            if row['value'] is None:continue
            layer=result['maps'][region+':dry'];rgba=decode(layer['dataUrl']);valid=decode(layer['validMaskUrl'])>0;active=rgba[:,:,3]>0
            assert layer['step']==1 and not (active&~valid).any()
            ys,xs=np.where(active);sx=xs+int(layer['x']);sy=ys+int(layer['y']);anatomy=A.closed_surface_mask(bgr.shape[:2],payload['meshes'][region],1)
            outside=int((~anatomy[sy,sx]).sum());assert outside==0
            assert int(active.sum())==row['components']['acceptedMaterialSourcePixels'];assert int(valid.sum())==row['evaluatedArea']['sourcePixels']
            assert row['value']==100*active.sum()/max(1,valid.sum())
            geometry.append(dict(region=region,sourceGrid=[bgr.shape[1],bgr.shape[0]],origin=[layer['x'],layer['y']],step=layer['step'],activePixels=int(active.sum()),outsideNativeAnatomy=outside,visibleAreaScore=row['value'],mapSHA256=hashlib.sha256(base64.b64decode(layer['dataUrl'].split(',')[1])).hexdigest()))
            preview=bgr.copy();preview[sy,sx]=(.45*preview[sy,sx]+.55*np.array([0,0,255])).astype(np.uint8);cv2.imwrite(str(OUT/(path.name[:8]+'-'+region+'-native-staging.png')),preview)
        assert np.array_equal(bgr,original)
        after=A.analyze_skin(payload);unchanged=all(after[k]==baseline[k] for k in ['measurements','maps','contours']) and after.get('general',{}).get('measurements')==baseline.get('general',{}).get('measurements')
        assert unchanged
        (OUT/(path.name[:8]+'-native-staging.json')).write_text(json.dumps(result),'utf8')
        rows.append(dict(source=path.name[:8],payloadSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),photoId=digest,seconds=time.monotonic()-start,scores=scores,nativeMetadata=result['nativeMetadata'],maps=geometry,currentProductionUnchanged=unchanged,normalProductEnabled=False))
        print(json.dumps(dict(source=path.name[:8],scores=scores,nativeMetadata=result['nativeMetadata'])),flush=True)
    (OUT/'native-staging-path.json').write_text(json.dumps(dict(rows=rows,acceptedForProduction=False,reason='native component separation fails fixed familiar-development object and negative criteria'),indent=2),'utf8')

if __name__=='__main__':main()
