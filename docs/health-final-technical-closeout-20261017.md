# Beş sağlık modülü: ortak giriş ve teknik kapanış

Başlangıç: `09d3cd159c1c614f27cb9911e975b7b1eb0d52d9`, doğrulanmış temiz birleşik dental checkout. Çalışma yalnız `attune-cdc-health-final-technical-20261017`, `research/health-final-technical-closeout-20261017` dalındadır. Son commit/build kimliği dış kanıt klasöründeki `delivery.json` ve `status.json` ile bağlanır. Normal Windows kısayolu, kullanıcı profili ve önceki teslim alanları değiştirilmedi; push/merge yapılmadı.

Kanıt kökü: `../cdc-progress/health-final-technical-closeout-20261017`. Kullanıcı fotoğrafı/kaydı/anahtarı rapora alınmadı. Sayısal tarayıcı senaryoları açıkça belirtilmiş izole sentetik kayıtlardır. Diş entegrasyonu önceki kayıtlı geliştirme envanterindeki tek mevcut kaynakla yerel olarak çalıştırıldı. Fiziksel kullanıcı ve klinik kabul **açık**.

## Giriş ekranları

`HealthStartCard` beş hazırlık ekranını aynı yapıda toplar: 1024 CSS px masaüstü kartı, 360 × 450 portre, sağda kısa başlık/ikonlar/hazırlık ve mevcut başlatma eylemi. 390 px dar pencerede kartlar 352 px, portreler yaklaşık 302.67 × 378.33 px; yatay taşma yok. `delivered-screens.json` on görünümün ölçülerini ve sıfır otomatik kamera çağrısını kaydeder. `delivered-<modül>-desktop/narrow[-card].png` görüntüleri açılıp incelendi. Başın üst sınırı, çene ve üst omuzlar kaynakta tamamdır; `object-contain` kırpma/esnetme yapmaz.

| Modül | Önce | Sonra |
|---|---|---|
| Cilt | Onaylı kişi ve temsili mesh referansı | Aynı kimlik/mesh, tam baş ve omuz kadrajı; üç açılı gerçek çekim değişmedi |
| Diş | Baş eğik, ağız motifi daha kaba | Dik/frontal doğal gülümseme; görünür diş yayını izleyen ince temsili ağ; kamera + yükleme korunuyor |
| İşitme | Saçın üstü kesik | Tam baş, doğal kulak görünürlüğü ve kenarda ses dalgaları |
| Göz | Farklı, liste ağırlıklı giriş | Aynı sol portre/sağ metin düzeni; harf/yön protokolü değişmedi |
| Ruh | Farklı giriş düzeni | Aynı portre/sağ metin düzeni; yalnız sesli, tanı/ifade skoru veya yazılı fallback yok |

Kalıcı beş PNG, üretim kimlikleri, referans hash'leri ve prompt seti `health-preparation-assets-20261017.json` / `health-preparation-prompts-20261017.md` içindedir. Önceki görseller korunmuştur. Yeni kalıcı izin/mute paneli eklenmedi. Aktif test, sonuç, geçmiş ve analiz yöntemleri yeniden tasarlanmadı.

Gerçek Chrome %200: ayrı kalıcı test profili, native zoom tercihi, `visualViewport.scale=1`, CSS zoom=1 ve yaklaşık yarıya düşen CSS viewport ile doğrulandı. Windows ölçeği nedeniyle DPR=3 olması tek başına %200 kanıtı sayılmadı. `native200-proof.json` gerçek viewport ve tercih seviyesini taşır. Normal dikey kaydırma kullanılır. Playwright full-page clip'i native zoom'da yanlış bitmap alanı verdiği için nihai görüntüler doğrudan görünür Chrome compositor yüzeyinden, clip/resize olmadan alınır; OS masaüstü görüntüsü olduğu iddia edilmez.

## Bu görevde bulunan gerçek ortak hata

