# Göz Sağlığı teknik teslimi — 17 Ekim 2026

Teknik kapsam tamamlandı; `physicalUserAcceptance:false`. Doğal konuşma, gerçek göz yumma/el veya opak örtüyle kapatma ve fiziksel mesafe kabulü yapılmadı. Kontrollü koordinat/ASR olayları algılama doğruluğu olarak sunulmuyor.

Kaynak checkout salt okunur incelendi. Kaynak HEAD `5f11c111e3f6547e6420ddf37db477190d232f10` üzerinden oluşturulan ayrı checkout:
`C:\Users\PC\Desktop\AI Workspace\TOGG\attune-cdc-vision-technical-20261017`

Dal: `research/vision-technical-closeout-20261017`. BUILD_ID: `jxdWpuNZvsmHvFPN32Lbz`.
Yerel teslim commit'i ve son durum `C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\vision-technical-closeout-20261017\status.json` içindedir. Push/merge veya normal başlatıcıya aktivasyon yapılmadı.

## Bulunan gerçek hatalar

| Vaka | Önce | Sonra / kapsam |
|---|---|---|
| Sesli duraklat/devam | Duraklatılmış sayfada sıfır aktif ASR; ekranda sunulan “devam et” komutu dinlenemiyordu. Eski callback geçersizdi. | Yeni nesil yalnız devam/bitir komutlarını dinler. Harf gizli kalır; düşük güvenli komut ve harf yanıtı puanlanmaz. Devamda aynı bekleyen hedef korunur. Sessize alma yine ASR'ı kapatır. |
| NaN/Infinity ölçüm koruması | Geçersiz zaman, göreli ölçek veya SVG geometri değerleri sayı karşılaştırmalarını aşabiliyordu. Üç odaklı test başlangıçta başarısızdı. | Sonlu sayı doğrulaması; bilinmeyen mesafe ve puanlanmayan deneme. Aynı üç test geçti. Bu kontrollü robustness vakasıdır; kameranın gerçekten NaN ürettiğine dair iddia yoktur. |

Kanıtlar: `output/playwright/vision/pause-before.json`, `pause-after.json`; ilerleme klasöründe `before-nonfinite.xml`, `after-nonfinite.xml`. Eşik, ses, metin, yerleşim, deneme planı veya boyut ölçeği değiştirilmedi. Tarihsel başarılı tekrarlar güncel hata sayılmadı.

## Teknik doğrulama

65 benzersiz odaklı regresyon geçti: `focused-tests.xml` 63, `local-api-test.xml` 1, `tracking-geometry-test.xml` 1. Başlangıçta mevcut 60 test de geçmişti; toplamın üzerine tekrar sayılmadı. `next typegen` + `tsc --noEmit` geçti (`typecheck.log`). Production build geçti (`build.log`); önceden mevcut cilt hook bağımlılığı ve header `<img>` lint uyarıları kapsam dışında korundu.

React incelemesinde ek event listener, kalıcı UI veya geniş refactor eklenmedi. ASR callback'leri mevcut oturum/hedef/nesil kontrolünü kullanıyor; duraklatılan hedef için komut dinleyicisi ayrı ve yanıt belleğine kapalı.

