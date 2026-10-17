# Sağlık arayüzü, izin ve ses düzenlemeleri — 17 Ekim 2026

Tek izole uygulama: **http://127.0.0.1:3308/**. Normal başlatıcı/checkout değiştirilmedi; push ve main merge yapılmadı. Teknik teslim, fiziksel/klinik kabul anlamına gelmez.

- Başlat: bu checkout içindeki `Start-Health-UI.ps1`.
- Durdur: `Stop-Health-UI.ps1`.
- Kaynak: `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-cdc-health-ui-20261017`.
- Kanıt: `C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\health-ui-consent-audio-followup-20261017`.
- Kesin BUILD_ID, varlık kimlikleri ve sonuçlar: yanındaki `health-ui-consent-audio-followup-20261017.json`. Son yerel SHA ayrıca kanıt klasörünün `status.json` ve `delivery-receipt.json` dosyalarında bulunur.

## Birleştirme ve koruma

| Başlangıç / dondurulmuş teslim | Bu alanda kullanılan yol |
|---|---|
| Kaynak `5f11c111e3f6547e6420ddf37db477190d232f10` | Salt okunur kaynak; mevcut iki görev belgesi korunur. |
| Cilt `2637d1b3a342d333b43a40d53e195e8374c8691d` | Yeni worktree doğrudan bu teslimden açıldı; `ebd44bc → 29b9979 → f230cce → 2637d1b` bağımlılıkları içerilir. |
| Göz `1cdb95ebdddd3a2fd4b83cca7408a1ae6cd3b502` | `57d4a75` olarak aktarıldı; spoken resume ve geometri doğrulaması korunur. |
| Ruh `eead4b23d92dc40887a3ed223628b2e1297cddea` | `88e5b8d` olarak aktarıldı; pending turn, epoch ve kayıt korumaları korunur. |

Ortak API adresi çatışması, sayfa/araç/mahremiyet çağrılarını aynı izole backend'e yönlendiren mevcut `localBackend` sözleşmesiyle çözüldü. Cilt preview adresi ve CSP bu teslimin 8308 portuna uyarlandı. Varsayılan normal kurulum adresleri korunur.

Altı korunan checkout'un HEAD/status kontrolü, kaynak görev belgelerinin önceki dondurulmuş makbuzla birebir hash karşılaştırması ve 32 mevcut backend yönteminin birebir karşılaştırması `served-protection-receipt.json` içindedir. AG/Claude ağaçlarına, kullanıcı profillerine veya normal kullanıcı tarayıcısına yazılmadı.

Genel sivilce manifesti değiştirilmedi: **accepted:false / file:null** korunur. Önceki V5 teslimindeki yerel preview yalnız bu izole uygulamada aynı opt-in ile bulunur; yeni genel aktivasyon veya model kabulü değildir. Detector/verifier dosyaları mevcut teslimden hash doğrulamasıyla alındı. Yeni eğitim, model arayışı, eşik değişikliği veya araştırma tekrarı yapılmadı.

## Emel engelinin gerçek sonucu

İlk yerel kaynak incelemesinde kurulu `edge-tts 7.2.8` bulundu. İlk sınırlı canlı teşhiste katalog çalıştı ve Emel listelendi; sentezin WebSocket handshake aşaması **403** verdi. Önceki endpoint bunu genel HTTP 503'e çeviriyordu. Mesaj/URL/anahtar içermeyen aşama, hata türü ve upstream durum bilgisi artık tutulur.

