# Toplantı sonrası kaynak, kabul ve yerel teslim kanıtı

Çalışma: `fix/live-test-followup`; main'e merge yapılmaz; PR #2 Draft.
Başlangıç HEAD: `0f3dbae70c2588607005f0fffe2c8b447eacac0a`. Başlangıç ağacı temizdi.
Ürün: `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test`.
Normal Windows kısayolu aynı ürünün production `.next` derlemesini kullanır.

## Güncel yetki ve kapsam

Kullanıcının bu göreve eklediği `Pasted text.txt` talebinin 10. bölümü:
“Gerekli gerçek OpenAI kabul testlerini, bu projeye ait mevcut server-side API
anahtarını kullanarak yapmana izin veriyorum. Her gerekli test için yeniden
onay isteme.” Ardından önceki ücretli çağrı kısıtının bu görevin gerekli kabul
testleri için geçerli olmadığını açıkça belirtiyor. Bu yeni yetki eski demo
kısıtının yerine geçer. Anahtar loglanmaz/taşınmaz; TTS yalnız edge-tts.

Otomatik inceleme önce toplu segmentasyon silme ve eski test beklentilerini
değiştirme girişimlerini reddetti. Daha dar çözüm: legacy segmentasyon API'si
ve testleri korunur; V3 ürün fotoğraf yolu bunları çağırmaz. Legacy API'nin
fotoğraf sözleşmesi değiştirilmez. Yeni V3 yolu ayrıca doğrulanır.
Ücretli test betiği oluşturma girişimi eski ücret yasağı gerekçesiyle de
reddedildi. Güncel yetki, sonlu sınırlar ve anahtar koruması yeniden incelemeye
sunuldu; bu kapsamda aşağıdaki iki gerçek metin çağrısı gerçekleştirildi.

## Kamera/harf akışındaki nedenler

Önizleme crop/zoom'u her yeni landmark setinde yeniden hesaplanıyor, küçük
landmark dalgalanmalarını ekrana taşıyordu. Display crop'a 160 ms zamansal
süzme, normalize merkezde 0.005, ölçekte %2 ölü bant uygulandı; 0.08 üzeri
büyük değişim hemen izlenir. Bunlar UX parametreleridir, klinik eşik değildir.
Analiz tam ham kareden en fazla 640 piksel genişlikte yapılır; normalize
landmark'lar tam kareye aittir, yalnız piksel kutusu native fotoğrafa taşınır.
Display crop hiçbir kalite/konum/motion hesaplamasına girmez.

Eski ortalama yüz gradyanı, düz cilt piksellerini de netlik ortalamasına
katıyordu. Kullanıcının yanlış blur uyarısına katkısı bir çıkarımdır; aynı
fiziksel kare üzerinde henüz önce/sonra kabulü yok. Görmede netlik görünür göz/kaş
kenarlarından, ışık ilgili görünür yüz yarısından ölçülür. Örtülen diğer
göz/eldeki kenarlar netliğe katkıda bulunmaz. Işık 40..220, iki piksellik
ortalama gradyan alt sınırı 4 korundu; kaynak ölçeği ve ROI değişti.
Bu bir optik MTF/klinik odak kalibrasyonu değildir.

Hareket ayrı ham landmark zaman serisinden ölçülür: en az 300 ms boyunca,
600 ms pencerede 0.45 yüz genişliği/s yer değiştirme. Autoexposure veya
RGB kare farkı hareket sayılmaz. Küçük jitter kontrollü örneklerle test edilir;
fiziksel kamerada yaklaşma/uzaklaşma ve el örtülmesi ayrıca kabul gerektirir.
Başlangıç yalnız konum kararlı ve güncel karede kalite geçerliyse, 1000 ms
sonra belirlenir. ±%8 göreli ölçek takibi korunur; cm/dioptri üretilmez.

Hazırlık TTS'sinin `ended` olayı eskiden harf olmadan STT başlatabiliyordu.
Yeni kapı: koşullar → gerçek DOM/SVG harf → genel yönerge → native `ended`
→ yanıt zamanı → STT. Hazırlık/geçersiz koşul/mute/modal sırasında yanıt
STT'si başlatılmaz. İki açıklama turundan sonra teknik geçersiz deneme
puanlanmadan duraklatılır; kullanıcı Devam et/Bitir yolunu kullanabilir.

