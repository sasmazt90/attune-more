TOGG Attune — yedi hedef ara teslimi
Ölçüm: 2026-10-12T02:33:56.091820+02:00

Beş korunmuş tam checkpoint, tüm uygun development validation kayıtları üzerinde karşılaştırıldı. Eski completeROI filtresinin 241 karosuna karşı yeni kapsam 1019 karodur. Çakışan karolar kaynak koordinatında birleştirilir; sayılar kişi sayısı değildir. Pozitif ve negatif ROI aynı fotoğrafta ayrı olabilir.

| Hedef | Hazırlanmış eğitim foto P / incelenmiş N | Validation foto P / incelenmiş N | Etiketli alan recall | Negatif ROI FPR | Tam pozitif Dice | Aktif yöntem |
|---|---:|---:|---:|---:|---|---|
| acne | 112 / 8 | 28 / 2 | 99.688% | 50.275% | Ölçülemiyor: tam pozitif ROI incelemesi yok | Normal üründe kabul edilmiş detector yok; ACNE_MODEL_NOT_ACCEPTED |
| oil | 123 / 12 | 25 / 3 | 97.609% | 0.412% | Ölçülemiyor: tam pozitif ROI incelemesi yok | Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil |
| redness | 134 / 11 | 26 / 2 | 94.706% | 0.717% | Ölçülemiyor: tam pozitif ROI incelemesi yok | Genel Bakış: skin-appearance-photo-ridge-20261010-v1 / ordinal-0-5-times-20-v1; Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil |
| tone | 137 / 11 | 23 / 3 | 96.937% | 0.412% | Ölçülemiyor: tam pozitif ROI incelemesi yok | Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil |
| lines | 161 / 21 | 8 / 3 | 77.976% | 18.131% | Ölçülemiyor: tam pozitif ROI incelemesi yok | Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil |
| dark | 65 / 7 | 14 / 2 | 98.791% | 70.202% | Ölçülemiyor: tam pozitif ROI incelemesi yok | Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil |
| bags | 31 / 22 | 6 / 3 | 94.674% | 21.036% | Ölçülemiyor: tam pozitif ROI incelemesi yok | Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil |

| Hedef | Train pozitif / incelenmiş negatif native ROI | Validation pozitif / incelenmiş negatif native ROI | Kaynak aile kodları | Etiket görevi |
|---|---:|---:|---|---|
| acne | 743 / 68 | 178 / 10 | arnold, dc, face, old-eye, old-skin, skin5, v11, wrinkles | Kısmi kaynak poligon/RLE pozitif; yalnız incelenmiş bölgesel engineering negatif. Dışı bilinmeyen. |
| oil | 736 / 73 | 146 / 6 | arnold, old-eye, old-skin, v11 | Kısmi kaynak poligon/RLE pozitif; yalnız incelenmiş bölgesel engineering negatif. Dışı bilinmeyen. |
| redness | 872 / 45 | 180 / 4 | arnold, care, old-eye, old-skin, v11 | Kısmi kaynak poligon/RLE pozitif; yalnız incelenmiş bölgesel engineering negatif. Dışı bilinmeyen. |
| tone | 895 / 45 | 157 / 6 | arnold, care, old-eye, old-skin, skin5, v11 | Kısmi kaynak poligon/RLE pozitif; yalnız incelenmiş bölgesel engineering negatif. Dışı bilinmeyen. |
| lines | 461 / 77 | 41 / 13 | arnold, clean3, face, old-eye, old-skin, skin5, smart, wrinkles | Kısmi kaynak poligon/RLE pozitif; yalnız incelenmiş bölgesel engineering negatif. Dışı bilinmeyen. |
| dark | 307 / 19 | 48 / 8 | arnold, dc, old-skin, skin5, wrinkles | Kısmi kaynak poligon/RLE pozitif; yalnız incelenmiş bölgesel engineering negatif. Dışı bilinmeyen. |
| bags | 134 / 83 | 22 / 13 | arnold, clean3, dc, old-eye, old-skin, smart, v11 | Kısmi kaynak poligon/RLE pozitif; yalnız incelenmiş bölgesel engineering negatif. Dışı bilinmeyen. |
Bu native ROI sayıları çakışan eğitim karolarıdır; bağımsız kaynak değildir. YOLOX acne görevi ayrıca Pimple sınıfı kaynak kutusudur. Analitik karşılaştırmanın zayıf fotoğraf/engineering varlık etiketleri maskenin uzman piksel etiketi veya klinik derece sayılmaz.

