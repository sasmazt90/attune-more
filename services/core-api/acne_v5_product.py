"""V5 replaces acne only in the normal camera response; all other methods stay intact."""
import copy,hashlib,json
import numpy as np
from acne_box_support import box_area,VERSION as SUPPORT_VERSION
from skin_measurement_contract import attach_result_receipts
from experimental_acne_v5 import analyze,PreviewUnavailable,PreviewRejected,STEP0_HASH,V5_HASH,THRESHOLD

METHOD='appearance-acne-step0-verifier-v5-2'
SAMPLING='step0-staging-v5-scored-center-support-v2'
GRAPH_HASH='9c87475d9302aed16f09abedc109211c2ac1b49f22f465f86aab408a5244d0be'
MODEL_HASH=hashlib.sha256((STEP0_HASH+GRAPH_HASH+V5_HASH).encode()).hexdigest()
NORMALIZATION='unique-detection-box-anatomical-area-v2'

def scored_candidates(boxes,support,scale,origin,source_shape,region,photo):
    """One list for scoring, points and persistence. Never clamp or reassign a point.

    The detector/staging/verifier are frozen. A regional result may only expose
    their candidates whose actual center belongs to its scored anatomical skin
    and whose unchanged box contributes pixels to that same fixed support.
    """
    kept=[];rejected=[];h,w=support.shape;source_h,source_w=source_shape
    for box in boxes:
        center=np.array([box['x']+box['width']/2,box['y']+box['height']/2])
        x,y=np.floor((center-np.asarray(origin))*scale).astype(int)
        in_source=bool(0<=center[0]<source_w and 0<=center[1]<source_h)
        in_analysis=bool(0<=x<w and 0<=y<h)
        eligible=bool(in_analysis and support[y,x])
        pixels=int((box_area([box],support.shape,scale,origin)&support).sum())
        reason='REGION_ID_MISMATCH' if box.get('region',region)!=region else 'OUTSIDE_SOURCE' if not in_source else 'OUTSIDE_ANALYSIS' if not in_analysis else 'CENTER_OUTSIDE_SCORED_SUPPORT' if not eligible else 'NO_SCORED_BOX_PIXELS' if not pixels else None
        receipt=dict(candidateId=box['candidateId'],region=region,photoId=photo,sourceCenter=center.tolist(),analysisCenter=[int(x),int(y)],centerInScoredSupport=eligible,scoredPixels=pixels)
        if reason:rejected.append(dict(receipt,reason=reason,box=box))
        else:kept.append(dict(box,scoreSupportPixels=pixels))
    return kept,dict(version=SAMPLING,photoId=photo,region=region,inputCount=len(boxes),acceptedCount=len(kept),rejectedCount=len(rejected),rejected=rejected,supportSHA256=hashlib.sha256(support.tobytes()).hexdigest(),supportShape=list(support.shape),sourceOrigin=list(origin),analysisScale=scale,centerSampling='floor((sourceCenter-sourceOrigin)*analysisScale); no clamping',denominatorAnalysisPixels=int(support.sum()))

