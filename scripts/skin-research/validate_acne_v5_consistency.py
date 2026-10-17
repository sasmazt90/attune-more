"""Verify saved real API/DOM receipts; reconstruct old area accounting, never run a model."""
import argparse,copy,json,sys,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'services/core-api'),str(Path(__file__).parent)]
from diagnose_acne_v5_consistency import inspect
from acne_v5_product import METHOD,SAMPLING,non_acne_fingerprint

def validate(data,previous):
    reports=[]
    for entry in data['ledger']:
        response=entry['response'];payload=entry['payload'];runtime=response['acneRuntime'];selection=runtime['supportSelection'];saved=copy.deepcopy(entry)
        assert entry['status']==200 and response['photoId']==payload['photoId']
        assert runtime['methodVersion']==METHOD and selection['version']==SAMPLING and runtime['nonAcnePreservation']['equal']
        for region,receipt in selection['regions'].items():
            saved['response']['acneCandidates'][region]=response['acneCandidates'][region]+[r['box'] for r in receipt['rejected']]
        scope=inspect(saved);rows=[]
        for region,row in scope['regions'].items():
            actual=next(r for r in response['measurements'][region] if r['id']=='acne');after=row['after'];receipt=selection['regions'][region]
            assert abs(after['rawBar']-actual['value'])<1e-10
            assert row['denominatorAnalysisPixels']==actual['evaluatedArea']['analysisPixels']
            assert after['pointCount']==len(actual['components']['bounds'])==len(response['acneCandidates'][region])
            assert receipt['supportSHA256']==after['selection']['supportSHA256']
            assert {b['candidateId'] for b in actual['components']['bounds']}=={b['candidateId'] for b in response['acneCandidates'][region]}
            rows.append(dict(region=region,beforePoints=row['pointCount'],afterPoints=after['pointCount'],beforeRaw=row['rawBar'],afterRaw=after['rawBar'],beforeDisplay=row['displayPercent'],afterDisplay=after['displayPercent'],denominatorAnalysisPixels=row['denominatorAnalysisPixels'],beforeSupportPixels=row['unionScoredPixels'],afterSupportPixels=after['unionScoredPixels'],candidateAudit=row['candidates'],rejected=receipt['rejected']))
        old=next((x['response'] for x in previous['ledger'] if x['response']['photoId']==response['photoId']),None)
        preservation=dict(currentBeforeAfter=runtime['nonAcnePreservation'])
        if old is not None:
            preservation['previousDeliveryIncludingTimingsEqual']=non_acne_fingerprint(old)==non_acne_fingerprint(response)
            old_values=copy.deepcopy(old);new_values=copy.deepcopy(response)
            old_values['drynessRuntime']=None;new_values['drynessRuntime']=None
            preservation['previousValuesMapsContoursAndGeneralEqual']=non_acne_fingerprint(old_values)==non_acne_fingerprint(new_values)
            preservation['changedDrynessRuntimeFields']=[k for k,v in response.get('drynessRuntime',{}).items() if v!=old.get('drynessRuntime',{}).get(k)]
            assert preservation['previousValuesMapsContoursAndGeneralEqual']
            assert set(preservation['changedDrynessRuntimeFields'])<={'timings','profile','fullAnalysisSeconds'}
        reports.append(dict(pose=payload['pose'],photoId=payload['photoId'],beforePoints=selection['inputCount'],afterPoints=selection['acceptedCount'],rejected=selection['rejectedCount'],rows=rows,nonAcne=preservation))
    assert len(data['selectionChecks'])==7
    for check in data['selectionChecks']:
        assert check['criteriaExact'] and check['correctPhoto'] and check['resetCleared'] is not False
        if 'acne' in check:
            a=check['acne'];assert a['expected']==a['actual'] and a['sourceCoordinatesExact'] and float(a['barValue'])==a['expectedBar'] and a['onlyPoints']
        if 'other' in check:
            assert check['other']['markersCleared'] and check['other']['selected']=='true'
            assert all(layer['criterion']==check['other']['id'] and layer['photoId']==check['photoId'] for layer in check['other']['layers'])
    record=data['record'];front=next(x['response'] for x in data['ledger'] if x['payload']['pose']=='FRONT')
    assert record['captures']['FRONT']['captureId']==front['photoId']
    assert next(x for x in record['general']['indicators'] if x['id']=='acne')['score']==next(x for x in front['general']['measurements'] if x['id']=='acne')['value']
    return dict(evidenceKind=data['kind'],recordId=record['id'],cases=reports,checkedViews=len(data['selectionChecks']),physicalCameraVerified=False,modelMethod=METHOD,sampling=SAMPLING,previousEvidenceSHA256=hashlib.sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--browser',type=Path,required=True);parser.add_argument('--previous',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=validate(json.loads(args.browser.read_text('utf8')),json.loads(args.previous.read_text('utf8')))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps([{k:v for k,v in row.items() if k!='rows'} for row in result['cases']],indent=2))
