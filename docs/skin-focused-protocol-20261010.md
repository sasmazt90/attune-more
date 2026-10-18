# Yerel cilt araştırması ve üretim sınırı

Bu dosya başlangıç protokolünü ve çıktının anlamını kaydeder. Nihai metrikler,
seçilen checkpoint/hash, model kabulü ve üretim build'i teslim raporundadır.
Model dosyası, küçük altkümede öğrenme veya HTTP başarısı analiz doğruluğu değildir.

## Veri ve haklar

İki kullanıcı arşivi SHA256 ile doğrulandı:

- `eye-training-v2.zip`: `03afd248006874f714a1b39210801be70918cf96e669084c5776a6590ca73f03`.
  Roboflow Skin Condition Detection_Merged v2, CC BY 4.0. Özgün README atfı,
  kutular, çokgenler ve değişiklik bildirimi ayrı manifestte korunur.
- `skin-18criteria-v1.zip`: `8f2bebd6b97bdd3acd06a42798babbd377b7937db362a734586ff5fb3d0ea4a1`.
  Killa92 facial-skin-analysis-and-type-classification; yayımcı Apache 2.0.
  4.093 sınıf fotoğrafı; yalnız 200 fotoğrafta 18 ek derece. Dereceler uzman
  protokolü veya anatomik/piksel etiketi olarak sunulmaz.

Fotoğraflar, kişisel belgeler, veri manifestlerinin görüntü/etiket satırları ve
başarısız araştırma ağırlıkları ignored dizinlerde kalır. Kullanıcının normal
fotoğrafı/geçmişi kullanılmadı. Notebook'lar kod incelemesidir; onların sonuçları
bu eğitimlerin başarısı olarak alınmadı. Bilinmeyen lisanslı notebook kodu kopyalanmadı.

Temizlik: gerçek yerel MediaPipe tek yüz ve görünür uç anatomiler; native yüz
genişliği/netlik; tam SHA, kaynak adı ve pHash türev grupları; sınıfı çatışan
ailelerin tamamının dışlanması; belirgin sentetik impuls bozulması ve örneklenen
stok/işlenmiş yüzlerin dışlanması. Görsel kontrol **örneklemdir**, bütün yüzlerin
makyajsız veya klinik olarak temiz olduğunun garantisi değildir. Bilinmeyen kişi
bağlantıları çıkarılamaz; bu ayrım kişi bazlı bağımsızlık diye adlandırılmaz.
Kaynakların 640×640 stretch hazırlanmış olması kamera görüntüsüyle alan farkıdır.

Donmuş validation hata sayfalarının gerçek görsel incelemesinde tip havuzunda
artık impuls bozulması, makyaj/işlenmiş doku ve metin kaldığı görüldü. Dolayısıyla
istenen tamamen temiz tip giriş koşulu **FAIL** olarak ayrıca kaydedildi. Bu
iki adayın protected test'i, her iki validation incelemesi hash'e bağlı olarak
tamamlanmadan açılmadı; açılmış test üzerinden yeni temizlik/eşik/eğitim seçimi
yapılmaz. Derece altkümesi ayrı validation + örneklenen train fotoğraflarıyla
incelendi; bu örneklem bütün korpus veya uzman etiketi onayı değildir.

Temiz tip ayrımı: train 1.802 / validation 367 / test 342. Derece ayrımı:
124 / 21 / 33. Konum korpusu: 1.292 / 236 / 251. Görev altkümeleri gerçek
görünür etiket/ROI sayısına göre protokol JSON'larında ayrıca tutulur. Derece test
kaynak grupları tip omurgasının train ve selection verisinden tamamen çıkarıldı.
Geçersiz `11` yalnız kendi derece hedefinde maskelenir. Q sütun farkı açık
eşlemedir; 18 etiketi olmayan fotoğrafa derece üretilmez.

## Sonlu eğitimler

- Tip: yalnız ResNet18 ve EfficientNet-B0. Aynı ayrım, native MediaPipe
  `camera-crop-v1`, RGB INTER_AREA224 ve ImageNet mean/std. Sınıf ağırlıklı CE;
  en fazla 5 frozen-head +20 upper-layer epoch, patience5, 3.600 saniye sınırı
  epoch başlangıcında. Devam eden epoch tamamlanır; sınır aşımı raporlanır.
  Batch16/AdamW, upper LR5e-5; renk/ayrıntı üretmeden yalnız train yatay flip.
  Seçim validation macro-F1, sıcaklık validation NLL, güven eşiği validation'da
  en az10 destek ve doğruluk>=0,70. Final hedef macro-F1>=0,60, her sınıf
  F1>=0,40, train sınıf-prior tahmininden iyi. Güven şiddet yüzdesi değildir.
