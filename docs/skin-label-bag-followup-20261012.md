# Türkçe etiket ve torbalanma desteği — 2026-10-12

Başlangıç: `32ac20e3b724202094a9b9934b69cb06b7abd268`, BUILD_ID `dxFr1OhOItAcorPw-G3Yp`. Önceki build ve kanıtlar saklandı. AG çalışma dosyaları okunup kopyalanmadı/değiştirilmedi; teslim edilmemiş çizgi v4 adayı entegre edilmedi.

## Etiket zinciri

Kaynak merkezi `skinCriterionLabel`/id sözlüğü doğru UTF-8; görünüm API’si sayısal ölçüm ve id taşıyor. Önceki **bize ait doğrulama profilindeki** `audit-v5-20031f35` kaydında bozuk dokuz Genel Bakış etiketi bulundu. Her biri doğru kaynak metnin UTF-8 byte’larının Windows CP1252 olarak okunmasıyla birebir eşleşiyor; kayıt zamanı kullanıcı ekranındaki 19:36:57 ile aynı UTC oturumunu gösteriyor. Önceki utility-fixture yükleyicisinin varsayılan dosya kodlaması bu bozuk stringleri kayıt üretimine taşıdı. JSON ve render bunları olduğu gibi korudu. Son göz çevresi kontrolü, eski Genel Bakış kaydının doğruluğunu kanıtlamıyordu.

Bilinen id için görüntüleme adaptörü, hem yeni sonuç hem geçmişte merkezi etiketi kullanır. `sag` ve `dry` Genel Bakış isimleri ayrıca korunur. Eski record/score/unit/fotoğraf yeniden yazılmaz. Bilinmeyen id metni aynen kalır; bütün metinlere Latin-1/UTF-8 çevrimi yok. Fixture kaynakları açık UTF-8 okunur/yazılır. CP1252 bozma yalnız izole eski-label test senaryosunun alanlarında uygulanır.

Gerçek normal build/kamera fixture/MediaPipe/API sonucunda; yeni sonuç, yeni geçmiş, doğru eski ve bozuk eski geçmiş için 28 görünüm ve 168 bağımsız Türkçe etiket karşılaştırması geçti. Genel Bakış+altı bölge her senaryoda gezildi. Ham test geçmişi yeniden açılışta byte olarak aynı. Dar pencere ve gerçek Chrome %200 geçti; CSS zoom=1, DPR=3, innerWidth641/outerWidth1298. Doğal fotoğraf, yakın kadraj, ağ çizgileri, font/boyut ve tasarım korunuyor. İzole kamera aygıtına kullanım hakkı bilinen gerçek 20031f35 fotoğrafının YUV video fixture’ı verildi; poz/kalite/MediaPipe çıktısı ve API cevabı değiştirilmedi.

## Torbalanma desteğinin somut hatası

Göz ağı kapalı anatomik dörtgen hücrelere sahip fakat görünür diyagonal her hücrede çizilmiyor. Eski triangle-union yalnız üç kenarı çizilmiş üçgenleri ölçüyordu: 20031f35’te sekiz kapalı hücrenin 2.896 analiz pikseli gereksiz boştu. Gerçek fold merkezleri bu boşluklarda eleniyor, continuity sağda .15625 ve solda .109375 ile .20 kapısının altında kalıyordu. Crop/origin/scale hatası veya kalite override yok. Aynı payload origin=[37,135], scale=.682969544, analiz345×376. Katman görselleri crop dönüşümü, gerçek browser noktaları, bant, eski triangle-union, kapalı hücreler, otomatik kutular, saç/pozlanma, takip koridorları/merkezleri ve kısmi pozitif desteği ayrı gösterir.

Düzeltme: gerçek dört sınır kenarı mevcut ve desteklenmiş **konveks** hücreler, torbalanma için iki üçgene ayrılır. Görünür ağ kenarları/noktaları değişmez; çizim tasarımına diyagonal eklenmez. Skor ve gradyen aynı kabul edilen merkezlerden gelir; merkez desteği geri alınmadı. Eski diğer kriterler sparse union’ı kullanır. Torbalanma formülü v5 ve ofset7..27, continuity .20, coverage .55, gölge .75 kapıları aynı; scope `tracked-center-closed-cells-v2` olarak kaydedilir. Render aynı hücre üçgenlerini yalnız seçili bags haritasında kullanır, gerçek `step` dönüşümü korunur.