[Resmî 7.3.0 sürümü](https://github.com/rany2/edge-tts/releases/tag/7.3.0) Sec-MS-GEC v2 desteğini, [7.3.1](https://github.com/rany2/edge-tts/releases/tag/7.3.1) tarih ayrıştırma düzeltmesini içeriyor. Yalnız bu worktree'nin `.runtime/edge-tts` hedefine 7.3.1 kuruldu; global/site-packages değiştirilmedi. Gereksinim sürümü sabitlendi. Başka endpoint sağlayıcısı, ses, ücretli TTS veya sessiz fallback eklenmedi.

| Sınırlı canlı deneme | Gerçek sonuç |
|---|---|
| 1 — eski bağımlılık | Katalogda exact Emel var; WebSocket 403, ses yok. |
| 2 — gerçek `/api/mental/speech`, yeni bağımlılık | HTTP 200; yeni yalnız-sesli giriş yönergesi, 57.168 bayt MP3. Yerel dosya/manifest SHA eşleşti. |
| 3 — tarayıcıdaki dinamik yanıt yolu | Bir gerçek TTS isteği; native Audio `playing/ended`; MSE playback; dalga tepesi 0,34788, bitiş/duraklatma 0. |

Toplam üç üst-seviye seslendirme denemesi yapıldı; uygulamaya retry döngüsü eklenmedi. Eski SDK'nin 403 için kendi sınırlı saat-düzeltme tekrarı bulunduğu ayrıca kaynak incelemesinde görüldü. Canlı playback kontrolündeki yanıt kişisel olmayan kontrollü bir metindi; gerçek canlı TTS ve uygulamanın normal ses yolu kullanıldı, yeni bir canlı LLM görüşme kampanyası yapılmadı. Dinamik kontrol eski ses dosyasını kullanmadı. Teknik metadatanın ilk kayıt yolundaki hata mevcut başarılı denemenin dosya/hash bilgisinden düzeltildi; aynı isteği yeniden çalıştırmadı.

**tr-TR-EmelNeural / -10% / -10Hz** korunur. Transport bağlantı/okuma sınırları 5/15 saniye, uygulama isteği 30 saniyedir. Akış başladıktan sonraki hata da yarım sesi başarılı yanıt gibi tamamlamaz. Güncel sınırlı kontrollerde Emel teknik engeli kapandı; doğal telaffuz kabulü henüz yapılmadı.

## Yalnız sesli görüşme ve oturum bağlamı

Mesaj alanı, Gönder, yazılı moda geçiş, yinelenen mute düğmesi ve yazmaya yönlendiren görünür/sesli metinler kaldırıldı. Başlat/Bitir ve Duraklat/Devam et korunur. Görüşme dökümü ekranda kalır; isteğe bağlı geçmiş/transkript tercihleri değişmez. Sol bölümde görünür “Seslendiriliyor” metni yoktur; speaking durumu ve erişilebilir açıklama korunur. Ses/ASR hatası görüşmeyi dürüstçe durdurur; yazılı yedek veya sahte dinleme durumu yoktur.

Header hoparlörü tek ses çıkışı kontrolüdür. Mikrofon tercihini değiştirmez. Ruh görüşmesinde çıkış mute iken giriş dinlemesi ayrı çalışır; açık Duraklat her iki kaynağı durdurur. Göz/işitmede gerekli yönerge/test sesi kesilirse görev güvenle duraklar; yanıt/ölçüm uydurulmaz.

`extractive-user-quotes-v1`, eski tamamlanmış kullanıcı turlarından **birebir alıntıların sınırlı belleğini** yakın turlarla birlikte taşır. Yeni model veya servis kullanılmaz; mevcut sağlayıcı seçicisi kullanılır. Üretilmiş/atıfsız bilgi reddedilir, alıntılar kaynak sırasına yerleştirilir ve sonraki kullanıcı düzeltmeleri önceliklidir. Bu, bütün eski konuşmayı eksiksiz saklama iddiası değildir; kontrollü erken bilgi/düzeltme kontrolleri geçti.

- Güncelleme tetikleri: 32 yakın mesaj veya 80.000 yakın karakter.
- Güncellemeden sonra bırakılan yakın pencere: en fazla 16 mesaj ve 48.000 karakter; tamamlanmış tur çiftleri bölünmez.
- Bellek: en fazla 32 alıntı, alıntı başına 2.000, toplam 16.000 karakter.
- Mevcut converse 40, özet 200 mesaj / 120.000 karakter sınırları kaldırılmadı. Her ağ aşaması kendi 30 saniyelik sınırını korur; mevcut sağlayıcı retry=0 davranışı korunur.
- Eski prefix yalnız geçerli bellek cevabı alındıktan sonra ilerletilir. Güncelleme başarısızsa önceki bellek/prefix korunur, görüşme görünür biçimde duraklar ve açık Devam et gerekir.
- Son özet eski belleği ve henüz özetlenmemiş yakın turları kullanır; 200 mesajı aşan tam transcript gönderilmez.
- Tur sayısına bağlı otomatik bitiş yoktur. Kullanıcı düğmesi/açık bitirme komutu, sürüş, kriz, izin ve hata korumaları korunur.
- Bellek yalnız ilgili oturumun RAM'indedir; yeni oturum sıfır bellek/geçmiş bağlamıyla başlar. Backend oturum belleği yazmaz. Transcript saklama izni bu bellek üzerinden açılmaz; eski kayıtlar yeniden yazılmaz.

Kontrollü **110 tur / 220 mesaj** denemesinde erken bilgi ve düzeltme korundu, en büyük yakın istek 32 mesajdı; son özet **22 yakın mesaj + 6 alıntı** ile oluştu. Bir bellek hatasında önceki istek aynen korunup açık devamla tamamlandı. Son production controller ayrıca 22 turluk odaklı kontrolü geçti. Ayrıca 15×6.000 karakterlik kontrollü girişte karakter tetikli güncelleme çalıştı; en büyük yakın istek 78.169 karakterdi, son özet 16 mesaj / 48.104 karakterle sınır içinde kaldı. Bu kontrollerde canlı LLM/TTS çağrısı yapılmadı.

## Tek ve kalıcı izin akışı

Modal ve Gizlilik sayfası aynı sürümlü `attune_health_processing_v1` kaydını okur/yazar. Onay kaydı yazılıp geri okunmadan erişim açılmaz. İzin yoksa sayfa bileşeni mount edilmez; kamera/ASR/analiz başlamaz. Onay kamera veya mikrofonu otomatik başlatmaz.

| Modül | İlk giriş | Yenileme / tekrar giriş | Gizlilik / diğer sekmeden geri çekme |
|---|---|---|---|
| Göz | İşaretlenmemiş modal; yerel işlem + ses hizmeti açıklaması | Yeniden checkbox yok | Modal geri gelir; geç gelen kamera akışı kapatıldı. |
| Cilt | İşaretlenmemiş yerel işlem modalı | Yeniden checkbox yok | Modal geri gelir; geç gelen kamera akışı kapatıldı. |
| Diş | İşaretlenmemiş yerel işlem modalı | Yeniden checkbox yok | Modal geri gelir; geç gelen kamera akışı kapatıldı. |
| İşitme | İşaretlenmemiş yerel test modalı | Yeniden checkbox yok | Hazırlık sesi durdu, işitme AudioContext kapandı, kayıt oluşmadı. |
| Ruh | ASR, OpenAI işleme ve Emel için ayrı işaretlenmemiş kutular | Yeniden checkbox yok | ASR/ses/request iptal edildi; gecikmiş cevap yeni kayıt oluşturmadı. |

İlk modal aşamasında her modülde gözlenen sağlık çağrısı **0**. Reddetme güvenle Kokpit'e çıkar. Enjekte edilen depolama hatasında modal açık kaldı ve medya başlamadı. İşleme izni; native kamera/mikrofon yetkisi, Roboflow izni ve isteğe bağlı sayısal/fotoğraf/transkript saklamasından ayrıdır. Bu tercihlerin varsayılanları açılmadı. Gövdelerdeki hizmet checkbox'ları kaldırıldı; Gizlilik yönetimi korundu ve merkezi hizmet izni kaldırma satırları eklendi.

## Ekranlar, görseller ve gerçek ses dalgası

Diş/işitme girişleri cildin görsel/metin sütunu, tipografi, boşluk ve ikon yaklaşımını kullanır. Dişte yalnız ağız/diş bölgesinde temsili ağ, işitmede kulağa ulaşan ses dalgaları vardır. İki portre de bu görev için yetkili built-in `image_gen` ile üretilmiş kurgusal insan görselleridir; hasta fotoğrafı veya tanısal sonuç değildir. Dosya kimlikleri ve üretim promptları JSON makbuzundadır. Üretilen görseller ve MP3 yerel varlık olarak kalır; bu yeni commit'e fotoğraf/ham ses/konuşma eklenmez.

Yerel görseller: `apps/vehicle-app/public/assets/dental-preparation-v1.png`, `hearing-preparation-v1.png`. Eski cilt hazırlık görseli korunur. İstenen diş/işitme/cilt kısa giriş metinleri kaldırıldı; kamera, dört açılı diş, saf ses ve sayı testi protokolleri değişmedi.

AIswers salt okunur incelendi. Bir React bileşeni yerine `scripts/build-week15-main.js` içindeki gerçek ses örneklerinden `showwaves` üreten FFmpeg hattı bulundu; bulunmayan bileşen varmış gibi gösterilmedi. Attune dalgası oynatılan uygulama sesinin Analyser zaman verisinden hesaplanır. Yeni mikrofon dinleme, rastgele/CSS konuşma animasyonu, gain veya ikinci duyulur bağlantı yoktur.

Bekleme/sessizlik/mute/ended/hata/iptal/route çıkışında dalga sıfırlanır. Canlı Emel ölçümünde ses çalarken üç sessiz örnek de 0 verdi; ritim gerçek örneklere bağlıdır. Kaynak/analyser bağlantıları ayrılır, RAF sonlanır, boş ortak context askıya alınır; işitmenin kendi motoru kapatılır. Gerçek OfflineAudioContext stereo karşılaştırmasında 2×2.048 örneğin maksimum farkı **0**, bit düzeyinde eşleşme vardır. Tek çıkış yolu ses seviyesini/kanal ayrımını değiştirmedi.

Masaüstü 1440 ve dar 390 genişlikte diş/işitme/cilt/ruh ekranları çekildi; kırık görsel ve yatay taşma yok. Kanıtlar: `output/playwright/health-ui/{dental,hearing,skin,mental}-{desktop,narrow}.png`. Header yükseklikleri makbuzda bulunur.

## Doğrulama ve güvenli yerel teslim

Odaklı pytest sonucu, typecheck ve production build makbuzları JSON raporundadır. Gerçek sunulan **38 JavaScript** dosyası source/build makbuzundaki SHA-256 ile eşleştirilir; test ASR/provider override'ları production bundle'da yoktur. Backend test ledger endpoint'i 404'tür. Araştırma/NN deneyleri tekrar çalıştırılmadı.

Başlatıcı build/kaynak/varlık hash'lerini denetler; süreçleri gizli başlatır, caller environment'ı geri yükler ve anahtarı yalnız backend belleğinde mevcut kaynaktan kullanır. Kayıtlar ayrı progress data dizini ve ayrı tarayıcı profiline aittir. Başka port sahibini değiştirmez; yalnız PID/başlangıç zamanı/komut/checkout/build kimliği doğrulanmış kendi çalışan teslimini yeniden kullanabilir. Durdurucu yalnız aynı kimliği tekrar doğrulanan kendi server süreçlerini kapatır. Başlat/durdur/yeniden başlat ve mevcut sahipliği güvenle yeniden kullanma çalıştırıldı.

Teknik blocker kalmadı. Son ortak fiziksel kabul hâlâ ayrıdır; aşağıdakiler bu teslimle yapılmış sayılmadı:

1. Gerçek kullanıcı/kamera ile cilt ve dört açılı diş çekimi, göz kapatma/örtme koşulları.
2. Doğal Türkçe konuşma, sözlü duraklat/devam/bitir ve ilk mikrofon izin akışı.
3. Onaylı Emel/Ahmet seslerinin telaffuz, doğallık ve gerçek cihazdaki çakışma kabulü.
4. Gerçek stereo kulaklıkta sol/sağ kanal, sessiz ortam ve işitme görevlerinin fiziksel kabulü.