Seçim beş eski TAM model ve tamamlanmış yeni validation checkpoint’lerini aynı sabit development kuralıyla karşılaştırır. En yeni model otomatik tercih edilmez.
| Hedef | Seçilen TAM model | Yeni faz son validation recall / negatif FPR |
|---|---|---|
| acne | negative-mask-continuation / checkpoint-0012043-01791750474685901500 | 99.979% / 100.000% |
| oil | negative-mask-continuation / checkpoint-0012043-01791750474685901500 | 99.944% / 14.137% |
| redness | negative-mask-continuation / checkpoint-0012043-01791750474685901500 | 99.484% / 16.477% |
| tone | negative-mask-continuation / checkpoint-0012043-01791750474685901500 | 99.845% / 9.962% |
| lines | negative-mask-continuation / checkpoint-0012043-01791750474685901500 | 36.775% / 0.000% |
| dark | negative-mask-continuation / checkpoint-0010621-01791745272486029600 | 100.000% / 100.000% |
| bags | corrected-scope-mask-v4 / checkpoint-0013465-01791761677808960300 | 47.587% / 2.332% |
Maske fazı iki validation sonunda tam checkpoint14176/epoch6/cursor0 ile doğal durdu. Yeniden başlatılmadı; ek tur yok. YOLOX fazı ayrı devam ediyor. Yeni maskeler ürün kabulünü sağlamadı.
Yeni fazın 2 validation sonucu var. Son yedi hedef ortak skor 0.486721; baseline en iyi TAM model ortak skor 0.607676. Torbalanma development adayı değişti; yeni checkpoint negatif FPR sınırını hâlâ geçiyor. Öğrenme eğrileri ayrı tutuldu.

Kutular piksel maskesi değildir. Kısmi poligon/RLE dışı bilinmeyendir; oralardan precision/Dice/FP üretilmez. Tablodaki yüksek pozitif recall, fazla boyanmış bir maskenin doğru lokalizasyonu olduğunu göstermez. Negatifler sadece gerçekten incelenmiş anatomik alt alanlardır; fotoğrafın bütünü sağlıklı sayılmaz. Final holdout açılmadı. Kaynak aile/split ve haklar için eksik bağımsız final incelemeleri True yapılmadı.

Doğrulanan düzeltmeler:
- Validation pozitiflerinin dışlanması giderildi; yedi hedefin tamamı dahil edildi. Eksik Dice artık sıfır değildir; pozitif + incelenmiş negatif kanıtı olmayan hedef sıralanmaz. Global skor hiçbir hedefi sessizce atlamaz.
- Genel filament dışlaması dark validation etiketlerinden 2792 ve bags validation etiketlerinden 292 pozitif karo pikselini kaldırmıştı. Orijinal etiketler yalnız anatomik cilt içinde geri kondu. Bunlar çakışan karolardaki sayılardır. Göz açıklığı, dudak, burun deliği, kaş ve gerçek saç bilinmeyen kalır.
- Eski negatif kapsamının tamamı doğrulanmış sayılmadı. Yeni v4 ledger yalnız gerçekten incelenmiş negatif destekleri kullanır; eski desteklerde bilinmeyen alanlar gradient üretmez. 8 veri kanalı → 7 model kanalı gerçek kaynak/tensor ve gradient üzerinde doğrulandı.
- KnownObjectnessBCE shape uyuşmazlığında sessiz BCE fallback yerine hata verir; atanmış pozitifleri ve bilinen negatif hücreleri korur. Gerçek YOLOX başlığında unknown gradient=0, pozitif/negatif gradient>0 doğrulandı.
- Üç adet 12 güncellemeli, seri küçük kontrol öğrenme başarısı kanıtlamadı: dark negatif FPR yaklaşık .960 → .980/.990/.991 oldu. Loss düşüşü ürün başarısı sayılmadı; yeni ana fazda orijinal balanced loss korunur.