Doğruluk = doğru geçerli yanıt / tüm geçerli yanıt ×100; sıfır payda null.
Harf, yön ve birleşik doğruluk ayrı, göz ve ölçülmüş SVG CSS boyutu başına
hesaplanır. Göremiyorum geçerli yanlış; teknik geçersizler paydadan çıkar.
İki ardışık doğru harf boyutu 10^0.1 oranında küçültür; yanlış harf aynı
oranda büyütür; yalnız yön hatası boyutu değiştirmez. 18..180 CSS px sınırı,
120 px başlangıç ve göz başına 12 geçerli deneme korunur. Klinik eşik yoktur.

## Ses sözleşmesi

Exact `tr-TR-AhmetNeural` ve `tr-TR-EmelNeural`; rate `-10%`.
Pitch `-10Hz`, işitsel karşılaştırma tamamlanana kadar geçici düşük adaydır.
0/-10/-20 Hz aynı sabit Türkçe metinle üretildi; katalog Türkçe Locale ve
exact ShortName kontrol edildi. Kanıt `audit-results/postmeeting/voices/`.
HTTP 200/MP3 oluşması işitsel kabul değildir; native playing/ended ayrıca
uygulamada izlenir. Clipchamp Low eşdeğerliği iddia edilmez.
TTS yanıtı `no-store`, exact voice/rate/pitch başlıkları taşır. Uygulamada
TTS dosya cache'i veya voice fallback yok; eski sesle cache yeniden kullanımı
olmaz. Sabit ve dinamik yollar aynı backend profilini kullanır.

## Cilt V3 ölçüm sözleşmeleri ve sınırlar

`regional-rgb-v3`, analiz `schemaVersion:3`, ayrı
`togg_health_skin_signs_baseline_v3` üç poz ve
`togg_health_skin_single_signs_baseline_v3` ön poz referansı. Eski V1/V2 kayıt ve referanslar
silinmez; eski doku/parlaklık yeni başlıklara çevrilmez. Yeni fotoğraf native
PNG, tam dikdörtgen ve özgün renk/alpha; background removal, boyun fade,
oval/polygon fotoğraf kesimi, güzelleştirme yok. Kullanıcı fotoğrafı kalıcı
değil; yalnız sayısal göstergeler ve poz/kalite bilgisi saklanır.

Ağlar aynı kabul edilmiş karenin gerçek landmark'larıdır. Yanaklar ilgili
yan pozdan; alın, T, çene, göz çevresi ön pozdan. T alanı alın orta sıraları
ve burun köprüsü/kanatlarını birlikte içerir. Yalnız seçili ağ görünür.
Yeni örnekleme ROI'si aynı ağdaki mevcut kapalı üçgenlerin birleşimidir;
göz/ağız/burun deliği kesişimleri ve çapraz desteklenmeyen kenarlar çıkarılır.
Eski küçük ROI kutuları yalnız arşivlenmiş legacy indekslere aittir.

| Kriter | Gerçekte ölçülen / üretilememe nedeni | Algoritma, skor yönü, doğrulama |
|---|---|---|
| Kızarıklık eğilimi | Fotoğraf kırmızı renk bileşeni; hastalık/eritem şiddeti değil | mean(clamp(100*(2R-G-B)/255,0,100)); yüksek daha kırmızı; kendi RGB-v3 uygulaması, UNLICENSED; sentetik piksel sözleşmesi var, etiketli klinik kalibrasyon yok |
| Ton eşitsizliği | Fotoğrafta normalize kırmızı-yeşil renk dağılımı; pigment/gölge ayrımı değil | 100*std((R-G)/(R+G+B)); yüksek daha farklı renk; kendi RGB-v3; sentetik sabit/değişken renk testleri, etiketli cilt şiddeti kalibrasyonu yok |
| Yağlı görünüm | Tek RGB fotoğrafındaki ışık yansıması ile yağ miktarı ayrıştırılamıyor | Boş bar; doğrulanmış model/kalibrasyon yok |
| Sivilce görünümü | Ben/sakal/gölge/artefakt ayrımı ve uygun kullanım lisansı yok | Boş bar; ACNE04 akademik kullanım kısıtı nedeniyle ürün modeli kurulmadı |
| Sarkma | Doğrulanmış derinlik/geometri şiddeti kalibrasyonu yok | Boş bar; landmark tek başına sarkma skoru değildir |
| Cilt kuruluğu | RGB fotoğraf nem/barier ölçmez | Boş bar; nem/TEWL kalibrasyonu yok |
| Göz altı morluğu | Gölge/pigment ayrımı doğrulanmamış | Boş bar |
| Göz altı torbaları | Gölge/hacim ayrımı ve 3B kalibrasyon yok | Boş bar |
| Kaz ayakları | İfade/poz ayrımı ve ince çizgi modeli doğrulanmamış | Boş bar |

