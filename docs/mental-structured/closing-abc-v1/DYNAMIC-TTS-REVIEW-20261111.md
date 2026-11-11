# Normal konuşmada dinamik TTS — kaynak ve mevcut kanıt incelemesi

11 Kasım 2026. İncelenen kaynak tabanı: `dd3025ad7acdf15a05bd27a31e8ad2928a677e55`.
Bu incelemede yeni AWS deneyi veya canlı ölçüm yapılmadı. Kapanıştaki hazır 144 kayıt çözümü,
normal konuşma turlarının dinamik sentezini hızlandırmış sayılmaz.

## Kodda zaten bulunanlar

- `services/core-api/mental_provider.py`: park halindeki yanıt istemi en fazla iki kısa cümle,
  toplam 25 kelime ve en fazla bir takip sorusu istiyor. Bunu ilk defa eklemek yeni çözüm değildir.
  İstem, sağlayıcının her cevabının gerçekten bu uzunlukta olduğunu tek başına kanıtlamaz.
- `apps/vehicle-app/src/utils/mentalNeuralSpeech.ts`: ilk bölüm en az altı kelimeye ulaşana
  kadar cümle toplar; kalan metni ikinci bölüm yapar. İlk ses hazır olunca ikinci sentez başlar,
  ilk bölüm çalarken ilerler. Kullanıcının önerdiği örtüşmeli hazırlık zaten kısmen uygulanmış.
- `useMentalConversation.ts`: normal tur açık speakerProfile göndermez; profil servis config'inden
  gelir. Önceki host doğrulaması official-default idi. Yeni dağıtımda gerçek config tekrar okunmalı.
- `mental_neural_worker.py` ve `mental_neural_resident.py`: model bellekte, inference_mode ve
  resident süreç mevcut. Generate tüm sesi döndürür; HTTP gövdesi okumayı streaming yapmak
  modelin daha erken bir ses parçası üretmesini sağlamaz.
- `mental_neural_tts.py`: sentez iptalinde worker öldürülür; yeniden ısınma son isteğin dil/profiliyle
  planlanır. İptal sonrası gecikme, normal sıcak sentez gecikmesinden ayrı değerlendirilmelidir.

## Önceki gerçek GPU kanıtı

Kaynaklar: bu dizindeki `review-20261110-round3.json` (benchmark ve servicePath),
`review-20261110-round4-live.json` (web.summary ve gpu.diagnostic), README'nin 3./4. tur bölümleri.
JSON'lar ve ilgili kaynak kodu doğrudan okundu. Bunlar **female-calm-v1 kapanış metinleri**;
normal official-default konuşma turuna ait yeni bir karşılaştırma değildir.

| Ölçüm | CPU | Aynı model, A10G GPU | Sınır |
| --- | --- | --- | --- |
| Kısa satır sıcak sentez medyanı, aynı metin/seed | 15,57 sn | 3,14 sn | Her cihazda 45 örnek; uçtan uca ilk ses değil |
| Uzun parça sıcak sentez medyanı | 28,18 sn | 6,65 sn | Her cihazda 30 örnek |
| Kısa satır token üretimi medyanı | 6,13 sn | 2,46 sn | Tanılama ölçümü |
| Kısa satır waveform decoding medyanı | 9,05 sn | 0,57 sn | Tanılama ölçümü |
| Sıcak servis yolu medyanı | 16,59 sn | 5,16 sn | n=13 / 60; HTTP dışı, farklı örnek sayıları |

4. tur canlı WEB→API→GPU zincirinde ses isteği medyanı 5,516 sn idi (23 sesli sıcak kapanış):
yaklaşık 2,170 sn doğrulama ve 3,363 sn worker. 24 girişimden birinde satır reddedildi.
A/B/C bu üretimin önünde çalıyordu; 126 ms'lik C→kişisel geçişi normal dinamik yanıt süresi diye
sunmak yanlış olur. Aynı turda profil ilk yüklemesi 19,6–20,6 sn ve iptal sonrası yeniden ısınma
23,3–23,5 sn ölçülmüş; GPU tek başına soğuk başlangıcı ortadan kaldırmıyor.

## Karar sırası

