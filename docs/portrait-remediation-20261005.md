# Yerel portre düzeltmesi ve kontrollü kabul kapsamı

PR #2 Draft kalır; main'e merge yapılmaz. Eski commitler, kısayol, sayısal
cilt ROI/kalite/poz eşikleri ve exact Giuseppe/Ava profilleri korunur.
Yeni bulut görüntü servisi, yüz üretimi, kaynak renk düzeltmesi veya ücretli
OpenAI çağrısı yoktur.

## Gerçek 256 sınırı

Yerel TFLite dosyasının tensorları `[1,256,256,3]` → `[1,256,256,6]`.
MediaPipe API fotoğraf boyunda olasılık haritaları döndürebilir; bunlar yeni
segmentasyon ayrıntısı değildir. `compactSkinMask` bu yinelenen haritaları
256 semantik gride alır. Segmenter girdisi de doğrudan 256×256 model grididir;
SDK altı confidence haritasını gereksiz yere fotoğraf boyuna açmaz. Aynı
beş kare karşılaştırmasında category uyumu %98,84–99,38, probability ortalama
farkı 0,0038–0,0054 idi; bu doğruluk/ground truth iddiası değildir. Bağlantılı baş/saç alanı ve boşluk koruma bu gridde
hesaplanır; yalnız 851.968 bayt semantik veri aktarılır. Kamera bitmap'i ve
PNG kaynak çözünürlüğünde kalır.

`skinMatte.ts` bounded RGB guided filter katsayılarını en fazla 512 piksel
uzun kenarlı gridde hesaplar, **özgün çözünürlükteki RGB'de** değerlendirir.
Değişiklik semantik sınırın iki model hücresindeki belirsiz bandıyla sınırlıdır.
Kesin opak iç yüz ve göz/ağız boşluğu pikselleri opak kalır. Kaynak RGB'ye
yazılmaz. PNG canvas premultiplication nedeniyle kısmi alpha kenarında
yuvarlama olabilir; opak kaynak RGB birebir kontrol edilir.