| Kontrol | Gerçek yapılan / sonuç | Kanıt |
|---|---|---|
| Tam oturum | Gerçek production sayfası, SVG, state machine, API, native Audio/MSE, kayıt yolu; testte kontrollü kamera/model/ASR. 12 RIGHT + 12 LEFT geçerli, 5 teknik geçersiz deneme. Tek tamamlanmış test kaydı. | `desktop-proof.json`, `desktop-result.png`, `desktop-history.png` |
| Skor / adaptasyon | Sağ: harf 10/12, yön 11/12, ortalama %87,5; sol: her ikisi 12/12. “Göremiyorum” 1; ayrıca geçerli yanlış ve teknik geçersiz ayrı. İlk boyutlar 120,120,60,60,120; gerçek SVG ölçümü ile kayıttaki boyut aynı. | `desktop-proof.json` |
| Geçmiş | Yeniden yükleme sonrası aynı iki göz özeti, JSON kayıt değişmedi. Klinik ölçek, cm, dioptri veya sahte eksik-sonuç sıfırı eklenmedi. | `desktop-proof.json`, sonuç/geçmiş ekranları |
| ASR | İki sıra, parçalı/final/interim/tekrar, düzeltme, yankı, düşük güven, yönerge çalarken yanıt, no-speech yeniden başlama, eski callback reddi. | 63 test, tam oturum, `pause-after.json` |
| Yaşam döngüsü | Sessize alma, ASR not-allowed, tekrar dene, yeni oturum, uygulama iznini kaldırma, gerçek izole araç API'sinde 25 km/h sürüş kilidi, kontrollü kamera izin reddi. Puan/kayıt eklenmedi; sahip olunan kaynaklar kapandı. Araç API'si park durumuna döndürüldü. | `lifecycle-proof.json` |
| Ses hatası | Yalnız testte 503 taşıma hatası: harf yok, ASR yok, geçerli deneme artışı yok; iptalde kayıt yok, track'ler ended. | `voice-failure-proof.json` |
| Gerçek yerel modeller | Mevcut lisanslı 640×480 kayıtlı kare → değiştirilmemiş Face/Hand production worker, GPU. İki göz açık, göreli ölçek 0, mesafe stable. El bulunmayan görüntüye el noktası eklenmedi. | `models-proof.json` |
| Takip kaybı / güncellik | Siyah karede faceCount=0, iki göz uncertain, mesafe unknown. Video duraklatılınca >750 ms eski kare deneme açmadı; oynatınca güncellik döndü. SPA çıkışında worker kapandı, track ended, kayıt yok. | `models-proof.json` |
| Kaynak geometrisi | Aynı kayıtlı kaynakta pencere 750 px'e inince video 640×480, baş kutusu ve mesafe değişmedi. Ayrı üretilmiş geometri/piksel alanı testinde ağız tek başına mesafe üretmedi; ölçek/histerezis/toparlanma ve yeni tracker referansı sınandı. İkinci vaka gerçek fotoğraf değildir. | `models-proof.json`, `tracking-geometry-test.xml` |
| Dar görünüm | 750×900, 3 gerçek SVG yanıtı; 120,120,60; taşma yok, kısmi oturum iptalinde kayıt yok. | `narrow-proof.json`, `narrow-active.png` |
| Native %200 | Ayrı Chrome profili, viewport:null ve Chrome native zoom tercihi. %100 DPR=1,5 → %200 DPR=3; aynı dış pencere 1298×738. CSS zoom=1, visualViewport.scale=1. 120,120,60 CSS px; kaynak 640×480. Dokuz path noktası görünür ve SVG hit-test içinde. | `native100-control.json`, `native200-proof.json`, `native200-surface.json/png` |

Native zoom'da Playwright'ın varsayılan/full-page screenshot clip'i bu makinede hatalıydı. Bu dosyalar görsel kabul olarak kullanılmadı. Gerçek görünür compositor `Page.captureScreenshot(fromSurface:false)` ile alınıp incelendi; harf kesilmedi. Uygulama bu otomasyon sorununu gidermek için değiştirilmedi. Tam oturumdaki otomasyon bir ara toparlanma karesini beklemeden yanıt denediğinde ürün doğru reddetti; testin fresh-frame beklemesi düzeltildi, aynı 6/24 oturumdan devam edilerek 24 tamamlandı.

Kayıtlı kare: mevcut `attune-live-test/audit-fixtures/head-shake-frames/frame-001.jpg`, SHA-256 `749c9a841db3303eb7085dc9068d7ab8e70016153860c58c36b7e8ea1108fe22`, mevcut NMu11er Head_Shake.webm / CC BY-SA 4.0 envanteri. Yeni veri indirilmedi. Testte yalnız bu kare isteği yerel dosyadan karşılandı; model/API/ses yanıtları gerçekti. Teslimde fotoğraf veya ham ses rapora/Git'e eklenmedi; geçici public kopyası kaldırıldı.

## F001–F027 durum tablosu

`TEKNİK GEÇTİ` ilgili kaynak/state/UI sözleşmesinin kanıtıdır. Fiziksel doğruluk veya klinik kabul anlamına gelmez. `DOĞAL POZİTİF AÇIK` durumlarında hesap/durum makinesi kontrolü geçti, gerçek kapatma algısı kabulü açık.

