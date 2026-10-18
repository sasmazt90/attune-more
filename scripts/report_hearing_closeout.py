"""Derive closeout counts and evidence hashes; keep physical acceptance open."""
import hashlib,json,re,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/hearing-technical-closeout-20261017'
def read(name):return json.loads((OUT/name).read_text('utf8'))
def atomic(path,value):
 t=path.with_suffix(path.suffix+'.tmp');t.write_text(value,'utf8');t.replace(path)
tone=read('tone-session.json');din=read('din-session.json');pcm=read('pcm.json');lifecycle=read('lifecycle.json');bank=read('bank-failures.json');late=read('digit-deadline.json');views=read('views.json');served=read('served-protection-receipt.json');focus=read('focus.json');guidance=read('guidance-null.json');driving=read('driving.json');consent=read('consent-proof.json');care=read('care-context.json')
assert tone['BUILD_ID']==din['BUILD_ID']==served['BUILD_ID']
assert tone['result']['totalPresentations']==len(tone['result']['presentations']) and len(tone['result']['thresholds'])==14
assert din['result']['validTrials']==len(din['reference'])==24
assert all(r['maxReconstructionDifference']<=1e-8 and abs(r['independentSNR']-r['requestedSNR'])<1e-9 for r in pcm['mixes'])
assert len(lifecycle['rows'])==9 and all(not r['records'] for r in lifecycle['rows'])
assert len(bank['rows'])==5 and all(not r['records'] for r in bank['rows'])
assert not driving['after']['records'] and not late['late']['records'] and late['stale']['before']==late['stale']['after']=='0/24'
assert focus['blockedDuringLease'] and focus['readerCancelled'] and focus['playedAfterExpiry']
assert consent['healthCallsBeforeConsent']==consent['physicalMediaAttempts']==0
assert care['specialty']=='Kulak Burun Boğaz'
unit_logs=['unit-hearing.log','unit-persistence.log','unit-protocol-final.log','unit-shared.log']
for file in unit_logs:
 text=(OUT/file).read_text('utf-8-sig');assert 'passed' in text and not re.search(r'\d+ failed',text),file
