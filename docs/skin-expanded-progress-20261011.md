# Genişletilmiş cilt çalışması ve ayrı kabul aşamaları — 2026-10-11

Bu, 2026-10-11T12:45:36.341001+00:00 anındaki ara teslimdir. **On kriter birlikte teste hazır değildir.**
Çalışan YOLOX/U-Net koşuları iptal edilmedi veya yeniden başlatılmadı; checkpoint,
optimizer, scheduler, RNG ve kalan örnek sırası korunuyor. Kapsam yalnız rapor veya
UI düzenlemesi değildir: kaynak havuzları, gerçek özellik/decoder öğrenmesi,
doğal negatifler, sürümlü yerel ölçüm ve normal başlatıcı/API/harita zinciri işlendi.
Zayıf adaylar mevcut kabul edilmiş modeli değiştirmedi. Tasarım/kaynak renkleri,
kullanıcı kayıtları ve diğer sağlık modülleri korunuyor.

P/N = pozitif/bağımsız negatif fotoğraf. ROI sayısı fotoğraf sayısı değildir.
`≥` yalnız checkpoint örnek sıralarıyla kanıtlanabilen tüketilmiş alt sınırdır.
Hazırlanmış havuz sayısı gerçek eğitim kapsamının yerine yazılmamıştır.

| Kriter | Veri/etiket türü | Gerçek eğitim P/N fotoğraf ve ROI | Eğitim | Tespit/yerelleştirme | Görünüm ölçeği/kalibrasyon | Ürün entegrasyonu / aktif yöntem | Kalan somut iş |
|---|---|---|---|---|---|---|---|
| Cilt tipi | 4 kaynak sınıfı; gerçek RGB | 879 eğitim/187 doğrulama foto; P/N uygulanmaz | 22 epoch tamamlandı | Macro-F1 0.329, sınıflar başarısız | Şiddet/grade uygulanmaz | Aday aktif değil; tip unavailable | Sınıf anlamı/genelleme ve kullanılmamış dört-sınıflı final |
| Sivilce | Aktif lezyon kutuları + ayrı gerçek maskeler | D:113/11 foto,645/68 ROI; M:≥111/13 foto; ≥374/128 ROI | YOLOX ve U-Net sürüyor | P .212/R .152/F1 .177/AP50 .099; maske pozitif-val Dice N/A, FPR .403 | Odak/alan ölçeği bekliyor; confidence şiddet değil | Adaylar aktif değil; unavailable | Kaçırılan lezyonlar, doğal FP, pozitif tam ROI ve yeni negatif faz |
| Yağlı görünüm | Oily poligon/RLE; doğal parlama kontrolleri | ≥123/2 foto; ≥402/16 ROI | U-Net sürüyor | Maske başarısız: Dice 0.157; FPR 0.699 | Doğal AUC 0.412; başarısız ayrım | Mevcut yerel parlama CV geçti; yeni maske kabul edilmedi | Doğal parlama/ürün/ışık ayrımı; +6 negatif foto fazı |
| Görünür kuruluk | PUL kutusu: zayıf ROI presence; flake CV | 21/47 foto; 38/71 ROI | 32 eski +14 yeni epoch tamamlandı | Presence F1 .769/R .714/FPR .0526: başarısız | Grade uygulanmaz; doğal uygun pozitif flake CV kontrolü eksik | Mevcut flake CV ürün zinciri geçti; CNN aktif değil | İşlenmiş PUL pozitiflerin kaynak karıştırıcısı ve doğal uygun pozitifler |
| Kızarıklık | Redness maskeleri; ayrı mevcut fotoğraf derecesi | ≥134/1 foto; ≥436/14 ROI | U-Net sürüyor | Maske başarısız: Dice 0.388; FPR 0.618 | Doğal AUC 0.767; kabul bekliyor | Mevcut kabul edilmiş global derece + bölgesel renk CV geçti; yeni maske yok | Negatif FP, doğal ışık/ten tonu kontrolleri; global dereceden piksel şiddeti üretme |
| Ton eşitsizliği | Uneven/pigment maskeleri + yerel renk | ≥137/1 foto; ≥417/9 ROI | U-Net sürüyor | Maske başarısız: Dice N/A; FPR 0.555; pozitif tam-val ROI yok | Doğal AUC 0.542; başarısız ayrım | Mevcut yerel renk CV geçti; yeni maske yok | Uygun pozitif/negatif ROI ve ışık/makyaj ayrımı; kötüleşen alternatif kurulmadı |
| Kaz ayakları | Gerçek çizgi maskeleri + dış göz köşesi sinyali | ≥160/12 foto; ≥318/58 ROI | U-Net sürüyor | Maske başarısız: Dice 0.239; FPR 0.807 | Doğal AUC 0.864; kabul bekliyor | Göz başına yerel kalite ve harita zinciri geçti; maske yok | İfade/poz karıştırıcıları; +21 eğitim/+3 val negatif foto fazı |
| Göz altı morluğu | Dark-circle maskeleri + aynı göze komşu renk | ≥65/1 foto; ≥190/3 ROI | U-Net sürüyor | Maske başarısız: Dice 0.339; FPR 0.814 | Doğal AUC 0.562; kabul bekliyor | Göz başına yerel kalite ve harita zinciri geçti; maske yok | Yalnız 2 uygun doğal negatif kontrol; geniş negatif/ışık kapsamı |
| Göz altı torbalanma | Gerçek bag maskeleri + lokal kontur/kıvrım | ≥31/11 foto; ≥87/59 ROI | U-Net sürüyor | Maske başarısız: Dice 0.802; FPR 0.319; Dice geçer, FPR geçmez | Kontur v4: doğal uygun pozitif 0; ölçek bekliyor | Mevcut hedef ROI/unknown/harita zinciri geçti; maske yok | Normal kapak/gölge FP; +22 eğitim/+3 val negatif foto; uygun doğal pozitifler |
| Sarkma | Anlık geometri + gerçek alt yüz kontur/kıvrımı | ML eğitimi yok; 2 P/8 N doğal kontrol, uygun 2/5 | Analitik kontroller tamam; kabul açık | Pixel mask/Dice/grade uygulanmaz; alt sağ ROI geçerli ölçülüyor | v5: P indeksleri .2145/0; negatif medyan0; kabul bekliyor | Kendi ROI kalite, kısmi kapsam ve normal ürün zinciri geçti | İkinci pozitif zayıf; daha geniş doğal poz/ifade/gölge kontrolleri |

