# Native materyal runtime ve kontur kapsamı — 13 Ekim 2026

Başlangıç `d190b6c70aff6442366f47a5a4af10077f5ac263`; korunan BUILD_ID `JO0Xyvupv72uoBiX42mWq`. [Hesaplanan makbuz](material-runtime-evidence-20261013.json) ve Git dışında `audit-results/material-runtime-followup-20261013` kaynak koordinatlarını, aşama görüntülerini ve artifact SHA'larını tutar. **Yeni adaylar normal üründe etkin değildir.** Kuruluk v3, çene v9, yanak v7 ve diğer yöntemler değişmedi. AG/sivilce hattına müdahale edilmedi.

## Süre: gerçek native girdiler ve aynı kararlar

Mevcut yerel frozen ImageNet EfficientNet-B0 safe ağırlığı CPU ONNX'e aktarıldı. RGB224, ImageNet mean/std, pad114 ve kaynakla ölçeklenen iki crop sözleşmesi değişmedi. Gerçek crop tensorlarında maksimum özellik farkı 0,0000261; tanımlanmış tolerans geçti. Üç tam kaynakta eski skor ve haritalar **tam eşleşti**. CNN eğitimi, indirme veya hosted çağrı yoktur. Export/source hash'leri makbuzdadır; artifact'ler Git dışında kalır.

Akış en fazla 32 crop tensoru tutar; encoder batch 16 çalışır. Aynı istek içindeki **tam aynı crop kutuları** özellik paylaşabilir. Yalnız örtüşen farklı kutular eşdeğer sayılmaz. Üç gerçek kaynakta tam aynı kutu tekrarı **0** bulundu; bu fotoğraflardaki hız kazanımını crop-cache kazanımı diye sunmuyoruz. Kalıcı fotoğraf/feature cache'i inference çözümü değildir. Proposal alanları, kaynak detayları ve normal görüntü renkleri küçültülmedi/değiştirilmedi.

| Kaynak | Önce toplam | ONNX/akışlı toplam | Decode | Geometri | Proposal | Encoder | Crop | Classifier | Harita/sonuç |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9bab7ab2 | 44,765 s | 18,704 s | 0,110 | 0,062 | 2,453 | 14,875 | 0,798 | 0,015 | 0,157 |
| 24031977 | 21,375 s | 6,718 s | 0,031 | 0,078 | 1,156 | 4,968 | 0,282 | <0,001 | 0,093 |
| e1646fda, 1944×2592 | 508,469 s | **367,203 s** | 0,750 | 0,266 | **89,000** | **255,262** | 16,207 | 0,358 | 1,125 |

Describe ve diğer küçük material işlemleri toplamın kalanıdır; bütün aşamalar ayrı makbuzdadır. Bunlar aynı kaynak/kapsamda, eşzamanlı sistem yükü altındaki gözlemlerdir; kontrollü idle hız katsayısı veya genel performans garantisi değildir. Büyük kaynakta 12 native tile ve 1.236 bileşen/2.472 crop kaldı. Bu iş yükü **45 saniyeye sığmıyor**; süre bütçesi yükseltilmedi.

Daha önce encoder benchmark'ına girmemiş doğal **00312529** fotoğrafı, gerçek browser MediaPipe → uygun FRONT/kalite → otomatik snapshot → gerçek HTTP/native araştırma backend yolunda ilk kez **16,109 saniyede** çalıştı. Proposal 2,047, encoder 12,703, crop 0,719 saniye. Development NPZ cache'i okunmadı. Bu, yeni kaynakta runtime kanıtıdır; fotoğraf kuru-materyal pozitifi veya bağımsız doğruluk testi olarak etiketlenmedi.

## Backend bütçesi ve iptal

Normal frontend'deki 45.000 ms AbortController değiştirilmedi. Gerçek ürün router'ı/geometry/body/busy-lock/threadpool yolu, ayrı **18011** HTTP hostunda araştırma analyzer'ı ile çalıştırıldı; normal **8000** seçicisi değiştirilmedi. Request'e ait deadline/iptal scope'u context ile worker'a geçer. Tile/candidate döngüleri, bounded encoder batch'leri ve map aşamaları stop kontrolü yapar. Worker gerçekten sonlanmadan lock serbest bırakılmaz; dış Future timeout'u ile arkada hesap bırakılmaz.

Yüksek kaynakta 45,062 saniyede HTTP **504 / LOCAL_ANALYSIS_TIMEOUT**; worker durdu ve lock açıldı. Bağlantı kesilmesinden yaklaşık **1,015 saniye** sonra worker **CANCELLED** ile bitti. Sonraki gerçek istek **200**, 9,437 saniye ve önceki skor/harita ile tam eşleşme verdi. İlk test harness'inin ortak request-state yarışması düzeltildi; nihai kontrol request'e özel ContextVar ve izlenen/cancel-await edilen watcher kullanır. Bunlar **staging** güvenlik kanıtıdır; normal v3 worker'ına bu araştırma yürütücüsünün entegre edildiği iddia edilmez. Hiçbir timeout sonucu sağlıklı sıfır olarak kaydedilmez.

