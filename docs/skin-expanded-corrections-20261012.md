# Göz çevresi v5 ürün entegrasyonu — 2026-10-12

Kaynak yalnız dondurulmuş AG `ff0b161bd807fe81d2ba5ee6283d4f5b26f6a102`; hareketli AG dosyaları okunup kopyalanmadı/değiştirilmedi. Önceki gerekli göz çevresi değişiklikleri tam commit sürümünden seçildi, bütün dal merge/cherry-pick yapılmadı.

Torbalanma `contour-fold-local-support-v5`, morluk `lower-lid-contrast-chroma-local-v4`, çizgi `outer-canthus-gabor-radiating-hair-excluded-v3` normal üründe analitik görünüm indeksleridir. Confidence veya binary mask şiddeti değildir. Ofsetler 320 normalize yüz genişliğinde 7..27; alt kapak kenarı dışlanır. Continuity <0.20 sıfırlama yalnız periorbitalde. Yanak/çene v6, kuruluk ve diğer mevcut yöntemler korunur. AG global hair ve acne-brow-tail değişiklikleri taşınmadı; saç dışlama yalnız ilgili göz hedefinde. Hosted izin/config ve reddedilmiş modeller değişmedi.

## Skor/harita desteğinde bulunan ve düzeltilen hata

AG profil takibi geniş context_skin üzerinde fold merkezi seçiyor, kart skoruna dahil ediyor; harita ise merkez seçili band/mesh içinde değilse çizmiyordu. 5bd42346 gerçek GPU yolunda 0.514288 → UI1, harita 0 hücreydi. Fotoğrafa özel kural eklemeden yalnız periorbital örnek merkezlerini gerçek eligible band/mesh/saç desteğine bağladık: `samplingSupportVersion=tracked-center-eligible-v1`. Paired bright/dark/bright doğrulaması çevre piksellerini kullanabilir; ölçülen merkez ve ortalama yalnız haritanın kabul ettiği alanı kullanır. .20 continuity, .55 coverage ve kalite kapıları korunur. Yanak/çene çağrısına bu kısıt verilmez.

Bu düzeltme 20031f35 pozitifini kurtarmadı: eski geniş destek sağ/sol 63/60 pozitif merkezden yalnız 8/8 merkez gerçek hedefteydi, 41/52 merkez seçili bölge dışındaydı; sağda 21 merkez saç desteğine denk geldi (kategoriler örtüşebilir). Dar destek üzerinde süreklilik yetersiz ve sonuç 0. Bu pozitif kaçırmadır; yanlış boyamanın azalması başarı diye sunulmadı. Mevcut band/mesh sınırını örneğe özel genişletmedik, eşik düşürmedik veya AG sayısını sabitlemedik.

## Gerçek normal ürün sonuçları

| SHA başlangıcı | Kapsam | Torba raw → UI | Morluk raw | Çizgi raw | Torba sonucu | Aktif bag hücresi | Band/bölge dışı hücre |
|---|---|---|---|---|---|---|---|
| 20031f35 | development_positive_polygon | 0.000000 → 0 | 20.922380 | 6.608452 | valid | 0 | 0/0 |
| 36e4010b | development_positive_polygon | 1.013258 → 1 | 3.799388 | 0.000000 | valid | 52 | 0/0 |
| beda0290 | natural_reviewed_negative | — → — | 2.045249 | 0.725190 | HARD_DIRECTIONAL_SHADOW | 0 | 0/0 |
| 4b13b16a | natural_reviewed_negative | — → — | 11.642267 | 0.144426 | ANATOMICAL_BAND_NOT_VISIBLE | 0 | 0/0 |
| e0ee9f0c | natural_reviewed_negative | 0.000000 → 0 | 0.342580 | 0.000000 | valid | 0 | 0/0 |
| 5bd42346 | transformed_noisy_regression | 0.000000 → 0 | 1.538581 | 0.504463 | valid | 0 | 0/0 |

Beş istenen fotoğraf kaynak SHA-256 ile mevcut kullanım hakkı envanterinden çözüldü. Gerçek tarayıcı GPU MediaPipe, mevcut kaynak RGB/crop, face-cropped kalite kontrolü ve otomatik dışlama dikdörtgenleri kullanıldı. Kalite override edilmedi. API photoId kaynak canvas RGBA hash’iyle aynı. Her normal response Genel Bakış, altı bölge, fotoğraf/harita ve aynı izole geçmiş kaydına üretim fonksiyonlarıyla aktarıldı. Önceden yazılmış skor API cevabı olarak kullanılmadı.