| ID | Özellik | Bu teslim / kanıt |
|---|---|---|
| F001 | Kamera/yüz edinimi | TEKNİK GEÇTİ; gerçek Face/Hand worker, `models-proof` |
| F002 | Işık/netlik/güncellik | TEKNİK GEÇTİ; boş/eski kare reddi, kalite testleri |
| F003 | Göreli mesafe | TEKNİK GEÇTİ; geometri/piksel alanı histerezisi + gerçek kayıtlı kaynakta pencere bağımsızlığı; fiziksel yaklaşma/uzaklaşma açık |
| F004 | Anatomik sağ/sol | TEKNİK GEÇTİ; kaynak burun orta hattı ve roll testleri, RIGHT12→LEFT12 |
| F005 | Ekrana bakış | TEKNİK GEÇTİ; poz/kadraj/geometri kapıları korundu, kamera bakış zorunluluğu eklenmedi |
| F006 | Sabit kamera/harf alanı | TEKNİK GEÇTİ; masaüstü/dar/native zoom, değişmeyen kaynak boyutu |
| F007 | Rastgele hedef/rotasyon/ayna | TEKNİK GEÇTİ; gerçek SVG path/transform ve oturum testleri |
| F008 | SVG boyutu/kesilmeme | TEKNİK GEÇTİ; DOM ölçümü, path hit-test, native compositor |
| F009 | İki söyleme sırası/birleşik | TEKNİK GEÇTİ; parser + kontrollü ASR tam oturum |
| F010 | Kelimeyle kodlama/düzeltme | TEKNİK GEÇTİ; parser/bellek testleri, tam oturum düzeltmesi |
| F011 | Ayna/dönüşüm | TEKNİK GEÇTİ; yön eşdeğerliği ve gerçek SVG transform |
| F012 | Parçalı yanıt belleği | TEKNİK GEÇTİ; eksik bileşen/tekrar/final kontrollü ASR |
| F013 | Gecikmiş olay izolasyonu | TEKNİK GEÇTİ; eski recognizer/oturum callback reddi |
| F014 | Yönerge sırasında yanıt | TEKNİK GEÇTİ; native Audio çalarken kontrollü yanıt kabulü |
| F015 | Sistem sesi/yankı reddi | TEKNİK GEÇTİ; yönerge metni yanıt sayılmadı; fiziksel hoparlör yankısı açık |
| F016 | Geçerli yanlış ilerlemesi | TEKNİK GEÇTİ; tam oturum gerçek yanlış kayıtları |
| F017 | Göremiyorum | TEKNİK GEÇTİ; geçerli yanlış, teknik engelden ayrı |
| F018 | Teknik geçersizlik | TEKNİK GEÇTİ; 5 invalid hariç 24 geçerli; NaN, ses/kamera/izin hataları |
| F019 | İki doğru sonrası küçülme | TEKNİK GEÇTİ; gerçek 120,120,60 SVG, min15 |
| F020 | İki yanlış sonrası büyüme | TEKNİK GEÇTİ; gerçek 60,60,120 SVG |
| F021 | İki göz 24 deneme | TEKNİK GEÇTİ; 12+12, bir tamamlanmış izole kayıt |
| F022 | Harf/yön/ortalama paydaları | TEKNİK GEÇTİ; aynı denemeden hesaplanan ayrı skorlar, boş payda null testleri |
| F023 | Duraklat/devam/konum/mute/bitir | DÜZELTİLDİ ve TEKNİK GEÇTİ; `pause-before/after`, `lifecycle-proof` |
| F024 | Sonuç/geçmiş | TEKNİK GEÇTİ; yeniden yüklemede aynı özet ve değişmeyen kayıt |
| F025 | Göz yumma | DOĞAL POZİTİF AÇIK; 600 ms hold/anatomik eşleme/blink durum testleri geçti; kayıtlı görüntü yalnız açık göz negatifi |
| F026 | Elle örtme | DOĞAL POZİTİF AÇIK; palm/piksel/koordinat ve başlangıç referansı korumaları kontrollü testte geçti; fotoğrafa el noktası uydurulmadı |
| F027 | Opak cisimle örtme | DOĞAL POZİTİF AÇIK; iki bağımsız lokal piksel desteği ve uncertain reddi teknik testte geçti; gerçek eşleşmiş örtme görüntüsüyle kabul açık |

