# Diş Sağlığı teknik kapanış — 17 Ekim 2026

Teknik uygulama eksikleri aşağıdaki sınırlı kanıt kapsamında kapatıldı. D/d algılama başarısı, doğal birikim/dizilim kabulü ve fiziksel kullanıcı kamerası tamamlandı sayılmıyor. Yeni eğitim, veri indirme, model/eşik araması veya hosted çağrı yapılmadı.

## Kimlik ve kapsam

- Başlangıç: `e82cc2ffe8739d14b99dc68f02fec33875fc465c`; kaynak birleşik işitme tesliminin gerçek temiz HEAD’i.
- Kod commit’i: `f0b76cf405f66d399a8248f277f4fa19bd892552`; branch `research/dental-technical-closeout-20261017`.
- Ayrı checkout: `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-cdc-dental-technical-20261017`.
- BUILD_ID: `sHzFjTPoO56PaM7NQAge-`. Normal Windows başlatıcısı değiştirilmedi; genel aktivasyon/push/merge yok.
- Model: `eafaca8139e4447b1aa64375156aa47764affd91cf0594392b896ea78463bf03`; `yolox-s-dental-from-scratch-v1`; D=daimi, d=süt dişi **adayları**. Eşik 0.35, sınıf bazlı NMS 0.45; BGR 320×320, 114 padding, üst-sol letterbox ve 15% gerçek ağız marjı korunur.
- Kanıt kökü: `C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\dental-technical-closeout-20261017`. Metadata/hash indeksi bu belgeyle aynı adlı JSON’dadır. Fotoğraf/ham ses/anahtar bu rapora veya Git’e konmadı. Özel ham test payload’ı ve ekran görüntüleri yalnız dış izole kanıt klasöründe kalır.

## Başlangıç ayrımı

| Sınıf | Başlangıç bulgusu | Son durum |
|---|---|---|
| Yeniden üretilen uygulama hatası | Eski upload Worker cleanup yeni Worker’ı kapatıyor; aynı sonuç iki UUID ile kaydediliyor; kaynak kimliği kayıt dışı; FRONT metni bozuk; geçersiz olasılıklar geçerli aday olabiliyor | Aynı kaynak/yarış ve sınır kontrollerinde düzeltildi |
| Güncel teknik kanıt eksiği | Dört-açı kaynak/API/geçmiş, EXIF, izinli fotoğraf sürekliliği, deadline/izin/sürüş temizliği | Son build’de ayrı kanıtlarla tamamlandı |
| Algılama/veri sınırlaması | Zayıf d sınıfı; doğal birikim ve dizilim hedefleri; leke/dolgu/yiyecek zor negatif kapsamı | Açık bırakıldı; test PASS’i kalite kazanımı sayılmadı |
| Yalnız fiziksel kabul | Aynı gerçek kullanıcının dört açısı, gerçek kamera netlik/parlama ve doğal ağız koşulları | Kullanıcıdan ara test istenmedi; son listededir |

## Gerçek hatalar ve dar düzeltmeler

