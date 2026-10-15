# Sivilce devri: gerçek ürün girdisi ve kaynak-etiket denetimi

Üretim korunmuştur: sivilce `accepted:false`, `file:null`. Yeni staging modeli normal API seçicisine bağlanmadı. BUILD_ID `mlOb9YC5JKNnbE_1xzdjD`; bu görevde üretim build'i, UI veya kullanıcı kaydı değişmedi. AG `d90ff95434c44b4e73ae77a7f1d5d6b2e167c987` salt okunur incelendi; dal bütünü taşınmadı.

## Ürün eşdeğerliği

AG adaptörünün kendi checkout'una göreli TS importları, tüm açılarda FRONT `isAligned` kapısı, 720 ölçekli yaklaşık yüz/kıl maskesi ve %15 pad tile kapsamı düzeltildi. Ana checkout'un gerçek SkinAnalyzer/MediaPipe classic worker, `matchesSkinAngle`, native `snapshotRawSkinFrame`, otomatik dışlamalar ve `skin_models.photo_input` crop'u kullanıldı. Backend destekleri güncel `analyze_skin` prelude'undan aynen alınır; scale/origin ve 320 analiz ölçeği kopya bir formülle taklit edilmez. Native BGR 384 tile, 288 stride, objectness×class ≥0.30, ardından gerçek ürün Hard-NMS 0.30 ve staging anatomik filtre sırası sabit.

Eski 1/28 yerine **3/28** statik tam giriş uygundur. Poz reddi 23, BLURRY 10, NO_FACE 2; nedenler örtüşebilir. Uygun kaynaklar 26ebdde4, 2ed3716e (LEFT), f2ed24a9. Frontend ve backend gözlük kontrolleri bu üçünde CLEAR. Gerçek tarayıcı MediaPipe çalıştı; fiziksel kamera, zaman içindeki 900 ms kararlılık ve normal API'de aday aktivasyonu doğrulanmış değildir. Eşikler veri geçirmek için gevşetilmedi.

Scope B sabit 3 pozitif fotoğraf/14 kaynak hedefi +9 incelenmiş negatif fotoğraftır. Tam giriş kapısından 10 fotoğraf (3 pozitif+7 negatif) geçer; iki reddedilen negatifin FP'si 0 olduğundan burada toplam Scope B ve uygun alt kapsamın FP'si aynıdır. Pozitif fotoğrafta etiket dışı alan UNKNOWN; fazladan kutular otomatik FP sayılmaz. FP merkezi incelenmiş negatif destekte olan kutu ve kutu alanının ≥%80'i destekte olan kutu ayrı kaydedilir; bunlar piksel precision/Dice değildir.

## Aynı güncel kapsamda sonuç

AG eski giriş referansı Step0 5/14 FP2, IoU150 5/14 FP7, GIoU150 5/14 FP8 idi. Bunlar güncel ürün sonucu değildir. Mevcut tamamlanmış modeller yalnız çıkarım için yüklendi; IoU/GIoU pilotları tekrarlanmadı.

| Yöntem/model | Scope B kaynak yakalama | İncelenmiş negatif FP merkez / ≥%80 alan | Uygun 3 kontrol girdisi | 28 kontrol, yalnız dayanıklılık |
|---|---:|---:|---:|---:|
| step0 | 4/14 | 3 / 3 | 16/29 (3 fotoğraf) | 84/155 |
| control_iou | 3/14 | 9 / 9 | — | — |
| candidate_giou | 3/14 | 10 / 10 | — | — |
| control | 4/14 | 4 / 4 | 16/29 (3 fotoğraf) | 84/155 |
| hard-negative | 4/14 | 3 / 3 | 16/29 (3 fotoğraf) | 84/155 |

Eski IoU/GIoU ağırlıkları yalnız aynı Scope B ve TRAIN negatif tanı kaynaklarında tekrar çıkarıma alındı; 28 kontrol sütunları bu iki ağırlık için ölçülmedi (—). Yeni iki kol ve Step0 aynı 28 kontrolü kullanır. 28 kontrolün pozitif kısmi kutularında bağımsız incelenmiş temiz negatif paydası yoktur; buradaki FP=0 başarı/FPR iddiası değildir. 29 sabit kaynak hedefinin yalnız 16'sının merkezi seçili envelope içindedir; bu ikincil anatomik kapsam, 29 paydasının yerine geçirilmez. Step0 bu ikincil kapsamda 11/16 yakalar. Scope B'de de 14 sabit hedeften 6'sının merkezi güncel seçili envelope içindedir; bunların 3'ü eşleşir. 55d380f7 gerçek RIGHT girdisidir ve seçili yanak desteği eski anotasyon kapsamından farklıdır. Merkez-dışı hedeflerin tamamı hedef-dışı/sağlıklı diye yeniden etiketlenmez; bir eşleşme anatomik mesafe fallback'iyle kabul edilir. 4/14 bu nedenle tam güncel ROI doğruluğu diye sunulmaz, aynı sabit kaynak karşılaştırmasıdır. Kişi kimlikleri bilinmiyor; kaynak/family/decoded/yakın kopya ayrımı kayıtlıdır, kişi ayrımı kanıtlanmış sayılmaz. Scope B tekrar görülmüş geliştirme/regresyondur; final test yoktur.