YOLOX ve ürün zinciri:
- Korunmuş eski faz validation: 6 tur, F1 .075535, precision .041605, recall .409420; 113 etiket eşleşmesi, 2603 annotation-relative fazla aday, 163 kaçırma. En iyi eski development F1 .104099 (3. tur); son model yaşından dolayı tercih edilmedi.
- Bitmiş dört kaynak teşhisi: 228 kaynak adayı; 11 eşleşme, 1 duplicate, 6 incelenmiş negatif yanlış aday, 210 etiket/anatomik sınır kapsamı belirsiz aday; 21/32 etiket kaçırıldı. Beş yakın plan göz/kirpik/burun deliği/dudak/kıyafet yönünden görev dışı görüldü; belirsiz 210 adayın tamamı klinik yanlış veya eksik etiket sayılmadı.
- Native tensor/etiket, BGR, pad114, bounded regression, objectness×class, decode, source offset ve NMS zincirinde somut decode/koordinat/class mapping hatası bulunmadı. Ham ONNX regression strict toleransında bir değer başarısız; gerçek kaynak kutuları .000123 piksel içinde eşleşse de export geçer olarak sunulmadı.
- Ek önden hizalanmış kaynaktaki 5 etiket eşleşmesi normal ürün filtresinde 1 kaldı. İki kutu >%53/%58 clipped piksellerle elendi; iki kutunun mevcut bölgesel mesh kapsamı %36/%7 idi. Filtrenin tüm geçerli lezyonları koruduğu kanıtlanmadı. Bu adayın ürün kabulü bloke; canlı görüntü/grafik tasarımı ve AG uygulamaları değiştirilmedi.
- Kart değeri/sayı/model hash aynı saved product bounds ve alan oranından geliyor; confidence şiddet yüzdesi yapılmıyor. Adayın lokal harita ve fiziksel kamera/normal API teslimi henüz kanıtlanmış değildir.

Maske export ve kabul:
- Seçilen kanallar üç TAM modele aittir: acne/oil/redness/tone/lines epoch3; dark epoch1; bags ilk corrected-phase validation checkpoint13465 (önceki aday frozen parent epoch10). Encoder/head karışımı yok. Her hedefin full-model/channel, gerçek native RGB256/pad114/ImageNet normalize/no-resize ve ONNX/source-coordinate kanıtı hash bağlı selected-full-export-current.json üzerinden plan dosyasında bulunur. Değişmeyen export kanıtları tekrar inference yapılmadan hash/contract kontrolüyle kullanıldı; yeni bags TAM modeli iki gerçek kaynakta ayrıca doğrulandı.
- Tüm maskelerde tam pozitif ROI Dice/IoU eksik. Acne/lines/dark/bags negatif FPR de donmuş .05 kabul sınırını geçiyor. Oil/redness/tone düşük negatif FPR gösterse de tam lokalizasyon/final kanıtı olmadan üretime alınmıyor. Kabul eşikleri değişmedi.
- Development sıralaması, staging export doğrulaması ve kullanıcıya hazır teslim ayrı tutuldu. Hiç yeni aday normal API’ye yüklenmedi; bu yüzden yeni aday için normal API/build/kısayol kabulü yapılmış gösterilmiyor.

Mevcut appearance-cv-6:
| Hedef | Ölçülebilen P/N foto | P/N median | Rank AUC | Sınır |
|---|---:|---:|---:|---|
| oil | 2/17 | 0.0 / 0.0 | 0.4117647058823529 | Visible specular area requires baseline oil response and local top-hat/shine support; zero does not prove no oil. Capture/exposure gates and photo-class vs regional highlight mismatch remain. |
| redness | 5/6 | 5.189444065093994 / 4.226536750793457 | 0.7666666666666667 | Lab red excess has a small development separation signal; warm light/pigment and capture gates remain confounders. |
| tone | 6/4 | 4.064942836761475 / 4.302836298942566 | 0.5416666666666666 | Lab deviation from local median cancels homogeneous colour casts; it measures local photographic variation, not source class or a clinical tone grade. |
| lines | 11/20 | 1.3292689323425293 / 0.0049364116275683045 | 0.8636363636363636 | Outer-canthus directional Gabor/local detail bands differ from whole-photo wrinkle labels; source-detail and glare gates exclude many photos. |
| dark | 16/2 | 20.065933227539062 / 18.874140739440918 | 0.5625 | Narrow lower-lid relative contrast vs adjacent skin; two measurable negative photos cannot establish broad specificity. |
| bags | 0/11 | None / 0.0 | None | Local fold/edge/paired-contour support is not a photo bag class; all six positive source photos were unavailable, so positive performance is unmeasured. |

Kalite kapıları/fotoğraf başına ölçülememe sebepleri analytic-scope-assessment.json içinde gerçek receipt satırlarından çıkarıldı. Ölçülemeyen bazı redness/lines/bags satırlarında limitationCode kayıtlı değil; bunların nedenleri bilinmiyor, tahmin edilmedi. Bags 0 pozitif ile başarılı sayılmadı; oil/tone ayrışması zayıf; dark yalnız 2 negatif; lines/redness küçük development sinyali bağımsız doğrulama değildir. Görünüm indeksi klinik derece değildir.

