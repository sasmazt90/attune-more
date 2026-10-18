# TOGG Attune: tamamlanan fazlar ve ürün entegrasyonu
Sonraki cilt tipi entegrasyonu ve güncel build durumu: [dört sınıflı hosted teslim](skin-type-integration-20261012.md). Aşağıdaki cilt tipi erişimi/build notları bu önceki teslimin tarihli durumudur; eğitim ve yedi hedefin değerlendirmeleri korunur.
Kanıt zamanı: 2026-10-12T04:39:36.905168+02:00

İki düzeltme fazı iki validation sonunda tamamlandı. Maske CURRENT14176/epoch6, YOLOX CURRENT9680/epoch8; optimizer/RNG/scheduler ve son checkpoint’ler C: üzerinde korundu. Kalan eğitim süresi 0; üçüncü validation/uzun eğitim yok. Ürün mühendisliği ve modellerin kabulü aşağıda ayrı gösterilir.

## Detector seçimi
Aynı development veri SHA/split, 43 fotoğraf/grup, IoU .5 ve önceden sabit confidence .7:

| Aday | Precision | Recall | F1 | TP / etikete göre eşleşmeyen / FN |
|---|---:|---:|---:|---:|
| negative-yolox / epoch3 | 0.0596 | 0.4094 | 0.1041 | 113 / 1782 / 163 |
| corrected-scope-yolox-v2 / epoch8 | 0.0331 | 0.4493 | 0.0617 | 124 / 3619 / 152 |

Yeni YOLOX ikinci validation P .0331 / R .4493 / F1 .0617. Korunmuş epoch3 / checkpoint7260 / F1 .1041 seçildi. Etikete göre eşleşmeyen kutuların tamamı klinik yanlış pozitif değildir; etiketsiz alan bilinmeyendir. Seçilen eski TAM ağırlığın gerçek dört kaynakta raw/native→ONNX→source/NMS paritesi geçti; bu teknik aktarım detector başarısı veya ürün kabulü değildir.

## Yedi ayrı hedef
Kısmi poligon/RLE pozitif recall ve gerçekten incelenmiş bölgesel negatif FPR ayrı ölçülür. Hiçbir hedefte tam etiketli pozitif ROI Dice/IoU yok; confidence/binary çıktı klinik şiddet değildir. Eğitim/validation kaynak grupları ayrıdır; bağımsız kişi sayısı iddiası yok.

| Hedef | Seçilen tam checkpoint / kanal | Pozitif lokal yakalama | İncelenmiş negatif FPR | Normal üründe aktif yöntem | Seçili maske aktif mi? | Kalan işlem |
|---|---|---:|---:|---|---|---|
| acne | checkpoint-0012043-01791750474685901500 / 0 | 99.69% | 50.27% | Normal üründe kabul edilmiş detector yok; ACNE_MODEL_NOT_ACCEPTED | Hayır | Detector specificity fails; blurred brow false candidate remains; no production activation |
| oil | checkpoint-0012043-01791750474685901500 / 1 | 97.61% | 0.41% | Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil | Hayır | Full localization/appearance specificity on unknown positive-photo areas and independent frozen acceptance remain; isolated staging complete |
| redness | checkpoint-0012043-01791750474685901500 / 2 | 94.71% | 0.72% | Genel Bakış: skin-appearance-photo-ridge-20261010-v1 / ordinal-0-5-times-20-v1; Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil | Hayır | Full localization/appearance specificity on unknown positive-photo areas and independent frozen acceptance remain; isolated staging complete |
| tone | checkpoint-0012043-01791750474685901500 / 3 | 96.94% | 0.41% | Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil | Hayır | Full localization/appearance specificity on unknown positive-photo areas and independent frozen acceptance remain; isolated staging complete |
| lines | checkpoint-0012043-01791750474685901500 / 4 | 77.98% | 18.13% | Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil | Hayır | Reviewed negative FPR fails; retain current appearance method |
| dark | checkpoint-0010621-01791745272486029600 / 5 | 98.79% | 70.20% | Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil | Hayır | Reviewed negative FPR fails; retain current appearance method |
| bags | checkpoint-0013465-01791761677808960300 / 6 | 94.67% | 21.04% | Bölgesel appearance-cv-6 görünüm indeksi; yeni maske değil | Hayır | Reviewed negative FPR fails; retain current appearance method |

| Hedef | Eğitim fotoğraf P / incelenmiş N | Development fotoğraf P / incelenmiş N | Eğitim native ROI P/N | Development native ROI P/N |
|---|---:|---:|---:|---:|
| acne | 112/8 | 28/2 | 743/68 | 178/10 |
| oil | 123/12 | 25/3 | 736/73 | 146/6 |
| redness | 134/11 | 26/2 | 872/45 | 180/4 |
| tone | 137/11 | 23/3 | 895/45 | 157/6 |
| lines | 161/21 | 8/3 | 461/77 | 41/13 |
| dark | 65/7 | 14/2 | 307/19 | 48/8 |
| bags | 31/22 | 6/3 | 134/83 | 22/13 |