| Yöntem/kapsam | Mikro <8 kaynak px | Küçük <16 px | Orta ≥16 px |
|---|---:|---:|---:|
| step0 / scopeB | 0/1 | 1/10 | 3/3 |
| step0 / heldoutStaticAdmissible | 0/3 | 14/17 | 2/9 |
| control / scopeB | 0/1 | 1/10 | 3/3 |
| control / heldoutStaticAdmissible | 0/3 | 14/17 | 2/9 |
| hard-negative / scopeB | 0/1 | 1/10 | 3/3 |
| hard-negative / heldoutStaticAdmissible | 0/3 | 14/17 | 2/9 |

Staging merkez-kıl desteği aynı 55d380f7 girdisinde eski filtrenin 1/7 eşleşmesini 2/7'ye çıkarır. Kaynak kutuları değişmeden kalır; göz/ağız delikleri, yoğun kıl ve görünmeyen bölge retleri korunur. Step0'nun güncel toplamı 4/14 FP3'tür; AG'nin 5/14 FP2'si zorla eşleştirilmedi. Sabit ≥0.30 güven/IoU≥0.50 kapsamında 14 hedefin yalnız 4'ü NMS öncesinde zaten eşleşen kutuya sahiptir; NMS ve staging bu dördünü korur. 695ed248'de 5 hedefin hiçbiri bu aşamada eşleşmez. Diğer on sabit kaynak hedefini filtreyi kapatarak kurtarmak mümkün değildir; ancak yukarıdaki ROI farkı nedeniyle bu onunu tek başına yeni algoritma hatası saymıyoruz. Bu kayıt tek başına düşük güven ile kutu yerelleştirme kaybını birbirinden ayırmaz ve mimari suçlaması değildir. Kaynak/tile/anchor/objectness/class/decode/NMS/ret nedenleri her fotoğrafın JSON'unda; `product-trace-*.png` görüntüleri gerçek snapshot ve destekleri gösterir.

## TRAIN'de kanıtlanan kök neden ve düzeltme

Özgün ledger'daki 834 Pimple kutusu korunur. 401 otomatik fotometrik pseudo-pozitif kaynak gerçeği değildir; 110 TRAIN fotoğrafında üretilmiş dış poligon delikleri/UNKNOWN alanı temiz gerçek yapamaz. Yeni iki kolda pseudo'lar pozitif değil UNKNOWN/güvenlik alanıdır. Ledger'da 19 açık negatif TRAIN fotoğrafı vardır; bunun 15'i pilot TRAIN grubundadır. Bu 15'in 9'unda gerçek ürün görünür alın/burun/yanak desteğiyle kesişen 393.788 native piksel vardır; çene/kıl, gözlük, delik ve kalite dışı alanlar UNKNOWN. Bu ortak kapsam daralması model kazanımı diye sunulmaz.

İncelenmiş temiz TRAIN alanlarında ≥0.30 ve ≥%80 destekli mevcut yanlış kutu bulunmadı; yoğun düşük skorlu arka plan anchor'ları zaten gradyan alıyor. Dolayısıyla bütün negatiflerin loss dışında kaldığı iddia edilmez ve kolay arka planı tekrar eğiten top-tail planları fit edilmedi.

Asıl somut çelişki: kaynak COCO'da Pimple olmayan nesnelerle çakışan 191 otomatik Pimple adayı/56 TRAIN kaynak bulundu. Bunların tümü negatif yapılmadı. Görsel olarak incelenen **5 kaynak-Mole nesnesi /4 TRAIN grubu** seçildi; belirsiz Post-acne ve çevre cilt UNKNOWN kaldı. Bu, klinik tanı veya sağlıklı cilt etiketi değildir. Üç nesnenin eski 150-adım dizisinde gerçekten pozitif Pimple hedefi aldığı; diğer ikisinin ilgili tile'ının hiç örneklenmediği kaynak koordinatlarıyla kanıtlandı. Step0 ham güvenleri 0.583–0.858.