e0ee9f0c doğal negatifinin kaynak, kategori, kalite, gerçek 0 sonucu ve seçilme gerekçesi JSON makbuzunda yer alır. 5bd42346 döndürülmüş/dolgulu/gürültülü regresyondur; doğal çekim kanıtı değildir. Kısmi poligon dışı ve incelenmiş negatif ROI dışı bilinmeyen bırakıldı. Full ROI Dice ve şiddet etiketi yok. 20031f35 pozitif desteğinde aktivasyon yok; 36e4010b’de gerçek lokal aktivasyon var. Üç doğal negatiften yalnız e0ee9f0c ölçülebilir; diğer ikisi kullanılamıyor, sağlıklı/başarılı negatif diye sayılmıyor.

## Farkların kontrolü ve makine kanıtı

İlk, destek düzeltmesinden önceki aynı-girdi kontrolünde dondurulmuş AG ile ürünün altı fotoğraf/üç hedef sonucu tam eşleşti. Bu eski teşhis `preSupportFixIdenticalInputFrozenAGParity` altında korunur; son kodun AG ile eşitliği iddia edilmez. Python MediaPipe 0.10.32 CPU referansı ile ürün @mediapipe/tasks-vision 1.0.1 GPU gerçek landmark’ları farklıdır (20031f35 en büyük fark 13.34 kaynak piksel); AG exclusions=[] ve ürün üç otomatik dışlama kullanır. Aynı kaynak/model dosyası farklı runtime geometrisini eşitlemez. Somut destek hatası ayrıca yukarıda düzeltildi.

[Makine makbuzu](periorbital-v5-evidence-20261012.json) her hedef için PNG alpha>0 hücreleri, gerçek roll-aware eye_skin_bands ve triangle-union seçili bölge örtüşmesini kaydeder. Yalnız y koordinatı kontrolü kullanılmadı. Global üretim raster’ı aynı origin/scale ile oluşturulup map crop’u alınır. Kaynağa nearest projection dış piksel sayıları ayrıca kaydedilir; raster sınır belirsizliği gizlenmez. Alpha>0 ile uint8 ağırlıklı RGB görünürlük sayıları ayrıdır; map step gerçek kaynak dönüşümünde kullanılır.

Altı gerçek ürün girdisinde önceki d596873 kaynakla hedef dışı 30 ölçüm ve harita fotoğraf başına birebir aynı (180 kontrol); yanak/çene sarkması dahil. Eski v4 test kaydı byte/değer/fotoğraf ilişkisi yeniden açılışta korundu. v4/v5 farklı normalization eşdeğer trend/delta oluşturmadı, null gap ve ayrı gruplar korundu. Kullanıcı profilleri/kayıtları yeniden hesaplanmadı, taşınmadı veya silinmedi.

Gerçek normal build ve backend, doğal fotoğraf/yakın kadraj, mevcut tasarım, Türkçe etiket, Genel Bakış+altı bölge, seçili kriter gradyeni ve tam sayı barlar doğrulandı. Bölge/kriter değişiminde eski harita temizlendi. Masaüstü, dar pencere ve gerçek Chrome %200: CSS zoom=1, DPR=3 (OS1.5 × browser2), innerWidth641/outerWidth1298, yatay document taşması yok. İzole profil ve seçili harita ekran kanıtı output/playwright/periorbital-v5-20261012 altında.

Typecheck ve production build geçti; 15 odaklı regresyon geçti. BUILD_ID `dxFr1OhOItAcorPw-G3Yp`; önceki build .runtime/skin-before-periorbital-v5-20261012 altında korunur. Normal Windows kısayolu → backend → 213 frontend kaynak dosyası → sunulan 18 JS chunk → analiz/model hash zinciri makbuzda eşleşti. Frontend kaynak değişmedi; build sonrası son backend düzeltmesi normal kısayolun kontrollü doğal kapanış/yeniden açılışıyla yüklendi.

## Açık kalanlar

- 20031f35 positive is missed after enforcing actual selected-region fold centers; do not call decreased marking improved positive detection. Most unrestricted centers were outside selected mesh/hair support.
- beda0290 is unavailable: HARD_DIRECTIONAL_SHADOW.
- 4b13b16a is unavailable: ANATOMICAL_BAND_NOT_VISIBLE. Neither missing measurement is healthy zero.
- Only two previously exposed partial-positive polygons and three bags-reviewed natural-negative ROIs; no general accuracy or full ROI Dice claim.

Yeni eğitim, ücretli/hosted çağrı, model araştırması veya AG’nin diğer görevlerinin tamamlandığı iddiası yok. Sivilce/reddedilmiş nöral maskeler etkinleştirilmedi. PR #2 Draft; main merge yapılmaz.