## Kabul sözleşmesi

`skin-label-function-20261011-v2` tespit/presence, lokalizasyon, görünüm ölçeği,
eşleşmiş grade kalibrasyonu, bağımsız final, ONNX eşdeğerliği, ürün entegrasyonu
ve kullanıcı test hazırlığını ayrı tutar. Başarısız metrikler ve eksik işler ayrı
`failures`/`pending` listeleridir; uygulanmayan aşama `not_applicable` olur.
`selected-acceptance.json` sayısal eşikleri değişmedi: TYPE macro-F1 .60,
minimum sınıf F1 .40; box P/R/F1 .60/.40/.50; mask Dice/IoU .65/.50 ve FPR .05.
Yeni presence aşaması doğal P/R/F1 .80 ve FPR .05 sınırlarını kullanır.

MAE/minimum eşleşmiş 0–5 grade yalnız gerçek eşleşmiş dereceleri olan ve derece
tahmini sunan yönteme uygulanır. Kutu, poligon/RLE, presence ve analitik indekse
olmayan grade yüklenmez. Bags Dice .802/IoU .674 geçer; FPR .319 lokalizasyonu
reddeder. Red/tone/acne/dark/lines/oil hataları da kendi metrikleriyle kaydedilir.
Tone/acne tam-val pozitif kapsamı eksik olduğunda Dice sıfır yapılmaz. Küçük
val kapsamı bir mimarinin kesin başarısızlığı veya geniş doğruluk iddiası değildir.

İlk protokol dondurması ve ek wire-state/mevcut sabit indeks dondurması final
pikselleri açılmadan alındı. Görülmüş geliştirme/test örnekleri final sayılmaz.
`require_promotion` gerçek gerekli veri/metrik/export/ürün aşamalarından karar
verir; `accepted=false` sabiti karar mekanizması değildir. Alan veya eğitim
bitişi de kabul yerine geçmez. Yeni adaylar henüz bütün uygulanabilir aşamaları
geçmediği için ürüne kurulmadı; mevcut kabul edilmiş Redness ONNX gerçekten
yüklendi. Kabul edilmiş model hatasında sonuç unavailable olur, eski vekile
sessiz düşülmez.