## Materyal hata aşamaları ve tek sınırlı deneme

Native proposal, eski 50 lokal etiket ve **63 TRAIN / 15 kaynak grubu** korunur. Görülmüş validation kaynakları bağımsız final test değildir. UNKNOWN veya bbox dışı negatif değildir. Fotoğrafın F/PUL sınıfı bütün bileşenlere yayılmaz. Kaynak poligonları inference girdisi değildir.

**9bab7ab2:** Eski tam ürün yolunda gözlük rimindeki 440 piksel proposal'dan gelir; iki birleşik bileşen classifier tarafından p=0,5746 / 0,6694 ile kabul edilir. Decode/crop/ONNX farkı yoktur. Bunlar gerçek görünür gözlük yanlış desteğidir; bütün göz bölgesi sağlıklı negatif sayılmadı. Mevcut incelenmiş TRAIN materyal/gözenek/yansıma/kıl bileşenlerine validation gözlük hatası taşınmadı.

**24031977:** Eski iki konum poligonunun biri saç/dış kenara, diğeri gerçek materyalin üstündeki yanak alanına denk geliyordu. Eski makbuz korunur; yanlış konumlar doğruluk kanıtı olarak kullanılmaz. Orijinal bitmap üzerinde görülen alt-yanak materyali için ayrı exposed-development konum kaydı açıldı. İlk gerçek konumda 143 pre-anatomy proposal pikseli → 38 eligible piksel → 0 classifier kabulü; ikinci konumda 16 → 8 → 0. Hem kapsam/dışlama hem classifier kaybı vardır. Kısmi konumlar tam pixel truth/Dice değildir; biyolojik kuruluk/kozmetik film nedeni UNKNOWN'dır. Üstteki kaş desteği kaçırılan yanak başarısı sayılmaz.

**C0/C9 ve ölçek:** C0'ın kaybedilen iki native hedefinde yeterli proposal var, classifier p=0,0768 / 0,0689 ile reddediyor. Aynı fiziksel crop sözleşmesiyle yarım kaynakta p=0,6941 / 0,8297 oluyor. Bu artık crop minimumu ölçek hatası değildir; frozen visual özellik/domain kararsızlığıdır. C9'un ilk hedefinde proposal yok; diğer kaybedilen hedefte proposal var fakat p=0,1988–0,4544. Doğal yarım kaynakta proposal'ın 6/9 desteğinin classifier sonrası 4/9'a düşmesi aşama makbuzunda bileşen ve kaynak koordinatıyla ayrıldı. Encoder bulunmayan proposal'ı geri getiremez.

Kaybedilen hedeflerin logit ayrıştırmasında 12 geometri özelliği yaklaşık 0,01 büyüklükte, 2.560 visual özellik ise birkaç logit birimi katkı yapıyor. **Tek önceden kayıtlı deneme:** standartlaştırılmış yakın/çevre/geometri bloklarına sqrt(1280)/sqrt(1280)/sqrt(12) boyut dengelemesi; sabit L2/C=1/p≥0,5. Aynı 63 TRAIN bileşeniyle yalnız küçük logistic head bir kez fit edildi. CNN, proposal, crop veya validation fit değişmedi; eski head hash'i aynı kaldı. Parametre/threshold araması yapılmadı.

| Aynı kısmi optik kapsam | Korunan head | Blok dengeli aday |
|---|---:|---:|
| Native materyal hit | 11/21 | 12/21 |
| Görülmüş validation hit | 5/8 | 7/8 |
| TRAIN hit | 6/13 | 5/13 |
| İncelenmiş native negatif destek | 0 piksel | 30 piksel |
| Doğal native / yarım-source hit | 7/9 / 4/9 | 7/9 / 4/9 |
| İncelenmiş gözlük rim desteği, gerçek ürün girdisi | 440 piksel | 73 piksel |
| 24031977 düzeltilmiş iki materyal konumu | 0 / 0 piksel | 0 / 0 piksel |

TRAIN ve validation birleştirilip genelleme iddiası yapılmaz. Object-hit eski ≥3 kaynak pikseli ve ≥%10 kısmi materyal desteği ölçütüdür. Tek negatif piksel otomatik klinik başarısızlık değildir; 30 pikselin lokal kapsamı ayrıca kaydedilir. Buna rağmen gerçek gözlük yanlış haritası, iki gerçek materyal kaçırması ve büyük-source latency engeli sürdüğünden **admission başarısız**. Confidence şiddet yüzdesi olmadı; skor benzersiz kabul edilmiş kaynak alanından gelir. Dengeli aday v2 / native normalization v5-staging olarak ayrılır, korunmuş v1/v4-staging ile aynı seri sayılmaz. Normal ürün/geçmiş seçicisi hiçbirine bağlanmadı.

