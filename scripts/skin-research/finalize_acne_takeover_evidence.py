"""Package measured staging evidence; no training or production writes."""
import hashlib
import json
import subprocess
from pathlib import Path

from acne_takeover_support import ROOT, OUT, read, digest


def aggregate(rows):
    return dict(photos=len(rows), targets=sum(r['targetCount'] for r in rows), matched=sum(len(r['pairs']) for r in rows), reviewedNegativePhotos=sum(r.get('verifiedCleanPixels', 0) > 0 for r in rows), cleanCenterFP=sum(r['cleanFP'] for r in rows), cleanArea80FP=sum(v['cleanAreaFraction'] >= .8 for r in rows for v in r['verifiedCleanFalseCandidates']), scale={name:dict(targets=sum(r['scale'][name]['targets'] for r in rows), matched=sum(r['scale'][name]['matched'] for r in rows)) for name in ('micro','small','medium')})


def target_set(rows):
    return {(r['sha256'], p[0]) for r in rows for p in r['pairs']}


def pairs_without_runtime(truth, boxes):
    """Same fixed greedy IoU .50 one-to-one rule for stored filter traces."""
    possibilities=[]
    for t, a in enumerate(truth):
        for p, b in enumerate(boxes):
            intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
            union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
            possibilities.append((intersection/union if union else 0,t,p))
    pairs=[];used_t=set();used_p=set()
    for iou,t,p in sorted(possibilities,key=lambda x:(-x[0],x[1],x[2])):
        if iou>=.50 and t not in used_t and p not in used_p:
            pairs.append([t,p,iou]);used_t.add(t);used_p.add(p)
    return pairs