1. Eski bitmap beklemesi sürerken dosya değiştirilince eski `finally`, global ref üzerinden yeni Worker’ı kapatıyordu. Her upload kendi detector/controller örneğini kapatıyor; ref yalnız aynı örnekse temizleniyor. Önce hata ve sıfır sonuç; sonra aynı kontrollü gecikmeyle gerçek MediaPipe/ONNX sonucu, sıfır kendiliğinden kayıt.
2. Her Kaydet tıklamasında UUID üretiliyordu: bir sonuçtan iki kayıt. UUID artık kabul edilen sonuçta bir kez üretiliyor; senkron saving kilidi ve saved durumu tekrar kaydı engelliyor. Tam görüş metadata’sı sayısal kayıtta; raw medya bu kayıtta yok.
3. Eski sayısal kayıtta photoId/native boyut yoktu ve kaynak fotoğraf saklanmıyordu. Yeni kayıtlar `dental-source-identity-v1` ilişkisini, poz/kaynak/boyut/model/koordinat bilgilerini korur. Ayrı, varsayılan kapalı Gizlilik tercihi yalnız yeni açıkça kaydedilen sonuçların PNG’lerini yerel IndexedDB’de saklar. 32MiB/kayıt ve 128MiB toplam; eski kayıtları yer açmak için silmez. Fotoğraf izni geri çekilince sayısal kayıt korunur. Eski sayısal kayıt silme yolu yeni IDB’ye zorunlu bağımlı bırakılmadı.
4. Bilinen sabit kamera yönergeleri kaynakta mojibake idi. Yalnız bu literal’ler düzeltildi; genel Latin-1/UTF-8 dönüşümü veya kullanıcı kaydı değişimi yok.
5. Negatif obj ve class olasılıklarının çarpımı 0.81, 1.2×1.1 ise 1.32 güvenle geçiyordu. Gerçek model ağırlıkları/eşik değişmeden raw şekil/finite/probability sözleşmesi, manifest sınıf sırası ve kimlik değişimi fail-closed oldu. Frontend kaynak/geometri/sayı sözleşmesini de doğrular; bozuk/eksik view başarılı sonuç veya kayıt olmaz.
6. Son build’in gerçek upload koşusunda yeni PNG hash doğrulaması `fetch(data:)` nedeniyle mevcut CSP’ye takıldı. PNG baytları doğrudan Blob’a açıldı; connect-src genişletilmedi. Gerçek CSP ile IndexedDB testi ve ürün yüklemeleri başarılı tekrarlandı.
7. Backend dental işine 30s cooperative bütçe, bağlantı/park iptali ve sahip olunan worker’ın drain edilmesi eklendi. İstemci timer’ı yalnız kendi controller’ını abort eder; geç epoch/yanıt kabul edilmez. Opaque CV/ORT çağrısının ortasında zorla thread kesilmesi iddia edilmez.

## F053–F066

Kanıt sütunundaki göreli isimler yukarıdaki kanıt köküne aittir.

