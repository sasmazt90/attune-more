"""Publish measured learnability evidence after freeze, verification and evaluation."""
import hashlib
import json
from acne_takeover_support import ROOT,OUT,read,digest

DEST=OUT.parent/'acne-learnability-20261015'


def source_positive_result(measure,rows,original):
    mapping={};all_ids=set();matched=set()
    for row in rows:
        a,b,c,d=row['rect'];ids=[]
        for i,ann in enumerate(original[row['sha256']]['annotations']):
            if ann.get('classId')!=0:continue
            x,y,ex,ey=ann['box'];cl=[max(x,a),max(y,b),min(ex,c),min(ey,d)]
            if cl[2]-cl[0]>=2 and cl[3]-cl[1]>=2 and (cl[2]-cl[0])*(cl[3]-cl[1])>=.7*(ex-x)*(ey-y):ids.append(i)
        assert len(ids)==len(row['boxes']);mapping[(row['sha256'],tuple(row['rect']))]=ids
        all_ids|={(row['sha256'],i) for i in ids}
    for row in measure['positiveProbeTiles']:
        ids=mapping[(row['sha256'],tuple(row['tile']))]
        matched|={(row['sha256'],ids[t]) for t,_,_ in row['pairs']}
    return dict(targets=len(all_ids),matched=len(matched),matchedSourceIDs=sorted(matched),identity='source SHA + original annotation index in pinned ledger; overlapping tile observations counted once')


def matched_source_set(rows):return {(r['sha256'],p[0]) for r in rows for p in r['pairs']}