Diş/işitme paylaşım adaptörü `.at(-1)` ile listede en eski kaydı seçiyordu; mevcut yazma sözleşmesi bu iki türde yeni kaydı başa ekler. Ayrıca ölçüm kalitesi geçersiz olduğu hâlde kalan sayıyı yazdırabiliyordu. `test_health_share_latest.py` düzeltme öncesi başarısız oldu. Düzeltme, saklanan diziyi değiştirmeden en güncel kaynak zamanını seçer; geçersiz/null/sonlu olmayan ölçümü sayı veya sağlıklı sıfır yapmaz. Saf seste desteklenmeyen eşik de ölçülmüş gibi yazılmaz. İki farklı dizi sırası, yeni/eski tarih, dental kalite ve üç işitme kalite durumu sonrasında geçer. `share-before.log`, `share-after.log`; gerçek son ürün önizlemesi ve üretilen yerel PDF `print-proof.json` / `selected-summary.pdf` ile doğrulanır. OS yazıcısı veya başkasına gönderim yapılmadı.

## Ortak F107–F130 uzlaştırması

Eski ana tablo salt okunur bırakıldı. Aşağıdaki durumlar bu teslimin kanıtını ve sınırlarını belirtir; geçmiş kampanyalar yeni yapılmış sayılmaz.

| ID | Güncel durum | Kanıt / açık sınır |
|---|---|---|
| F107 Beş modül/menü | CONTROLLED_PATH_VERIFIED | `common-proof.json`: canonical sıra, gerçek dropdown → beş yol → kokpit |
| F108 Kokpit/geçmiş carousel | CONTROLLED_PATH_VERIFIED | Gerçek kayıt kartından grafik dialog'u; kalıcı alt panel eklenmedi |
| F109 Tarih/kriter/bölge | CONTROLLED_PATH_VERIFIED | `common-proof.json`: depolanmış kayıtlar, tarih/ölçüm/çene seçimi, ayrı yöntem serileri; ilgili adapter regresyonları |
| F110 Tooltip | CONTROLLED_PATH_VERIFIED | Odaklanan gerçek grafik noktasında tarih/ölçüm/bölge/değer; merkezi Türkçe etiket |
| F111 Null/birim | CONTROLLED_PATH_VERIFIED | 2 depolanmış sayısal fixture noktası + null/uyumsuz kayıt boşlukları; sahte sıfır yok; paylaşım kalite regresyonu |
| F112 Paylaşım | CONTROLLED_PATH_VERIFIED | Yalnız seçili alan; en güncel kayıt; gerçek üretilmiş HTML → yerel PDF, iframe temizliği. Gönderim/OS yazıcı kabulü değil |
| F113 Demo ayrılığı | PRESERVED_AND_CHECKED | Normal yollar, sıfır tamamlanmamış kayıt; demo kaynak/anahtarları değişmedi |
| F114 Fotoğraf izni | CONTROLLED_PATH_VERIFIED | `upload-partial.json`: ayrı varsayılan kapalı opt-in; fotoğraf numeric payload'a girmiyor; gerçek IDB regresyonları |
| F115 Tek fotoğraf+sayısal silme | CONTROLLED_PATH_VERIFIED | Güncel gerçek IDB rollback/reopen testi, source-map/test fixture düzeltmesi; UI tek silme ve reload |
| F116 Tüm kayıt/harita silme | CONTROLLED_PATH_VERIFIED | İzole beş-store wipe, aynı izole backend; kullanıcı deposuna dokunulmadı |
| F117 Kota/yarım yazım | CONTROLLED_PATH_VERIFIED | 5 modülde izin yazımı kapalı; IDB/numeric journal rollback ve crash recovery |
| F118 Genel sayfa sessizliği | CONTROLLED_PATH_VERIFIED | Route çıkışı, eski pending yanıt; dalga sıfır; menü/genel sayfa yeni TTS tetiklemedi |
| F119 Exact Ahmet/Emel | PRESERVED_BYTE_IDENTITY | Mevcut ses bankası/manifest hash'leri aynı; kontrollü gerçek native audio/MSE. Yeni ses üretimi veya canlı kampanya yok |
| F120 Yerel yüz/el | PRESERVED_BYTE_IDENTITY | Mevcut task/WASM dosyaları ve HTTP bayt hash'leri; dental gerçek yerel MediaPipe yolu. Yeni fiziksel göz/çekim doğrulaması değil |
| F121 Sabit göz ses bankası | PRESERVED_BYTE_IDENTITY | Mevcut Ahmet manifest/dosyaları korunuyor; yeni prompt/ses/protokol yok |
| F122 Kaynak sahipliği | CONTROLLED_PATH_VERIFIED | 3 geç kamera callback'i ended; mental ASR/audio iptali; hearing context closed; bağımsız native canvas stream live kalıyor |
| F123 Park | CONTROLLED_PATH_VERIFIED | Gerçek izole frontend/backend sürüş toggle; dental kamera/yükleme disabled, PARK'ta dönüş; API 409 regresyonu |
| F124 Beş uzmanlık | CONTROLLED_PATH_VERIFIED | Göz/Dermatoloji/Diş/KBB/Klinik Psikoloji payload'ları `common-proof.json` |
| F125 Canlı müsaitlik | OPEN_EXTERNAL | Kontrollü 503 unavailable doğrulandı; yeni canlı dış servis araması/müsaitlik kabulü yapılmadı |
| F126 Sağlayıcı yönlendirme | PRESERVED_AND_CHECKED | Mevcut bağlantı/bağlam korunuyor, yeni sağlayıcı yok; rezervasyon yapılmadı |
| F127 Production audit | CURRENT_AUDIT_ZERO | `npm-audit-production-final.json`: 0. Bu tüm güvenlik/klinik kabul anlamına gelmez |
| F128 Dev audit | OPEN_DEV_DEPENDENCIES | 7 high, 0 moderate. Dar parser pin'i; aşağıdaki upstream/bundled sınırlar açık |
| F129 Responsive/%200 | CONTROLLED_VISUAL_VERIFIED | On aynı ölçekli masaüstü/dar görünüm; gerçek native %200 ve kaydırılan eylemler |
| F130 Başlatıcı/kimlik | ISOLATED_CHAIN_VERIFIED | Yerel commit → build/source → sunulan JS/public varlıklar → backend model hash'leri. Normal Windows kısayolu değiştirilmedi ve yeni sürüme teslim edilmiş sayılmadı |

