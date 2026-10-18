"""Replay saved V5 candidates against their exact product masks, without model inference."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
from experimental_acne_v5 import context_function
from acne_box_support import box_area
from acne_v5_product import scored_candidates

def inspect(saved):
    payload=saved['payload'];runtime=saved['response'];context=context_function()(payload)
    result=dict(photoId=payload['photoId'],sourceShape=list(context['bgr'].shape[:2]),origin=list(context['origin']),scale=context['scale'],regions={})
    for region,boxes in runtime['acneCandidates'].items():
        if region not in context['acne_envelopes']:continue
        anatomical=context['acne_envelopes'][region];support=anatomical&context['acne_skin'];rows=[]
        for box in boxes:
            source=[box['x']+box['width']/2,box['y']+box['height']/2]
            center=np.floor((np.asarray(source)-context['origin'])*context['scale']).astype(int)
            x,y=map(int,center);inside=0<=x<support.shape[1] and 0<=y<support.shape[0]
            pixels=int((box_area([box],support.shape,context['scale'],context['origin'])&support).sum())
            rows.append(dict(candidateId=box['candidateId'],box=box,sourceCenter=source,analysisCenter=[x,y],inAnalysis=inside,centerInAnatomical=bool(inside and anatomical[y,x]),centerInEligibleSupport=bool(inside and support[y,x]),scoredPixels=pixels))
        signal=box_area(boxes,support.shape,context['scale'],context['origin'])&support
        raw=float(signal.sum()/support.sum()*100)
        accepted,selection=scored_candidates(boxes,support,context['scale'],context['origin'],context['bgr'].shape[:2],region,payload['photoId'])
        after_signal=box_area(accepted,support.shape,context['scale'],context['origin'])&support;after_raw=float(after_signal.sum()/support.sum()*100)
        result['regions'][region]=dict(pointCount=len(boxes),denominatorAnalysisPixels=int(support.sum()),denominatorSourcePixels=float(support.sum()/context['scale']**2),unionScoredPixels=int(signal.sum()),rawBar=raw,displayPercent=int(np.floor(raw+.5)),candidates=rows,after=dict(pointCount=len(accepted),unionScoredPixels=int(after_signal.sum()),rawBar=after_raw,displayPercent=int(np.floor(after_raw+.5)),selection=selection))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    saved=json.loads(args.input.read_text('utf8'));value=inspect(saved);value['inputSHA256']=hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({r:{k:v for k,v in row.items() if k!='candidates'} for r,row in value['regions'].items()},indent=2))
