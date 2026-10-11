"""Separate annotated polygon overlap from unlabelled whole-ROI coverage.

Unknown lower-lid pixels are not declared normal negatives. Engineering visual
review cannot supply missing expert labels for pigment, shadow or swelling.
"""
import json,sys
import cv2,numpy as np,onnxruntime as ort
from PIL import Image,ImageDraw
from train_focused_local import setup,bag_rois,bag_tensor,OUT as OLD
from diagnose_followup import NEW,write
from prepare_focused_data import ROOT,sha
sys.path.insert(0,str(ROOT/'services/core-api'))
from skin_models import eye_rois
def main():
    cv2.setNumThreads(1);source=setup('bags');positive=bag_rois(source['validation']);train=source['train'];manifest=json.loads((OLD/'learning-manifest.json').read_text());dev=[r for r in manifest['rows'] if r['corpus']=='eye' and r['eligible'] and r['split']=='validation']
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;session=ort.InferenceSession(str(OLD/'bags/candidate.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    rows=[];samples=[]
    for t in positive:
        x,y,s=bag_tensor(t);p=(session.run(None,{'rgb_eye_roi':x[None].numpy()})[0][0,0]>0);truth=y.numpy()[0].astype(bool);support=s.numpy()[0].astype(bool);inter=int((p&truth&support).sum());union=int(((p|truth)&support).sum());poly=int(truth.sum());unknown=int((p&~support).sum())
        rows.append(dict(sha256=t['row']['sha256'],group=t['row']['group'],eye=t['eye'],Dice=2*inter/max(1,int((p&support).sum())+poly),IoU=inter/max(1,union),wholeROIPredictedFraction=float(p.mean()),outsideSupervisedBandPredictedPixels=unknown,outsideSupervisedBandGroundTruth='unknown',wholeROIFalsePositiveRate=None,normalNegativeKnown=False))
    # Deterministic source selection by hash, not model success/failure.
    pos=sorted(positive,key=lambda t:t['row']['sha256'])[:12]
    unknown=[]
    for r in sorted(dev,key=lambda r:r['sha256']):
        if any(a['classId']==1 for a in r['annotations']):continue
        points={int(k):v for k,v in r['eyeLandmarks'].items()}
        for roi in eye_rois(points,r['width'],r['height']):unknown.append(dict(row=r,eye=roi['eye'],rect=roi['rect'],annotations=[]))
        if len(unknown)>=12:break
    chosen=pos+unknown[:12];sheet=Image.new('RGB',(1200,6*192),(12,18,30));d=ImageDraw.Draw(sheet)
    for k,t in enumerate(chosen):
        x,truth,support=bag_tensor(t);p=session.run(None,{'rgb_eye_roi':x[None].numpy()})[0][0,0]>0;a,b,c,e=t['rect'];bgr=cv2.imread(t['row']['absolutePath']);rgb=cv2.resize(bgr[b:e,a:c,::-1],(128,128));overlay=rgb.copy();overlay[p]=(overlay[p]*.6+np.array([0,210,245])*.4).astype(np.uint8);mask=truth.numpy()[0]>0
        # Green outline: source polygon; cyan: predictions, full ROI.
        contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);cv2.drawContours(overlay,contours,-1,(255,220,0),1)
        left=k%4*300;top=k//4*192;sheet.paste(Image.fromarray(rgb),(left,top));sheet.paste(Image.fromarray(overlay),(left+136,top));d.text((left+3,top+132),f'{k} / {t["eye"]} / {t["row"]["sha256"][:12]}',fill='white');d.text((left+3,top+148),'polygon labelled' if t['annotations'] else 'unlabelled lower lid != normal',fill='white');d.text((left+3,top+164),f'whole ROI candidate area {p.mean():.3f}',fill='white')
        samples.append(dict(index=k,sha256=t['row']['sha256'],group=t['row']['group'],eye=t['eye'],rect=t['rect'],sourceHasNonRectBagPolygon=bool(t['annotations']),wholeROIPredictedFraction=float(p.mean()),wholeROINegativeExpertLabel=False,engineeringReviewOnly=True))
    sheet.save(NEW/'bags-development-coverage.png')
    write('bags-coverage-review.json',dict(modelSHA256=sha(OLD/'bags/candidate.onnx'),developmentPolygonROIs=len(rows),polygonDice=float(np.mean([r['Dice'] for r in rows])),polygonIoU=float(np.mean([r['IoU'] for r in rows])),rows=rows,samples=samples,wholeROIConfounderSpecificityEstablished=False,expertNormalDarkShadowLabelsAvailable=False,expertLabelsInvented=False,oldFinalOpened=False,architectureFailureEstablished=False,productAccepted=False,remaining='Need fully supervised lower-lid normal/pigment/shadow/bag source groups to estimate specificity. Unlabelled outside polygon is unknown; engineering review records omissions, not expert ground truth.'))
    print(json.dumps(dict(annotatedDevelopmentROIs=len(rows),Dice=float(np.mean([r['Dice'] for r in rows])),IoU=float(np.mean([r['IoU'] for r in rows])),wholeROIFPR=None)),flush=True)
if __name__=='__main__':main()