Güncel indeks anlamları ve gerçek lokal degrade sözleşmesi
[skin-appearance-indices-20261011.md](skin-appearance-indices-20261011.md) içinde.
Farklı kriterlerin sayıları ortak fiziksel yüzde değildir. Binary maske/kutu
lokalizasyon desteği şiddet haritası yapılmaz; model güveni, sigmoid veya
Grad-CAM şiddet değildir. Eski kayıtlar yeni formülle yeniden etiketlenmedi.

## Veri envanteri ve kapsam

Master havuz 26,722 kaynak fotoğraf ve 11,260 fotoğraf/export grubu içerir;
bunlar farklı kişiler değildir. On bir izinli yerel arşiv kullanıldı; yeni
indirme, kullanıcı fotoğrafı eğitimi, ücretli GPU/cloud veya yasak veri eklenmedi.
SHA/decoded-pixel/export ilişkileri korundu; 272 split-aşan yakın ilişki karantinaya
alındı. Kaynakların kutu, gerçek maske, presence ve varsa grade türleri ayrı.
CSV sıfırları pixel negatif değildir; anotasyonsuz kısmi alan unknown'dur.
Fotoğraf bazlı hak belirsizliği, düşük detay ve eksik inceleme ayrı nedenlerdir.
Yayıncı lisans beyanı bireysel stok hakkını otomatik doğrulamaz.

Aşağıdaki kaynak havuzları birbiriyle örtüşür. `Hazır` hedef-kaynak mühendislik
incelemesi içindir; model kabulü veya eğitime tüketilme değildir. Yeni negatif
fazların hazırlık sayıları ayrı tutulur. Kaynak/split/etiket geometrisi ve neden
ayrıntıları [sayısal snapshot](skin-expanded-progress-20261011.json) içindedir.

| Kriter | İlişkili kaynak fotoğraf | Hedef anotasyon | Fotoğraf/export grubu | İlk pozitif/kaynak incelemesi hazır | Bekleyen | Hariç |
|---|---:|---:|---:|---:|---:|---:|
| Cilt tipi | 4093 | 0 | 1618 | 1066 | 1645 | 1382 |
| Sivilce | 11423 | 43379 | 6377 | 418 | 10784 | 221 |
| Yağlı görünüm | 10050 | 2160 | 3893 | 154 | 9730 | 166 |
| Görünür kuruluk | 12470 | 4111 | 4996 | 49 | 12326 | 95 |
| Kızarıklık | 8604 | 1634 | 4146 | 171 | 8274 | 159 |
| Ton eşitsizliği | 6739 | 4647 | 3402 | 175 | 6438 | 126 |
| Kaz ayakları | 8209 | 11884 | 3016 | 166 | 8033 | 10 |
| Göz altı morluğu | 2108 | 730 | 2013 | 89 | 2009 | 10 |
| Göz altı torbalanma | 6689 | 2875 | 4379 | 43 | 6511 | 135 |
| Sarkma | 17461 | 0 | 7444 | 0 | 17290 | 171 |

Initial/supplement görsel kararları kaynak hash'lerine bağlıdır; uzman veya
klinik doğruluk diye sunulmaz. 2,034 ana +732 ek adayın incelemesi ve yeni120
negatif adayın on görsel panosu tamamlandı. Ticari/işlenmiş, kolaj, düşük detay,
hedef belirsizliği ve üçüncü taraf kaynak bildirimi ayrı gerekçelerle işlenir.

## Korunan gerçek eğitim ve yeni fazlar

TYPE üst EfficientNet-B0 blokları6/7/8 ve sınıflayıcı öğrendi; 22 epoch, seçilen14.
Özellik ağırlık değişimleri .0147–.0181 ve pozitif gradyanlar doğrulandı.
Val sınıf F1: normal .365, dry .397, oily .336, combination .216;
recall .388/.357/.333/.286. Val destek49/70/54/14, sınıf confusion matrix ve
879/187 kaynak sınıf dağılımı sayısal kanıtta. Eski açık test hariç. .329 kabul
mekanizması düzelince başarılı sayılmadı; source directory etiketi uzman gerçekliği
değildir.

U-Net native256 (batch2/CPU1), erken encoder sabit, üst encoder/decoder/7head
öğrenir; hedef/grup dengeli pozitif ve bilinen negatif kayıplar kullanır. Native
karo detayını korur, upsample ile detay icat etmez, unknown sıfır kayıptır.
YOLOX native384 (batch2/CPU2), üst backbone/neck/head öğrenir; unknown objectness
sağlıklı negatif sayılmaz. Adversarial/düşük-karıştırıcı fotoğraflar aynı kişinin
tekrar exportlarıyla bağımsız sayılamaz.