| Seçenek | Beklenen fayda ve kanıt | Uygulanabilirlik / risk | En küçük gerekli doğrulama |
| --- | --- | --- | --- |
| Aynı modeli GPU'da normal konuşmaya uygulamak | En güçlü mevcut kanıt: diğer ses profilinde sıcak sentez yaklaşık 5 kat hızlandı. Normal tur kazanımı henüz ölçülmedi | Orta; mevcut ağırlıklar korunabilir. Ek ücret, ilk yükleme ve GPU ses farkı var | Yeni kaynak onayından sonra mevcut gerçek normal ses profiliyle TR/EN/DE kısa eşleşmiş CPU/GPU örnekleri; ilk ses, sentez aşamaları ve dinleme ayrı |
| İlk bölümü gereksiz uzatan altı kelime eşiğini değerlendirmek | Kısa bir onay cümlesi ile sorunun birleşmesini önleyebilir. Kazanç ölçülmedi | Küçük frontend değişikliği; çok kısa cümlelerde prosodi veya ek parça maliyeti riski | Aynı mevcut yanıtlarda splitter çıktısını çevrimdışı karşılaştır; yalnız gerçekten birleşen örnek varsa küçük A/B ölçümü öner |
| Yanıt uzunluğu sözleşmesinin gerçekten uygulanıp uygulanmadığı | 25 kelimeyi aşan cevap varsa gereksiz sentez işini azaltabilir. Kural zaten istemde | Düşük/orta; cümleyi körlemesine kesmek anlamı veya güvenliği bozabilir | Yayındaki kısa kontrolden gelen sentetik yanıtların kelime/satır sayısını kontrol et; aşım yoksa yeni çalışma açma |
| İptal sonrası doğru profilin yeniden ısınması | Yalnız sonraki soğuk beklemeyi azaltabilir; sıcak sentezi hızlandırmaz | Orta; güvenli iptal/worker sonlandırma korunmalı | Önce mevcut kod ve kayıtlarla yanlış profil senaryosunun kullanılan yolda oluştuğunu göster; oluşmuyorsa değiştirme |
| Model dosyası doğrulamasını daha az tekrarlamak | Kadın sesi GPU isteğinde yaklaşık 2,2 sn maliyet görüldü | Bütünlük kontrolü mimarisini etkiler; basit mtime önbelleği eşdeğer güvence değildir | Şimdilik uygulama; bütünlük garantisi korunmadan hash kontrolünü kaldırma |
| Daha fazla HTTP streaming, aynı compile veya thread denemelerini tekrarlamak | Mevcut darboğazı çözdüğüne dair kanıt yok; önceki compile/thread denemeleri fayda vermedi | Ek karmaşıklık ve doğrulama maliyeti | Tekrar deney başlatma |

**Öneri:** önce hazır kayıt kapanışını dağıt. Normal dinamik tur için aynı modeli GPU'da tutmak en
kuvvetli seçenek; mevcut kanıtı normal profil için ölçüm sonucu saymadan, ek kaynak ve işletim
maliyetini somutlaştırıp onaya sun. Kaynak açmadan mevcut splitter'ın altı kelime birleşmesini
ve 25 kelime kuralına uyumu kontrol etmek düşük maliyetli hazırlıktır. Yeni bir model/Qwen kolu,
geniş benchmark veya ses kimliği değişimi önerilmiyor.

## Doğrudan incelenen dosyalar

- `apps/vehicle-app/src/utils/mentalNeuralSpeech.ts`
- `apps/vehicle-app/src/utils/useMentalConversation.ts`
- `apps/vehicle-app/src/utils/mentalClosingBridge.ts`
- `services/core-api/mental_provider.py`
- `services/core-api/mental_neural_worker.py`
- `services/core-api/mental_neural_resident.py`
- `services/core-api/mental_neural_tts.py`
- `scripts/qa/realistic/mental_resident_probe.py`
- `docs/qa/PERFORMANCE-FOLLOWUP-20261105.md`
- `docs/qa/DEPLOYMENT-BASELINE-20261105.md`
- `docs/mental-structured/closing-abc-v1/README.md`
- `docs/mental-structured/closing-abc-v1/review-20261110-round3.json`
- `docs/mental-structured/closing-abc-v1/review-20261110-round4-live.json`

Dağıtım hazırlığı ayrıca iki kapanış manifesti/kataloğu, dört ilgili test dosyası, AWS operasyon
belgeleri ve deploy_host/deploy_release/build_bundle/systemd kaynaklarına dayanır.
GitHub üzerinden depo kaynakları okundu; ayrı bir GitHub coding agent'ı çalıştırılmadı.