## Kaynak ve hata kontrolleri

- Son tek build üzerinde kısa ilk izin/reentry/reload/cross-tab revoke/ret; izin öncesi sağlık isteği ve otomatik fiziksel kamera sayısı 0.
- Dental/vision/skin'in gerçek ürün capture callback'lerinde kontrollü native canvas stream kullanıldı; geç gelen her owned track kapandı, kayıt oluşmadı. Bağımsız fixture stream kapanmadı; test sonunda yalnız testin kendi fixture'ı temizlendi.
- Ruh: kontrollü ASR/provider ve mevcut Emel klibi; header mute girdiyi koruyor, pause iki tarafı durduruyor, speech 503 dürüst error ve ASR/audio stop, route cleanup ve pending turn abort. Yeni canlı/ücretli LLM/TTS çağrısı yok. Sağlayıcı-status salt-okunur yapılandırma kanıtıdır; canlı servis kalitesi kabulü değildir.
- İşitme: gerçek native audio ve AudioContext revoke sonrası owned engine closed, header dalgası 0 ve tamamlanmamış kayıt 0. Önceki tam saf ses/sayı kampanyası tekrarlanmadı.
- Diş: mevcut tek kısmi kaynak → gerçek yerel MediaPipe giriş yolu → mevcut ONNX → 8 aday, kart=kutu listesi → tek opt-in kayıt → aynı kaynak/kutularla reload/geçmiş. Model başarı/klinik doğruluk ölçümü değildir. Native filechooser otomasyonunun sonuç üretmeyen koşusu kanıt sayılmadı; başarılı mevcut input upload yolu ayrı kaydedildi.
- Yanlış içerik/izin/park/geometri/model çıktısı ve deadline: ilgili yerel sınır regresyonları başarısız kapalı; gerçek hata detayı/ham medya dışarı echo edilmiyor.
- Hatırlatma helper'ı: 28 takvim günü, gerçek ICS/VALARM içeriği, geçersiz tarih/ID, kota hatası, güncelleme/iptal testleri güncel kaynakla geçti. Mevcut UI yalnız plan/ICS der; yeni OS bildirimi kurulmadı, takvim hesabına aktarım veya bildirim teslimi doğrulanmadı.