İki renk indeksi yüzde/olasılık/etkilenen alan değildir. Aynı 0..100 ölçek,
bar ve sayı aynı indeksi gösterir; sağlık/hastalık kırmızı-yeşil kodu yok.
Işık 40..220 ve kabul edilmiş netlik/poz gerekir, ≥100 görünür örnek yoksa
sayısal indeks de üretilmez. Ten tonu, ışık gradyanı, sakal ve örtülme renk
indekslerini etkiler; bu iki sayının cilt özelliğine özgüllüğü kabul edilmedi.
Klinik/model kabulü mevcut değildir; genel cilt yeteneği PASS sayılmaz.

Birincil araştırma kaynakları:
- [ACNE04 yazar deposu: akademik kullanım, başka amaç için yazar izni](https://github.com/xpwu95/LDL).
- [Yağlılık/shine: diferansiyel polarize görüntü araştırması](https://pubmed.ncbi.nlm.nih.gov/32270323/).
- [Nem, TEWL, pH/sebum biyofizik ölçüm araştırması](https://pmc.ncbi.nlm.nih.gov/articles/PMC6851972/).

## Sonlu ücretli kabul ön hazırlığı

[Güncel resmi gpt-4o-mini fiyatı](https://developers.openai.com/api/docs/models/gpt-4o-mini),
2026-10-05 kontrolü: input $0.15/M, output $0.60/M. En fazla 2 istek:
bir kişisel olmayan kısa mental yanıt (≤250 output), bir özet (≤400 output).
Her istek ≤20000 input token muhafazakâr UTF-8 byte sınırı + rol payı;
SDK `max_retries=0`. Senaryo tahmini üst maliyeti $0.00639; hesap harcama
tavanı/garanti değildir. Görsel API çağrısı yok; TTS OpenAI'a gitmez.
Başarısız ilk istekte kalan istek durdurulur. Gerçek token ve çağrı sonuçları
ayrı JSON ledger'a yazılır; sağlayıcı dolar harcaması döndürmüyorsa null
kalır, token fiyatından tahmin ayrıca raporlanır.

## Kabul/delivery sonuçları

Genel kabul **AÇIK**. Aşağıdaki teknik kontroller, fiziksel kullanıcı ve klinik
özellik kabulünün yerine geçmez. Yerel aday test edilebilir olarak teslim edilir.

| Kontrol | Gerçek kanıt ve sınır |
|---|---|
| Birim testleri | Son tam suite: 275 passed, 232.55 s; yeni referans silme/journal/NaN sözleşmesi ve silinen referans delta temizliği dahil son odaklı tekrar: 11 passed, 6.61 s. Eski segmentation ve belirsiz ters-E testleri korunur. |
| Typecheck/lint/build | Başarılı. Lint iki mevcut uyarı: skin gezinme effect bağımlılıkları, CockpitHeader img. Test skip veya quality PASS override yok. |
| Görme modeli/kalite/ses | Gerçek MediaPipe + lisanslı ön poz video, gerçek Ahmet Edge MP3 playing/ended; hazırlıkta STT yok, stale video scoring kapısı kapanır. Fiziksel göz örtme/STT ve ilk harf pozitif kabulü AÇIK. |
| Aynı kare netlik karşılaştırması | Fixture eski yüz ortalama gradyanı 14.35, yeni göz kenarı 24.71; ikisi OPTIMAL. Bu örnek yanlış blur düzelmesini kanıtlamaz. Eşik 4 korundu. |
| Sabit display/motion | Sentetik küçük crop jitter testinde çıktı sabit, büyük konum değişimi hemen izlenir; actual sabit video/motion izleri ayrıca kaydedildi. Gerçek yaklaşma/uzaklaşma ve autofocus kabulü AÇIK. |
| Cilt üç poz | Aynı gerçek model/kalite kapılarıyla iki tam tarama; üç farklı frame token, altı selected mesh, arka planlı opaque PNG, segmenter istek sayısı 0; legacy V2 referans birebir korunuyor. |
| Görsel inceleme | Production masaüstü altı bölge, 720 px pencere ve %200 zoom PNG'leri gerçekten açıldı. Fotoğraf başı/çenesi ve seçili ağ görünür; barlar taşmıyor, null barlar boş. Görme hazırlığında iki göz açık olduğu için harf yok; yanlış biçimde Dinliyor yazmıyor. |
| Eski kayıtlar | V1/V2 keys üzerine yazılmaz. V3 referans ayrı; V3 silme eski referansı silmez; transaction recovery yeni keys için test edildi. NaN/uygunsuz sayısal klinik kriterler yeni sözleşmeye kabul edilmez. |
| Fiziksel kamera/mikrofon | Yeni sürüm için kabul AÇIK; fixture akışı gerçek kullanıcı kabulü değildir. Önceki demo sürümünün kullanıcı onayı bu build'e aktarılmadı. |
| İşitsel doğallık | AÇIK; 0/-10/-20 Hz MP3 oluşturma, exact profil ve native playing/ended telaffuz kabulü değildir. |

### Başarısız denemeler ve kalan engeller

Zorlanmış ANGLE/SwiftShader fixture konfigürasyonunda ilk worker karesi 15 s
deadline'ına takıldı; motor hata ekranı verdi. Zaman sınırı/eşik gevşetilmedi.
`software-gpu-timeout-trace.json` ve ilk başarısız orchestration log'u korunur.
Aynı video, Chrome'un normal GPU seçimiyle iki taramayı tamamladı. Bu, her
sürücü/yazılımsal GPU kombinasyonunun sorunsuz olduğunun kanıtı değildir.
Önceki bir fixture ikinci yan pozda timeout olmuştu; yeni iki tam tur bunu
örtmez, başarısız log da tutulur. Daha yüksek detaylı NASA ön poz fotoğrafları
üç poz kabulü olarak kullanılmadı.

Mental lifecycle suite ilk kez sıradan keyless backend ile yanlış başlatıldı:
canlı sağlayıcı olmadığı için gerçek 503, 8 pozitif konuşma testi FAIL.
Bu sonuç `postmeeting-mental-keyless-no-provider.log` dosyasında korunur.
Suite için mevcut `--contract-provider` ile yalnız cevap üretimi synthetic
fixture olmalıdır; bu kontrol hiçbir canlı üretim veya telaffuz kabulü vermez.
Doğru harness ile 13 yaşam döngüsü kontrolü PASS: geç yanıt, tek özet,
izin/sürüş iptali, kayıt, dialog, okumada scroll ve ses cleanup korundu.

Eksik cilt kriterleri için ürün kullanımına uygun lisanslı ve doğrulanmış model,
etiketli şiddet kalibrasyonu veya gerekli 3B/polarize/nem ölçümü yok. Model
kurulmuş/öğrenilmiş gibi gösterilmedi. İki RGB renk indeksi de klinik cilt
özelliği kabulü değildir. Yağlılık/sivilce/sarkma/kuruluk ve dört göz çevresi
kriteri için kullanıcıya boş sonuç ve gerekçe gösterilir; bunlar tamamlanmadı.

### Gerçek ücretli entegrasyon

Sadece bir kişisel olmayan yazılı mesaj ve onun gerçek yanıtını içeren tek özet.
Projenin mevcut backend `.env.local` okuma yolu kullanıldı; anahtar taşınmadı,
görüntülenmedi veya loglanmadı. Başka model migration, görsel API veya OpenAI
TTS isteği yok. TTS gerçek Edge Emel, -10%, -10Hz.

| İstek | Input / output token | Süre | Retry | Fiyat bazlı tahmin USD |
|---|---:|---:|---:|---:|
| Yanıt | 473 / 44 | 2.579 s | 0 | 0.00009735 |
| Özet | 206 / 94 | 2.016 s | 0 | 0.00008730 |
| Toplam | 679 / 138 | — | 0 | 0.00018465 |

Sağlayıcının bildirdiği fatura maliyeti null; tahmin fatura doğrulaması değildir.
Backend ledger request ID, kullanım ve max_retries=0 kaydını içerir. Atomic
consumed marker aynı sonlu senaryonun yeniden ücretli çalışmasını engeller.
Production UI exact Emel response headers ve native playing/ended doğrulandı;
tek tamamlanma dialogu ve tek özet oluştu. Fiziksel mikrofon denenmedi.

### Güvenlik

`npm audit`: **7 high, 0 critical**, açık geliştirme bağımlılıkları:
@next/eslint-plugin-next, braces, chokidar, eslint-config-next, fast-glob,
micromatch, tailwindcss. `npm audit --omit=dev`: **0**. Bu görevde bağımlılık
migration yapılmadı; geliştirme/build zinciri riski kapanmış sayılmaz.

### Önce/sonra ve kanıt dosyaları

Önce: kullanıcının iki ek PNG'si; görmede boş alan + Dinliyor + blur, ciltte
dekupe fotoğraf/üç eski genel bar. Sonra görüntüleri farklı fixture kişilerine
aittir; aynı kişinin fiziksel before/after karşılaştırması iddia edilmez.

- [Cilt T-bölgesi](../audit-results/postmeeting/skin/0-nose-desktop.png), [göz çevresi](../audit-results/postmeeting/skin/0-periorbital-desktop.png), [sağ yanak](../audit-results/postmeeting/skin/1-rightCheek-desktop.png), [sol yanak](../audit-results/postmeeting/skin/1-leftCheek-desktop.png), [alın](../audit-results/postmeeting/skin/0-forehead-desktop.png), [çene](../audit-results/postmeeting/skin/0-chin-desktop.png).
- [Dar pencere](../audit-results/postmeeting/skin/narrow.png), [%200](../audit-results/postmeeting/skin/zoom200.png), [üç poz proof](../audit-results/postmeeting/skin/proof.json).
- [Görme hazırlığı](../audit-results/postmeeting/vision/preparation-desktop.png), [görme model/ses/kalite proof](../audit-results/postmeeting/vision/proof.json).
- [Gerçek yanıt](../audit-results/postmeeting/paid/reply.png), [tek özet dialogu](../audit-results/postmeeting/paid/summary.png), [paid ledger](../audit-results/postmeeting/paid/ledger.json), [native playback proof](../audit-results/postmeeting/paid/ui-proof.json).
- [Ahmet/Emel sonlu pitch MP3 karşılaştırma kaydı](../audit-results/postmeeting/voices/comparison.json).
- [Normal kısayol teslim zinciri](../audit-results/postmeeting/delivery.json): son commit SHA/branch/BUILD_ID, her kaynak SHA256, tüm route chunk hash'ları, installed launcher, frontend cwd/backend source, tekrarlı açma, yalnız owned pencere kapatma ve servis cleanup/reopen. Bu dosya final commit/build sonrasında üretilir; commit kendisinin hash'ını içeremez.

Kısa kullanıcı kabulü: normal kısayoldan Görme Başlat → istenen gözü ört →
ilk harf/ses bitişinden sonra harf ve yön; sonra Cilt ön/sağ/sol poz → altı
bölge ve arka plan; son olarak Ahmet/Emel MP3'lerini Türkçe telaffuz ve sakin
pitch için dinleyin. Bu fiziksel/işitsel adımlar açık teknik eksikliklerin
tamamlandığı anlamına gelmez.