Yöntem kendi uygulamamızdır; kopyalanmış üçüncü taraf kodu/ek npm paketi yok.
[Guided filter birincil kaynak](https://people.csail.mit.edu/kaiming/eccv10/index.html).
Semantik model 16.371.837 bayt, SHA256
`c6748b1253a99067ef71f7e26ca71096cd449baefa8f101900ea23016507e0e0`,
[Google model kartına göre Apache 2.0](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Multiclass%20Segmentation.pdf).

## Denenen alternatifler ve sınır

Yerel tanısal `skin_matte_comparison.py`, önceki **aynı kabul edilmiş** public
kareler üzerinde gerçek modeli çalıştırır: NASA dijital ve film ön pozları,
lisanslı videonun ön ve iki ayrı yan karesi. Çıktılar kullanıcı kabulü değildir.
Alpha ground truth yoktur; IoU veya saç doğruluğu yüzdesi üretilmez.

| Yöntem | Gözlenen sonuç | Üretim kararı |
|---|---|---|
| Eski bilinear 256 semantic alpha | Basamaklı saç sınırı, düz boyun altı | Önce kanıtı korunur |
| RGB guided refinement | Dijital saç sınırında kaynakla daha iyi hizalanma; film/video ince saç kaybı tamamen çözülmez | Seçildi |
| Yerel foreground/background renk örnekleme | Film ve düşük detaylı video kenarında gürültü ve delikler | Reddedildi |
| Resmî 512 saç segmenter + 256 yüz + guided | Dijital şakak çevresinde eksik kesim; video saç parçaları kaybolur | Reddedildi, ürüne eklenmedi |

512 saç modelinin gerçek dosyası 781.618 bayt, tensorları `[1,512,512,4]`
→ `[1,512,512,2]`, SHA256
`2628cf3ce5f695f604cbea2841e00befcaa3624bf80caf3664bef2656d59bf84`.
[Resmî model kartı Apache 2.0](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20-%20Hair%20Segmentation.pdf).
Yalnız yerel araştırma fixture'ında tutulur; görüntü gönderilmedi.

Guided alternatifin çalışma dizileri için konservatif ayırma üst sınırı
1920×2160'da 41.502.720 bayttır; bu model/WASM/bitmap/PNG veya toplam process
RSS değildir. Tanısal JS heap ayrıca kayıtlıdır ve çoklu karşılaştırma PNG'lerini
de içerir; üretim belleği diye sunulmaz. Süreler gerçek model yükleme, inference
ve refinement için ayrı kaydedilir. Eski yaklaşık 19 saniyeyle yeni, farklı
yükteki koşu karşılaştırılarak hız kazanımı iddia edilmez.

## Doğal yerleşim ve altı ağ

Yalnız mevcut maskenin desteklediği gerçek kısa boyun tutulur. Yüz altındaki
kaynak alanı, mevcut kadraja uyarlanan eğri bir alpha geçişiyle sonlanır; sert
yatay crop kaldırılır. Eğri fade, semantik güven eşiğinden sonra uygulanır;
eşik fade'in alt kısmını tekrar keskin bir kapağa dönüştüremez. Boyun/gövde yeniden üretilmez. Çok kısa kaynak kadrajı
uzun bir boyun portresine dönüşemez.

Alın üç komşu sıra, her yanak altı komşu sıra; çene dört yerel sıra kullanır.
Burun kanadı/çevre düğümleri genişletildi. İki göz bandı ayrı halkalarla genişler;
göz açıklığı/iris/burun üzerinden birbirine bağlanmaz. Saç ve desteklenmeyen
cilt yüzeyi üzerinde çizgi gösterilmez. Güvensiz göz, dudak ve burun deliği
kenarları ve düğüm dışı kesişimler elenir. Burun deliği açıklıkları, eski
küçük alt üçgen yerine gerçek kanat/columella çevresindeki altı landmark ile
dışlanır; karanlık açıklığın içinden çizgi geçirilmez. Yalnız seçili bölge render edilir.
Farklı yüzün referans kadınla aynı şeklini değil, görünür anatomi, komşu temiz
bağlantılar ve mevcut turkuaz çizgi/düğüm/diamond dilini doğrularız.

NASA fotoğrafları yalnız ön pozdur. Yanak kabulünün ayrı kanıtı, mevcut
gerçek üç poz video/MediaPipe akışıdır; public fixture kişisel kullanıcı veya
yüksek detaylı üç poz kabulü olarak sunulmaz.

## Bekleme ve iptal

MediaPipe task construction aynı worker'da sıralıdır; yüz modeli hazır olunca
segmentasyon kullanıcı konumlanırken ısınır. Worker başına tek başarılı
hazırlık promise'i saklanır; tekrar tarama başarılı modeli yeniden yüklemez.
Yükleme 30, inference 30 ve sonraki alpha/refinement aşaması ayrı 30 saniye
bounded bütçeler kullanır. Native yüksek detaylı karede sistem yükü altında
15 saniyelik inference sınırı portreyi düşürebildiği için inference bütçesi
30 saniyedir; bu bir hızlanma değildir. Son gerçek koşuda refinement 7,47 saniyede
çalıştı ancak client phase mesajından sonuç teslimine 15,63 saniye geçti; 15
saniyelik client sınırı tamamlanan portreyi düşürdü. Hazırlık/sonuç transferi
bütçeleri 30 saniyeye çıkarıldı; yüz hizalama sınırı 15 saniye kaldı. Bu hata
koşusu saklanır ve başarı ölçümü yerine kullanılmaz. Refinement ölçümü coarse alpha hesabını da içerir. Büyük confidence maskeleri
matting'den önce bırakılır; native boyda semantik flood/transfer kaldırıldı.

Model/inference/refinement aşaması, animasyon, gerçek aşama süresi ve tek/üç
pozda iptal görünürdür. Portre hazırlanırken geçerli kare yüzdesi gösterilmez.
İptal/izin/araç durumu geç kaydı engeller; hazırlık sırasında iptal edilen
bitmap, inference başlamadan kapanır. Gerçek worker koşusunda repaint ve
iptal sonrası kayıt/fotoğraf yazılmaması doğrulanır.

## Ses ve güvenlik açıkları

Giuseppe `it-IT-GiuseppeMultilingualNeural`, `+20%`, `-10Hz`; Ava
`en-US-AvaMultilingualNeural`, `+10%`, `+0Hz` değişmedi. Kurulu edge-tts 7.2.8
SSML kökünde en-US kullanır; desteklenmeyen language/custom SSML parametresi
eklenmez. [Upstream kısıtlar](https://github.com/rany2/edge-tts#custom-ssml).
Önceden izinli kişisel olmayan sabit MP3 örnekleri korundu. Bu düzeltmede yeni
provider çağrısı yoktur. İşitsel Türkçe aksan kabulü **OPEN**; playback/ended
bu kabul değildir.

`npm audit`: **7 high development / 0 production**. Etkilenen development
paketleri: @next/eslint-plugin-next, braces, chokidar, eslint-config-next,
fast-glob, micromatch, tailwindcss. Paket zinciri bu kapsamda değiştirilmedi;
güvenlik kapanmış ve genel CI yeşil sayılmaz. Ayrıntı mevcut dependency
advisory incelemesinde ve yeni audit JSON'undadır.

İnce saç/film halo sınırı ve işitsel aksan açıkken genel görsel/ürün kabulü
kapanmaz. Bilinen kusurlar kullanıcıya “iyi ışıkta tekrar tarayın” denerek
devredilmez. Exact commit/build, final ekranlar ve normal kısayol zinciri
yerel teslim raporunda ayrıca kaydedilir.

CI kamera tanısı sabit 500 ms yeniden çizim beklentisi yerine gerçek yüz/478
landmark algısından sonra bounded yeniden çizimi bekler. Kaynak uygulama
aynıdır; bu test değişikliği kabul edilmiş kare hazırlanırken kamera çiziminin
durmasını canlı preview donmasıyla karıştırmaz. Windows gerçek fixture
koşusunda çizimler 3 -> 4 olarak doğrulandı. Linux native ses adımları bu
yerel kamera doğrulamasında çalıştırılmış sayılmaz.