def non_acne_fingerprint(result):
    value=dict(measurements={region:[row for row in rows if row['id']!='acne'] for region,rows in result['measurements'].items()},maps={key:value for key,value in result['maps'].items() if not key.endswith(':acne')},contours=result['contours'],drynessRuntime=result.get('drynessRuntime'))
    if 'general' in result:value['general']={**result['general'],'measurements':[r for r in result['general']['measurements'] if r['id']!='acne']}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def replace_acne(result,payload,check=lambda:None):
    before=non_acne_fingerprint(result);check();runtime=None;context=None;failure=None
    try:
        runtime,context=analyze(payload,check,with_context=True)
        if runtime['photoId']!=result['photoId'] or runtime['sourceWidth']!=result['sourceWidth'] or runtime['sourceHeight']!=result['sourceHeight'] or runtime['model']['onnxSHA256']!=GRAPH_HASH or runtime['model']['verifierSHA256']!=V5_HASH:raise PreviewUnavailable('ACNE_V5_SOURCE_OR_MODEL_MISMATCH')
    except (PreviewUnavailable,PreviewRejected) as error:
        failure=str(error);runtime=None;context=None
    measured=[];final={};available_areas=[];selections={}
    def stamp(row,boxes,support,reason,anatomical=None):
        # Same unique detection-box / eligible anatomical area formula and unit
        # as appearance_analysis; no probability, new score or added floor.
        signal=box_area(boxes,support.shape,context['scale'],context['origin']) if context is not None else np.zeros(support.shape,bool)
        value=float(signal[support].mean()*100) if reason is None and support.any() else None
        area=copy.deepcopy(row['evaluatedArea'])
        if context is not None:area.update(scope=SUPPORT_VERSION,sourcePixels=float(support.sum()/context['scale']**2),analysisPixels=int(support.sum()),anatomicalSourcePixels=float((anatomical if anatomical is not None else support).sum()/context['scale']**2))
        row.update(value=value,type='appearance_proxy',methodVersion=METHOD,modelVersion='experimental-step0-verifier-v5-local-preview-v1',modelHash=MODEL_HASH if runtime else None,normalizationVersion=NORMALIZATION,quality='valid' if reason is None else 'invalid' if reason=='CAPTURE_QUALITY' else 'insufficient',limitationCode=reason,localMap=None,evaluatedArea=area,referenceId=None)
        row['components'].update(bounds=boxes if reason is None else [],candidateCount=len(boxes) if reason is None else 0,evaluatedArea=area,candidateBoxCoveragePercent=value,visibleCandidateAreaPercent=value,normalization='unique accepted detection-box pixels / visible anatomical source pixels *100',pixelSegmentation=False,filterVersion=SUPPORT_VERSION,clinicalSeverity=False,experimental=True,accepted=False,samplingSupportVersion=SAMPLING)
        if runtime:row['components']['inference']=dict(runtime['model'],tileCount=runtime['tileCount'],detectorForwardCount=runtime['detectorForwardCount'],loadMs=runtime['timing']['modelLoadMs'],inferenceMs=runtime['timing']['inferenceMs'])
        return row
    for region,rows in result['measurements'].items():
        row=next((x for x in rows if x['id']=='acne'),None)
        if row is None:continue
        reason=failure;boxes=[];support=np.zeros((1,1),bool);anatomical=support
        if context is not None:
            anatomical=context['acne_envelopes'][region];support=anatomical&context['acne_skin'];observed=anatomical&(context['face_support']>0)&(context['exclusion']==0)&~context['hair']
            reason='CAPTURE_QUALITY' if not payload.get('qualityValid') else 'GLARE_OR_EXPOSURE' if observed.any() and context['acne_clipping'][observed].mean()>.03 else 'INSUFFICIENT_VISIBLE_AREA' if support.sum()<100 else None
            if reason is None:
                boxes,selections[region]=scored_candidates(runtime['acneCandidates'].get(region,[]),support,context['scale'],context['origin'],(result['sourceHeight'],result['sourceWidth']),region,result['photoId'])
                measured.append(support);available_areas.append(anatomical)
        stamp(row,boxes,support,reason,anatomical)
        if region in selections:row['components']['supportSelection']=selections[region]
        final[region]=row['components']['bounds']
    all_boxes={box['candidateId']:box for rows in final.values() for box in rows};final['overview']=list(all_boxes.values())
    if 'general' in result:
        row=next(x for x in result['general']['measurements'] if x['id']=='acne')
        support=np.logical_or.reduce(measured) if measured else np.zeros(context['gray'].shape if context is not None else (1,1),bool)
        anatomical=np.logical_or.reduce(available_areas) if available_areas else support
        reason=failure or (None if measured else 'INSUFFICIENT_VISIBLE_AREA')
        stamp(row,final['overview'],support,reason,anatomical)
    result['maps']={key:layer for key,layer in result['maps'].items() if not key.endswith(':acne')}
    result['acneCandidates']=final
    result['acneRuntime']=dict(methodVersion=METHOD,status='measured' if measured else 'unavailable',reason=failure,experimental=True,accepted=False,modelHash=MODEL_HASH if runtime else None,step0SHA256=STEP0_HASH,onnxSHA256=runtime['model']['onnxSHA256'] if runtime else None,verifierSHA256=V5_HASH,threshold=THRESHOLD,candidateCount=len(all_boxes),normalizationVersion=NORMALIZATION)
    result['acneRuntime']['supportSelection']=dict(version=SAMPLING,photoId=result['photoId'],inputCount=sum(s['inputCount'] for s in selections.values()),acceptedCount=len(all_boxes),rejectedCount=sum(s['rejectedCount'] for s in selections.values()),regions=selections)
    if runtime:result['acneRuntime'].update(timing=runtime['timing'],resources=runtime['resources'],tileCount=runtime['tileCount'],detectorForwardCount=runtime['detectorForwardCount'])
    attach_result_receipts(result);check();after=non_acne_fingerprint(result)
    if before!=after:raise ValueError('NON_ACNE_RESULT_CHANGED')
    result['acneRuntime']['nonAcnePreservation']=dict(beforeSHA256=before,afterSHA256=after,equal=before==after)
    return result
