# Native kuruluk ve sarkma kapsamı — 13 Ekim 2026

Normal ürünün kuruluk v3, çene v9 ve yanak v7 seçimi korunmuştur. Yeni native kuruluk kodu çalıştırılabilir, izole bir analiz yoludur; normal API tarafından çağrılmaz. Materyal ayrıştırması kabul edilmediği için yeni yöntem etkinleştirilmemiştir. Kaynak fotoğraflar, kullanıcı kayıtları, tasarım, hosted izin/config ve AG çalışma alanı değiştirilmedi. Yeni build veya eğitim başlatılmadı.

Başlangıç kaynak SHA: `11a6447d1e3419bab867b6d3c70a5ba3804bc606`. Korunan BUILD_ID: `JO0Xyvupv72uoBiX42mWq`. Makine kanıtı: [native-dry-sag-scope-evidence-20261013.json](native-dry-sag-scope-evidence-20261013.json). Fotoğraflar, payload’lar, görseller ve tek fit’in ağırlıkları Git dışında `audit-results/native-dry-scale-20261013` altında kalır.

## Uygulanan mekanizma

`native_dry_path.py`, kaynak PNG’yi özgün boyutunda açar. Gerçek browser mesh’inin kapalı hücreleri, kaynak koordinatlı dışlamalar ve landmark delikleri aynı native grid’e uygulanır. Uzun kıl dışlaması gerçek yüz genişliğiyle ölçeklenir; kompakt gözenek halkaları proposal içinde ayrı ele alınır. Diğer kriterlerin 320 yüz-piksel yolu değiştirilmez.

`native_flake_support.py` bağımsız MSER bölgeleri ve çok ölçekli Hessian ridge adaylarını erken birleştirmeden değerlendirir. Ring referansı adayın kendi piksellerini dışlar. Yerel ring kontrastı, sınır kenarı ve gerçek kompakt koyu çekirdek çevresindeki açısal parlak desteği kullanır. Gözenek yakınlığı bütün materyal bileşenini silmez. İnference hiçbir etiket/poligon/sınıf veya kaynak adı almaz.

Native analiz 512-piksel çekirdekli, yarı çekirdek adımlı, bağlamlı karoları max-union ile birleştirir. Skor kabul edilen **benzersiz kaynak alanı / gözlenebilir native anatomik alan** üzerinden hesaplanır. Harita step=1 PNG ile aynı desteği tutar. Sunum için ayrı max-pool yardımcı fonksiyonu küçük materyali korur; skoru değiştirmez. Genel Bakış alanı bölge skorlarının toplamı değildir. Düşük çözünürlüklü kaynak büyütülmez. Önceden kullanılan kamera snapshot’ı tam native canvas’ı PNG’ye yazar; preview crop analiz girdisi değildir.

1944×2592 gerçek browser kaynağında 956×1256 native anatomik crop, 12 karo ve en fazla 381.924 piksellik çalışma karosu doğrulandı. Üç diğer gerçek ürün payload’ında kaynak origin/step, harita alpha’sı, eligible mask ve anatomik konum kontrolleri geçti. Bu, materyalin doğru sınıflandığını kanıtlamaz: aynı yüksek çözünürlüklü kaynağın çene görünür alan desteği v3’te 0 iken staging’de 10,5154 oldu. Fotoğrafta bütün bu alanların pul olduğu doğrulanmış değildir; incelenmiş yerel negatif sonuçları zaten etkinleştirmeyi engeller.

## Aynı etiket kapsamındaki sonuç

50 mevcut yerel etiket ve SHA `f0cec2daf46fd2f745dccf21e20c0f22c2bf59e1ff28b4039352091f984d7e34` değişmedi. 21 materyal, 24 incelenmiş materyal-dışı alan, 5 UNKNOWN. Poligon dışı negatif değildir. Bunlar kısmi optik materyal işaretleri; kuruluk etiolojisi veya klinik şiddet etiketleri değildir. Kaynak/grup ayrımı korunur; kişi kimliği bulunmadığından kişi bağımsız genelleme iddiası yoktur.

| Aynı optik kapsam | Önceki tek MSER | Bağımsız çok ölçekli proposal | Tek bileşen gate’i |
|---|---:|---:|---:|
| Native materyal alanı yakalama | 10/21 | 17/21 | 6/21 |
| Görülmüş development-validation yakalama | 2/8 | 7/8 | 1/8 |
| Native incelenmiş negatif aktif kaynak pikselleri | 4 | 1.153 | 204 |
| Doğal kaynak, yarım çözünürlük materyal yakalama | 0/9 | 6/9 | Ayrı makbuzda; kabul edilmedi |

Object-hit önceki mühendislik ölçütüdür: kısmi poligon içinde en az 3 kaynak pikseli ve %10 destek. Pixel Dice/precision, tam sağlıklı ROI veya bağımsız final test üretilmedi. Kısmi yüz kaynaklarının kısa kenarıyla yapılan 320 resampling **optik ölçek teşhisidir**; olmayan yüz landmark’larıyla normal API sonucu oluşturulmadı. Tam yüzü bulunan kaynaklarda gerçek browser face span kullanıldı. Aşama/ölçek değerleri her kontrol ve materyal nesnesi için JSON’da ayrı tutuldu; C3/C8/C9/C11 görselleri audit klasöründedir.