assert not (OUT/'typecheck-initial.log').read_text('utf-8-sig').strip()
max_leak=max(row['stats'][1 if row['ear']=='left' else 0]['peak'] for row in pcm['channels'] if row['ear']!='both')
max_meter=max(row['maxAbsoluteMeterDifference'] for row in pcm['channels'])
max_peak=max(row['peak'] for row in pcm['mixes'])
max_snr=max(abs(row['independentSNR']-row['requestedSNR']) for row in pcm['mixes'])
checks=[
 ('F067','Kullanıcı eylemi / AudioContext','İzin öncesi 0 medya; explicit hazırlık; own lease','consent-proof.json; lifecycle.json'),
 ('F068','Stereo sağ/sol PCM',f'18 kombinasyon; hedef dışı kanal peak={max_leak}; fiziksel kanal kabulü açık','pcm.json; tone-session.json'),
 ('F069','Kullanıcı kanal onayı','İki kanal örneği bitmeden checkbox/test açılmıyor; otomasyon onayı fiziksel duyma değildir','tone-session.json; din-session.json'),
 ('F070','Cihaz / görünürlük / kesinti','Kontrollü devicechange, gerçek context suspend ve route cleanup; fiziksel kopma açık','lifecycle.json; driving.json'),
 ('F071','Genlik / ramp / dur','35 ms ramp, kaynak gain doğrulaması; stop ile context closed, meter 0','pcm.json; tone-session.json; lifecycle.json'),
 ('F072','14 aşamalı plan','Sol 7 → sağ 7; 1000/2000/4000/8000/500/250/1000 Hz','tone-session.json'),
 ('F073','Adaptif dijital eşik','Mevcut −10/+5 dB ve ascending vote korundu; gerçek PCM seviyeleriyle 14 eşik','tone-session.json; unit-protocol-final.log'),
 ('F074','Sunum / yanıt zamanı','Natural ended + context clock bitişi olmadan sunum/yanıtsızlık puanlanmıyor','baseline.json; bank-failures.json; tone-session.json'),
 ('F075','Catch / erken / geç / çift / held',f"13 catch/0 yanlış alarm; {tone['heldRepeatEvents']} repeat-key olayı yanıta dönüşmedi; press sınıfları unit kontrolü",'tone-session.json; unit-hearing.log'),
 ('F076','Aralık / tohum','Üründe crypto seed; testte ilan edilmiş 8102026; gap 1.1–2.7 s, duration .8–1.35 s','tone-session.json; unit-hearing.log'),
 ('F077','Yanıtsız / sınır / null','Alt/üst/max-trials null; teknik kesinti miss değil; null geçmişte sıfır değil','unit-protocol-final.log; guidance-null.json; bank-failures.json'),
 ('F078','Tekrar tutarlılığı','Her iki 1000 Hz tekrar aynı; repeatInconsistent=false, eşik sabiti değişmedi','tone-session.json'),
 ('F079','Grafik / legend / kayıt','14 değer, ayrı kulak işaretleri, aynı ID/değerler reload sonrası; bir kayıt','tone-session.json; tone-result.png; tone-history.png'),
 ('F080','Türkçe sayı bankası','10 sayı + noise hash/mono 48 kHz/RMS; Ahmet −10% / −10Hz aynı banka','pcm.json; bank-failures.json'),
 ('F081','SNR / RMS / clipping',f'5 bağımsız karışım; max SNR hatası {max_snr:.3g} dB, max peak {max_peak:.6f}','pcm.json; din-session.json'),
 ('F082','Yönerge → geri sayım','Gerçek ended → yalnız bir 5,4,3,2,1 → PCM; sonraki turlarda tekrar yok','din-session.json'),
 ('F083','Üç sayı / sıra / keypad','24 gerçek PCM bağımsız banka/sıra/offset karışımıyla eşleşti; keypad yanıtları','din-session.json'),
 ('F084','24 geçerli / token','24 valid; 24 duplicate probe ek tur olmadı; gerçek eski callback yeni turu cevaplamadı','din-session.json; digit-deadline.json; unit-persistence.log'),
 ('F085','Ayrı paydalar','36/72 doğru sayı, 12/24 tam üçlü; partial 2/3 vs 0 ve tekrar dışlama unit kontrolü','din-session.json; unit-protocol-final.log'),
 ('F086','Adaptif SNR / null','23 reversal, −1 dB SNR; yetersiz/boundary null; klinik veya insan sonucu değil','din-session.json; unit-protocol-final.log; guidance-null.json'),
 ('F087','Dur / yeniden başlat / sahiplik','9 lifecycle + driving + 60 s deadline; foreign lease korunuyor; MSE focus stop/block/expire','lifecycle.json; driving.json; digit-deadline.json; focus.json'),
 ('F088','Sonuç / uzman bağlamı','Gerçek kayıt ID → hearing / Kulak Burun Boğaz; booking/paylaşım yapılmadı','care-context.json; history-390.png'),
]
evidence_names=['baseline.json','pcm.json','tone-session.json','din-session.json','lifecycle.json','bank-failures.json','digit-deadline.json','views.json','served-protection-receipt.json','focus.json','guidance-null.json','driving.json','consent-proof.json','care-context.json','build-receipt.json']+unit_logs+['typecheck-initial.log']
evidence=[dict(path=str(OUT/name),bytes=(OUT/name).stat().st_size,sha256=hashlib.sha256((OUT/name).read_bytes()).hexdigest()) for name in evidence_names]
value=dict(time=datetime.now(timezone.utc).isoformat(),baseCommit='7fe773c1f87e0e45dd3386c6e08d13fda6f2cba7',checkout=str(ROOT),branch='research/hearing-technical-closeout-20261017',BUILD_ID=served['BUILD_ID'],deliveryCommitReceipt=str(OUT/'status.json'),physicalHeadphoneAcceptance=False,clinicalValidation=False,technicalStatus='COMPLETE_ISOLATED',normalLauncherChanged=False,pushed=False,merged=False,features=[dict(id=i,name=n,status='TECHNICAL_VERIFIED_ISOLATED',result=r,evidence=e) for i,n,r,e in checks],metrics=dict(toneStages=14,tonePresentations=len(tone['result']['presentations']),catchTrials=tone['result']['catchTrials'],catchFalsePositive=tone['result']['catchFalsePositive'],heldKeyRepeatsIgnored=tone['heldRepeatEvents'],dinValid=din['result']['validTrials'],dinValue=din['result']['value'],dinUnit=din['result']['unit'],maxChannelLeak=max_leak,maxMeterSampleDifference=max_meter,maxMixPeak=max_peak,maxSNRDifference=max_snr,bankFiles=len(pcm['files']),uniqueUnitTests=18,servedJS=len(served['servedJS']),sourceFiles=served['sourceFilesVerified'],localAssets=served['assetsVerified'],protectedTrees=len(served['protected'])),evidence=evidence)
atomic(OUT/'evidence-index.json',json.dumps(value,ensure_ascii=False,indent=2))
table='\n'.join('| '+ ' | '.join([i,n,'Teknik doğrulandı; fiziksel kabul ayrı',r,e])+' |' for i,n,r,e in checks)
report=f'''# İşitme teknik kapanış — 17 Ekim 2026

Teknik durum: **ayrı worktree'de tamamlandı**. Fiziksel kulaklık ve klinik kabul **yapılmadı**. Normal başlatıcı/ana ürün aktivasyonu, push ve merge yok.

- Kaynak taban: `7fe773c1f87e0e45dd3386c6e08d13fda6f2cba7`; temiz birleşik teslimden ayrı worktree.
- Checkout: `{ROOT}`
- Branch: `research/hearing-technical-closeout-20261017`
- BUILD_ID: `{served['BUILD_ID']}`
- Yerel teslim commit'i: kanıt klasöründeki atomik `status.json` / `commit-receipt.json` içinde kayıtlı. Bu raporun kaynak kimliği ayrıca 183 kaynak/build girdisinin hash'iyle sabitlenmiştir.
- Kanıt: `{OUT}`; her dosyanın boyut/SHA-256'sı `evidence-index.json` içinde.

## Başlangıç ayrımı

| Kategori | Bulgu |
| --- | --- |
| Yeniden üretilen gerçek hata | Source.start bilinçli olarak hiç başlatılmadığında 8 sunum tamamlandı diye ilerledi; Durdur sonrası engine context running kaldı; claim ilgisiz DOM videoya 2 pause çağrısı yaptı. `baseline.json`. |
| Güncel teknik kanıtı eksik | Eski ver47 build'indeki başarılı tam oturumlar mevcut 7fe build'i için kanıt değildi. Yeni build'de tek tam saf ses ve tek 24 geçerli DIN oturumu yapıldı. |
| Teknik geçmiş / fiziksel açık | Dijital PCM/kanal/SNR kontrolleri kulaklığın akustik yönü, rahat duyulabilirliği veya insan performansını doğrulamaz. Önceki birleşik revoke/passthrough kanıtı arka plan olarak okundu; yeni build için güncel kontroller üretildi. |

## Gerçek düzeltmeler

1. **Eksik sesin miss sayılması:** Web Audio kaynağı artık context clock üzerinde 20 ms ileriye açıkça zamanlanıyor. Natural ended ve beklenen dijital bitiş doğrulanıyor. Erken bitiş, hiç başlamama, start exception ve iptal reject ediliyor; bekleyen promise/watchdog/node/analyser hemen temizleniyor. Saf ses response window'u bu timeline'a bağlı; bitiş makbuzu yoksa adaptasyon/sunum paydası ilerlemiyor. Dijital zaman akustik gecikme kalibrasyonu değildir.
2. **Duraklamada açık motor:** mute, Durdur, cihaz olayı, sürüş, context suspension ve route/izin kesintisi engine'i kapatıyor. Yeniden hazırlık yeni engine/kanal doğrulaması gerektiriyor. Unmute eski uyaranı oynatmıyor.
3. **Sahiplik dışı müdahale:** tüm DOM audio/video ve global speechSynthesis iptali kaldırıldı. Uygulamaya ait guidance/MSE mevcut focus lease olaylarıyla duruyor/bloklanıyor; yabancı lease silinmiyor. İlgisiz video pause sayısı yeni tam ürün koşusunda 0.

Ek sözleşme sağlamlaştırması: DIN için yalnız tamamlanmış güncel sunumu bir defa tüketen token, stale callback kontrolü ve basılı klavye repeat koruması eklendi. Bunlar önceki her akışın bozuk olduğu iddiası değildir; istenen eksik güncel kontroller artık doğrudan kanıtlıdır. `presentationVersion=source-complete-token-v1`; mevcut ölçüm yöntemi, ölçek ve birimler değişmedi.

## Hata bulunmayan / korunan protokol

`hearingProtocol.ts`, `playbackMeter.ts`, merkezi izin, RecordHistory, tüm diğer üretim kaynakları ve backend yöntemleri tabanla aynı. Frekanslar/kulak sırası, −10/+5 dB adaptasyon ve ascending vote, catch olasılığı .12, 1.1–2.7 s aralık, .8–1.35 s ton, 1.2 s yanıt penceresi; 24 DIN, 4→2 dB adım, son 6 reversal ve null koşulu korunuyor. Banka/profil/auditoryAcceptance değişmedi. Eski kullanıcı kayıtları okunup yeniden yazılmadı.

## Ölçüm ve iki tam ürün oturumu

| Kontrol | Gerçek teknik sonuç |
| --- | --- |
| PCM / stereo | 6 frekans × sol/sağ/both = 18 OfflineAudioContext render; hedef dışı kanal max peak **{max_leak}**; üretim analyser'ıyla doğrudan render farkı **{max_meter}**. |
| Gain / ramp | Gerçek kaynak PCM peak'i her adaptif seviyenin örneklenmiş sinüs genliğiyle eşleşti; 35 ms ramp, ilk/son örnek 0; clipping yok. |
| Banka | **{len(pcm['files'])}** dosyanın tüm byte SHA-256'sı, mono 48 kHz, RMS/peak kontrol edildi. `{pcm['bankVersion']}`, tr-TR-AhmetNeural / −10% / −10Hz. Bankanın insan auditoryAcceptance değeri `{pcm['bankProfile']['auditoryAcceptance']}`. |
| SNR | −15/−8/0/8/15 dB bağımsız speech/noise yeniden oluşturması; max oran hatası **{max_snr:.3g} dB**; peak max **{max_peak:.6f}**, clipping 0. |
| Tek tam saf ses | 14 aşama, **111** tamamlanmış sunum = 98 gerçek ton + 13 silent catch; catch yanlış alarm **0/13**. Mühendislik PCM-peak yanıtlarıyla 14 eşik **−45 dBFS peak**; iki 1000 Hz tekrar aynı. **{tone['heldRepeatEvents']}** repeat-key olayı fazladan yanıta dönüşmedi. Bu bir kişinin eşiği değildir. |
| Tek tam DIN | **24** tamamlanmış gerçek uyaran; her PCM bankanın doğru sayı/sıra/noise offset/SNR'ıyla bağımsız yeniden oluşturuldu. Gerçek keypad'de 36/72 sayı ve 12/24 üçlü; 23 reversal, mühendislik sonucu **−1 dB SNR**. 24 duplicate-submit probe, ek valid tur 0. |
| Yönerge / sayaç | Gerçek guidance ended → tek 5/4/3/2/1 → ilk uyaran; sonraki 23 turda tekrar sayaç yok. |
| Sonuç / geçmiş | İki gerçek tamamlanmış test için birer kayıt; yenileme sonrası aynı ID/14 kulak-frekans-değer ve aynı DIN/SNR. Saf ses grafiği ve legend aynı sonuçtan. |
| Null / saklama | Null fixture geçmişte “Eşik bulunamadı / Kararlı eşik bulunamadı”, sağlıklı sıfır değil. Save-off/revoke gerçek transaction guard unit'inde yazmıyor; eski kayıt, cihaz, yöntem ve farklı birimler korunuyor. Bu guard testi ikinci tam oturum diye sunulmadı. |

Tarayıcı test süreci `--mute-audio` ile fiziksel çıkışsız çalıştı; sinyal ve native zamanlamalar değişmedi. İnsan yanıtı, cihaz dB SPL/HL kalibrasyonu ve klinik doğruluk çıkarımı yok.

## Kesinti, izin ve sahiplik

- 9 lifecycle kontrolü: uyaran sırasında header mute/unmute, gerçek AudioContext suspend, kontrollü devicechange, Durdur, start exception, hiç başlamayan/bitmeyen source, route unmount, başka sekmeden izin geri çekme, başka oturum sahipliği. Kesintilerde kayıt 0; own context closed, ortak meter context suspended/0. Kontrollü olay fiziksel cihaz kopması değildir.
- Gerçek izole araç API'si 10 km/h → PARK zorunluluğu → tüm own kaynaklar kapalı, kayıt 0; API 0 km/h'a geri alındı. Önceki teslimin backend'i/araç durumu değiştirilmedi.
- Gerçek **{late['late']['seconds']:.3f} s** yanıtsız DIN bekleme sonrası güvenli pause. Önceki render'dan tutulan gerçek submit callback yeni tamamlanmış turda çalıştırıldığında **0/24 → 0/24**; ardından test temiz durduruldu.
- Yönerge sesi sırasında ayrıca mute: gerçek dalga **{guidance['requiredGuidanceMute']['before']['amplitude']} → 0**, engine closed / ortak context suspended; unmute otomatik kanal/test başlatmadı, kayıt 0.
- Beş ortak hizmette unchecked/persistent giriş izni, reload/reentry, cross-tab revoke, storage failure ve güvenli ret kontrol edildi: izin öncesi sağlık çağrısı ve fiziksel medya girişimi 0.
- Mevcut static onaylı MP3 ile gerçek MSE: hearing lease stream'i pause/abort ediyor, yeni stream'i blokluyor, süre bitince yeniden oynatma mümkün. Provider çağrısı 0.

## F067–F088 güncel durum

Bu tablo yeni izole build içindir. Kaynak görev tablosuna yazılmadı. “Teknik doğrulandı” fiziksel kulaklık/insan kabulü anlamına gelmez.

| ID | Özellik | Durum | Sonuç | Kanıt (kanıt klasörüne göre) |
| --- | --- | --- | --- | --- |
{table}

## Teslim doğrulaması

- 4 işitme + 14 etkilenen ortak unit regression = **18 farklı test geçti**. Son eklenen max-trials/partial-digit assertions tekrar ilgili testte geçti; tekrarlar yeni test sayılmadı.
- Typecheck geçti; production build geçti. Test harness seçici/JSON interop/Node navigator sorunları test tarafında düzeltildi; ürün bunları geçirmek için değiştirilmedi. İlk route seçicisi “Gizlilik” yerine gerçek “Gizlilik & İzinler” olarak düzeltildi; geçmiş altı lifecycle kontrolünün kanıtı korundu.
- **38** gerçek HTTP JS yanıtı byte/hash eşleşti; **183** kaynak/build girdisi; **93** yerel varlık; **7** korunan checkout HEAD/status aynı. Production bundle test callback/fixture işaretleri içermiyor; backend test ledger 404.
- Masaüstü 1440×1000 ve dar 390×844: fotoğraf/giriş tasarımı, tek header mute, merkezi izin, geçmiş dialog'u korundu; yatay taşma 0. Ekran görüntüleri görsel olarak incelendi.
- Tek teslim URL'si: **http://127.0.0.1:3309/hearing**. Yerel API 8309; yalnız bu worktree'ye ait kayıtlı PID + başlangıç zamanı + tam komut satırı sahipliğiyle yönetilir.
- Başlat: `{ROOT / 'Start-Hearing-Technical.ps1'}` (`-NoBrowser` isteğe bağlı). Durdur: `{ROOT / 'Stop-Hearing-Technical.ps1'}`. Başlatıcı doğrulanmış aynı build/PID'leri tekrar kullanır; yabancı port/process'i korur. Geliştirme sunucularının sahiplik kontrollü durdurulması ve production başlatıcının idempotent reuse yolu doğrulandı. Normal Windows kısayolu değişmedi.

## Sona bırakılan tek fiziksel kulaklık kontrol listesi

1. Gerçek stereo kulaklıkta sol ve sağ örneğin yalnız doğru taraftan gelmesi.
2. Kullanıcının seçtiği rahat seviyede başlangıç ve test seslerinin duyulabilirliği; sistem sesine uygulama müdahalesi olmaması.
3. Türkçe sayıların sırasıyla anlaşılabilirliği ve gürültü içindeki pratik dinleme deneyimi.
4. Gerçek kulaklık ayrılması/değişimi sırasında güvenli kesinti ve yeniden kanal hazırlığı.
5. Tek ortak fiziksel kabul oturumunda doğal kullanıcı yanıtlarıyla tam saf ses + 24 geçerli DIN, sonuç ve aynı geçmiş kaydı.

Bu liste ara kullanıcı test talebi değildir. `physicalHeadphoneAcceptance:false`, `clinicalValidation:false` korunur. Yeni ses/model/eğitim/sağlayıcı, ücretli çağrı, normal aktivasyon veya eski kayıt değişikliği yapılmadı.
'''
atomic(OUT/'report.md',report)
(ROOT/'docs').mkdir(exist_ok=True)
atomic(ROOT/'docs/hearing-technical-closeout-20261017.md',report)
atomic(ROOT/'docs/hearing-technical-closeout-20261017.json',json.dumps(value,ensure_ascii=False,indent=2))
print(json.dumps(value['metrics']))