| ID | Başlık | Durum | Kontrol edilen davranış | Kanıt | Kalan kapsam/sınır |
|---|---|---|---|---|---|
| F053 | Çürük D | TEKNİK DOĞRULANDI / ALGILAMA SINIRLI | Gerçek ONNX, kaynak kutuları ve aday sayısı aynı. Kısmi ağızda 8 D; bu doğruluk ölçütü değildir. | native-chain.json; upload-partial.json | Doğal leke/dolgu/yiyecek zor negatifleri ve bağımsız lokal hedefler açık. |
| F054 | Çürük d | ZAYIF SINIF AÇIK | Sınıf sırası D/d, d=süt dişi korunur; d kutu dönüşümü kontrollü ham çıktıyla doğrulandı. Yeni doğal d başarısı iddia edilmez. | unit-final.log; model-boundary-baseline.json | Eski korunan sette P .517 / R .476 / F1 .496; hasta bağımsız değil, 10 yaş altı kapsam yok. |
| F055 | Birikim görünümü | TEKNİK DOĞRULANDI / DOĞAL HEDEF AÇIK | Payda görünür diş-diş eti sınırı; tek görünüm teyitsiz. Yetersiz sınır null; aday sayısından farklı alan oranı. | camera-current.json; unit-native-final.log | Leke/yiyecek/dolgu/yansıma için doğal etiketli ayrım hâlâ sınırlı. |
| F056 | Görünür dizilim | TEKNİK DOĞRULANDI / KAPSAM SINIRLI | BITE gerçek konturları; üçten az güvenilir konturda null. Eksen/artık/örtüşme geometri kontrolleri geçti. | camera-current.json; unit-native-final.log | 2D görünür kontur; gizli diş veya 3D kapanış/klinik dizilim ölçümü değil. |
| F057 | FRONT/RIGHT/LEFT/BITE | KAYITLI SANAL KAMERA DOĞRULANDI | 4 ayrı kaynak hash, 478 nokta, 1920×1080; aynı sırayla gerçek API ve tek geçmiş kaydı. | camera-current.json | Farklı lisanslı katılımcılar; tek doğal kullanıcının fiziksel dört açısı doğrulanmadı. |
| F058 | Doğal ton/dudak/dil/payda | ODAKLI TEKNİK DOĞRULANDI | Kaynak RGB değiştirilmez; native renk ayrımı, görünür ağız paydası ve yetersiz kalite null testleri. | unit-final.log; unit-native-final.log; camera-current.json | Doğal renk/ışık çeşitliliği klinik doğrulama sayılmaz. |
| F059 | Netlik/parlama/örtülme | ODAKLI TEKNİK DOĞRULANDI | Mevcut gerçek kaynağın bulanık/örtülü/parlak kontrollü türevleri frontend ve backend’de reddedildi. | dental-negative/proof.json | Türevler doğal zor negatif veya fiziksel kamera kabulü değildir. |
| F060 | Kamera sabit crop | TEKNİK DOĞRULANDI | Gerçek snapshot 1920×1080; önizlemeden bağımsız kaynak viewBox, crop/origin ve aynasız çıktı. | camera-current.json; native-chain.json; photo-privacy-ui.json | Gerçek cihaz mesafesi/ayna algısı fiziksel listede. |
| F061 | Tam portre yükleme | TEKNİK DOĞRULANDI | Gerçek MediaPipe 478 nokta → detected-inner-mouth → native crop → ONNX → aynı kaynaklı geçmiş; kamera isteği 0. | upload-portrait.json; negative.json | Diş görünmeyen portre 422; sağlıklı sıfır veya kayıt yok. |
| F062 | Kısmi ağız fotoğrafı | TEKNİK DOĞRULANDI | Yüz noktası uydurulmadan local-colored-enamel-gingiva yolu; gerçek ONNX ve kaynak piksel kutuları. | upload-partial.json; native-chain.json | Yükleme tek fotoğraftır; çok açılı teyit değildir. |
| F063 | EXIF/format/boyut | TEKNİK DOĞRULANDI | EXIF6 bir kez çevrilir; JPEG/PNG/WebP; bozuk signature/decoder, >20MiB, >8192 kenar, alpha ve animasyon reddi. | exif.json; unit-final.log; lifecycle.json | EXIF türevi geometri kontrolüdür, doğal doğruluk örneği değildir. |
| F064 | İptal/dosya değişimi | TEKNİK DOĞRULANDI | Worker sahipliği, gerçek bekletilen yanıtlar, 30s istemci bütçesi, cooperative backend ve izin/rota/sürüş temizliği. | worker-race.json; lifecycle.json; camera-lifecycle.json | Native CV/ORT çağrısının içinde zorla preemption yok; sahip olunan iş doğal bitene kadar kilit korunur. |
| F065 | Kutular ve kaynak kaydı | TEKNİK DOĞRULANDI | Tek sonuç UUID; photoId/poz/sourceType/boyut/koordinat/model kimliği; ayrı açık fotoğraf izniyle aynı fotoğraf ve harita. | camera-current.json; upload-partial.json; photo-privacy-ui.json | Eski eksik fotoğraflar yeniden üretilmez; izin kapalıysa yalnız sayısal kayıt. |
| F066 | Yöntem uyumluluğu | TEKNİK DOĞRULANDI | Model/hash/eşik/geometri/kaynak/birim farklılıkları ayrı seride; null sağlıklı sıfır olmaz; eski kayıtlar değişmez. | unit-history-final.log; unit-final.log | Bu sürüm eski kayıtları yeniden hesaplamaz. |

## Gerçek ürün zinciri ve hata bulunmayan davranışlar