Devam ve depolama:
- Mask checkpoint-0013045-01791755252897174600: epoch4/cursor291 → corrected-scope-mask-v4; YOLOX checkpoint-0008716-01791755253264409500: epoch6/cursor8 → corrected-scope-yolox-v2. Model, tüm optimizer tensorları/scalar/param groups, Torch/NumPy/Python RNG, scheduler ve kalan order/cursor birebir doğrulandı. İlk gerçek gradient güncellemeleri kaydedildi; eski fazların pause marker’ları korunur.
- Kör min12/max20 kuralı kaldırıldı. Önce kalan sıra, sonra yeni negatif havuzlu bir tam sıra; en fazla iki validation sonucu. Sonuçta doğal sınırda review gerekir. Miras cosine T_max=32, last_epoch mask16/YOLOX18; ufuk sonrası LR artışı bloke.
- Önceki gerçek epoch süreleri CPU/yük durumuna göre mask40–58 dakika ve YOLOX41–99 dakika değişti. Yeni mask validation kapsamı daha büyük; maske tamamlandığında kalan maske eğitimi 0 olur; YOLOX’ın kalan süresi gerçek cursor ve sonraki validation’a bağlıdır, teslim taahhüdü değildir. Dört saatlik invocation sonlanırsa tüm checkpoint ile devam edilir.
- Düzeltme fazı başlangıcı: 8.26 GiB. Güncel C: 6.173 GiB. Arşiv penceresi: 5.466 → 5.602 GiB, gerçek +146075648 bayt. Toplam alan azalması yeni tensor/export/checkpoint’ler ve Windows paging ile birlikte ölçülür; upload boyutu boş alan diye sayılmaz.
- Kalan rolling peak hesabı 4.415 GiB; ölçüm anında yeterli. Yalnız C: çalışma diski. Drive streaming; cache C: üzerinde 4 dosya/45112 bayt. Ek fiziksel disk yok. 60 saniye disk gözetimi, <3GiB iki native güvenli pause, resume için >=6GiB ve doğrulanmış sahiplik/CURRENT gerekir.
- checkpoint0011332: üç cloud dosyanın tüm bayt SHA-256’ları doğrulandı, yalnız soğuk tensorları kaldırıldı; state ve makbuz yerel. checkpoint0012387: model kopyası var, optimizer aktarımı başarısız; tüm yerel kaynaklar korundu ve otomatik retry listesi dışında. checkpoint8546: üç yükleme var, optimizer doğrulama stdout kaydı eksik; tüm yerel kaynaklar ve otomatik tekrar engeli korunur. Ek cloud-archive.json yükleme otomatik incelemede kapsam dışı metadata/yerel yollar nedeniyle reddedildi; makbuz yerelde.

AG devir notu: type/dry/sag teslim edilmiş sayılmadı ve onların worktree dosyaları değiştirilmedi. Native 256 maske helper eski 128 eye-ROI adaptörüyle aynı sözleşme değildir. AG normal API method/hash, kalite/visibility, bölgesel scope ve render-gate kanıtını kendi adayları için sağlamalı; appearance alanı confidence/clinical severity olarak adlandırılmamalı.

Üretim manifest/model hash’leri değişmedi; mevcut build sUqjoY1oyQXF6lvSRvtff. Kısayol dosyası korundu; bu turda yeni adayla launcher/API testi yapılmış değil. On yedi odaklı regresyon ve gerçek tensor/source kontrolleri uygulandı; ilgisiz genel test kampanyası yapılmadı.

Ayrıntılı, hash bağlı yerel JSON kanıtı: seven-target-delivery.json; source seçimleri, scope-v2/v4, actual-loss-v2, finite-learning-v2, selected-full-export-v4, product-filter-label-retention, product-box-support-attribution, corrected-resume-integrity ve runtime arşiv makbuzları.

Düzeltilmiş YOLOX fazının güncel ayrı sonucu:
- 1 validation: precision 0.022956, recall 0.445652, F1 0.043663; 123 kaynak etiketi eşleşmesi, 5235 annotation-relative fazla aday, 153 kaçırma; 43 fotoğraf/43 kaynak grubu. Threshold 0.7 development üzerinde önceden sabit; final açılmadı. Etiketsiz alan sağlıklı negatif sayılmıyor.
- Bu sonuç eski korunmuş fazın eğrisine karıştırılmadı ve eski en iyi F1 .104099’dan daha iyi değil. Maske fazı tamamlandı; YOLOX yalnız kendi sonlu ikinci validation sırasını tamamlıyor. Ek üçüncü tur yok.