Mask: eski2 epoch, karışık destek geçiş epoch1, tam rafine destek epoch2+ ayrıdır.
YOLOX: eski decoder eğrisi, aynı seçilmiş ağırlığın bounded revalidation'ı,
sayısal geçiş epoch4, önceki destek epoch5, karışık destek epoch6, tam rafine
kapsam epoch7+ ayrı kaydedildi. Sayısal/destek geçişinde ağırlık, optimizer,
scheduler, RNG ve mevcut örnek sırası korunmuştur. Eski/yeni kapsam tek kesintisiz
başarı eğrisi yapılmaz. Başlangıçtaki train-only öğrenme karşılaştırması ve reset,
ara yönergeden önceki tarihsel ilk hazırlıktır; devam fazı başlangıcı değildir.

Kutu round-trip ve SimOTA ataması üzerinde gerçek audit: 45 assigned tahmin,
0 assigned saturation; 18,099 unassigned tahminin4,320'si doyar. .1–768 native
boyut sınırı exp öncesinde uygulanır. Train/validation/ONNX decoder aynı sınırı
kullanır; altı gerçek val karosunda ve izole gerçek `skin_models.infer_acne`
yolunda koordinat/preprocessing eşdeğerliği geçti. NaN kaybolması veya sonlu
gradyan tek başına lezyon başarısı sayılmadı. Seçili geliştirme box sonuçları
42TP/156FP/234FN, IoU .5 eşleştirme, AP50 .0986; yanlış aday/kaçırma sorunu açık.

Yeni doğal negatif havuz kaynak öğretici sınıf veya model tahmininden değil,
görülmüş kriter yokluğu ve uygun görünen anatomik ROI'den etiketlendi. Göz,
dudak, burun deliği, kaş, saç, görünmeyen/padding alanlar unknown. Native/geometri
filtresi sonrası38 farklı negatif fotoğraf hazırlandı. Önce devam eden invocation
kendi doğal dilimini bitirir, sonra saklanan sıranın kalan kısmı eski veriyle doğal
epoch sınırına tamamlanır; ardından ayrı sürümlü faz aynı checkpoint'ten açılır.
Supervisor hiçbir trainer'ı sonlandırmaz. Sonuç gözlemcisi bitişte güncel gerçek
kabul kararlarını hesaplar; otomatik model promotion yapmaz.

| Hedef | Yeni negatif eğitim foto/ROI | Yeni negatif val foto/ROI | Durum |
|---|---|---|---|
| Sivilce | 8/68 | 0/0 | Ayrı YOLOX/U-Net fazına hazır; bu snapshotta henüz tüketilmedi |
| Yağlı görünüm | 6/53 | 0/0 | Ayrı YOLOX/U-Net fazına hazır; bu snapshotta henüz tüketilmedi |
| Görünür kuruluk | 32/279 | 6/51 | Dry presence fazında gerçek fotoğraf/ROI olarak eğitildi; dry pixel head yok |
| Kızarıklık | 2/18 | 0/0 | Ayrı YOLOX/U-Net fazına hazır; bu snapshotta henüz tüketilmedi |
| Ton eşitsizliği | 2/18 | 0/0 | Ayrı YOLOX/U-Net fazına hazır; bu snapshotta henüz tüketilmedi |
| Kaz ayakları | 21/77 | 3/13 | Ayrı YOLOX/U-Net fazına hazır; bu snapshotta henüz tüketilmedi |
| Göz altı morluğu | 0/0 | 0/0 | Ayrı YOLOX/U-Net fazına hazır; bu snapshotta henüz tüketilmedi |
| Göz altı torbalanma | 22/83 | 3/13 | Ayrı YOLOX/U-Net fazına hazır; bu snapshotta henüz tüketilmedi |

Dry presence devamı aynı son checkpoint/AdamW/RNG ve orijinal cosine scheduler
state'inden14 epoch sürdü (32'den sonraki cosine artışı faz protokolünde açık).
21P/47N eğitim fotoğrafı,38P/71N gerçek tüketilmiş gray64 ROI; val7P/19N fotoğraf.
Yeni scope confusion [[18,1],[2,5]], FPR .05263, F1 .76923; hâlâ başarısız.
Üst/alt conv ve sınıflayıcı gerçek ağırlıkları değişti; tüm checkpointler korunur.
İşlenmiş PUL pozitif/kosmetik-coating karıştırıcısı açıktır; klinik moisture,
pixel mask veya severity üretilmez. Yeni negatif gerçek fotoğraflarla ONNX gray64
crop/padding/preprocessing/logit eşdeğerliği doğrulandı; normal API'ye kurulmadı.

