UI-01 ve UI-02 izole teslimde tamamlandı. Başlangıç: b9a5fb76a5244d555ba31c0f0e04a06d9164ffb4; branch: research/health-final-technical-closeout-20261017. Yeni BUILD_ID: TVEQTCRJKDqfXF2nwFXoX. Çalışan adres: http://127.0.0.1:3311/ (API: 8311).

| İş | Yapılan değişiklik | Doğrulama |
|---|---|---|
| UI-01 | Kullanıcının 1. Cilt, 2. Diş, 3. Göz, 4. İşitme ve 5. Ruh PNG'leri ilgili hazırlık ekranlarına bağlandı. | Beşi de 1086×1448; byte-identical kaynak/hedef SHA-256 eşleşti. Ortak 3:4 çerçeve, object-contain; kırpma/retouch/yeniden üretim yok. |
| UI-02 | Yalnız Sağlık Merkezi sırası: Cilt Sağlığı → Diş Sağlığı → Göz Sağlığı → İşitme Sağlığı → Ruh Sağlığı. | Exact beş metin, ikon, route; ArrowUp/Down/Home/End, sarma, Escape ve tetikleyiciye focus dönüşü geçti. |

HEALTH_CENTRE_MENU_IDS yalnız dropdown tarafından kullanılır. Merkezi HEALTH_MODULE_IDS ve shared/healthModules.json değişmedi. Gerçek tarayıcıda hem kokpit hem geçmiş karuseli vision → skin → dental → hearing → mental sırasını korudu. İlgili eski ortak kontrolün menü beklentisi güncellendi; o geniş kampanya yeniden çalıştırılmadı.

Beş modülün 1440×1000 ve 390×1000 görüntüleri açılıp incelendi: tam kaynak, eşit kart/portre oranı, doğru PNG ve yatay taşma olmaması doğrulandı. Beş modülde gerçek headed Chrome native %200 kullanıldı: CSS zoom=1, visualViewport.scale=1, DPR=3, innerWidth=641, outerWidth=1298. Normal dikey kaydırmayla düğmeler görünür ve erişilebilir kaldı. Kamera/mikrofon kullanılmadı; bu kontrol fiziksel cihaz veya model doğruluk kabulü değildir.

Typecheck ve production build geçti. Build mevcut çift atomik lease altında tek ağır süreç olarak çalıştı: 175.49 s, çocuklar dahil ölçülen tepe RSS 602.91 MiB. İlk build girişimi typecheck sürerken 1200 MiB başlangıç rezervi sağlanmadığı için başlamadan reddedildi; typecheck bittikten sonra korumalar değiştirilmeden çalıştırıldı. Önceden var olan img/useEffect lint uyarıları devam ediyor; tarayıcıda favicon.ico 404 görüldü. Bunlar bu iki UI işinin engeli değildir.

Kaynak/build 190 dosya ve runtime'da 127 dosya kimliği doğrulandı (111 HTTP, 16 backend-local). Beş orijinal public PNG endpoint'inin bütün baytları SHA-256 ile kontrol edildi; Next optimizer baytları orijinal PNG diye karşılaştırılmadı. Önceki 98 asset ve önceki teslimin üst düzey kanıt dosyaları değişmedi. Dokuz korunan checkout'un SHA/çalışma ağacı başlangıçla eşleşti.

İzole Start/Stop/build/verify araçları yeni kanıt dizinine bağlandı; hash ve PID/başlangıç/komut kontrolleri korundu. Ek doğrulama runtime CWD ve console-helper parent sahipliğini denetler. Backend'in önceki izole veri dizini değiştirilmedi. Normal Windows kısayoluna ve ana task-list dosyalarına yazılmadı. Model, eşik, accepted/file, hosted izin/config, ses, analiz yöntemi veya kullanıcı kaydı değişikliği yok. Eski portreler ve eski kanıtlar yerinde duruyor.

Kanıtlar C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\health-approved-assets-menu-20261017 içindedir:

- approved-screens.json ve approved-*-desktop/narrow*.png: 10 viewport ve açılıp incelenen ortak kart görüntüleri.
- menu-proof.json, menu-desktop.png, menu-narrow.png: gerçek sıra, ikon, klavye, route ve korunmuş karusel sırası.
- native200-proof.json, *-native200*.png: beş gerçek %200 ekranı ve kaydırılmış aksiyon görüntüleri.
- build-receipt.json, typecheck.log, build.log: build ve kaynak kimlikleri.
- delivery.json: son yerel commit → BUILD_ID → sunulan JS/asset hash zinciri ve süreç sahipliği.
- baseline.json, protected-start/final.json, local-assets.json: eski kanıt/asset korunum kayıtları.

Kaynak/hedef yolları, boyut ve hash'ler docs/health-approved-assets-20261017.json içindedir. Kesin teslim SHA'sı commit sonrasında delivery.json'da tutulur; bu dosyanın kendi commit SHA'sını içererek döngü oluşturması önlenir. Yalnız yerel commit; push/merge yok. Diğer model/veri, dış erişim ve fiziksel kullanıcı kabul açıkları bu teslimle kapanmış sayılmaz.
