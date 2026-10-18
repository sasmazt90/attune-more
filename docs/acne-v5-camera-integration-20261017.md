# Cilt Sağlığı kamera akışı — V5 entegrasyon düzeltmesi

Başlangıç: `29b99795f4ae5c2bed50d848634ed87f97e0a296`.
Çalışma ağacı: `attune-cdc-acne-v5-integration`, dal: `research/acne-v5-integration-20261017`.
BUILD_ID: `TJGEGuNep-WFkgXy4Cw-x`.

## Teslim edilen davranış

`/skin` artık her durumda mevcut `SkinPage` ve özgün başlangıç/kamera/sonuç bileşenlerini açar. Fotoğraf yüklemeli `ExperimentalAcnePhoto` bileşeni ve sayfa yönlendirmesi kaldırıldı. Teknik ayar yalnız motoru seçer. Fotoğraf formu, poz dropdown'u, yeni rozet veya teknik kullanıcı metni eklenmedi.

Normal `snapshot → analyzeAppearance → /api/local-health/skin` isteği, var olan `LOCAL_API_BASE` seçimini kullanır: bu izole build'de 8305, opt-in kapalıyken mevcut üretim varsayılanı localhost:8000. Normal analiz ve kuruluk yolu önce tamamlanır; V5 adaptörü yalnız sivilce satırlarını ve sivilce adaylarını değiştirir. Diğer sekiz kriter, haritalar, konturlar, cilt tipi ve kuruluk runtime metadata'sı için adaptör öncesi/sonrası SHA-256 eşitliği her gerçek yanıtta hesaplanır; fark olursa yanıt teslim edilmez.

Sivilce barı mevcut `appearance-score-0-100` birimini ve `unique-detection-box-anatomical-area-v2` sözleşmesini korur: benzersiz kabul edilmiş kutu pikselleri / sabit görünür anatomik destek ×100. Olasılık şiddet yüzdesine çevrilmedi; skor tabanı, yeni eşik veya yeni birleştirme kuralı yok. Yeni yöntem `appearance-acne-step0-verifier-v5-1`, sampling `step0-staging-v5-source-box-support-v1`. Eski yöntem/model/sampling kimlikleriyle geçmiş karşılaştırması eşdeğer sayılmaz; eski kayıtlar yeniden hesaplanmadı.

Sivilce barına tıklanınca yalnız seçili bölgenin aynı kaynak fotoğrafına ait küçük noktalar gösterilir. Noktalar ekran üzerinde yaklaşık 3,5 CSS piksel yarıçapındadır; kutu büyüklüğüne bağlı değildir. Bölge/kriter değişiminde önceki noktalar ve harita temizlenir. `SkinFacePanel` bu görevde değiştirilmedi.

## Dondurulmuş model

| Bileşen | SHA-256 / seçim |
|---|---|
| Step0 | `18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655` |
| Mevcut kararlı SiLU ONNX | `9c87475d9302aed16f09abedc109211c2ac1b49f22f465f86aab408a5244d0be` |
| Verifier V5 | `0d7bf03ca4d9898ef1b2e78c6d54d61be6aff580329b20b78a9232f79cfd43bb` |
| V5 eşiği | `0.15628215094908582` |
| Birleşik pipeline kimliği | `b8200e999c6c744247d264de70df5280900e08f0ba5130479425a6dac92d13f5` |

Yeni eğitim, fit, export, kalibrasyon, veri incelemesi veya model karşılaştırması yapılmadı. Aynı ileri geçişten P2–P5 özellikleri, mevcut tile/decode/obj×cls/Hard-NMS ve staging filtresi kullanıldı. Model bulunamazsa, kapalıysa veya kimliği uyuşmazsa sivilce `null/unavailable` kalır; diğer kriterler korunur. İptal/deadline istisnası yarım sonuç olarak kaydedilmez.

## Gerçek tarayıcı kanıtı ve sınırı

Headed Chromium, 1280×900 viewport, yalnız izole 3305 origin/profilinde çalıştırıldı. Sağlık Merkezi → Cilt Sağlığı → Analizi Başlat → FRONT/RIGHT/LEFT otomatik yakalama → sonuç/bar → Sağlık Geçmişim/aynı kayıt akışı gerçek uygulama koduyla tamamlandı.

Giriş **fiziksel kamera değildir**: önceki teslimde zaten kullanılan iki kayıtlı geliştirme görüntüsünden canvas video track'i üretildi (1280×1280/15 fps); LEFT, RIGHT kaynağının yatay aynasıdır. Aynalanmış görüntü bağımsız doğal fotoğraf doğruluğu kanıtı değildir. MediaPipe 478 noktayı, kaliteyi, gerçek pozları, anatomik ağları, gözlük ön kontrolünü ve kaynak snapshot'ını yeniden hesapladı; landmark, sonuç veya skor enjekte edilmedi. Capture koşulları override edilmedi. Kullanılan test enjeksiyonu uygulama kaynağına eklenmedi; geçici iki public JPEG sonradan kaldırıldı.

| Gerçek API isteği | Son aday | Tile / detector forward | V5 segmenti | Sonuç |
|---|---:|---:|---:|---|
| FRONT `818a8528…` | 22 | 12 / 12 | 5,334 sn | 200; diğer kriter hash'leri eşit |
| RIGHT `5f05f92c…` | 4 | 9 / 9 | 3,124 sn | 200; diğer kriter hash'leri eşit |
| LEFT `004f9a28…` | 2 | 9 / 9 | 3,885 sn | 200; diğer kriter hash'leri eşit |