Sampling sürümü hem bölgesel components hem Genel Bakış sourceComponents içinden çözülür. canCompareIndicator, compareAppearance ve history series anahtarı v1/v2’yi ayırır. **Gerçek eski/yeni kayıtlarda**, normalization aynı v5 olmasına rağmen her iki scope’ta delta engellendi ve iki ayrı seri üretildi. Eski kullanıcı kayıtları yeniden hesaplanmadı/ölçeklenmedi/silinmedi.

## Aynı gerçek ürün payload’ında önce/sonra

| SHA başlangıcı | Önce | Sonra | Aktif analiz hücresi | İncelenmiş/pozitif destekte aktif kaynak pikseli |
|---|---:|---:|---:|---:|
| 20031f35 | 0.000000 | 9.359850 | 312 | 0 |
| 36e4010b | 1.013258 | 0.976358 | 113 | 113 |
| beda0290 | null | 0.000000 | 0 | 0 |
| 4b13b16a | null | 0.000000 | 0 | 0 |
| e0ee9f0c | 0.000000 | 0.000000 | 0 | 0 |
| 5bd42346 | 0.000000 | 0.509856 | 16 | 16 |

20031f35’te görünür fold sinyali artık var, fakat **etiketli poligon yakalaması çözülmüş değildir**. 568 anotasyon analiz pikselinin 529’u sabit v5 bandının dışında; bantta39, son eligible destekte27 piksel kalır; kabul edilen fold haritası bunlarla örtüşmez (0 kaynak piksel). Poligon çoğunlukla daha üst alt-kapak alanını işaretliyor. V5 alt-kapak marjını dışlama sözleşmesini bu fotoğrafın skorunu tutturmak için değiştirmedik. Bu kaynağı full ROI başarı örneği saymıyoruz. Dışarıdaki bilinmeyen alan negatif değildir.

36e4010b pozitif sinyali ve 113 etiketli kaynak pikseli korunur. e0ee9f0c incelenmiş negatifinde aktivasyon0. beda0290 eski parçalı destekle gölge eğimi .752555 idi; kapanmış hücre desteğinde .717119 ve kapsam yeterli olduğu için 0 ölçülebilir. 4b13b16a’nın düşük görünürlük sebebi de boş hücrelerdi; son takip kapsamı yeterli ve paired edge sinyali0. Eşik/kalite şartı düşürülmedi. Gerçek yakalanamayan kalite durumları null olarak kalır; v2 CAPTURE_QUALITY regresyonu bunu doğrular.

5bd42346 dönüştürülmüş/gürültülü regresyon olarak ayrı: .509856/UI1 ve 16 bilinen destek pikselinde aktivasyon. Bu yeni açık regresyon gizlenmedi; doğal negatif veya başarı kanıtı sayılmadı. Kısmi poligon dışı/negatif destek dışı bilinmeyen kaldı. Full ROI Dice, şiddet ground truth veya genel uygulama doğruluğu türetilmedi.

Morluk v4, çizgi v3, kuruluk, yanak/çene sarkması ve diğer kriterlerin 192 ölçüm/harita çifti aynı gerçek payload’larda birebir korunuyor. Asıl yeni-kamera ürün akışında torbalanma 12.928161 → UI13 çıktı; bu YUV kamera/güncel browser landmark girdisi, sabit PNG payload9.359850 ile aynı giriş olarak sunulmaz.

## Teslim

19 odaklı regresyon, typecheck ve production build geçti. Genel Bakış nested sampling anahtarı keşfinden sonra ilgili kontroller/build tekrarlandı; uzun eğitim, üçüncü training validation veya ilgisiz kampanya yok. Normal Windows kısayolu → sahipliği doğrulanmış backend/frontend → 213 kaynak dosyası → 18 sunulan JS → analiz/model hash zinciri eşleşti. Önceki dxFr ve ilk staging jP9 build’leri korunuyor. Son BUILD_ID `yPTHcZKu38hukOVtSWnPV`. [Makine kanıtı](skin-label-bag-evidence-20261012.json). Lokal katman görselleri audit-results/bag-label-followup-20261012/*-layers.png; gerçek tarayıcı ekranları output/playwright/bag-label-followup-20261012 altında.

Hosted izin/config, üretim ağırlıkları, kullanıcı profilleri/izinleri/anahtarları, sesler ve AG kaynakları korunur. Yeni hosted/ücretli çağrı, eğitim, büyük indirme veya model arayışı yok. PR #2 Draft; main merge yok. Etiket işi tamamlandı; torbalanma kapalı-hücre mühendislik hatası düzeldi, anotasyon yakalaması ve dönüştürülmüş gürültü regresyonu açık.
