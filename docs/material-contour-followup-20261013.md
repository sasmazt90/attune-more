# Materyal ayrıştırıcı ve bağımsız kontur dalı — 13 Ekim 2026

Başlangıç SHA `085a20395c009199c5924ed9683d3f98ce771bb1`; korunan BUILD_ID `JO0Xyvupv72uoBiX42mWq`. [Makine kanıtı](material-contour-evidence-20261013.json) sayıları gerçek karşılaştırmalardan hesaplar. **Yeni adaylar normal üründe etkin değildir.** Kuruluk v3, çene v9 ve yanak v7 korunur. Bu teslim çalışan araştırma kodu ve kabul edilmeyen adayların somut teşhisidir; tamamlanmış kullanıcı özelliği değildir.

## Kurulukta gerçek değişiklik

Native proposal değiştirilmedi. Önceden incelenmiş envanterden 22 ek TRAIN kaynak grubu seçildi; arşiv/genel kaynak taraması yapılmadı. 264 bileşenin kaynak, yakın crop ve tam bileşen görünümü incelendi. 15 görünür materyal, 19 gözenek/doku, 2 yansıma ve 17 kıl/ringing bileşeni kabul edildi; **211 UNKNOWN/kapsam dışı** kaldı. F/PUL fotoğraf etiketi tüm bileşenlere uygulanmadı. Görünür stock/attribution ve muhtemel validation yakın kopyası olan dört ek kaynak fit dışında kaldı. Aynı burun fotoğrafının doğal/işlenmiş iki sürümü TRAIN grubunda birleştirildi. Önceki 50 etiket değişmedi; kişi kimliği/genelleme iddiası yoktur.

| Fit kapsamı | Bileşen | Kaynak grubu |
|---|---:|---:|
| Materyal | 19 | 6 |
| Gözenek/doku | 23 | 7 |
| Yansıma | 4 | 3 |
| Kıl/ringing | 17 | 3 |
| Toplam TRAIN | **63** | **15** |
| Korunan görülmüş validation | 28 | Kaynak/grup ayrımı korundu |

Sınıf grupları birbiriyle örtüşebilir; grup sütunu toplamı bağımsız kişi sayısı değildir. Materyalin deri mi kozmetik film mi olduğu belirlenemeyen örneklerden biyolojik kuruluk doğrusu üretilmedi. Mevcut optik materyal etiketleri klinik kuruluk/şiddet etiketi değildir.

Yereldeki özgün ImageNet EfficientNet-B0 safe ağırlığı kullanıldı: SHA-256 `e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a`. Eski cilt tipi head’i yüklenmedi. Encoder eval/frozen durumunda, tek thread, batch 4 çalıştı. Her aday için yakın ve çevre crop’larından 1280+1280 gerçek özellik ile ölçeğe uyumlu 12 geometri/ring/çekirdek ölçümü üretildi. RGB224, pad114, ImageNet mean/std uygulanır; crop büyütme kaynakta yeni detay değildir. Özellikler yerel NPZ cache’inde tutulur.

TRAIN-only standardizasyon ve L2/C=1/p≥0,5 classifier **bir kez** fit edildi. Aynı 63 TRAIN bileşeninde sekiz geometrik özellikli referans da bir kez fit edildi; korunmuş eski on-TRAIN head ayrıca aynı ölçüm kapsamına uygulandı. Validation scaler/PCA/fit’e girmedi; PCA veya eşik taraması yoktur. sklearn kurulu olmadığından aynı L2 hedefi yerel SciPy L-BFGS-B ile çözüldü; bu bir ikinci öğrenme denemesi değildir.

İlk özellik hazırlığındaki tüm crop tensorlarını bellekte tutma hatası fit başlamadan düzeltildi. Yalnız kendi dondurulmuş, henüz fit edilmemiş çıkarım süreçleri sonlandırıldı; AG süreçlerine dokunulmadı. Akış en fazla 32 crop tensoru tutar. Offline karşılaştırma, label-blind proposal üretiminden **sonra**, yalnız incelenmiş gözlem alanlarına dokunan adayların özelliklerini hesaplar. Etiketler classifier girdisi değildir; alan dışı sonuç sağlıklı kabul edilmez. Gerçek native ürün karşılaştırması ise **bütün anatomik proposal’ları** etiket kullanmadan sınıflandırır.