Çakışan karolar bağımsız ROI/fotoğraf değildir; kaynak düzeyinde OR ile birleştirildi. Kutu, kısmi poligon ve zayıf fotoğraf etiketi ayrı görevlerdir. Maskelerin yeni son validation sonuçları ve korunmuş tam modeller aynı scope-v4 içinde karşılaştırıldı. Çizgi/torbalanmanın yeni son adayında boyama azalırken pozitif recall .368/.476’ya düştü; eski dengeli adaylar ve normal görünüm yöntemleri korundu. Torbalanmanın daha dengeli ilk corrected adayı da FPR .2104 nedeniyle etkin değil.

## İzole yağlılık/kızarıklık/ton staging
Gerçek ilgili development P/N fotoğrafları inference öncesinde SHA sırasıyla seçildi ve dosya/hash kaydı tutuldu. Native RGB256 / pad114 / ImageNet / resize yok / stride192 / TAM model ve kanal → ONNX → gerçek MediaPipe anatomik destek → bölgesel yoğunluk → Genel Bakış → gerçek SkinFacePanel ve SkinIndicatorValue bileşenlerinde seçili harita doğrulandı. Eski 128 eye-ROI adaptörü kullanılmadı. Normal API manifesti değiştirilmedi.

| Hedef | Görünür etiketli pozitif yakalama | Toplam etiketli / anatomide görünür pozitif piksel | İncelenmiş negatif FPR / destek |
|---|---:|---:|---:|
| oil | 99.97% | 15621 / 7348 | 0.00% / 3672 piksel |
| redness | 99.32% | 9868 / 2509 | 0.00% / 3672 piksel |
| tone | 100.00% | 8210 / 3447 | 0.00% / 3672 piksel |

Bu altı kontrol fotoğrafı geniş ürün özgüllüğü değildir; üç hedefin negatif kontrolü aynı kaynak fotoğrafından farklı hedef desteği kullanır. Pozitif fotoğrafların bilinmeyen bölgeleri negatif yapılmadı. Örneğin oil pozitif fotoğrafında Genel Bakış tahmini görünür alan yoğunluğu yaklaşık %92; etiket dışının doğru lokalizasyonu bilinmiyor. Lokal yakalama yüksek diye maskeler başarılı/klinik şiddet olarak sunulmadı. Ölçülemeyen bölgelerde skor/harita yok. Tam ROI Dice veya şiddet etiketi uydurulmadı. Native/source/raw teknik parite ve gerçek bileşenlerin hash bağlı browser kanıtı tamam; bağımsız kabul ve bilinmeyen alandaki yanlış boyama sınırı hâlâ açık.

## Sivilce filtresi ve kök neden kararı
Sunum üçgenlerinin boşlukları ölçüm desteği olarak kullanılıyordu; doygun tek renk kanalı tam renk kaybı sayılıyordu. Sivilceye özel anatomik envelope, tüm kanalların clipping kontrolü, açık göz/kaş/dudak/burun deliği/saç/arka plan dışlamaları ve tek sahipli son kutu listesi getirildi. Kaş landmark sırasının poligon konturu olmaması ayrıca dikkate alındı. Göz sınırı desteği alınırken gerçek alın lezyonlarına kaş çevresinde geniş margin uygulanmadı.
Gerçek kaynaklarda decoder eşleşmeleri 5→ürün1 iken şimdi 5→5, diğer kaynakta 4→2 iken 4→4. Kart, adet, işaretler, bölgesel ve Genel Bakış lokal haritası aynı son liste/benzersiz alan oranından türetilir. Confidence şiddet değildir. Beş incelenmiş görev dışı kutudan dört tanesi reddedildi; bulanık kaş sınırı kutusu hâlâ geçiyor. Bu açık specificity başarısızlığıdır; yeni veya eski zayıf detector etkinleştirilmedi.
Tamamlanmış teşhiste tensor/etiket/class mapping/objectness×class/decode/source transform/NMS temel hatası bulunmadı. 228 adayın 11 eşleşme, 1 duplicate, 6 incelenmiş negatif yanlış ve 210 bilinmeyen kapsam ayrımı korunur. Bu örneklerde bilinen yanlışlar göz/kirpik/nostril/dudak/kıyafet/normal doku yanıtlarıdır; bütün bilinmeyen alanlara sağlıklı etiketi verilemez. Kalan sivilce/morluk sorunu modelin gerçek etiket görevini ve doku/negatif ayrımını öğrenemediği ölçülebilir sonuçtur; mimariyi veya bütün veri setini suçlayan kanıt yok. Dark negatif FPR .702; yeni aday 1.0, üç kısa loss kontrolü de başarısız. Yeni model/mimari/veri denemesi veya aynı başarısız saatlerce eğitim önerilmedi/başlatılmadı.