def markdown(payload):
    result=payload['results'];lines=[]
    for name in ('step0','control_iou','candidate_giou','control','hard-negative'):
        v=result[name];scope=v['scopeB'];held=v['heldoutStaticAdmissible'];robust=v['heldoutAllRobustnessOnly']
        held_text=f"{held['matched']}/{held['targets']} ({held['photos']} fotoğraf)" if held['photos'] else '—'
        robust_text=f"{robust['matched']}/{robust['targets']}" if robust['photos'] else '—'
        lines.append(f"| {name} | {scope['matched']}/{scope['targets']} | {scope['cleanCenterFP']} / {scope['cleanArea80FP']} | {held_text} | {robust_text} |")
    scales=[]
    for name in ('step0','control','hard-negative'):
        for cohort in ('scopeB','heldoutStaticAdmissible'):
            v=result[name][cohort]['scale'];scales.append('| '+name+' / '+cohort+' | '+' | '.join(f"{v[k]['matched']}/{v[k]['targets']}" for k in ('micro','small','medium'))+' |')
    replay=[]
    for before,after in zip(payload['fixedTRAINReplay']['control']['rows'],payload['fixedTRAINReplay']['hard-negative']['rows']):
        replay.append(f"| {before['sha256'][:8]} / {before['sourceAnnotationId']} | {before['step0']['maxConfidence']:.6f} | {before['maxConfidence']:.6f} | {after['maxConfidence']:.6f} | {before['aboveThresholdAnchors']} → {after['aboveThresholdAnchors']} |")
    decision='Kısa deneyin önceden kaydedilmiş koşulları sağlandı; bu yalnız kısmi geliştirme kanıtıdır, ürün kabulü değildir.' if payload['shortExperimentAcceptance']['passed'] else 'Aday önceden kaydedilmiş kabul koşullarını sağlamadı. Ürüne alınmadı; uzun eğitim gerekçelendirilmedi.'
    comparison=f"Eşlenik kontrol → aday Scope B: {result['control']['scopeB']['matched']}/14 → {result['hard-negative']['scopeB']['matched']}/14, FP {result['control']['scopeB']['cleanCenterFP']} → {result['hard-negative']['scopeB']['cleanCenterFP']}. Step0 FP {result['step0']['scopeB']['cleanCenterFP']} olduğundan adayın başlangıç modeline göre kazancı ayrıca değerlendirilir; yalnız kontrolü geçmesi yeterli değildir."
    return f'''# Sivilce devri: gerçek ürün girdisi ve kaynak-etiket denetimi

Üretim korunmuştur: sivilce `accepted:false`, `file:null`. Yeni staging modeli normal API seçicisine bağlanmadı. BUILD_ID `{payload['BUILD_ID']}`; bu görevde üretim build'i, UI veya kullanıcı kaydı değişmedi. AG `{payload['frozenAGCommit']}` salt okunur incelendi; dal bütünü taşınmadı.

## Ürün eşdeğerliği

AG adaptörünün kendi checkout'una göreli TS importları, tüm açılarda FRONT `isAligned` kapısı, 720 ölçekli yaklaşık yüz/kıl maskesi ve %15 pad tile kapsamı düzeltildi. Ana checkout'un gerçek SkinAnalyzer/MediaPipe classic worker, `matchesSkinAngle`, native `snapshotRawSkinFrame`, otomatik dışlamalar ve `skin_models.photo_input` crop'u kullanıldı. Backend destekleri güncel `analyze_skin` prelude'undan aynen alınır; scale/origin ve 320 analiz ölçeği kopya bir formülle taklit edilmez. Native BGR 384 tile, 288 stride, objectness×class ≥0.30, ardından gerçek ürün Hard-NMS 0.30 ve staging anatomik filtre sırası sabit.

Eski 1/28 yerine **3/28** statik tam giriş uygundur. Poz reddi 23, BLURRY 10, NO_FACE 2; nedenler örtüşebilir. Uygun kaynaklar 26ebdde4, 2ed3716e (LEFT), f2ed24a9. Frontend ve backend gözlük kontrolleri bu üçünde CLEAR. Gerçek tarayıcı MediaPipe çalıştı; fiziksel kamera, zaman içindeki 900 ms kararlılık ve normal API'de aday aktivasyonu doğrulanmış değildir. Eşikler veri geçirmek için gevşetilmedi.

Scope B sabit 3 pozitif fotoğraf/14 kaynak hedefi +9 incelenmiş negatif fotoğraftır. Tam giriş kapısından 10 fotoğraf (3 pozitif+7 negatif) geçer; iki reddedilen negatifin FP'si 0 olduğundan burada toplam Scope B ve uygun alt kapsamın FP'si aynıdır. Pozitif fotoğrafta etiket dışı alan UNKNOWN; fazladan kutular otomatik FP sayılmaz. FP merkezi incelenmiş negatif destekte olan kutu ve kutu alanının ≥%80'i destekte olan kutu ayrı kaydedilir; bunlar piksel precision/Dice değildir.

## Aynı güncel kapsamda sonuç

AG eski giriş referansı Step0 5/14 FP2, IoU150 5/14 FP7, GIoU150 5/14 FP8 idi. Bunlar güncel ürün sonucu değildir. Mevcut tamamlanmış modeller yalnız çıkarım için yüklendi; IoU/GIoU pilotları tekrarlanmadı.

| Yöntem/model | Scope B kaynak yakalama | İncelenmiş negatif FP merkez / ≥%80 alan | Uygun 3 kontrol girdisi | 28 kontrol, yalnız dayanıklılık |
|---|---:|---:|---:|---:|
{chr(10).join(lines)}

Eski IoU/GIoU ağırlıkları yalnız aynı Scope B ve TRAIN negatif tanı kaynaklarında tekrar çıkarıma alındı; 28 kontrol sütunları bu iki ağırlık için ölçülmedi (—). Yeni iki kol ve Step0 aynı 28 kontrolü kullanır. 28 kontrolün pozitif kısmi kutularında bağımsız incelenmiş temiz negatif paydası yoktur; buradaki FP=0 başarı/FPR iddiası değildir. 29 sabit kaynak hedefinin yalnız 16'sının merkezi seçili envelope içindedir; bu ikincil anatomik kapsam, 29 paydasının yerine geçirilmez. Step0 bu ikincil kapsamda 11/16 yakalar. Scope B'de de 14 sabit hedeften 6'sının merkezi güncel seçili envelope içindedir; bunların 3'ü eşleşir. 55d380f7 gerçek RIGHT girdisidir ve seçili yanak desteği eski anotasyon kapsamından farklıdır. Merkez-dışı hedeflerin tamamı hedef-dışı/sağlıklı diye yeniden etiketlenmez; bir eşleşme anatomik mesafe fallback'iyle kabul edilir. 4/14 bu nedenle tam güncel ROI doğruluğu diye sunulmaz, aynı sabit kaynak karşılaştırmasıdır. Kişi kimlikleri bilinmiyor; kaynak/family/decoded/yakın kopya ayrımı kayıtlıdır, kişi ayrımı kanıtlanmış sayılmaz. Scope B tekrar görülmüş geliştirme/regresyondur; final test yoktur.

| Yöntem/kapsam | Mikro <8 kaynak px | Küçük <16 px | Orta ≥16 px |
|---|---:|---:|---:|
{chr(10).join(scales)}

Staging merkez-kıl desteği aynı 55d380f7 girdisinde eski filtrenin 1/7 eşleşmesini 2/7'ye çıkarır. Kaynak kutuları değişmeden kalır; göz/ağız delikleri, yoğun kıl ve görünmeyen bölge retleri korunur. Step0'nun güncel toplamı 4/14 FP3'tür; AG'nin 5/14 FP2'si zorla eşleştirilmedi. Sabit ≥0.30 güven/IoU≥0.50 kapsamında 14 hedefin yalnız 4'ü NMS öncesinde zaten eşleşen kutuya sahiptir; NMS ve staging bu dördünü korur. 695ed248'de 5 hedefin hiçbiri bu aşamada eşleşmez. Diğer on sabit kaynak hedefini filtreyi kapatarak kurtarmak mümkün değildir; ancak yukarıdaki ROI farkı nedeniyle bu onunu tek başına yeni algoritma hatası saymıyoruz. Bu kayıt tek başına düşük güven ile kutu yerelleştirme kaybını birbirinden ayırmaz ve mimari suçlaması değildir. Kaynak/tile/anchor/objectness/class/decode/NMS/ret nedenleri her fotoğrafın JSON'unda; `product-trace-*.png` görüntüleri gerçek snapshot ve destekleri gösterir.

## TRAIN'de kanıtlanan kök neden ve düzeltme

Özgün ledger'daki 834 Pimple kutusu korunur. 401 otomatik fotometrik pseudo-pozitif kaynak gerçeği değildir; 110 TRAIN fotoğrafında üretilmiş dış poligon delikleri/UNKNOWN alanı temiz gerçek yapamaz. Yeni iki kolda pseudo'lar pozitif değil UNKNOWN/güvenlik alanıdır. Ledger'da 19 açık negatif TRAIN fotoğrafı vardır; bunun 15'i pilot TRAIN grubundadır. Bu 15'in 9'unda gerçek ürün görünür alın/burun/yanak desteğiyle kesişen 393.788 native piksel vardır; çene/kıl, gözlük, delik ve kalite dışı alanlar UNKNOWN. Bu ortak kapsam daralması model kazanımı diye sunulmaz.

İncelenmiş temiz TRAIN alanlarında ≥0.30 ve ≥%80 destekli mevcut yanlış kutu bulunmadı; yoğun düşük skorlu arka plan anchor'ları zaten gradyan alıyor. Dolayısıyla bütün negatiflerin loss dışında kaldığı iddia edilmez ve kolay arka planı tekrar eğiten top-tail planları fit edilmedi.

Asıl somut çelişki: kaynak COCO'da Pimple olmayan nesnelerle çakışan 191 otomatik Pimple adayı/56 TRAIN kaynak bulundu. Bunların tümü negatif yapılmadı. Görsel olarak incelenen **5 kaynak-Mole nesnesi /4 TRAIN grubu** seçildi; belirsiz Post-acne ve çevre cilt UNKNOWN kaldı. Bu, klinik tanı veya sağlıklı cilt etiketi değildir. Üç nesnenin eski 150-adım dizisinde gerçekten pozitif Pimple hedefi aldığı; diğer ikisinin ilgili tile'ının hiç örneklenmediği kaynak koordinatlarıyla kanıtlandı. Step0 ham güvenleri 0.583–0.858.

İki yeni kol Step0'dan, aynı 600 native tile sırası, seed, AdamW 3e-5, warmup30/cosine150, microbatch1/accum4 ile 150'şer adım çalıştı. Her onuncu tile beş TRAIN hata konumunu döner; diğer 540 seeded özgün sıra. Geometri/sınıf/backbone/BN donuk; yalnız sekiz `head.obj_preds.*` tensoru açıktır. Tek fark adayın kaynak-Mole ile eşleşen decoded kutulara negatif objectness denetimidir. Atanmış pozitifler ve tüm özgün Pimple/diğer UNKNOWN pseudo +16 px koruması her zaman önceliklidir. Scope B veya 28 kontrol mining/fit girdisi değildir.

İki kolun girdi-sırası SHA'sı `{payload['pilot']['control']['sampleSequenceSHA256']}`. Donuk durum SHA'sı aynı ve değişmemiş; aday 909 ek negatif-anchor maruziyeti, kontrol 0. Her 25 adımda immutable model/optimizer-RNG/state kaydedildi. Her iki 150-adım CURRENT'ın tam bayt hash'leri doğrulandı; optimizer momentleri, scheduler ve torch/Python/NumPy RNG yeniden yüklendi.

| TRAIN kaynak / nesne | Step0 ham max güven | Eşlenik kontrol | Denetim onarımı | ≥0.30 anchor kontrol → aday |
|---|---:|---:|---:|---:|
{chr(10).join(replay)}

Bu tablo aynı sabit TRAIN tile'larını ölçer; anchor'lar mükerrer olabilir, benzersiz ürün FP'si veya validation kazanımı değildir. Beş incelenmiş nesnenin beşi de ≥0.30 aday üretmeye devam eder; eşleşen yüksek skorlu anchor sayısı 55 →55'tir. Maksimum güvenlerdeki küçük düşüş, bu yanlış nesnelerin temizlendiği anlamına gelmez. Kanıtlanan etiket çelişkisi düzeltildi, ancak 150-adımlık bu müdahale güçlü kaynak-negatif ayrıştırmasını sağlamadı.

## Karar ve korunmuş teslim

{decision} {comparison} Kaynak-hedef kayıpları/kazanımları sayıya ek olarak JSON'da kimlikleriyle hesaplanır. Confidence/NMS ayarı veya uzun yeni eğitim yok. Mikro/küçük lezyon kaçırmaları, bilinen negatiflerde yanlış adaylar ve kişi kimliği belirsizliği sürer; normal ürün sivilcesi kapalıdır. Native araştırma adayını normal API/ONNX/hash kabulü yapılmış gibi sunmuyoruz.

19 Python regresyonu +8 gerçek frontend poz assertion'ı geçti. Üretim `appearance_analysis`, `instant_appearance`, `product_dryness`, `skin_models`, model config ve BUILD_ID hash'leri değişmedi. Kuruluk/sarkma, diğer sağlık modülleri, sesler, tasarım ve kullanıcı kayıtları korunur. Üretim kodu değişmediğinden typecheck/build/kısayol kabulü yeniden ana iş yapılmadı. Tek ağır süreç ve iki atomik sahiplik kilidi kullanıldı; başka süreç durdurulmadı. RAM açılması sonrası çalışma tamamlandı.

Makine makbuzu: `docs/acne-takeover-evidence-20261015.json`. Native fotoğraflar/ağırlıklar Git'e eklenmedi; yerel `audit-results/acne-takeover-20261015` altında korunur. Yeniden çalışma sırası: `acne_product_preflight.py` → mevcut modellerin `evaluate_acne_current_product.py` karşılaştırması → TRAIN denetim/probe (görsel inceleme zorunlu) → yalnız boş kolda sınırlı pilot → `verify_acne_pilot_checkpoints.py` → iki yeni kolun evaluator/replay'i → `render_acne_product_trace.py` → `finalize_acne_takeover_evidence.py`. Tamamlanmış kolu yeniden başlatma script tarafından reddedilir. PR #2 Draft; main'e merge yok.
'''