İlk seeded-growth prototipi 4/21’de kaldı. Erken union yapan ikinci yaklaşım 14/21’e çıktı fakat doku desteğini karıştırdı. Bağımsız adaylar bunu 17/21’e çıkardı. Bu son yaklaşım gerçek materyal proposal’ı ürettiğinden tek L2=1, p≥0,5 bileşen ayrıştırması gerekçesi önceden kaydedildi. Yeni proposal’ın mevcut kısmi etiketlere bağlanan 38 bileşeni iki görsel sayfada fit öncesi incelendi; 10 train, 28 görülmüş validation bileşeni vardı. Etiketsiz/UNKNOWN örtüşmeli bileşenler fit’e girmedi.

Tek fit 23 incelenmiş negatif validation bileşeninin 18’ini kabul etti; 5 materyal bileşeninin yalnız 2’sini kabul etti. Bileşen sınıflandırma sayıları 21 alan yakalama ölçütüyle karıştırılmaz. Native nesne yakalama 6/21’e düştü. Ring/şekil özellikleri bu küçük kapsamda gözenek/yansıma dokusunu materyalden ayıramadı. Ürün etkinleştirmesi reddedildi; ikinci fit, threshold araması veya uzun eğitim yapılmadı. Sabit-piksel eski descriptor ring’inin ölçek sınırlaması makbuzda kayıtlıdır; bu gate genel kullanıma uygun sayılmadı.

## Sarkmada kaynak ve hedef ayrımı

| Kaynak | Gerçek normal ürün | Aynı desteği koruyan native gray teşhisi | Karar |
|---|---|---|---|
| f90e68f8 | Çene null; 19 ham fold, sıfır yeterli run. Sağ/sol yanak 0,428393 / 0,012907 | 30 ham fold, 7 noktadan oluşan run; residual 4,82994; paired edge 0 | Küçültme kısmen destek kaybettiriyor; kaynak da çene v9’un sağlam iz/kenar koşulunu karşılamıyor. Yanak sinyali güçlü çene pozitifi değildir. |
| 64b02ede | Çene null; 3 ham fold, sıfır yeterli run | 4 ham fold, sıfır yeterli run; yarım ölçekte 0 | Gözlenebilirlik 64/64; eksik ROI değil, eşlenmiş kontrast/süreklilik eksikliği. Normal yüz şekli pozitif etiket yapılmadı. |
| dedbb492 | Çene yönlü gölge nedeniyle null; sol yanak 3,03379 | Görünür alt-çene/boyun pleat’i 2.933 kısmi mühendislik pikseli; 538’i hedef bandında | Hedefin çoğu boyun/submental alanda. Kıvrım alanı ve çene bandı farklı hedeflerdir; yanak skoru bunu çözmez. |
| e35b68b8 | Çene 0; sol yanak exposure-null | 28 yeterli native fold örneği, paired edge 0 | Yuvarlak alt yüz/şekil görünümü belirsiz; sarkma ground truth değildir. |
| 40c7edda | Çene ve yanaklar 0 | 14 native fold örneği; paired edge 0 | İncelenmiş normal kontur kontrolü korunur. |
| 74058e6c | Gerçek desteklenen RIGHT pozda sol yanak 0 | Sakal ve hedef görünürlüğü sınırlı | Çene payload’ı/negatif sağlık doğrusu uydurulmadı. |

Dört yeni kaynak, önceki manuel L/N inceleme kayıtlarından **skor hesaplanmadan önce** seçildi. Yeni genel kaynak taraması yapılmadı. Gerçek browser MediaPipe, kalite/poz ve snapshot girdileri normal API’den geçirildi; API ölçümleri/haritaları aynı kaynak fonksiyonuyla eşleşti. Fotoğraf kodlaması/native piksel, crop origin, band ve gözlenen/kabul edilen merkezler kaynak görsellerine çizildi. Native gray karşılaştırması başka kriterleri veya üretim protokolünü değiştiren bir teklif değildir; maske sabit tutularak yalnız fotometrik küçültme etkisi ayrıştırıldı.

Formül gerçekten fold **ve** eşlenmiş kenar **ve** yerel jaw-silhouette sapması gerektirir. Belirgin fold olmadan smooth kontur değişimi bu yöntemle ölçülmez. Bu kapsam sınırlaması kanıtlandı; fakat seçilen sıradan yüz konturlarını pozitif sayarak sadece boundary’den yeni sarkma skoru üretmek doğrulanmış bir çözüm değildir. Çene v9, yanak v7, poz/ifade/exposure/residual eşikleri korunur. İncelenmiş pleat dışı alan UNKNOWN kalır; hedef bandı örtüşmesi genel tespit doğruluğu değildir.

## Kontroller ve teslim

`test_native_dry_path.py`, `test_observed_chin_tracking.py`, `test_dry_sag_visible_support.py`: **24 geçti**. Karo sınırında benzersiz alan, native koordinat/mesh, küçük harita desteği, sabit kaynak paydası, input renklerinin korunumu, kalite-null ve mevcut normal ölçümleri etkilememe kontrolleri var. Normal üretim dosyalarında başlangıç SHA’ya göre fark yok; eski kayıtlar yeniden hesaplanmadı. Bu nedenle mevcut build/normal kısayol oturumu korundu; yeni typecheck/build veya bütün UI kampanyası çalıştırılmadı. PR #2 Draft üzerinden izole mühendislik kodu ve kanıtla devam edilir; başarısız aday teslim edilmiş özellik değildir.
