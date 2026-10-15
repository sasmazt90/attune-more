# Sivilce: sonlu objectness özellik öğrenebilirliği — 2026-10-15

Başlangıç `b6623336f02794130be364d08b6dabf083b28e75`. Tek yeni aday Step0'dan başladı, 150 optimizer adımında donduruldu. Önceki pilotlar yeniden eğitilmedi. Üretim `accepted:false, file:null`; korunan BUILD_ID `mlOb9YC5JKNnbE_1xzdjD`. Model SHA-256 `da3fa04e927ada92d8f1f8bd70f670cd294933772065c7e91383298b466c48e6`.

## Değişken ve sınırlar

Bu YOLOX'ta ayrı obj_convs yoktur; objectness ile kutu yolu reg_convs özelliklerini paylaşır. Yalnız objectness için Step0 reg_convs kopyası obj_convs olarak ayrıldı; mevcut stems/kutu/sınıf yolu değiştirilmedi. Öğrenenler 8 yeni convolution weight tensoru ve 8 obj_preds weight/bias tensorudur. Backbone/FPN, shared stems, reg_convs/reg_preds, cls_convs/cls_preds ve bütün BN affine/istatistikleri byte düzeyinde korundu. On beş sabit TRAIN tile'ında fit öncesi bütün çıktılar Step0 ile tam aynı (maksimum fark 0). Yeni 619-tensor grafiği açık sürümlüdür; eski grafa sessiz/partial yükleme yoktur.

Önceden kaydedilen plan: LR 3e-5, AdamW weight-decay .01, warmup30/cosine150, clip norm5, microbatch1/accum4, önceki onarılmış kolun aynı 600 tile sırası (`2d0c2732a9649ef5a0fde30649c4b6ba32a6af18f955750a52b9b5307fd52515`). 401 pseudo-pozitif Pimple yapılmadı; UNKNOWN ve özgün Pimple +16 px koruması korunur. Beş kaynak-Mole nesnesi sadece TRAIN'dedir; kaynak kategorisi klinik tanı veya bbox pixel-mask gerçeği değildir. Scope B ve 28 kontrol fit/mining girdisi değildir. Daha fazla öğrenen parametre ve global clipping'in fiili ölçeği farklıdır; sonuç tüm donuk backbone özellikleri hakkında nedensel kanıt değildir.

## Beş ayrı öğrenme yolu

| TRAIN kaynak / anotasyon | Geçerli negatif anchor | İlk normalize negatif loss | Özellik gradyan L2 toplamı | Step0 → önceki yalnız-prediction → yeni özellik adayı obj×cls | Tile / negatif-anchor maruziyeti |
|---|---:|---:|---:|---:|---:|
| 349b1a1d / 6510 | 16 | 6.932998 | 117.895 | 0.765798 → 0.762346 → 0.393470 | 14 / 224 |
| 349b1a1d / 6513 | 17 | 2.401388 | 66.353 | 0.623781 → 0.616856 → 0.180056 | 12 / 204 |
| c41f8bfe / 12627 | 13 | 8.255553 | 150.218 | 0.759345 → 0.756849 → 0.390101 | 12 / 156 |
| 690689ae / 21821 | 15 | 14.651921 | 173.180 | 0.857741 → 0.855879 → 0.451598 | 13 / 195 |
| 91cb7dfe / 23600 | 10 | 4.454899 | 107.081 | 0.583346 → 0.576907 → 0.148489 | 13 / 130 |

Hiçbir nesne pozitif koruması nedeniyle sıfır denetimde kalmadı. Her nesnede kaynak kutusu → gerçek native tile → decoded/emitter anchor → loss → parametre gradyanı → fiili ilk AdamW güncellemesi → aynı anchor'ın objectness/class/obj×cls değeri makbuzda ayrıdır. Toplam 909 maruziyet tek başına kanıt sayılmadı. İlk gerçek güncellemelerde özellik ağırlığı değişimi ve score değişimi ayrı kaydedildi; bbox/class değişmedi. Güncelleme gerçek dört-microbatch birikiminin toplamıdır; nesneye özel gradyan ile tüm batch'in parametre güncellemesi birbirine eşit sayılmaz. Negatif maske atanmış pozitifleri asla geçersiz kılmaz. Prefit beş backward denetimi optimizer güncellemesi yapmadı.

## Sabit TRAIN hedefleri ve zaman çizgisi

| Optimizer adımı | 0.30 altındaki Mole nesnesi | Benzersiz kaynak-Pimple | Tile hedef gözlemi |
|---|---:|---:|---:|
| 0 | 0/5 | 37/43 | 39/45 |
| 1 | 0/5 | 37/43 | 39/45 |
| 5 | 0/5 | 37/43 | 39/45 |
| 10 | 0/5 | 37/43 | 39/45 |
| 25 | 0/5 | 32/43 | 34/45 |
| 50 | 2/5 | 30/43 | 32/45 |
| 100 | 2/5 | 31/43 | 33/45 |
| 150 | 2/5 | 31/43 | 33/45 |