Korunan eski on-TRAIN gate'in altı hit'inden yeni iki-crop head'de kalan **3/6**, blok dengeli adayda da **3/6**; C0/C9 kayıpları tamamlanmadı. Gözlük periorbital alan skoru 5,97745 → 0,991713; 73 yanlış piksel görünür haritada hâlâ vardır. Diğer yeni kaynak alanları incelenmiş negatif sayılmadı. Dengeli adayın iki küçük gerçek isteği 16,234 / 6,672 saniye; büyük kaynakta yeniden uzun inference başlatılmadı. Önceki aynı encoder/proposal iş yükünün 367 saniyelik ölçümü runtime kabulünü zaten engeller; yeni head'e ölçülmemiş bir hızlı süre atanmıyor.

## Kontur: ifade ile gerçek hedef kapsamı ayrı

Gerçek browser MediaPipe noktalarında ağız açıklığı ve köşe yüksekliği kaynak piksel/mouth-width oranıdır; yaw/pitch skin browser estimator birimleridir, derece değildir. 99f82af5 ve fc3a6b13'te mouth opening 0,00219 / 0,01860, corner ratio −0,08341 / −0,12002. Reddin nedeni açılmış ağız değil statik lip-corner biçimidir. Kare kaynaklarda normalized/source-pixel opening aynı; koordinat/birim dönüşüm hatası bulunmadı.

Mevcut yerel FaceLandmarker task'ının gerçek blendshape çıkışı yalnız izole browser'da açıldı. Aynı bitmap'te landmark farkı **0**. 99f82af5 smile L/R 0,164/0,116; fc3a6b13 0,00079/0,00127. Statik dudak biçimini ifade doğrusu yapmak güvenilir değildir. Araştırma dalında fotoğraf-id'ye bağlı, önceden tanımlanmış local-expression rejection desteği denendi; mouth-opening, pose, kalite ve anatomik kapılar korunur. Blendshape katsayıları klinik ifade doğrusu veya şiddet olarak sunulmaz. Normal browser/instant_proxy ifade kapısı değiştirilmedi; ek negatif ifade kalibrasyonu ve gerçek pozitif admission olmadan üretime alınmaz.

Bu ifade aşamasını ayırmak **kontur pozitifi kurtarmadı**:

- **99f82af5:** sol konturda 56 image sample izleniyor, yerel excess 0; eski magenta hedef dış silüetin içinde, lateral yanak kıvrımına yakın. Target overlap 0, dış kontur bandını bu iç hedefe taşımayı gerekçelendirmez. Yaş veya ordinary fold sarkma doğrusu değildir.
- **fc3a6b13:** hedefte yalnız 5 image sample gözleniyor; görünür anatomik sınır kapsamı yetersiz ve null. İşaretli lateral edge doğrulanmış lokal outward prominence değildir.
- **05619d0a:** sağ kontur 65 örnekte izleniyor fakat komşu belirsizliği aşan lokal prominence yok; sol taraf örtülü/null, çene tracking yetersiz/null. Güçlü çene pozitifine dönüşmedi.
- **f90e68f8 / 64b02ede:** dış sınır/neighbor desteği engeli devam eder; önceki deri–boyun gölge reddi korunur. Null sağlıklı sıfır değildir.
- **40c7edda:** ölçülebilen sağ normal contour 0 korunur; sol shadow/null ve chin tracking/null korunur.

Yerel envanterin henüz incelenmemiş kısmından **yalnız altı** SHA/grup kayıtlı kaynak seçilip görsel olarak incelendi. Beşi collage/black artificial occlusion, kalan 00312529 doğal fotoğrafta açık gülümseme/cap shadow var. Uygun nötr contour pozitifi çıkmadı. Kalan envanterin incelendiği/uygunsuz olduğu iddia edilmez; bütün arşiv taranmadı. Aynı doğal kaynak native dry runtime kontrolü için kullanılabildi; sarkma pozitifi yapılmadı. **Gerçek nötr pozitif hâlâ gösterilemedi.**

Araştırma contour expression v3 / observed-boundary sampling sürümü row, trace ve map makbuzlarında tutarlıdır. Aktif chin v9/cheek v7 ile farklı hedef/ölçü serisidir; eski kayıtlar hesaplanmadı/yazılmadı.

## Teslim sınırı

39 ilgili regresyon geçti; son contour-map makbuz değişikliği sonrası ilgili 15'i tekrar geçti (54 bağımsız test iddiası yok). Cancellation/deadline, exact per-request crop reuse, feature-block scaler, photo-id bağlı ifade desteği, native map/area/overlap/null, mevcut v9/legacy-history ve kontur konum/ölçek/gölge kontrolleri kapsanır. Normal üretim import yoluna, frontend'e veya shared DTO'ya değişiklik yok; bu yüzden typecheck/yeni build/UI kampanyası tekrarlanmadı. Normal API'nin yeni kaynakta mevcut kaynak koduyla eşleşmesi, 115 pinned kaynak/build hash'i ve sunulan JavaScript byte eşleşmesi makbuzdadır. Kullanıcı kayıtları, fotoğrafları, izinleri, sesler ve tasarım korunur. PR #2 Draft; main merge yoktur.