## Kimlik ve koruma

`served-protection-receipt.json`: 38 sunulan JS dosyasının bütün baytları build dosyalarıyla SHA-256 eşleşti; HTML script'leri bu build'e bağlı. İki sunulan model de eşleşti:

- Face SHA-256: `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`
- Hand SHA-256: `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
- Mevcut 28 sabit yönergenin yerel byte/hash/metin/profil kontrolü; dört gerçek API yanıtı da aynı hash: `verified-fixed-cache`, `tr-TR-AhmetNeural`, rate `-10%`, pitch `-10Hz`. Yeni ses üretilmedi. Browser CORS nedeniyle özel header'ları okuyamasa da doğrudan HTTP byte/header kontrolü geçti.

Kaynak live-test HEAD/dirty durum ve iki görev dosyası hash'i değişmedi; acne `2637d1b3a342d333b43a40d53e195e8374c8691d`, Claude ve AG başlangıç HEAD/çalışma ağacı korundu. Normal launcher, kullanıcı profili/kayıtları ve diğer modüllerin analiz kodu değiştirilmedi. Paylaşılan VehicleContext değişikliği yalnız opsiyonel loopback API portudur; eski iki varsayılan origin aynı kaldı ve test edildi. İzole build API 8306 kullanır; normal üretime alınmadı. Yerel .env yükleme kapalı, AG anahtarları okunmadı.

## Yerel çalıştırma ve kanıt konumları

Çalışan URL: http://127.0.0.1:3306/vision — gerçek kamera/ASR kullanmaya hazır temiz, ayrı `vision-delivery` profili; test override'ı veya test kaydı yok. Kontrollü girdili diğer tarayıcı oturumları kapandı.

Sunucular zaten çalışıyor. Yeniden başlatma gerekirse yalnız bu checkout'ta:

```powershell
.\Stop-Vision-Technical.ps1
.\Start-Vision-Technical.ps1
```

Başlatıcı kaynak/build/model/banka hash'lerini doğrular, yalnız loopback 3306/8306 açar; ayrı `cdc-progress/vision-technical-closeout-20261017/browser-profile` Chrome profili kullanır. Stop script'i PID + başlangıç zamanı + komut + checkout makbuzunu iki kez kontrol eder; başka süreçlere dokunmaz. Başka port sahibi varsa değiştirmez. `-NoBrowser` ile iki script'in gerçek production yeniden başlatması ve byte kimliği tekrar doğrulandı.

İlerleme, başlangıç/proses/build/koruma makbuzları, XML/log'lar ve bu raporun `report.md` kopyası:
`C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\vision-technical-closeout-20261017`

Tarayıcı JSON ve UI kanıtları: bu checkout'ta `output/playwright/vision` (Git dışında). Fotoğraf/ham ses içermeyen toplu makbuz: `docs/vision-technical-closeout-20261017.json`.

## Bütün modüllerin sonunda yapılacak tek fiziksel kullanıcı kontrol listesi

1. Gerçek kamerada iyi ışıkta iki açık gözle başlangıç; sağ ve solu ayrı yumma, elle ve opak cisimle örtme. Kısa kırpma/belirsizlik ilerletmemeli; anatomik taraf ve 600 ms süre gözlenmeli.
2. Gerçek yaklaşma/uzaklaşma, kadraj kaybı ve dönüş: engelde aynı hedef/puan korunmalı; uygun konumda güvenli toparlanmalı. Ağız hareketi tek başına mesafe değişimi sayılmamalı.
3. Gerçek mikrofon/hoparlörde Türkçe harf/kelime, iki söyleme sırası, ayna/dönüşüm, düzeltme; yönerge sırasında yanıt ve fiziksel yankı ayrımı. Doğal ASR/duyulabilir Ahmet sesi ayrıca kabul edilmeli.
4. Sesli duraklat/devam/bitir, mute, izin kaldırma ve yeniden başlama; eski oturum yanıtı veya ses kalmamalı.
5. Aynı fiziksel oturumda sağ12+sol12, gerçek boyut değişimleri ve sonuç/geçmiş tutarlılığı; dar ekran/%200 ve rahat okunabilirlik. İptal edilmiş oturum kaydedilmemeli.

Bu liste ara test talebi değildir; fiziksel kabul bu teslimde yapılmadı.