def main():
    names = ['step0', 'control_iou', 'candidate_giou', 'control', 'hard-negative']
    evaluations = {n:read(OUT / ('evaluation-' + n) / 'summary.json') for n in names}
    support_reference={r['sha256']:r for r in evaluations['control']['rows']}
    legacy_metadata=[]
    for name in ('step0','control_iou','candidate_giou'):
        for row in evaluations[name]['rows']:
            if 'verifiedCleanPixels' not in row and row['cohort']!='pilot-train-diagnosis':
                ref=support_reference[row['sha256']]
                assert row['truth']==ref['truth'] and row['sourceTransform']==ref['sourceTransform'] and row['fullStaticProductPass']==ref['fullStaticProductPass']
                row['verifiedCleanPixels']=ref['verifiedCleanPixels']
                legacy_metadata.append(dict(model=name,sha256=row['sha256'],metadata='model-independent same-payload reviewed support pixel count',source='evaluation-control; FP/predictions unchanged'))
    summaries = {}
    scope_prefixes = {'55d380f7','695ed248','4a1762ee','36e4010b','20031f35','02386f86','0597e811','0560bfd8','0f3354ae','0d891a03','33da7a52','02413bf9'}
    for name, report in evaluations.items():
        assert report['confidence'] == report['hardNMS'] == .30
        assert report['tilingContract'] == 'current-skin-models-photo-input-camera-crop-v1'
        scope = [r for r in report['rows'] if r['sha256'][:8] in scope_prefixes]
        held = [r for r in report['rows'] if r['cohort'] == 'heldout-train']
        summaries[name] = dict(modelSHA256=report['modelSHA256'], scopeB=aggregate(scope), scopeBAnatomicalEnvelopeCenter=dict(targets=sum(len(r['anatomicalEnvelopeCenterTargets']) for r in scope),matched=sum(len(r['anatomicalEnvelopeCenterPairs']) for r in scope)), scopeBStaticAdmissible=aggregate([r for r in scope if r['fullStaticProductPass']]), heldoutStaticAdmissible=aggregate([r for r in held if r['fullStaticProductPass']]), heldoutAllRobustnessOnly=aggregate(held), resource=report['resource'], evaluationSHA256=digest(OUT/('evaluation-'+name)/'summary.json'))
    filter_trace=[]
    for row in evaluations['step0']['rows']:
        if row['sha256'][:8] not in scope_prefixes:continue
        old=[[b['x'],b['y'],b['x']+b['width'],b['y']+b['height']] for b in row['oldFilterCandidates']]
        filter_trace.append(dict(sha256=row['sha256'], targets=row['targetCount'], productAdmissible=row['fullStaticProductPass'], beforeNMS=len(row['trace']['confidenceCandidates']), afterNMS=len(row['trace']['nmsCandidates']), confidenceSourcePairs=pairs_without_runtime(row['truth'],[v['box'] for v in row['trace']['confidenceCandidates']]), nmsSourcePairs=pairs_without_runtime(row['truth'],[v['box'] for v in row['trace']['nmsCandidates']]), oldFilterPairs=pairs_without_runtime(row['truth'],old), stagingPairs=row['pairs'], cleanFalseCandidates=row['verifiedCleanFalseCandidates'], rejectedByReason={reason:sum(r['reason']==reason for r in row['rejections']) for reason in sorted({r['reason'] for r in row['rejections']})}, sourceTransform=row['sourceTransform']))
    control, candidate = [read(OUT/('clean-pilot-'+n)/'receipt.json') for n in ('control','hard-negative')]
    assert control['steps'] == candidate['steps'] == 150
    assert control['initialWeightsSHA256'] == candidate['initialWeightsSHA256'] == evaluations['step0']['modelSHA256']
    assert control['sampleSequenceSHA256'] == candidate['sampleSequenceSHA256']
    assert control['frozenGeometryClassBackboneSHA256'] == candidate['frozenGeometryClassBackboneSHA256']
    assert control['frozenStateUnchanged'] and candidate['frozenStateUnchanged']
    assert control['unknownGradientZeroVerified'] and candidate['unknownGradientZeroVerified']
    assert control['repairedNegativeAnchorExposures'] == 0 < candidate['repairedNegativeAnchorExposures']
    current = {}
    for arm in ('control','hard-negative'):
        directory = OUT / ('clean-pilot-'+arm)
        pointer = read(directory/'CURRENT')
        assert pointer['step'] == 150
        generation = directory/pointer['directory']
        assert generation.resolve().is_relative_to(directory.resolve())
        for name, expected in pointer['hashes'].items():
            assert name in ('model.safetensors','optimizer-rng.safetensors','state.json')
            assert digest(generation/name) == expected
        state = read(generation/'state.json')
        assert state['step'] == 150 and state['sampleSequenceSHA256'] == control['sampleSequenceSHA256']
        current[arm] = dict(pointer=pointer, preservedGenerations=sorted(p.name for p in directory.glob('checkpoint-step-*')), stateKeys=sorted(state), receiptSHA256=digest(directory/'receipt.json'))
    comparisons = {}
    for reference in ('step0','control'):
        comparisons[reference] = {}
        for cohort, predicate in [('scopeB', lambda r:r['sha256'][:8] in scope_prefixes), ('heldoutStaticAdmissible', lambda r:r['cohort']=='heldout-train' and r['fullStaticProductPass']), ('heldoutAllRobustnessOnly', lambda r:r['cohort']=='heldout-train')]:
            a = [r for r in evaluations[reference]['rows'] if predicate(r)]
            b = [r for r in evaluations['hard-negative']['rows'] if predicate(r)]
            assert [(r['sha256'],r['truth']) for r in a] == [(r['sha256'],r['truth']) for r in b]
            before, after = target_set(a), target_set(b)
            comparisons[reference][cohort] = dict(lostSourceTargets=sorted(before-after), gainedSourceTargets=sorted(after-before), allPreviousMatchesPreserved=before<=after, cleanFPDelta=sum(r['cleanFP'] for r in b)-sum(r['cleanFP'] for r in a))
    accepted = all(comparisons[n][c]['allPreviousMatchesPreserved'] for n in ('step0','control') for c in ('scopeB','heldoutStaticAdmissible','heldoutAllRobustnessOnly')) and summaries['hard-negative']['scopeB']['cleanCenterFP'] < min(summaries[n]['scopeB']['cleanCenterFP'] for n in ('step0','control'))
    protected = read(OUT/'protected-production-identity.json')
    for item in protected:
        item['currentSHA256'] = digest(ROOT/item['path'])
        item['preserved'] = item['currentSHA256'] == item['sha256']
        assert item['preserved'], 'PROTECTED_PRODUCTION_CHANGED: '+item['path']
    config = read(ROOT/'services/core-api/models/skin-focused.json')
    # Record the real config tree, with no secret or personal data extraction.
    def find_acne(value):
        if isinstance(value,dict):
            if 'acne' in value and isinstance(value['acne'],dict): return value['acne']
            for child in value.values():
                found=find_acne(child)
                if found is not None:return found
        return None
    acne = find_acne(config)
    assert acne is not None and acne['accepted'] is False and acne['file'] is None
    payload = dict(schema='acne-takeover-measured-evidence-v3', sourceHEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), frozenAGCommit='d90ff95434c44b4e73ae77a7f1d5d6b2e167c987', BUILD_ID=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip(), productActivation=dict(accepted=False,file=None,normalAPIChanged=False,newBuildRequired=False), results=summaries, matchedSourceTargetComparisons=comparisons, shortExperimentAcceptance=dict(passed=accepted, rule='preserve every matched source target in both held-out scopes and robustness; reduce reviewed-negative Scope B FP vs Step0 and paired control', longTrainingAuthorizedByEvidence=False), pilot=dict(control={k:v for k,v in control.items() if k!='logs'}, candidate={k:v for k,v in candidate.items() if k!='logs'}, checkpoints=current), sourceConflicts=read(OUT/'actual-old-supervision-conflicts.json'), fixedTRAINReplay={n:read(OUT/('source-negative-repair-replay-'+n+'.json')) for n in ('control','hard-negative')}, groupIsolation=read(OUT/'group-isolation-audit.json'), protectedProduction=protected, limitations=['Scope B is repeatedly exposed development/regression, not final test','28 controls have source/family separation; person identities unknown','3/28 static camera gates passed; physical camera temporal stability not tested','Positive partial labels do not define clean negatives; held-out positive photos have no reviewed-negative denominator','No claim that source Mole category is a medical diagnosis or that bounding boxes are pixel masks','Normal product remains acne disabled; research native inference is not an activated normal API/ONNX integration'])
    browser=read(OUT/'browser-preflight.json');controls=[r for r in evaluations['step0']['rows'] if r['cohort']=='heldout-train']
    payload['browserContract']=dict(sourceHashes=browser['sourceHashes'], actualBrowserMediaPipe=browser['actualBrowserMediaPipe'], physicalCameraStabilityVerified=False, controlCount=len(controls), staticPass=sum(r['fullStaticProductPass'] for r in controls), poseRejected=sum(r['poseRejected'] for r in controls), blurryRejected=sum(r['blurRejected'] for r in controls), noFace=sum(r['quality']['status']=='NO_FACE' for r in controls), gateRejectionsCanOverlap=True, passedSources=[r['sha256'] for r in controls if r['fullStaticProductPass']])
    payload['step0ProductFilterTrace']=filter_trace
    original={r['sha256']:r for r in read(OUT/'inputs/original-reviewed-detector-data.json')['rows']};cohort=read(OUT/'inputs/controlled_train_cohort.json');train=[original[s] for s in cohort['pilotTrainShas']];scope=[original[r['sha256']] for r in evaluations['step0']['rows'] if r['sha256'][:8] in scope_prefixes]
    overlap={key:sorted({r[key] for r in train if r.get(key)}&{r[key] for r in scope if r.get(key)}) for key in ('sha256','group','family','decodedSHA256','dhash')}
    near=[dict(train=a['sha256'],scopeB=b['sha256'],distance=(int(a['dhash'],16)^int(b['dhash'],16)).bit_count()) for a in train for b in scope if a.get('dhash') and b.get('dhash') and (int(a['dhash'],16)^int(b['dhash'],16)).bit_count()<=6]
    assert not any(overlap.values()) and not near
    payload['scopeBTrainIsolation']=dict(exactOverlap=overlap,nearCopyDistanceLE6=near,personIdentityNotEstablished=True)
    payload['focusedVerification']=read(OUT/'focused-verification.json')
    payload['legacyReviewSupportMetadata']=legacy_metadata
    payload['productTraceRendering']=read(OUT/'product-trace-render.json')
    payload['inputProvenance']=read(OUT/'input-provenance.json')
    payload['frozenCodeProvenance']=read(OUT/'frozen/provenance.json')
    payload['reproducibility']={name:digest(OUT/name) for name in ['source-selection.json','browser-preflight.json','pilot-preregistration.json','train-mole-label-review.json','source-negative-repair-probe.json','train-clean-support/manifest.json','inputs/original-reviewed-detector-data.json','inputs/train-data-engineering-reviewed-20261013.json','inputs/controlled_train_cohort.json','inputs/annotation-scope-manifest.json']}
    (ROOT/'docs/acne-takeover-evidence-20261015.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (ROOT/'docs/acne-takeover-20261015.md').write_text(markdown(payload),encoding='utf8')
    print(json.dumps(dict(results={k:{f:v[f] for f in ['scopeB','heldoutStaticAdmissible']} for k,v in summaries.items()},acceptance=payload['shortExperimentAcceptance'],comparisons=comparisons)))


if __name__ == '__main__':
    main()