- Son build’de gerçek sanal getUserMedia → MediaPipe → mevcut kaynak kalite/poz/stabilite kapıları → FRONT/RIGHT/LEFT/BITE → gerçek API/ONNX → sonuç → tek kayıt → reload → dört aynı fotoğraf/kutu doğrulandı. Dört ayrı kaynak hash ve her birinde 478 nokta, 1920×1080. Eski kayıtlı Y4M dört farklı lisanslı kişinin fotoğraflarından oluşur; tek doğal kullanıcı veya liveness başarısı değildir. Anatomik RIGHT negatif yaw, LEFT pozitif yaw; önizleme analizin kaynağını aynalamaz.
- Aynı son build’de kısmi ağız `64cd18004a9448ec75ec1f16413d4c6463d4eebca8268763ac9ce76e9eda1d6b`: 1617×1212, 8 D adayı; portre `75b14ba6c3f60dad5bc194043f97a7b81566f93cec917c30beca37ea368d9380`: 1024×638, 478 gerçek nokta, 0 aday. Bu sayılar doğru/yanlış lezyon sayısı veya sağlıklı teşhis değildir. Her iki yolda kamera isteği **0**. Kaydet/reload’da kaynak image href ve kutu değerleri eşit; numeric kayıt raw PNG içermez.
- Kısmi ağız native tensor `a8d4769ad00b053205f9188859e036a3b140d034fe21b96d459784a18aa6cb49` ve raw çıktı `6d0b6410253fd95f2703adb0217725a59273c948e2d6441ffa29973e85f676c1` gerçekten gözlendi; raw 1×2100×7; confidence obj×class, sabit filtre/NMS, sekiz kaynak kutusu browser API kutularıyla birebir aynı. Kontrollü raw unit’inde D ve d ayrı doğru source mapping alır; bu test d sınıfının doğal başarısı değildir.
- Kamera birikim görünümü FRONT/RIGHT/LEFT/BITE sırasıyla 14.9415 / 4.4166 / 15.625 / 0; gerçek sınır paydaları 1111 / 3351 / 1600 / 2380 kaynak piksel. Dört açı ayrı görünür alan ölçümüdür; çok açılı aynı diş teyidi yok. Dizilim yalnız BITE’da geçerli; diğer açılarda null. Birikim doğal pozitifliği anotasyonla doğrulanmadığı için bunlar doğruluk kanıtı sayılmaz.
- EXIF6 türevi yönü düzelmiş 1617×1212 kaynakla işlendi; ikinci normalize açma dönmüyor. JPEG yeniden encode edildiğinden eski dosyayla aynı piksel hash’i iddia edilmez. Dişsiz portre 422 `TEETH_NOT_VISIBLE_OR_NON_COLOR_IMAGE`: sıfır sağlıklı sonuç veya yeni kayıt yok.
- Mevcut kaynağın blur/opaque-cover/clipped-glare türevleri gerçek MediaPipe ve ürün `assessDentalCapture`/backend kalite fonksiyonlarında reddedildi; özgün kaynak kabul edildi. Bunlar kontrollü negatiflerdir; doğal dolgu/yiyecek/leke ayrımını kapatmaz.
- İptal, farklı dosyayla değiştirme, gerçek 30s istemci deadline’ı ve sekmeden işleme izni kaldırılması bekletilmiş gerçek model yanıtlarını reddetti. Backend’in model işi önce tamamlandıktan sonra test transport’unda tutulan süre 25.359s; toplam budget öncesindeki gerçek backend süresi de timer’a dahildir. Kaynak silinmedi/değiştirilmedi, kayıt yok. Native budget unit’i geç success’i reddedip kilidi worker sonrası bıraktı.
- Kamera route-exit, iptal/yeniden başlatma, kontrollü track-ended olayı, izole gerçek vehicle API ile sürüş ve başka sekmeden izin kaldırma: sahip olunan bütün track’ler ended, Worker’lar closed, eksik kayıt 0. Track-ended olayı fiziksel kablo çıkarma testi değildir.
- Sayısal kayıt yalnız kullanıcı Kaydet onayıyla. İlk default-off kamera koşusunda fotoğraf depolanmadı; son build’de açık ayrı izinle dört fotoğraf depolandı. Upload profilinde iki tamamlanmış kayıttan biri silinince diğeri aynı kaldı; sonra fotoğraf izni kaldırılınca IDB boş, kalan numeric kayıt byte içeriği aynı. Eski kayıtlar tekrar hesaplanmadı.
- Görünüm: masaüstü 1440×900 ve dar 390×844. Modal yatay taşma yok; kaynak viewBox değişmedi; fotoğraf/renk/kutu/card yapısı korunur. Lisanslı kontrol fotoğraflarının ekran görüntüleri yerel kanıt klasöründe incelendi.

## Sonlu doğrulama ve korunma