Her yeni uzun faz en az12, en çok20 epoch ve patience8 kullanır. Kriterler aynı
epoch'un immutable ağırlık checkpoint'ini paylaşır; yedi tam model kopyası
üretilmez. Persistent checkpoint helper artık hiçbir geçmiş checkpoint'i prune
etmez. Resume testi optimizer + torch/python/numpy RNG ve bir sonraki update'i
bit düzeyinde eşdeğer doğrular. Ara yönerge anındaki dört tam işlem snapshot'ı
ayrı pinlendi; ilk çalışan sürümün iki kopyalı dakikalık işlem cache'i tarihsel
resume düzenidir, tüm geçmiş dakikalık snapshot'ların arşivlendiği iddia edilmez.
Yeni başlatılan faz/epoch sınırı çağrıları bu cache pruning yolunu kullanmaz.

## Doğal görünüm ve lokal uygunluk

120 gelişim fotoğrafında gerçek MediaPipe poz/geometri/kalite ve aynı giriş
tekrarı çalıştırıldı. Doğal örneklerle .85/1.10 yardımcı exposure kopyaları ayrı;
kopyalar yeni doğal etiket veya bağımsız başarı değildir. Kayıtlı katsayılar ve
kalite eşikleri örnekleri geçirmek için ayarlanmadı. İstatistik, geçerli lokal
indekslerin maksimumudur; görünmeyen tam yüz şiddeti değildir.

| Kriter | Uygun P/N foto | Uygunsuz/bilinmiyor P/N | P/N medyan | Rank AUC | Ölçek kabulü |
|---|---|---|---|---|---|
| Sivilce | 0/0 | 22/34 | N/A/N/A | N/A | Ayrı aşamada pending |
| Yağlı görünüm | 2/17 | 12/14 | 0.000/0.000 | 0.412 | Ayrı aşamada failed |
| Görünür kuruluk | 0/24 | 0/48 | N/A/0.000 | N/A | Ayrı aşamada pending |
| Kızarıklık | 5/6 | 9/12 | 5.189/4.227 | 0.767 | Ayrı aşamada pending |
| Ton eşitsizliği | 6/4 | 19/1 | 4.065/4.303 | 0.542 | Ayrı aşamada failed |
| Kaz ayakları | 11/20 | 7/22 | 1.329/0.005 | 0.864 | Ayrı aşamada pending |
| Göz altı morluğu | 16/2 | 4/0 | 20.066/18.874 | 0.562 | Ayrı aşamada pending |
| Göz altı torbalanma | 0/11 | 6/30 | N/A/0.000 | N/A | Ayrı aşamada pending |

SAG10 doğal kontrol ayrıca:2P/8N içinden2P/5N ölçülebilir. Kendi alt yüz ROI'si
üzerinden exposure/plane fit yapılır; başka bölgedeki parlama engellemez. Geçerli
tek alt yüz parçası sonucu destekleyebilir; üç bölgenin hepsi şart değildir.
Kavisli anatomik kılavuz tracking noise'dan çıkarıldı,2.5 eşiği değişmedi. İlk
pozitif alt sağ kıvrım artık ölçülür: foto indeks .2145; ikinci uygun pozitif0.
Negatif medyan0, bir negatif .01235; bu küçük kontrol bir ölçek kabulü değildir.
Kısmi karşı taraf/örtülü alan null kalır. Genel kırışıklık/yaş/forehead brow fold
tek başına SAG değildir. İki tarafın güven veya ortalama fold/edge değerlerinden
yapay degrade üretilmez; aynı kaynak noktasındaki gerçek joint destek kullanılır.

## Kullanılmamış final veri hazırlığı

Ayrı sealed görev631 fotoğraf/631 kaynak grubunu hazırladı. Önceki bütün ana,
ek, maske, detector, kontrol ve yeni negatif hazırlık havuzlarıyla SHA/decoded/
grup çakışması olmadığı tekrar doğrulandı. Eski açılmış testler ve cross-group
yakın ilişkiler finalden dışarıda. Kutu/poligon/RLE/CSVpresence indeksleri gerçek
source JSON/CSV/RLE'den materialize edildi; shape/positive pixels doğrulandı.
Fotoğraf pikseli veya model tahmini açılmadı; kutular dolgu maske yapılmadı,
CSV0 pixel negatif, absent severity de icat edilmiş grade yapılmadı.