## Aynı kapsamda sonuç

| Sabit optik ölçüm | Önceki on-TRAIN gate | Yeni sekiz-geometri referansı | Frozen encoder + geometri |
|---|---:|---:|---:|
| Native materyal yakalama | 6/21 | 13/21 | **11/21** |
| Görülmüş validation materyal yakalama | 1/8 | 7/8 | **5/8** |
| Native incelenmiş negatif aktif kaynak pikseli | 204 | 734 | **0** |
| Doğal native materyal yakalama | 2/9 | 6/9 | **7/9** |
| Doğal yarım çözünürlük materyal yakalama | 3/9 | 3/9 | **4/9** |

Object-hit önceki mühendislik ölçütüdür: kısmi poligon içinde ≥3 kaynak pikseli ve ≥%10 destek. Tam ROI Dice/precision veya bağımsız final test değildir. 17/21 ve 7/8 sayıları sabit proposal’ın üst desteğidir; nihai başarı diye kullanılmaz. Negatif sıfır yalnız mevcut incelenmiş alanların sonucudur.

Kontrollü yarım-source karşılaştırmasında sabit minimum 48-piksel context ve 8-piksel yakın margin’in kaynakla küçülmediği bulundu. Bu, fiziksel crop kapsamını genişletiyordu. `pixel_density` ile minimumlar da ölçeklendirildi. Aynı head/threshold/scaler korundu; tüm 63 native TRAIN özelliklerinin değişmediği sayısal olarak doğrulandı. Yeniden fit yapılmadı. Düzeltme sonrası yarım capture daha kötü kaldı; sonuç gizlenmedi. Native gerçek ürün girişleri density=1 kullandığından değişmedi.

## Gerçek ürün girdisinde kalan hatalar

Native skor kabul edilen benzersiz kaynak alanından hesaplanır; confidence skora girmez. Tile max-union, anatomik payda, step=1 harita ve region/overview ilişkisi korunur. Classifier callback’i `native_dry_path.py` üzerinde gerçekten çalışır; normal API seçicisine bağlanmış değildir.

- **9bab7ab2:** Gözlük alt çerçevesinin incelenmiş küçük rim alanında **440 yanlış materyal pikseli**. Periorbital görünür alan skoru staging’de **5,97745**; normal v3 **0,119925**. Bütün göz çevresi negatif ilan edilmedi. Gözlük/skin-edge ile gerçek materyal sınıfı ayrılmıyor.
- **24031977:** Önceden görünür peeling/film olarak incelenmiş iki küçük yanak konumunda kabul edilen destek **0**. Buna karşılık brow yakınında **48 piksel** ve periorbital **0,66052** oluştu. Bu hedeflerde nedenin kuru deri olduğu bilinmiyor; görünür materyalin kaçırılması yine gerçek optik eksiktir. Kısmi konum poligonları pixel truth/Dice olarak kullanılmadı.
- **e1646fda:** Önceki C15’in 6.750 incelenmiş negatif pikselinde gerçek native yol da **0** destek verdi. Ancak diğer alanlar UNKNOWN’dır. Global kabul edilen 5.285 pikselin tamamının doğruluğu kanıtlanmış değildir.
- 1944×2592 kaynak, eşzamanlı yük altında tek-thread/batch-4 karşılaştırmada **508,469 saniye** sürdü. Bu idle benchmark değildir; mevcut **45 saniye** API bütçesine sığmaz. Geliştirme fotoğrafı cache’ini yeni kamera girdisinin runtime çözümü gibi sunmadık.
- Eski gate’in altı hit’inden yalnız üçü korundu; özellikle C0 ve C9’daki düşük/ince materyal–yansıma/doku ayrımı hâlâ kayıp yaratıyor.

Bu nedenle kısmi negatif metriği iyileşse de yeni head etkinleştirilmedi. Ağırlık/scaler/özellik cache’leri ve kaynak fotoğraflar Git dışında audit klasöründe kalır; manifest hash’leri makbuzdadır.

## Kıvrımdan ayrı kontur yöntemi