- **54 benzersiz odaklı kontrol**: final ana koşu 39; native geometri/birikim/dizilim 14; son history koşusu 2’den biri ana koşudaki response testinin tekrarı, yalnız 1 yeni history testi sayılır. Başarılı tekrarlar tekrar toplanmadı. `unit-final.log`, `unit-native-final.log`, `unit-history-final.log`.
- Bağımsız typecheck exit 0 (`typecheck-final.log`); production build başarılı (`build.log`, `build-receipt.json`). Atomik ağır-iş kilidi kullanıldı; build ölçülen RSS tepesi 611.3MiB, bütçe 2100MiB; yabancı süreç durdurulmadı.
- Sunulan **38 JS** dosyası HTTP bayt hash’leri, **186 kaynak/build dosyası**, **93 değişmeyen varlık**, model hash’i ve **8 korunan checkout’un HEAD/status’u** eşleşti. Test ledger endpoint’i 404; test hook’ları production JS’de yok. İlgili `served-protection-receipt.json` son yerel commit sonrasında tekrar üretilecektir.
- Cilt/göz/ruh/işitme analiz kaynakları, işitme protokol/audio/progress, merkezi consent, header playback meter, onaylı ses/model varlıkları ve normal launcher korunur. Ortak privacy/record değişikliği diş fotoğraf izni/ilişkisiyle sınırlıdır. Gerçek işitme ses dalgası 0.0058’den revoke sonrası 0’a indi; owned context closed, meter suspended, ses paused, eksik kayıt 0. Klinik/işitsel fiziksel kabul iddia edilmez.
- İlk yanlış test selector’ü carousel ikon SVG’lerini kaynak fotoğrafı saydı; APIResponse.status testte property yerine method olmalıydı; JS label options parantezi ve bir eski fixture’ın artık eksik tek-camera-view beklentisi düzeltildi. Uygulama bu test hatalarını geçirmek için değiştirilmedi; başarılı tekrar kanıtları yukarıdadır.
- Önceki bağımlılık/güvenlik taraması bulguları bu görevin kapsamında kapatılmış sayılmaz. Yeni provider, kişisel fotoğraf gönderimi, eğitim veya kalite eşiği değişimi yok.

## İzole uygulama ve güvenli kullanım

Tek uygulama URL’si: **http://127.0.0.1:3310/dental**. Backend yalnız loopback 8310; veri klasörü bu teslimin `backend-data` alanıdır. `.env` kopyalanmaz/yüklenmez. Normal kullanıcı profiline test kaydı yazılmaz.

Başlatma (ayrı Chrome test profili açar; otomatik kamera/analiz başlamaz):

```powershell
& 'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-cdc-dental-technical-20261017\Start-Dental-Technical.ps1'
```

Sunucu kontrolü için `-NoBrowser` kullanılabilir. Aktif runtime tekrar başlatmada PID/başlangıç zamanı/command/workspace/build/asset kimliğiyle doğrulanıp tekrar kullanıldı. Yabancı port/process sahipliğinde işlem reddedilir.

Güvenli durdurma (yalnız bu teslimin kayıtlı PID/başlangıç zamanı/command sahipliği eşleşen süreçleri):

```powershell
& 'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-cdc-dental-technical-20261017\Stop-Dental-Technical.ps1'
```

Başka checkout/normal uygulama ve kullanıcının tarayıcıları kapatılmaz. Çalışma kendi CLI test profillerini kapatır; sunucular izole URL için açık bırakılır. Kod ve bu rapor yerel commit’lerde; push/merge/main değişikliği yok. Son teslim SHA’sı atomik `status.json` ve dış `report.md` başlığında bulunur.

## En son yapılacak tek fiziksel kamera kontrol listesi

1. Tek gerçek kullanıcıyla FRONT → anatomik RIGHT → anatomik LEFT → rahat BITE; eski/eksik açı tekrarının kabul edilmediğini kontrol et.
2. Görünür diş, doğal ağız açılması, netlik, aydınlatma/parlama ve örtülme koşullarını gerçek cihazda kontrol et; uygun olmayan çekim sağlıklı sıfır/kayıt oluşturmasın.
3. Kaynak fotoğrafla aynasız kutu/birikim/contour hizasını ve açı değişiminde doğru kaynak ilişkisini kontrol et.
4. Tam sonuçtan tek kayıt; açık ayrı fotoğraf izni varsa uygulama yenilendikten sonra aynı fotoğraf/harita; izin kapalıysa yalnız numeric geçmiş; iptal/izin geri çekmede medya temizliği.