def iou(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection/union if union else 0


def main():
    plan=read(DEST/'preregistration.json');receipt=read(DEST/'receipt.json');verification=read(DEST/'verification.json');gradient=read(DEST/'gradient-interference.json');prefit=read(DEST/'prefit-learning-path.json')
    product=read(OUT/'evaluation-objectness-features/summary.json');initial_product=read(OUT/'evaluation-step0/summary.json');previous_product=read(OUT/'evaluation-hard-negative/summary.json')
    assert digest(DEST/'preregistration.json')==receipt['preregistrationSHA256'] and product['modelSHA256']==receipt['modelSHA256']
    original={r['sha256']:r for r in read(OUT/'inputs/original-reviewed-detector-data.json')['rows']};sequence=read(OUT/'clean-pilot-hard-negative/sequence.json');components=read(OUT/'source-negative-repair-probe.json')['components'];rows=[next(r for r in sequence if r['sha256']==c['sha256'] and r['rect']==c['selectedTile']['rect']) for c in components]+plan['positiveProbes']
    measures=[read(DEST/f'measure-step-{step:06d}.json') for step in plan['measureSteps']]
    for m in measures:m['sourcePositives']=source_positive_result(m,rows,original)
    start,final=measures[0],measures[-1];baseline_ids=set(map(tuple,start['sourcePositives']['matchedSourceIDs']));final_ids=set(map(tuple,final['sourcePositives']['matchedSourceIDs']))
    previous=verification['previousArmReplay'];previous['sourcePositives']=source_positive_result(previous,rows,original)
    chain=[]
    for update in receipt['firstActualUpdates']:
        a,b,_,_=update['tile'];after={r['anchor']:r for r in update['afterActualOptimizerUpdate']}
        for anchor in update['anchors']:
            cx,cy,w,h=anchor['decodedTileBox'];anchor['decodedTileFormat']='cx,cy,width,height';anchor['decodedSourceXYXY']=[a+cx-w/2,b+cy-h/2,a+cx+w/2,b+cy+h/2]
            offset=anchor['anchor']
            for stride in (4,8,16,32):
                count=(384//stride)**2
                if offset<count:
                    side=384//stride;anchor['emitterSourceCenter']=[a+(offset%side+.5)*stride,b+(offset//side+.5)*stride];anchor['stride']=stride;break
                offset-=count
            anchor['afterActualUpdate']=after[anchor['anchor']]
            anchor['classProbabilityDelta']=after[anchor['anchor']]['classProbability']-anchor['classProbability']
            assert abs(anchor['classProbabilityDelta'])<=1e-6
        chain.append(update)
    train_ok=all(o['objTimesCls']<.30 for o in final['objects']) and baseline_ids<=final_ids
    comparisons={}
    for reference_name,reference in [('step0',initial_product),('previous-objectness-only',previous_product)]:
        result={}
        for name,predicate in [('scopeB',lambda r:r['cohort']=='scope-B-development'),('admissibleControls',lambda r:r['cohort']=='heldout-train' and r['fullStaticProductPass']),('allControlsRobustness',lambda r:r['cohort']=='heldout-train')]:
            before=[r for r in reference['rows'] if predicate(r)];after_rows=[r for r in product['rows'] if predicate(r)]
            assert [(r['sha256'],r['truth']) for r in before]==[(r['sha256'],r['truth']) for r in after_rows]
            a_ids,b_ids=matched_source_set(before),matched_source_set(after_rows)
            result[name]=dict(beforeMatched=len(a_ids),afterMatched=len(b_ids),targets=sum(r['targetCount'] for r in before),lostSourceTargets=sorted(a_ids-b_ids),gainedSourceTargets=sorted(b_ids-a_ids),beforeCleanFP=sum(r['cleanFP'] for r in before),afterCleanFP=sum(r['cleanFP'] for r in after_rows))
        comparisons[reference_name]=result
    generalization_ok=all(not v['lostSourceTargets'] for v in comparisons['step0'].values()) and comparisons['step0']['scopeB']['afterCleanFP']<comparisons['step0']['scopeB']['beforeCleanFP']
    protected=read(ROOT/'docs/acne-takeover-evidence-20261015.json')['protectedProduction']
    for r in protected:r['nowSHA256']=digest(ROOT/r['path']);r['preserved']=r['nowSHA256']==r['sha256'];assert r['preserved']
    cfg=read(ROOT/'services/core-api/models/skin-focused.json')['models']['acne'];assert cfg['accepted'] is False and cfg['file'] is None
    pointer=read(DEST/'CURRENT')
    for name,expected in pointer['hashes'].items():assert digest(DEST/pointer['directory']/name)==expected
    payload=dict(version=plan['version'],baselineCommit=plan['sourceCommit'],BUILD_ID=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip(),preregistration=plan,modelSHA256=receipt['modelSHA256'],graphVersion=receipt['graphVersion'],trainable=receipt['trainable'],changedTensors=verification['changedTensors'],perObjectPrefitProof=prefit,perObjectActualLearningChain=chain,perObjectExposure=receipt['perObjectExposure'],measurements=measures,previousObjectnessOnlyTRAINReplay=previous,uniqueTRAINLoss=dict(lost=sorted(baseline_ids-final_ids),gained=sorted(final_ids-baseline_ids)),gradientDiagnostic=gradient,productResults={name:product[name] for name in ['preflight','heldoutAdmissible','heldoutAnatomicalEnvelopeCenter','heldoutRobustness','scopeBDevelopment','scopeBProductAdmissible']},productComparisons=comparisons,decision=dict(trainAcceptancePassed=train_ok,productComparisonPassed=generalization_ok,longTrainingJustified=train_ok and generalization_ok,productionAccepted=False,productionFile=None),verification={k:v for k,v in verification.items() if k!='previousArmReplay'},protectedProduction=protected,currentCheckpoint=pointer,resource=receipt['resource'],artifactHashes={n:digest(DEST/n) for n in ['preregistration.json','prefit-learning-path.json','receipt.json','verification.json','gradient-interference.json','model.safetensors','optimizer-rng.safetensors','state.json']})
    with (DEST/'model.safetensors').open('rb') as file:
        length=int.from_bytes(file.read(8),'little');assert 0<length<2**20;header=json.loads(file.read(length))
    schema={k:dict(dtype=v['dtype'],shape=v['shape']) for k,v in header.items() if k!='__metadata__'}
    payload['modelTensorContract']=dict(tensors=len(schema),schemaSHA256=hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest(),strictLoadVerified=verification['strictFeatureGraphLoad'])
    old_rows={r['sha256']:r for r in initial_product['rows']};new_rows={r['sha256']:r for r in product['rows']};loss_stages=[]
    for cohort in ('scopeB','admissibleControls'):
        for sha,index in comparisons['step0'][cohort]['lostSourceTargets']:
            before,after=old_rows[sha],new_rows[sha];truth=before['truth'][index];old_raw=[v for v in before['trace']['confidenceCandidates'] if iou(truth,v['box'])>=.5];new_raw=[v for v in after['trace']['confidenceCandidates'] if iou(truth,v['box'])>=.5];new_nms=[v for v in after['trace']['nmsCandidates'] if iou(truth,v['box'])>=.5]
            loss_stages.append(dict(cohort=cohort,sha256=sha,targetIndex=index,sourceBox=truth,step0MatchingRawAnchors=old_raw,newConfidenceMatchingAnchors=new_raw,newNMSMatchingAnchors=new_nms,lossStage='CONFIDENCE_0_30' if not new_raw else 'NMS_OR_ONE_TO_ONE' if not new_nms else 'FINAL_SUPPORT_OR_ONE_TO_ONE'))
    payload['productPositiveLossStages']=loss_stages
    payload['sourceHashesAtDelivery']={f:digest(ROOT/f) for f in ['scripts/skin-research/run_acne_learnability.py','scripts/skin-research/acne_objectness_features.py','scripts/skin-research/evaluate_acne_current_product.py','scripts/skin-research/audit_acne_gradient_interference.py']}
    table=[]
    old={r['sourceAnnotationId']:r for r in previous['objects']};proofs={r['sourceAnnotationId']:r for r in prefit['objects']};initial={r['sourceAnnotationId']:r for r in start['objects']}
    for obj in final['objects']:
        key=obj['sourceAnnotationId'];p=proofs[key];exposure=receipt['perObjectExposure'][str(key)]
        table.append(f"| {obj['sha256'][:8]} / {key} | {p['negativeAnchors']} | {p['normalizedNegativeLoss']:.6f} | {p['featureGradientL2Sum']:.3f} | {initial[key]['objTimesCls']:.6f} → {old[key]['objTimesCls']:.6f} → {obj['objTimesCls']:.6f} | {exposure['tileExposures']} / {exposure['negativeAnchorExposures']} |")
    timeline=[f"| {m['step']} | {sum(o['objTimesCls']<.30 for o in m['objects'])}/5 | {m['sourcePositives']['matched']}/{m['sourcePositives']['targets']} | {m['positiveMatched']}/{m['positiveTargets']} |" for m in measures]
    scope=comparisons['step0']['scopeB'];control=comparisons['step0']['admissibleControls'];robust=comparisons['step0']['allControlsRobustness']
    cosines=[r['gradientCosine'] for r in gradient['records'] if r['model']=='features-150' and r['gradientCosine'] is not None]
    feature_cosines=[r['featureGradientCosine'] for r in gradient['records'] if r['model']=='features-150' and r['featureGradientCosine'] is not None]
    final_loss_stages=[r for r in gradient['positiveLossStages'] if r['model']=='features-150'];confidence_losses=sum(r['maxMatchingConfidence'] is not None and r['maxMatchingConfidence']<.30 for r in final_loss_stages)
    scope_centers={n:dict(targets=sum(len(r['anatomicalEnvelopeCenterTargets']) for r in report['rows'] if r['cohort']=='scope-B-development'),matched=sum(len(r['anatomicalEnvelopeCenterPairs']) for r in report['rows'] if r['cohort']=='scope-B-development')) for n,report in [('step0',initial_product),('features',product)]}
    payload['scopeBSelectedEnvelopeCenterComparison']=scope_centers
    text=f'''# Sivilce: sonlu objectness özellik öğrenebilirliği — 2026-10-15

Başlangıç `{plan['sourceCommit']}`. Tek yeni aday Step0'dan başladı, 150 optimizer adımında donduruldu. Önceki pilotlar yeniden eğitilmedi. Üretim `accepted:false, file:null`; korunan BUILD_ID `{payload['BUILD_ID']}`. Model SHA-256 `{receipt['modelSHA256']}`.

## Değişken ve sınırlar

Bu YOLOX'ta ayrı obj_convs yoktur; objectness ile kutu yolu reg_convs özelliklerini paylaşır. Yalnız objectness için Step0 reg_convs kopyası obj_convs olarak ayrıldı; mevcut stems/kutu/sınıf yolu değiştirilmedi. Öğrenenler 8 yeni convolution weight tensoru ve 8 obj_preds weight/bias tensorudur. Backbone/FPN, shared stems, reg_convs/reg_preds, cls_convs/cls_preds ve bütün BN affine/istatistikleri byte düzeyinde korundu. On beş sabit TRAIN tile'ında fit öncesi bütün çıktılar Step0 ile tam aynı (maksimum fark 0). Yeni {len(schema)}-tensor grafiği açık sürümlüdür; eski grafa sessiz/partial yükleme yoktur.

Önceden kaydedilen plan: LR 3e-5, AdamW weight-decay .01, warmup30/cosine150, clip norm5, microbatch1/accum4, önceki onarılmış kolun aynı 600 tile sırası (`{plan['sampleSequenceSHA256']}`). 401 pseudo-pozitif Pimple yapılmadı; UNKNOWN ve özgün Pimple +16 px koruması korunur. Beş kaynak-Mole nesnesi sadece TRAIN'dedir; kaynak kategorisi klinik tanı veya bbox pixel-mask gerçeği değildir. Scope B ve 28 kontrol fit/mining girdisi değildir. Daha fazla öğrenen parametre ve global clipping'in fiili ölçeği farklıdır; sonuç tüm donuk backbone özellikleri hakkında nedensel kanıt değildir.

## Beş ayrı öğrenme yolu

| TRAIN kaynak / anotasyon | Geçerli negatif anchor | İlk normalize negatif loss | Özellik gradyan L2 toplamı | Step0 → önceki yalnız-prediction → yeni özellik adayı obj×cls | Tile / negatif-anchor maruziyeti |
|---|---:|---:|---:|---:|---:|
{chr(10).join(table)}

Hiçbir nesne pozitif koruması nedeniyle sıfır denetimde kalmadı. Her nesnede kaynak kutusu → gerçek native tile → decoded/emitter anchor → loss → parametre gradyanı → fiili ilk AdamW güncellemesi → aynı anchor'ın objectness/class/obj×cls değeri makbuzda ayrıdır. Toplam 909 maruziyet tek başına kanıt sayılmadı. İlk gerçek güncellemelerde özellik ağırlığı değişimi ve score değişimi ayrı kaydedildi; bbox/class değişmedi. Güncelleme gerçek dört-microbatch birikiminin toplamıdır; nesneye özel gradyan ile tüm batch'in parametre güncellemesi birbirine eşit sayılmaz. Negatif maske atanmış pozitifleri asla geçersiz kılmaz. Prefit beş backward denetimi optimizer güncellemesi yapmadı.

## Sabit TRAIN hedefleri ve zaman çizgisi

| Optimizer adımı | 0.30 altındaki Mole nesnesi | Benzersiz kaynak-Pimple | Tile hedef gözlemi |
|---|---:|---:|---:|
{chr(10).join(timeline)}

On grup-kayıtlı pozitif tile ve beş hata tile'ında 45 hedef gözlemi, **43 benzersiz özgün kaynak anotasyonuna** karşılık gelir. İki örtüşen tile gözlemi kaynak başarısında iki kez sayılmaz. Benzersiz başlangıç {start['sourcePositives']['matched']}/43 → son {final['sourcePositives']['matched']}/43; kayıp {len(baseline_ids-final_ids)}, kazanım {len(final_ids-baseline_ids)}. Önceki yalnız-objectness kolu aynı yeni sabit TRAIN probe'larında yalnız çıkarımla tekrar ölçüldü: {previous['sourcePositives']['matched']}/43. Bunlar TRAIN sonuçlarıdır, genelleme/final test değildir. Orijinal ölçüm JSON'ları değiştirilmedi; benzersiz kaynak eşlemesi ayrıca türetildi.

Dondurma sonrası beş gerçek dört-tile batch'inde sıfır optimizer güncellemesiyle pozitif/nesne-negatif gradyanları ayrıldı. Son modelde ölçülebilir beş yerel kosinüsten {sum(c<0 for c in cosines)}/{len(cosines)} negatiftir; yalnız özellik-conv gradyanlarında da {sum(c<0 for c in feature_cosines)}/{len(feature_cosines)} negatiftir. Bu yerel çatışma denetimi bütün optimizer geçmişinin nedensel açıklaması değildir. Altı kayıp TRAIN hedefinin {confidence_losses}'ünde sabit geometriyle eşleşen en yüksek obj×cls 0.30 altındadır; diğer {len(final_loss_stages)-confidence_losses} kayıp güven sonrası NMS/bire-bir seçim aşamasındadır. Örnek kaynak 2cecc2fe (663,697)-(686.5,708.5) güveni 0.599086 →0.294184, sınıf olasılığı 0.868873 sabit. Kaynak 431c54b4 (717,59)-(726.5,73.5) 0.326484 →0.164409, sınıf olasılığı 0.828400 sabit. Etiketin loss'a ulaşmaması/pozitif korumasında gizlenmesi olasılığı dışlandı; bu ayarlarda bastırma öğrenilirken gerçek Pimple yakalaması kaybolmaktadır. Tam seçici ayrım öğrenilmedi; daha uzun eğitimin bunu düzelteceği çıkarılamaz.

## Dondurulmuş model, aynı güncel ürün evaluator'ı

| Kapsam | Step0 → yeni yakalama | Step0 → yeni incelenmiş-negatif FP |
|---|---:|---:|
| Scope B, 3 pozitif /14 sabit kaynak hedefi +9 negatif fotoğraf | {scope['beforeMatched']}/{scope['targets']} → {scope['afterMatched']}/{scope['targets']} | {scope['beforeCleanFP']} → {scope['afterCleanFP']} |
| Statik ürün kapılarından geçen 3 kontrol fotoğrafı | {control['beforeMatched']}/{control['targets']} → {control['afterMatched']}/{control['targets']} | İncelenmiş negatif paydası yok |
| 28 kontrol, sadece dayanıklılık kapsamı | {robust['beforeMatched']}/{robust['targets']} → {robust['afterMatched']}/{robust['targets']} | İncelenmiş negatif paydası yok |

Kaynak-hedef kayıp/kazanım kimlikleri, mikro/küçük/orta ve ≥%80 incelenmiş-negatif destekli yanlış kutular makbuzda ayrı. .30 confidence → .30 Hard-NMS, browser MediaPipe/snapshot/exclusions, mevcut crop, scale/origin, gerçek anatomik filtre aynı kaldı. Model/graph strict kimliği doğrulandı. Fiziksel kamera kararlılığı yeniden test edilmedi. Scope B tekrar görülmüş geliştirmedir; kişi kimlikleri bilinmediğinden bağımsız kişi-final testi iddiası yoktur. Sabit kaynak anotasyon kapsamı seçili anatomik envelope ile aynı değildir; b662333 kapsam notu korunur. Yalnız seçili envelope-merkezi kapsamında da Step0 {scope_centers['step0']['matched']}/{scope_centers['step0']['targets']} → yeni {scope_centers['features']['matched']}/{scope_centers['features']['targets']}; 14 sabit kaynak hedefi bu daha küçük payda ile değiştirilmez. UNKNOWN alanlar negatif sayılmadı.

## Karar ve teslim

TRAIN kabulü: **{train_ok}**. Başlangıç modeline göre ürün karşılaştırma kabulü: **{generalization_ok}**. Uzun eğitim gerekçesi: **{train_ok and generalization_ok}**. Beş hatayı bastırıp bütün önceki Pimple eşleşmelerini koruma şartı sağlanmadan uzun eğitim veya ürün aktivasyonu yok. Tek aday donduruldu; yeni loss/LR/eşik/örnekleme taraması yapılmadı. Kuruluk, sarkma, diğer yöntemler, hosted izin/config, UI, sesler ve kullanıcı kayıtlarına dokunulmadı.

{verification['tests']} odaklı Python kontrolü, strict model/optimizer/scheduler/RNG yüklemesi ve frozen/BN hash denetimleri geçti. Altı immutable checkpoint ve CURRENT yerelde korunur. Üretim kaynakları/config/build hash'leri aynı; üretim kodu değişmediği için yeni build veya shortcut teslimi iddiası yoktur. PR #2 Draft kalır; main'e merge yoktur.

Makbuz `docs/acne-learnability-evidence-20261015.json`; model/fotoğraflar Git'e alınmadan `audit-results/acne-learnability-20261015` altında kalır. Öğrenme kodu `run_acne_learnability.py`; tamamlanmış adayı tekrar başlatmayı reddeder. Son ürün çıkarımı `evaluate_acne_current_product.py --model objectness-features`; eski pilotları çalıştırmaz.
'''
    (ROOT/'docs/acne-learnability-20261015.md').write_text(text,encoding='utf8')
    (ROOT/'docs/acne-learnability-evidence-20261015.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps(dict(trainAcceptance=train_ok,productComparison=generalization_ok,objects=[o['objTimesCls'] for o in final['objects']],sourcePositiveBefore=start['sourcePositives']['matched'],sourcePositiveAfter=final['sourcePositives']['matched'],productComparisons=comparisons)))


if __name__=='__main__':main()
