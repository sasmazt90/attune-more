# 9 Ekim 2026 — güncel kapsam ve kabul sınırları

Son başlangıç teslimi: `87132aab72f0a8333ee0f1caf2cd69e6c79acbe7`. Çalışma branch’i: `fix/live-test-followup`. İncelenen production build: `UKOQG9a9mh5Z6f4I4fJMo`. Kesin teslim commit’i, normal kısayol zinciri ve sunulan dosya hash’leri yerel `audit-results/current-health-20261009/delivery.json` raporundadır. Bu belge bir fiziksel kullanıcı kabulü değildir.

| # | Kapsam | Son build’de doğrulanan davranış / sınır |
|---|---|---|
| 1 | Ortak durum tipografisi | Sayı/durum ayrımı, tam sayıya yuvarlama, satır kırılması; dar pencere ve native Chrome %200 geçti. |
| 2 | İlk taramada sonuç | İki gerçek production üç poz akışı kontrollü lisanslı video ile geçti. Boş geçmiş ve bozuk korunmuş eski referans engellemedi; otomatik referans yazılmadı. |
| 3 | Anlık sarkma/torbalanma | Yeni mevcut-fotoğraf formülü, ayrı anatomi/yanlar ve gerçek kaynak sinyali çalışıyor. Pozitif piksel mühendislik kontrolleri geçti. İnsan fotoğrafında pozitif sarkma/torbalanma kabulü kanıtlanmadı; aşağıdaki görünürlük/ışık sınırları açık. |
| 4 | Ortak ses yönlendirmesi | 32 sabit Edge cache, exact Ahmet/Emel −10%/−10Hz; gerçek Audio/MSE ended, autoplay retry, tekrar/dedup/route/mute/odak kontrolleri geçti. 24 gerçek DIN PCM uyaranı ile TTS çakışmadı; saf ses ve sessiz kontrol aralıkları ayrıca doğrulandı. İşitsel telaffuz ve fiziksel mikrofon kabulü açık. |
| 5 | Yalnız diş fotoğrafı | Gerçek full-face içermeyen 1617×1212 JPEG, frozen ONNX ile 8 aday; native fotoğraf/SVG kaynak kutuları, iptal/değiştirme gecikmeleri geçti. JPEG/PNG/WebP decode, EXIF ve sınır kontrolleri geçti. |
| 6 | Beş modülün geçmişi | Aynı liste, gerçek yeni diş/işitme kayıtları, kontrollü eski kayıtlar, ayrıntı, tek silme/tümü silme, onay ve medya saklamama geçti. Eski cilt oranı eski yöntemi ve ×10⁻³ birimiyle korundu. |
| 7 | Merkezi adlar/liste | Menü, geçmiş, sonuçlar, ses cache metinleri, paylaşım ve uzman eşlemesi aynı modül tanımını kullanıyor; 32 paylaşım seçimi kontrolü geçti. |
| 8 | Ruh Sağlığı | Kullanıcıya görünen eski modül adları kaldırıldı; /mental ve iç teknik kimlikler korundu. Gerçek konuşma yanıtları ortak sabit yönerge dedup’una alınmadı. |
| 9 | Footer | Gizlilik ayrı alt satırda relative /privacy; native %200, dar ekran ve klavye geçti. |
| 10 | Uzman ve saatler | Beş branş/route, kullanıcı aralığı, saat dilimi ve süre payload’ları geçti. Kaynak tarih/saat doğrulaması ve aralık hesabı geçti. Gerçek sağlayıcı erişim koruması nedeniyle FALLBACK_BLOCKED döndü; 0 doğrulanmış saat, boş liste/güvenli bağlantı. Canlı müsaitlik kabulü açık, rezervasyon yapılmadı. |
| 11 | Sağlık Merkezi menüsü | Dört ana öğe ve beş gerçek alt bağlantı; mouse/klavye/ESC/dış tık/odak/route/back/forward/native %200 geçti. |

## Anlık fotoğrafın sınırları