- 18 derece: seçilen frozen görüntü özellikleri +hedef başına masked ridge;
  feature mean/std yalnız train. λ0,01/0,1/1/10 yalnız validation MAE ile seçilir.
  Train mean/median ve karşılaştırılabilir mevcut genel görünüm yöntemiyle
  karşılaştırılır. Validation/test en az10 geçerli hedef, iki sabit tahmini
  geçme, final MAE<=1. 0–5×20 sabit dönüşümdür; sınıf olasılığı değildir.
  Elasticity sarkma, dehydration biyolojik nem olmaz. Fotoğraf başlığı yerel
  maske üretmez. Sivilce derece başlığı kabul edilse bile validation'da
  desteklenmiş birleşim olmadan detector kutu-alan kartını değiştirmez.
- Sivilce: resmi detection-pretrained YOLOX-S, native384 BGR tile/stride288,
  padding114, kaynak kutuları ve NMS0,30. Aynı temiz ayrımda tespit ön eğitimli
  Faster R-CNN R50-FPN baseline. Küçük train-only80adım öğrenme kontrolünden
  sonra model yeniden başlatılır. YOLOX12/baseline6epoch, patience4/3.600sn;
  validation eşikleri0,10/0,25/0,40/0,55/0,70. Final F1>=0,50/P>=0,60/R>=0,40.
  Eksik anotasyonlu boş train tile sağlıklı negatif yapılmaz; değerlendirmede
  bütün tile'lar kullanılır. FP anotasyona göredir; klinik FP değildir.
- Torbalanma: SMP Unet ResNet18, MIT, aynı doğrulanmış resmi başlangıç omurgası;
  native alt-kapak ROI→RGB INTER_AREA128/IM normalization. Yalnız gerçek,
  dikdörtgen olmayan çokgenler ve iki kaynak-piksel sınır bandı denetimlidir.
  122 dikdörtgen/327 box-only örnek kesin maske sayılmaz. Bilinmeyen dış alan
  negatif etiketlenmez. 80adım öğrenme +yeniden başlangıç; en fazla15epoch,
  patience4/3.600sn, eşikler0,30/0,50/0,70; final Dice>=0,65/IoU>=0,50.
  Bu kısıtlı destek Dice'ı bütün göz-altı özgüllüğü değildir. Morluk/gölge/normal
  alt kapak bağımsız incelemesi geçmeden ürün maskesi kabul edilmez.
- Mevcut renk/yağlılık/pullanma/çizgi/morluk/torba filtrelerinin genel fotoğraf
  derecelerine train-only monoton kalibrasyonu validation'da seçildi; kabulü
  geçmeyen dönüşümler üretime bağlanmaz. Gölgeyi doku hacmi olarak yorumlama yoktur.

Seçim ve preprocessing dondurulmadan test okunmaz. Teste göre eşik değişimi veya
tekrar seçim yapılmaz. Checkpoint/protokol/seed/validation hataları korunur.
ONNX parity/gecikme başarılı olsa da başarısız hedef ürüne bağlanmaz.

## Üretim sözleşmesi

`appearance-cv-6`, ön poz `front-appearance-union-v1`, yeni yedi görünüm. Genel
ve bölgesel değerler, model confidence, geçerlilik, kaynak transform ve yerel
katman ayrı alanlardır. Alın/T-bölgesi union alanında bir kez sayılır; aynı poz
kutu adayları tek kimlikle tekrar sayılmaz. Yan poz sayıları ön pozla toplanmaz.
Eksik alan sıfırla doldurulmaz; tek küçük ROI tüm yüzü temsil etmez.

Sabit ölçekler: LAB Δab clamp0–100; kızarıklık lokal a* percentile25 üstü
deadband2×2; specular/uygun pullanma alanı yüzde; accepted sivilce kutularının
görünür kaynak-alan union yüzdesi; ayrı alt-kapak kontrast/dış-köşe Gabor;
kontur+fold için mevcut `instant-appearance-v2.md` sabitleri. Öğrenilmiş derece
varsa yalnız kabul edilmiş genel hedefe0–5×20. Bag maskesi olasılığı yoğunluk
değildir; eşiklenmiş görünür maskenin alanı ayrıdır. Ölçek kimlikleri ve artan
görünüm yönü her yeni ölçümde saklanır. Bar/yuvarlama yalnız sunumdur.