İki yeni kol Step0'dan, aynı 600 native tile sırası, seed, AdamW 3e-5, warmup30/cosine150, microbatch1/accum4 ile 150'şer adım çalıştı. Her onuncu tile beş TRAIN hata konumunu döner; diğer 540 seeded özgün sıra. Geometri/sınıf/backbone/BN donuk; yalnız sekiz `head.obj_preds.*` tensoru açıktır. Tek fark adayın kaynak-Mole ile eşleşen decoded kutulara negatif objectness denetimidir. Atanmış pozitifler ve tüm özgün Pimple/diğer UNKNOWN pseudo +16 px koruması her zaman önceliklidir. Scope B veya 28 kontrol mining/fit girdisi değildir.

İki kolun girdi-sırası SHA'sı `2d0c2732a9649ef5a0fde30649c4b6ba32a6af18f955750a52b9b5307fd52515`. Donuk durum SHA'sı aynı ve değişmemiş; aday 909 ek negatif-anchor maruziyeti, kontrol 0. Her 25 adımda immutable model/optimizer-RNG/state kaydedildi. Her iki 150-adım CURRENT'ın tam bayt hash'leri doğrulandı; optimizer momentleri, scheduler ve torch/Python/NumPy RNG yeniden yüklendi.

| TRAIN kaynak / nesne | Step0 ham max güven | Eşlenik kontrol | Denetim onarımı | ≥0.30 anchor kontrol → aday |
|---|---:|---:|---:|---:|
| 349b1a1d / 6510 | 0.765798 | 0.769216 | 0.762346 | 13 → 13 |
| 349b1a1d / 6513 | 0.623781 | 0.630871 | 0.616856 | 7 → 7 |
| c41f8bfe / 12627 | 0.759345 | 0.761850 | 0.756849 | 11 → 11 |
| 690689ae / 21821 | 0.857741 | 0.859420 | 0.855879 | 15 → 15 |
| 91cb7dfe / 23600 | 0.583346 | 0.589764 | 0.576907 | 9 → 9 |

Bu tablo aynı sabit TRAIN tile'larını ölçer; anchor'lar mükerrer olabilir, benzersiz ürün FP'si veya validation kazanımı değildir. Beş incelenmiş nesnenin beşi de ≥0.30 aday üretmeye devam eder; eşleşen yüksek skorlu anchor sayısı 55 →55'tir. Maksimum güvenlerdeki küçük düşüş, bu yanlış nesnelerin temizlendiği anlamına gelmez. Kanıtlanan etiket çelişkisi düzeltildi, ancak 150-adımlık bu müdahale güçlü kaynak-negatif ayrıştırmasını sağlamadı.

## Karar ve korunmuş teslim

Aday önceden kaydedilmiş kabul koşullarını sağlamadı. Ürüne alınmadı; uzun eğitim gerekçelendirilmedi. Eşlenik kontrol → aday Scope B: 4/14 → 4/14, FP 4 → 3. Step0 FP 3 olduğundan adayın başlangıç modeline göre kazancı ayrıca değerlendirilir; yalnız kontrolü geçmesi yeterli değildir. Kaynak-hedef kayıpları/kazanımları sayıya ek olarak JSON'da kimlikleriyle hesaplanır. Confidence/NMS ayarı veya uzun yeni eğitim yok. Mikro/küçük lezyon kaçırmaları, bilinen negatiflerde yanlış adaylar ve kişi kimliği belirsizliği sürer; normal ürün sivilcesi kapalıdır. Native araştırma adayını normal API/ONNX/hash kabulü yapılmış gibi sunmuyoruz.

19 Python regresyonu +8 gerçek frontend poz assertion'ı geçti. Üretim `appearance_analysis`, `instant_appearance`, `product_dryness`, `skin_models`, model config ve BUILD_ID hash'leri değişmedi. Kuruluk/sarkma, diğer sağlık modülleri, sesler, tasarım ve kullanıcı kayıtları korunur. Üretim kodu değişmediğinden typecheck/build/kısayol kabulü yeniden ana iş yapılmadı. Tek ağır süreç ve iki atomik sahiplik kilidi kullanıldı; başka süreç durdurulmadı. RAM açılması sonrası çalışma tamamlandı.

Makine makbuzu: `docs/acne-takeover-evidence-20261015.json`. Native fotoğraflar/ağırlıklar Git'e eklenmedi; yerel `audit-results/acne-takeover-20261015` altında korunur. Yeniden çalışma sırası: `acne_product_preflight.py` → mevcut modellerin `evaluate_acne_current_product.py` karşılaştırması → TRAIN denetim/probe (görsel inceleme zorunlu) → yalnız boş kolda sınırlı pilot → `verify_acne_pilot_checkpoints.py` → iki yeni kolun evaluator/replay'i → `render_acne_product_trace.py` → `finalize_acne_takeover_evidence.py`. Tamamlanmış kolu yeniden başlatma script tarafından reddedilir. PR #2 Draft; main'e merge yok.