Son production taramasındaki sarkma indeksi: alın `0.00000264296` (UI’da `0`); göz altı torbalanması `0`, kalite geçerli. Bunlar **bu görünüm formülünde destekli sinyal bulunmaması**, klinik olarak sarkma/torbalanma yokluğu değildir. Sağ ve sol yanak `null / ANATOMICAL_BAND_NOT_VISIBLE`; çene `null / HARD_DIRECTIONAL_SHADOW`. Yetersiz veri sağlıklı sıfıra çevrilmedi. Eski kişisel değişim oranları yeni sonuç diye sunulmadı. Bu fotoğraf seti yeni yöntemin pozitif insan doğrulamasını sağlamaz.

Formül, tüm sabitler, anatomik sinyaller, kaynak koordinatları ve kısıtlar [instant-appearance-v2.md](instant-appearance-v2.md) içindedir. Kısa formül: sarkma `100 F √E C √B`; torbalanma `100 F √E C`. F çift taraflı lokal parlaklık vadisi, E çift taraflı kenar, C kesintisiz eğrisel destek, B bağımsız görüntüden takip edilmiş lokal kontur desteğidir. Yaş, z derinliği, tarihsel değişim, fotoğrafa özel min/max veya klinik olasılık kullanılmaz. Tek RGB görüntüde makyaj, saydam gözlük ve tüm gölgeleri güvenilir biçimde ayırmak mümkün değildir; düzgün konturlu gerçek klinik sarkma da bu mühendislik sinyalinde yakalanmayabilir.

## Kontroller ve kanıtların türü

Son build için dokuz production senaryosu PASS: guidance, hearing-positive, dental-history, hearing-tone, audio-focus, vision-negative, skin, responsive, care. Sekiz `proof.json` aynı BUILD_ID’yi taşır; görme negatif senaryosunun gerçek izleri `vision/open-probe.json` ve ayrı owned-runner PASS logundadır. Kamera girdileri kontrollü lisanslı video, diş girdisi gerçek lisanslı yerel fotoğraf, işitme gerçek 48 kHz PCM’dir. Yanıtlar kontrollü/simüledir; canlı insan etkileşimi yapılmış gibi sunulmaz. Görmede mevcut erken/tam/iki parçalı ve sıra-serbest yanıt ile echo ayrıştırması unit regresyonlarla korundu; son build browser kanıtı iki-göz-açık negatif kapısına aittir, pozitif 24-deneme insan kabulü değildir.

Production build lint/typecheck geçti (iki mevcut lint uyarısı). İlgili son regresyon grupları 46 ve 18 test geçti; düzeltilen loader/geriye uyum grubu 22 test geçti. Önceki geniş koşuda 343 test geçmiş, altı test loader bağımlılığı nedeniyle kalmıştı; altısı onarılan grupta yeniden geçti. Tek bir temiz tam-suite koşusu yapıldı diye raporlanmaz. Ayrıntılı yerel loglar korunur; kaynak değişmeden başarılı kontroller gereksiz tekrarlanmadı.

Normal Windows launcher lifecycle: yeni build açma, tekrar açmada sahipli servisleri kullanma, ilk pencereyi kapatınca servisleri koruma, son pencereyle yalnız sahipli temizleme, profil sürekliliği, yabancı portu sahiplenmeme ve başarısız başlangıçta temizleme geçti. Son zincir doğrulaması delivery.json’da kaynak/derleme/model/ses hash’lerini ayrıca denetler. Başka Chrome pencereleri veya kullanıcı kayıtları değiştirilmez.

## Güvenlik ve korunmuş artefaktlar

npm production audit: **0 bulgu**. Tüm bağımlılık/dev audit: **7 high + 2 moderate açık**; production bulgusuzluğuyla gizlenmez. İzole Python runtime sürümleri normal launcher sağlık yanıtında doğrulanır. Ücretli sağlayıcı çağrısı, model eğitimi/eşik ayarı veya gerçek rezervasyon yoktur.

Diş ONNX SHA256 `eafaca8139e4447b1aa64375156aa47764affd91cf0594392b896ea78463bf03`; confidence `.35`, 35,800,550 byte. Fotoğraflar, fixture arşivleri, denetim ekran görüntüleri, kişisel veriler ve secret’lar GitHub’a dahil edilmez. PR #2 Draft kalır; main’e merge yapılmaz.