## Güvenlik düzeltmesi ve açık risk

`fix-finding` sonucu: **comprehensive resource-exhaustion closure BLOCKED**; dar advisory paket güncellemesi uygulanmış ve uyumluluğu doğrulanmıştır. Uygulama request yolundan saldırgan selector'ı derleyen endpoint bu sınırlı incelemede bulunmadı; runtime exploitability kanıtlanmadı.

Kaynak→sink: repo Tailwind content/globals.css → Tailwind selector helpers / postcss-nested → senkron parser. Normal PostCSS/Next yolundaki iki tüketici tek `7.1.6` kopyasına çözülür. Başka checkout'un junction bağımlılıkları değiştirilmedi; görev alanına yerel özel kopya alındı. Lock'ta yalnız bu paketin sürüm/URL/integrity üçlüsü değişti; framework major değişmedi. Callers'ın `^6` aralığını geçen exact override olduğu açıkça kaydedilir.

Meşru kontroller: beş parser round-trip, nested parent/child, Tailwind responsive/group/peer/arbitrary variant/pseudo/@apply/prefix/important; baseline ve patch CSS SHA-256 aynı. `selector-baseline.json` ve `selector-patched.json` zamanları timeout'lu child process'lerden gelir. İlk mixed 8k girdisi yaklaşık 280 ms idi; patch ilk koşuda yaklaşık 50 ms. Bunlar genelde linear karmaşıklık ispatı değildir. Orijinal class/ID örneği yeni pakette bounded kontrolleri geçer. [Maintainer advisory](https://github.com/advisories/GHSA-rj75-hqrm-r3gf).

Bağımsız post-patch inceleme ve yerel doğrulama: `1…1.a.a…` numeric-prefix girdisinde upstream regex tekrar taraması hâlâ maliyetlidir; 2k/4k/8k sınırlı ölçümleri makbuzdadır. Bu nedenle bütün parser CPU sınırı kapandı denmez. Tailwind'in normal Next/PostCSS yolunda kullanılmayan CLI `peers` bundle'ında da eski gömülü parser baytları kalır; exact override bunu yamamaz. Kurulu vendor dosyalarına özel yama yapılmadı.

Kalan 7 high audit zinciri braces/micromatch/fast-glob/chokidar/Tailwind/Next ESLint geliştirme bağımlılıklarıdır. Braces advisory'de güvenli pin yapılabilecek patched sürüm yok; audit'in geniş major/downgrade önerisi uygulanmadı. [Braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). `npm audit fix --force` kullanılmadı. Production 0, dev 7 high açık olarak birlikte raporlanır; bütün güvenlik kapanışı iddiası yok.

## Doğrulama ve başlatma

İlgili 45 regresyonda 44 geçti, bir eski skin atomic-deletion fixture'ı eksik yeni dental/serviceConsent modül yükleyicisi nedeniyle hata verdi. Yalnız fixture düzeltildi; gerçek IDB restart/rollback testi yeniden geçti. Ek dört boundary testi ve paylaşımın iki dar testi geçti (komutlar arasında tekrar edilen test vardır; toplam farklı test sayısı olarak toplanmaz). Yeni TSX'ler React bileşen/erişilebilirlik/hook kontrolünden geçirildi; yeni effect/fetch/state döngüsü eklenmedi. Typecheck ve production build makbuzları kanıt klasöründe. Önceden var olan img/hooks lint uyarıları gizlenmedi; sıfır lint warning iddiası yok.

`Start-Health-Final.ps1 -NoBrowser` loopback 3311/8311'i, kendi backend-data klasörünü ve source/build/asset hash'lerini doğrular. Default açılış kendi ayrı Chrome profilini kullanır. `Stop-Health-Final.ps1` yalnız kaydedilmiş PID + başlangıç zamanı + komut + workspace eşleşmesinde durdurur; başka port/sahiplikte kapalı kalır. Başlat/durdur/yeniden başlat makbuzu `restart-proof.json` içindedir. Sunulan HTTP public varlıkları ile yalnız backend'de kalan model dosyaları `delivery.json` içinde ayrı işaretlidir.

Sunucu CWD'leri bu checkout içindedir. Windows'un `conhost.exe` yardımcıları sistem CWD'sinde çalışır; bunlar yanlışlıkla Next worker diye sayılmaz, exact parent PID/başlangıç/komut sahipliğiyle ayrı sınıflandırılır. Son build 613.66 MiB toplam RSS ölçtü. Önceki 650 MiB ölçümü esas alınarak görev bütçesi 900 MiB, başlangıç bütçesi 1200 MiB oldu; ortak atomik lease ve 400 MiB canlı sistem rezervi değiştirilmedi. Guard başarısız olursa yalnız kendi doğrulanmış build alt süreçleri durur; yabancı süreç veya eğitim kapatılmaz. Bu kaynak kararı kaliteyi/protokolü veya analiz bütçesini değiştirmez.

## Açık kabul sınırları

- Dev bağımlılık açıkları, residual parser karmaşıklığı ve canlı uzman/müsaitlik yukarıdaki gerekçelerle açıktır; fiziksel teste devredilerek kapatılmaz.
- Süt dişi zayıf `d` sınıfı; doğal birikim/dizilim/zor negatif kapsamı; diğer modüllerin mevcut algılama/veri sınırları; sivilce genel kabul/kullanım hakkı bu görevle çözülmedi.
- Genel sivilce manifesti `accepted:false, file:null` kaldı. Önceki ayrı izole V5 preview bayrakları yeni genel aktivasyon sayılmaz.
- Kullanıcı kayıtları taşınmadı, yeniden hesaplanmadı veya silinmedi. Yalnız görev profillerinin sentetik kayıtları/fixture fotoğrafları kullanıldı.

## Tek ortak fiziksel kullanıcı oturumu — henüz yapılmadı

1. Araç parkta ve ortam sessizken bir kez gerçek webcam/mikrofon native izni verin; stereo kulaklığı takıp rahat ses ayarını koruyun.
2. Gözlüksüz yüzle ciltte önden/iki yandan doğal kısa baş hareketlerini yapın; yüz ayrıntısı/kadrajın gerçek kamerada algılandığını gözle kontrol edin.
3. Göz görevinde söylenen gözü kapatın/örtün, gerçek harf ve yönü sesle söyleyin; sistemin gerçekten duyduğu yanıta göre ilerlediğini deneyimleyin.
4. Dişte başı rahat/dik tutup doğal ön, sağ, sol ve kapanış görünümlerini gösterin; ışık ve ağzı zorlamama koşulunu insan olarak değerlendirin.
5. İşitmede yalnız sol/sağ sesin doğru kulakta duyulduğunu, rahat tonları ve gürültüde üçlü sayıları gerçek kulaklıkla dinleyip yanıtlayın. Klinik kalibrasyon sonucu saymayın.
6. Ruh görüşmesinde doğal konuşma, duraklama ve araya girme yapın; gerçek mikrofon tanıması ve mevcut Emel sesinin duyulabilirliğini dinleyin. Bu görevde canlı dış görüşme testi yapılmış sayılmaz.

Bu oturum algılama/klinik kabul açıklarını otomatik kapatmaz; `physicalUserAcceptance:false` korunur.