`contour_appearance.py` kişisel geçmiş istemez. Roll/face-width ve görünür taraf gerçek MediaPipe kaynak koordinatlarından normalize edilir. Anatomik guide yalnız arama bandını belirler. Orijinal görüntüden izlenebilen edge’ler kesintisiz parçalar içinde takip edilir; boşluk üzerinde argmax/varsayılan offset kullanılmaz. Merkez yedi örnek kendi ikinci derece komşu-kontur referans fit’ine girmez. Lokal dışa sapma ve komşu lokalizasyon belirsizliği ayrı ölçülür. Poz/ifade, sakal, gölge, exposure ve görünmeyen taraf kapıları korunur.

İlk dal 64b02ede’de çene–boyun gölge geçişini dış kontur sanıp **6,25 / altı kaynak pikseli** üretti. İkinci sürüm gerçek iç deri örneklerinden chromaticity zarfı çıkarır. Multiplikatif deri gölgesi dış-sınır kanıtı değildir; byte kuantizasyonu ve iç örnek değişkenliği referans alınır. Bu kontrol sonrası aynı kaynak **null / NEIGHBOR_CONTOUR_NOT_OBSERVED**, harita **0 piksel** oldu; sağlıklı sıfır üretilmedi.

| Gerçek kaynak | Yeni ayrı kontur dalı | Karar |
|---|---|---|
| f90e68f8 | Image boundary yeterince izlenemiyor; null | Eski küçük yanak fold sinyalleri korunur; güçlü kontur yakalama kanıtı değil. |
| 64b02ede | Önce 6,25; exterior kontrolü sonrası null | Gölge kaynaklı yanlış destek bastırıldı; pozitif başarı değil. |
| 40c7edda | Ölçülebilir sağ yanak 0; diğer destekler null | Normal kontur kontrolü; bütün yüz için sağlıklı etiketi değil. |
| 05619d0a | Gözlenen sağ kontur 0; sol target sınırı gözlenemiyor, çene izlenemiyor | Görünür lobule/örtülü taraf hedefi için yeterli lokal yakalama yok. |
| 515cc548 | Gerçek yeni browser capture desteklenen pozu kabul etmedi | Fotoğraf pozitifi kurtarmak için kalite override yapılmadı. |
| 99f82af5 / fc3a6b13 | Ayrı kaynak-konum hedefleri incelendi; mevcut ifade kapısı reddediyor | Nötr/gözlenebilir ürün kontur pozitifi olarak sunulmaz. |

Görüntüdeki hedef konumları ve kaynak SHA/grupları audit makbuzunda tutulur. Boyun/submental pleat, yaş, yüz yuvarlaklığı, sıradan jaw şekli ve nasolabial çizgi sarkma doğrusu değildir. Kısmi target dışı UNKNOWN kalır. Dalın ölçüsü **gerçek kabul edilen boundary support / bağımsız görünür sampling slotları** oranıdır; geometrik excursion keyfi katsayıyla klinik yüzdeye çevrilmez. Harita yalnız aynı kabul edilen kaynak merkezlerini kullanır. Formül `image-contour-neighbor-excursion-exterior-v2-staging`; fold v9/v7 ile aynı ölçek/seri sayılmaz. **Gerçek pozitif yakalama gösterilemediğinden dal etkinleştirilmedi.**

## Odaklı kontrol ve teslim sınırı

24 korunmuş native/v9/history regresyonu ve 11 yeni materyal/kontur kontrolü geçti: RGB crop, ölçekli context, TRAIN-only scaler, gerçek edge/guide ayrımı, boşluk üzerinde sahte süreklilik olmaması, kaynak roll/ölçek konumu, deri–boyun gölge reddi ve confidence değişse de kabul edilen harita/skorun değişmemesi. Bunlar doğal fotoğraf doğruluğu yerine kullanılmaz.

Normal kısayol oturumu task başlamadan durmuştu; mevcut kısayol mevcut build ile açıldı. Tek read-only normal API karşılaştırması mevcut kaynakla aynı measurements/maps/contours üretti; 115 korunmuş frontend/build kaynak hash’i eşleşti. Normal üretim analiz dosyaları/router/frontend değişmedi. Bu yüzden typecheck/yeni build ve tüm UI/geçmiş kampanyası tekrarlanmadı. Yeni yöntem fotoğraflı kullanıcı geçmişine yazılmadı; eski kayıtlar yeniden hesaplanmadı. AG, sivilce modelleri, hosted cilt tipi izin/config ve diğer sağlık modülleri bu çalışmanın dışında kaldı. PR #2 Draft; main merge edilmez.