**Metadata ve tipli etiket hazırlığı tamam; bağımsız performans kabulü tamam
 değildir.** Kör hedef/known-negative ROI kapsamı, bireysel haklar, doğal kamera
alanı ve kalan ilişki incelemesi açık. Fotoğraf/export grubu farklı kişi garantisi
değildir. Bu işler final aşamasında pending'dir, maskenin geliştirme metriğinde
başarısız grade diye kaydedilmez.

## Normal ürün ve doğrulama

Normal `TOGG Başlat.lnk` mevcut güncel build'i açtı. BUILD_ID
`sUqjoY1oyQXF6lvSRvtff`,212 frontend source hash'i ve15 gerçekten sunulan JS
chunk'ı eşleşti. Onaylanmış manifest SHA
`accc9ff193030bccde572ded39b1878fc7919e33daf62f2ac560c3357a83abfb` değişmedi.
Gerçek yüklenen mevcut Redness model SHA
`65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3` ile eşleşti.
Her kriterin gerçek method/model/hash/calibration/availability receipt'i API'de.

`product-ui-v4` PASS: gerçek lisanslı üç açılı video kamera fixture'ı, MediaPipe,
normal API, sonuç, altı source-mesh, lokal map, sayısal/fotoğraflı oturum geçmişi,
iptalden sonra bekletilmiş gerçek HTTP yanıtı ve gerçek yeniden tarama.
Pose/result mock veya quality override kullanılmadı. Dar pencere, desktop ve
Chrome gerçek200% zoom (inner641/outer1298/DPR3/CSSzoom1) doğrulandı.
Ayrı test profilleri kullanıldı; normal kullanıcı profili/kayıtlarına erişilmedi.
Kontrollü gerçek piksel fixture'ı fiziksel kullanıcı kamera kabulü değildir;
native OS pencere screenshot iddiası yoktur.

59 odaklı backend testi, ayrıca16 acceptance/checkpoint-resume testi geçti.
Önceki42 diğer sağlık/persistence/map-lifecycle regresyonu geçti; bu modüller
bu değişiklikte düzenlenmedi. Typecheck ve production build geçti. Python111
araştırma/backend dosyası compile edildi; son ek scriptler de kontrol edildi.
Kaynak diff-whitespace kontrolü geçti. TYPE, box-decoder ve dry presence gerçek
kaynak görüntüleriyle PyTorch/ONNX eşdeğerliği geçti; dosya/hash varlığı inference
başarısı yerine kullanılmadı. Mask export henüz kabul edilmiş aday yoktur.

## Kalan yerel hesap ve alan

Son tam CPU epoch'ları yaklaşık27–32 dakika; yeni12 epoch fazı yaklaşık5.5–6.5
saat,20 epoch üst sınırı9–11 saat/faz (eşzamanlı iki koşu) eder. Orijinal4 saatlik
invocation dilimleri en geç15:50 Berlin civarında doğal slice kaydeder; erken
plateau doğal bitiş olabilir. Eski sırayı bitirmek ek0–32 dakika gerektirebilir.

Boş C alanı ölçümde yaklaşık2 GB. Her YOLOX tam checkpoint~102 MiB, maske~139 MiB;
checkpoint'leri silmeden iki yeni12 epoch fazı için yaklaşık4 GB çalışma boşluğu,
20 epoch için yaklaşık6 GB gerekir. Dolayısıyla bu makinedeki mevcut alanın
iki minimum fazın tamamına yeteceği iddia edilmez.650 MiB rezervde gerçek son
checkpoint/order/RNG kaydedilip `RESOURCE_LIMIT_RESUMABLE` raporlanır; önceki
checkpoint veya kaynak veri silinmez. Ek yerel boş alanla aynı durumdan devam
edilebilir. Ücretli/cloud/GPU işlemi başlatılmadı.

Branch `fix/live-test-followup`; mevcut PR2 Draft kalır. Eğitim/veri/ONNX,
görseller, private payload ve runtime çıktıları ignored; yalnız kod, test,
sürüm sözleşmesi ve sanitised sayısal rapor Git'e alınır. Main merge yapılmaz.