Bu süreler V5 segmentidir, bütün kamera taramasının süresi değildir. Ayrı tek kayıtlı fotoğraf payload'ı, gerçek normal API'yi ve diğer kriterleri de çalıştırarak 15,509 saniyede tamamlandı; bu da fiziksel kamera kabulü değildir.

Genel Bakış ve altı bölgenin kriter listeleri, kaynak fotoğraf kimlikleri, barların ham değerleri, nokta sayısı/koordinatları, yaklaşık sabit ekran yarıçapı ve diğer kriter haritasına geçişi DOM/API karşılaştırmasından doğrulandı. Göz çevresine sivilce eklenmedi. Genel Bakış ham sivilce değeri `1.612221680481066`, mevcut UI yuvarlaması `%2`; nokta sayısı 22. Aynı izole geçmiş kaydı `a33dba69-120a-44b8-af2f-cdc27cc2f174` aynı fotoğraf/metot/model ve aynı 22 koordinatla açıldı.

Ölçümü geçerli olmayan ton/yağlılık/kızarıklık ve cilt tipi değerleri mevcut `—` davranışını korudu. Hosted izin testte kapalıydı; hosted cilt tipi çağrısı veya sınıf doğrulaması yapılmadı. Bunlar sahte sıfır veya sınıfla doldurulmadı.

Korunan staging filtresinin bilinen kapsam davranışı da görünür kaldı: FRONT'ta yakın anatomik mesafe fallback'i ile alın bölgesine atanmış bir adayın kutusu ölçülen alanı kesmediğinden alın kutu/nokta sayısı 1, ham alan oranı 0'dır. Bu görevde filtreyi değiştirmek veya yapay skor tabanı eklemek yerine mevcut iki sözleşme aynen korundu. Bu bir model doğruluğu kazanımı olarak sunulmuyor.

Park/sürüş kilidi (izole demo araç durumu), kamera iptali ve başka sekmeden kamera izninin kaldırılması gerçek UI'dan denendi: track'ler kapandı, yeni sonuç/ikinci geçmiş kaydı oluşmadı. Kamera izni test profilinde mevcut akışla geri açıldı. Onaylı ses kaynağı ve yönerge kodu korunmuştur; fiziksel ses duyulabilirliği bu tarayıcı kanıtıyla doğrulanmış sayılmaz.

Otomasyon oturumu kapatıldı. Son teslim tarayıcısı enjeksiyonsuz yeni oturumdur: `getUserMedia` native, `__cameraAudit` yok, dosya/select sayısı 0, reddedilen teknik metinler yok. Fiziksel PC/telefon/araç kamerası doğrulaması **yapılmadı**.

## Tasarım, kontroller ve teslim zinciri

Özgün `SkinStartView`, `SkinActiveScan`, `SkinResultView`, `SkinRegionSummary` dosyalarının başlangıç SHA-256'ları bire bir korundu. Başlangıç, aktif tarama ve sonuç görüntüleri aynı 1280×900 viewport'ta alındı; bazı çıktılar full-page olduğu için PNG yükseklikleri farklıdır. Onaylı yerleşim regresyonları ve görsel inceleme tamamlandı; eski sürümün ayrı tarayıcı görüntüsüyle piksel-piksel karşılaştırma yapıldığı iddia edilmiyor.

- Odaklı kontroller: 5 preview/kapı testi + 3 yeni normal-yanıt/kimlik/geçmiş testi + 7 korunmuş yerleşim/harita/Genel Bakış testi geçti.
- Typecheck ve production build geçti. Build'deki iki mevcut lint uyarısı korundu.
- İlk build gözeticisi `memory_full_info().uss` AccessDenied hatası verdi; başarısız makbuz ve log saklandı. Paylaşılan kilit/limitler değiştirilmeden mevcut daha muhafazakâr toplam RSS ölçümüyle tek tekrar başarılı oldu. Bellek güvenlik koşulları kaldırılmadı.
- Başlatıcı son backend koduyla yalnız kendi doğrulanmış PID/başlangıç/komut süreçlerini yeniden açtı. Çalışan portlar 3305/8305. 38 sunulan JavaScript dosyasının HTTP baytları build hash'leriyle eşleşti; kaynak, build, analiz dosyaları, model hash'leri ve süreç kimlikleri `delivery-chain.json` içinde.
- Dört korunan checkout'un HEAD'leri aynı. Ana `attune-live-test` alanında eşzamanlı iki rapor değişikliği saptandı (`docs/all-health-feature-acceptance-20261010.md`, `docs/all-health-task-status-20261017.json`); bu görev bunlara yazmadı ve dokunmadı. AG/Claude/araştırma alanları değiştirilmedi.
- Ana ürün başlatıcısı/portları, kullanıcı profilleri, üretim kayıtları ve ana model manifesti değiştirilmedi. Sivilce manifesti `accepted:false, file:null`. Yeni eğitim/veri indirmesi/ücretli çağrı yok; push, merge veya genel üretim aktivasyonu yok.

Başlatma: bu çalışma ağacındaki `Start-Acne-V5-Preview.ps1`; adres `http://127.0.0.1:3305/skin`.

Makbuzlar ve ekranlar: `C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\acne-v5-camera-integration-20261017`.
`camera-evidence.json`, `history-check.json`, `lifecycle-checks.json`, `clean-ready-browser.log`, `normal-api-photo-contract.json`, `final-contract-regressions.xml`, `focused-tests.xml`, `build-receipt.json` ve `delivery-chain.json` bu ayrımı korur. Bunlar modelin bağımsız doğruluğu veya genel üretim kabulü değildir.
