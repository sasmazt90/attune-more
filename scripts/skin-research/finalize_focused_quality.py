"""Apply visual decisions and detect synthetic impulse corruption before training.

Cached landmark preparation is preserved. Split recomputed after eligibility
changes; no model or protected test predictions are used for these decisions.
"""
import collections,json,sys
import cv2,numpy as np
from prepare_focused_data import OUT,write,group,sha
PREFIXES=['2d461ce7008a','64a81b5bac84','a92deb218cd3','528dcf47ca97','d69a3f014dcd','158774e7a29e','8d4eeb857f95']

def main():
    assert not any((OUT/n/'selection.json').exists() for n in ['resnet18','efficientnet_b0']),'Quality must be fixed before model selection'
    m=json.loads((OUT/'dataset-manifest.json').read_text());rows=m['rows'];reviewed=[];excluded=[]
    for corpus in ['skin','eye']:
        path=OUT/(corpus+'-quality-review-index.json')
        if path.exists():reviewed.extend(json.loads(path.read_text()))
    # Explicit visual decisions: composited/beautified/cosmetic advertisement
    # examples. Extend to their source family, not a silently relabelled class.
    badfamilies={r['sourceName'] for r in rows if any(r['sha256'].startswith(p) for p in PREFIXES)}
    for i,r in enumerate(rows):
        if r['sourceName'] in badfamilies:
            r['eligible']=False;r['qualityDecision']='visual-processed-or-cosmetic-advertisement';excluded.append(r['sha256']);continue
        if not r['eligible']:continue
        im=cv2.imread(r['absolutePath']);a,b,c,d=r['crop'];crop=im[b:d,a:c];med=cv2.medianBlur(crop,3);delta=np.max(np.abs(crop.astype(np.int16)-med.astype(np.int16)),axis=2)
        extreme=(np.max(crop,axis=2)>245)|(np.min(crop,axis=2)<10)
        count,labels,stats,_=cv2.connectedComponentsWithStats(((delta>65)&extreme).astype(np.uint8));areas=stats[:,cv2.CC_STAT_AREA];small=(labels>0)&(areas[labels]<=3)
        fraction=float(small.mean());r['impulseCorruptionFraction']=fraction
        if fraction>.002:
            r['eligible']=False;r['qualityDecision']='synthetic-impulse-corruption';excluded.append(r['sha256'])
        if i%500==0:print('quality',i,flush=True)
    components=group(rows);conflicts=[]
    for r in rows:r.pop('typeExcluded',None)
    for ids in components.values():
        labels={rows[i].get('class') for i in ids if rows[i].get('class')}
        if len(labels)>1:
            conflicts.append(dict(group=rows[ids[0]]['group'],classes=sorted(labels),paths=[rows[i]['path'] for i in ids],decision='exclude ambiguous class family, do not choose label'))
            for i in ids:rows[i]['typeExcluded']='conflicting-source-class-labels'
    testgroups={r['group'] for r in rows if r.get('grades') and r['split']=='test'}
    for r in rows:
        r['typeEligible']=r['corpus']=='skin' and r['eligible'] and not r.get('typeExcluded') and r['group'] not in testgroups
        r['degreeEligible']=r['corpus']=='skin' and r['eligible'] and bool(r.get('grades'))
        if r['group'] in testgroups:r['typeExcluded']='protected-degree-test-group'
    m.update(conflicts=conflicts,protectedDegreeTestGroups=sorted(testgroups),qualityFinalizedBeforeTraining=True)
    m['counts'].update(quality=dict(collections.Counter(r['corpus']+':'+r['qualityDecision'] for r in rows)),type=dict(collections.Counter(r['split']+':'+r['class'] for r in rows if r['typeEligible'])),degree=dict(collections.Counter(r['split'] for r in rows if r['degreeEligible'])),eye=dict(collections.Counter(r['split'] for r in rows if r['corpus']=='eye' and r['eligible'])))
    write('dataset-manifest.json',m);write('quality-review.json',dict(excludedSHA256=sorted(set(excluded)),sampledReview=reviewed,exhaustiveHumanPhotoReview=False,decisions={'visual':'exclude photographed cosmetics/composites/obvious beauty processing; source families included','impulse':'source RGB median3 discrepancy>65 plus extreme luminance, component<=3px, fraction>.002; no test/model outcome used','conflicts':'exclude entire ambiguous source class family'},counts=m['counts'],protectedTestStillSealed=True));print(json.dumps(m['counts'],indent=2))
    compact_manifest(m)

def compact_manifest(m):
    rows=m['rows'];compact=[]
    for row in rows:
        r={k:v for k,v in row.items() if k!='landmarks'}
        if row.get('degreeEligible'):r['landmarks']=row['landmarks']
        elif row['corpus']=='eye' and row['eligible']:r['eyeLandmarks']={str(i):row['landmarks'][i] for i in (33,133,145,263,362,374)}
        compact.append(r)
    write('learning-manifest.json',{**{k:v for k,v in m.items() if k!='rows'},'rows':compact,'completeSourceManifestSHA256':sha(OUT/'dataset-manifest.json')})
if __name__=='__main__':
    if '--compact-only' in sys.argv:compact_manifest(json.loads((OUT/'dataset-manifest.json').read_text()))
    else:main()