`skin_models.py` yalnız pinned accepted ONNX yükler. Torch/SMP/eğitim/download/
pickle üretim isteğinde yoktur. Hash, sınıf sırası ve preprocessing doğrulanır;
red edilen modelden skor, eski sonuç veya sağlıklı sıfır üretilmez. Genel ve
bölgesel dereceler aynı değer değildir. Skor/model/norm sürümü uyumsuz trendler
ayrıdır. Eski altı-bölge kayıtlarına Genel Bakış eklenmez.

Yerel harita gerçek piksel sinyali veya gerçek tahmin maskesidir; kutulardan
Gaussian/GradCAM şiddeti üretilmez. Kaynak fotoğraf değişmez. Harita kaynak ID,
poz, kriter, yöntem/hash ve koordinata bağlıdır; seçili anatomik mesh dışı,
göz/dudak/dışlama delikleri kırpılır. Torba konturu çalışmışken kullanılmamış
maske modelinin kimliği yazılmaz. Teknik ayrıntılar rapor/info alanında kalır.

## Provenans sınırları

R18 resmi torchvision ağırlığı f37072fd..., dağıtıcı `tv_in1k` BSD3 model kartı;
B0 resmi rwightman7f5810bc..., `ra_in1k` Apache2 model kartı. Kod/veri/başlangıç
ağırlığı koşulları ayrıdır; kesin256hash'ler pinned manifestte tutulur. YOLOX
Apache2 kod revizyonu6ddff4824372906469a7fae2dc3206c7aa4bbaee, resmi0.1.1rc0
COCO ağırlığı; kod koşulu bağımsız tıbbi veri hakkı gibi sunulmaz. Faster R-CNN
başlangıcı resmi D2 CC BY-SA3.0 uyarlamasıdır ve baseline araştırmada kalır.

Opsiyonel `Acnes_model.pth` SHA
aa18e19b1c76c33a2edc8c5a820497fe9ff4e023be88cabae83d1ce9e289da47:
whole-object pickle; repo Apache2 olması özgün eğitim verisi/weight provenansı
kanıtı değildir. Bu kaynak unsafe unpickle edilmedi, ağırlığı dönüştürülmedi ve
üretime eklenmedi. Ana YOLOX veya torbalanma eğitimi buna bağımlı değildir.

Kontrollü kamera/PCM/ASR fixture ve bağımsız doğal fotoğraf incelemesi, fiziksel
kullanıcı veya klinik kabul değildir. NASA ayrıntılı kaynaklar yalnız FRONT
kanıtıdır; video yan pozları üç ayrı yüksek detaylı portre diye sunulmaz.

## Validation görsel incelemesinin ek kabul kapısı

R18'in dondurulmuş validation hata sayfasında sayısal impulse eşiğini geçen
benek bozulması, makyaj/işleme ve metinli kaynaklar görüldü. İlk 96 örnekli
inceleme bütün 2.654 uygun fotoğrafın temizliğini kanıtlamadı. Bu kaynak kusuru
saklanmaz; aynı split üzerinde yeni temizleme/eşik/tekrar eğitim döngüsü
açılmaz. İki adayın validation görsel incelemesi korunmuş weight hash'ine
bağlanmadan korunan type test açılmaz. Model tipi terfisi, metrik eşiğine ek
olarak bu temiz-kaynak koşulunu gerektirir. Hata incelemesi final test sonucu
değiştirmek veya o test üzerinde seçim yapmak için kullanılmaz.

Derece altkümesinde 21 validation fotoğrafı ve seed ile seçilmiş 19 train
fotoğrafı ayrıca incelendi; korunan test görülmedi. Bu örneklerde yaygın
impulse bozulması görülmedi. Makyaj, el teması, ifade, yönlü ışık, stock ve
birkaç filigran kaynağı sınır olarak tutulur; kaynak etiketleri tanı sayılmaz.
Bu inceleme yalnız bütün-fotoğraf görünüm hedeflerinin sabit kabul protokolü
ile değerlendirilmesine izin verir; bütün altkümenin uzman doğrulaması değildir.