On grup-kayıtlı pozitif tile ve beş hata tile'ında 45 hedef gözlemi, **43 benzersiz özgün kaynak anotasyonuna** karşılık gelir. İki örtüşen tile gözlemi kaynak başarısında iki kez sayılmaz. Benzersiz başlangıç 37/43 → son 31/43; kayıp 6, kazanım 0. Önceki yalnız-objectness kolu aynı yeni sabit TRAIN probe'larında yalnız çıkarımla tekrar ölçüldü: 37/43. Bunlar TRAIN sonuçlarıdır, genelleme/final test değildir. Orijinal ölçüm JSON'ları değiştirilmedi; benzersiz kaynak eşlemesi ayrıca türetildi.

Dondurma sonrası beş gerçek dört-tile batch'inde sıfır optimizer güncellemesiyle pozitif/nesne-negatif gradyanları ayrıldı. Son modelde ölçülebilir beş yerel kosinüsten 5/5 negatiftir; yalnız özellik-conv gradyanlarında da 5/5 negatiftir. Bu yerel çatışma denetimi bütün optimizer geçmişinin nedensel açıklaması değildir. Altı kayıp TRAIN hedefinin 4'ünde sabit geometriyle eşleşen en yüksek obj×cls 0.30 altındadır; diğer 2 kayıp güven sonrası NMS/bire-bir seçim aşamasındadır. Örnek kaynak 2cecc2fe (663,697)-(686.5,708.5) güveni 0.599086 →0.294184, sınıf olasılığı 0.868873 sabit. Kaynak 431c54b4 (717,59)-(726.5,73.5) 0.326484 →0.164409, sınıf olasılığı 0.828400 sabit. Etiketin loss'a ulaşmaması/pozitif korumasında gizlenmesi olasılığı dışlandı; bu ayarlarda bastırma öğrenilirken gerçek Pimple yakalaması kaybolmaktadır. Tam seçici ayrım öğrenilmedi; daha uzun eğitimin bunu düzelteceği çıkarılamaz.

## Dondurulmuş model, aynı güncel ürün evaluator'ı

| Kapsam | Step0 → yeni yakalama | Step0 → yeni incelenmiş-negatif FP |
|---|---:|---:|
| Scope B, 3 pozitif /14 sabit kaynak hedefi +9 negatif fotoğraf | 4/14 → 2/14 | 3 → 2 |
| Statik ürün kapılarından geçen 3 kontrol fotoğrafı | 16/29 → 15/29 | İncelenmiş negatif paydası yok |
| 28 kontrol, sadece dayanıklılık kapsamı | 84/155 → 72/155 | İncelenmiş negatif paydası yok |

Kaynak-hedef kayıp/kazanım kimlikleri, mikro/küçük/orta ve ≥%80 incelenmiş-negatif destekli yanlış kutular makbuzda ayrı. .30 confidence → .30 Hard-NMS, browser MediaPipe/snapshot/exclusions, mevcut crop, scale/origin, gerçek anatomik filtre aynı kaldı. Model/graph strict kimliği doğrulandı. Fiziksel kamera kararlılığı yeniden test edilmedi. Scope B tekrar görülmüş geliştirmedir; kişi kimlikleri bilinmediğinden bağımsız kişi-final testi iddiası yoktur. Sabit kaynak anotasyon kapsamı seçili anatomik envelope ile aynı değildir; b662333 kapsam notu korunur. Yalnız seçili envelope-merkezi kapsamında da Step0 3/6 → yeni 1/6; 14 sabit kaynak hedefi bu daha küçük payda ile değiştirilmez. UNKNOWN alanlar negatif sayılmadı.

## Karar ve teslim

TRAIN kabulü: **False**. Başlangıç modeline göre ürün karşılaştırma kabulü: **False**. Uzun eğitim gerekçesi: **False**. Beş hatayı bastırıp bütün önceki Pimple eşleşmelerini koruma şartı sağlanmadan uzun eğitim veya ürün aktivasyonu yok. Tek aday donduruldu; yeni loss/LR/eşik/örnekleme taraması yapılmadı. Kuruluk, sarkma, diğer yöntemler, hosted izin/config, UI, sesler ve kullanıcı kayıtlarına dokunulmadı.

24 odaklı Python kontrolü, strict model/optimizer/scheduler/RNG yüklemesi ve frozen/BN hash denetimleri geçti. Altı immutable checkpoint ve CURRENT yerelde korunur. Üretim kaynakları/config/build hash'leri aynı; üretim kodu değişmediği için yeni build veya shortcut teslimi iddiası yoktur. PR #2 Draft kalır; main'e merge yoktur.

Makbuz `docs/acne-learnability-evidence-20261015.json`; model/fotoğraflar Git'e alınmadan `audit-results/acne-learnability-20261015` altında kalır. Öğrenme kodu `run_acne_learnability.py`; tamamlanmış adayı tekrar başlatmayı reddeder. Son ürün çıkarımı `evaluate_acne_current_product.py --model objectness-features`; eski pilotları çalıştırmaz.