## AG teslimi ve üretim
afad8f8 paketinin tamamı cherry-pick edilmedi. f4ded9f commit/diff ve güncel kanıt kod hash’leri doğrulandı. Yalnız altı değer döndüren ortak kuruluk fonksiyonu ve sürümlü alt yüz kontur/fold v6 görünüm indeksi bağımsız olarak ana checkout’a alındı; AG worktree değiştirilmedi. Gerçek üretim fonksiyonuyla odaklı yeniden ölçüm yapıldı. Cilt tipi adapter/config/modeli alınmadı; gerçek dış model erişimi bekliyor.
Kuruluk: 41 validation patch/26 grup (7P/19N), analitik CM [[17,2],[1,6]], F1 .80, recall .8571, FPR .1053. TextureNet CM [[18,1],[2,5]], F1 .7692, FPR .0526; model normal ürüne alınmadı. Merve pul kutusu zayıf doku varlığıdır; hidrasyon veya klinik kuruluk etiketi değildir. Rapor/JSON çelişkisi bu gerçek matrislerle ayrı açıklandı.
Sarkma: iki pozitif kontrolden yalnız biri nonzero; beş ölçülebilen negatif tam sayı barda 0, üç ifade confounder’ı ölçülmedi. Photo47 Genel Bakış 2.0612%, Photo57 etiket pozitif korunarak 0/partial; hâlâ kaçırma. Görselde alt yüz kıvrımları görülebiliyor, gölge/kısmi kapsam sonucu doğru-negatif sayılmaz. Bu görünüm indeksi klinik sarkma/elasticity başarısı değildir. Eski kayıtlar yeniden ölçeklenmedi; dry v2-shared ve sag v6 normalization sürümleri eski kayıtlarla doğrudan karşılaştırılmaz.

## Teslim ve depolama
Production build TStuRDUwonR8iNpes2955. Normal Windows kısayolu→sahipliği doğrulanmış API→gerçek fixture üç açı→sonuç/Genel Bakış+altı bölge/harita/geçmiş ve kaynak/build/servis/model hash zinciri geçti. Normal kullanıcı profili/kayıtları okunmadı/yazılmadı; ayrı test profilleri kullanıldı. Fiziksel kişisel kamera/ses kabulü iddia edilmedi. Doğal fotoğraf, arka plan, anatomik ağlar, lokal gradyen, tam sayı barlar ve onaylı ses dosyaları korunur. Otuz mevcut odaklı regresyon + üç yeni destek kontrolü, gerçek kaynak replay ve production build uygulandı; ilgisiz genel kampanya yok.
Normal manifest SHA256 accc9ff193030bccde572ded39b1878fc7919e33daf62f2ac560c3357a83abfb; kabul edilmiş eski global-redness model SHA256 65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3. Hiç yeni maske/detector normal modele aktarılmadı.
Bu teslim başlangıcı C: 6.662 GiB; rapor anı 6.055 GiB. Eğitim/veri/cache/korunmuş checkpoint ve üretim modeli C:. 9071 arşiv penceresi 6.322→6.422 GiB, gerçek +107130880 bayt. Model/optimizer/state üç dosyanın tüm bulut baytları SHA-256 doğrulandı; yalnız eski tensorlar kaldırıldı, state/dizin/makbuz yerel. Daha önce başarısız 12387/8546 kaynakları korunur. Drive çalışma diski yapılmadı; cache kazanımı varsayılmadı. Kalan eğitim/export yazımı yok; son doğrulama için 1GiB ek paging +2GiB güvenlik rezervi ölçüm anında yeterli.
Draft PR2 üzerinden commit/push; main merge yok. Eğitim tamamlandı; ürün mühendisliği çalışıyor; seçilen yeni öğrenilmiş adaylar ve dış erişim bekleyen cilt tipi henüz etkin değil. Başarısız model sonuçları ve Photo57 açık tutulur; klinik/user acceptance için hazır diye sunulmaz.

Seçilen gerçek epoch3 detector ağırlığı 1a014adad262… aynı iki development kaynağında ayrıca native ürün zincirinden geçirildi: 4/4 ve 4/4 eşleşme korundu. Önceki 5→1 teşhisi başka korunmuş diagnostic ağırlığın saved adaylarıdır; iki sonuç aynı modelmiş gibi birleştirilmedi. Seçilen detector’un gerçek kaynak fotoğrafı/son liste/model hash’iyle üretim SkinFacePanel/SkinIndicatorValue bileşenlerinde kart-adet-işaret-lokal harita eşitliği iki ayrı staging sayfasında browser üzerinde doğrulandı. Zayıf model normal API’ye kurulmadı.
