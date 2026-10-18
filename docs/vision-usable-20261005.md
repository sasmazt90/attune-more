# Görme akışı — 5 Ekim 2026

**Kullanıcı testine hazır kabulü verilmedi.** Bağımsız kaynak düzeltmeleri ve
negatif sözleşmeler tamamlandı; pozitif kapalı/el/cisim örtülü göz, ilk/sonraki
gerçek harf ve gerçek yaklaşma/uzaklaşma kabulü açık. Bu rapor fixture başarısını
fiziksel kabul yerine kullanmaz. Son SHA/build/teslim damgası, bu metinden
üretilen `audit-results/vision-usable/final-report.md` içindedir.

## Gerçek nedenler ve değişiklik

Önceki `SpokenLetterPage` yalnız `closed` gözü kabul ediyordu. Göz kontrolü sabit
EAR/piksel eşikleriyle çalışıyor, `covered` durumu bulunmuyordu. SkinAnalyzer'ın
cilt hizalama sınırları ve her karedeki bütün yüz kutusu ±%8 ölçek kapısı olarak
kullanılıyordu. Bu kombinasyon harfin mount edilmesini engelliyordu. Buna rağmen
`right/left` ses yönergesi henüz harf yokken **harfi ve yönünü söyleyin** diyordu.
SVG veya font yüklenmesi bu belirlenen ana neden değildi; önceki SVG strok yolu
font kullanmıyordu. Ayrı bir geometri kusuru da bulundu: A harfinin sivri miter
ucu eski 0…100 viewBox'ta kesiliyordu. Kaynak bileşenin viewBox'ı −8…108 olarak
düzeltildi. Gerçek production göz kapısından sonra ilk harfin ekran kabulü açık.

Yeni Görme worker'ı FaceLandmarker blink katsayılarını ve HandLandmarker palm
geometrisini yalnız cihazda değerlendirir. Cilt worker'ı, sonuç portresi/ağları,
Ruhsal İyi Oluş ve ses profilleri değiştirilmedi. Kamera önizleme crop'u yalnız
görseldir; ham analiz 640 piksel genişliğinde, aynasız kaynak koordinatındadır.
Görünür ankraj takibi kaybolunca son zoom yalnız görüntü için korunur; eski
landmark'lar skor için otomatik kabul edilmez.

`VisionFlow`: hazırlık → göz yönergesi → göz kontrolü → rendering → prompting →
listening; ayrıca koşul duraklatması, kullanıcı duraklatması, hata ve sonuç.
Oturum/sunum/göz/version token'ı TTS ve STT'yi; oturum/göz/sunum kamera
sonuçlarını korur. Eski recognition nesnesi de ayrı doğrulanır. Göz değişiminde
önceki göz kapısı yeni yönergeyi engellemez. Teknik belirsizlik skor/ölçek
uyarlaması yapmaz. İlk render, görünür nonzero SVG/path ölçümü ve iki RAF'tan
sonra yanıt yönergesine geçer. Bütün SVG viewport içinde olmalı ve gerçek path
üzerindeki dokuz ekran noktasında başka öğe tarafından örtülmemelidir. Sabit
siyah alan 400×320 CSS piksele kadar; dar pencerede kameradan önce görünür.
İki saniyelik render deadline'ı kamera
re-render'larıyla yeniden başlamaz. Normal yanıt süresi native ended sonrasında
başlar; TTS, tekrar ve duraklama aralıkları dışarıda kalır.

Kamera pause/ended/track-ended, eski inference zamanını beklemeden cevap
kapısını kapatır. Güncellik kartı hata/duraklatma aşamasında da yenilenir.
25 saniyelik TTS/playback watchdog, görünür yeniden deneme yolu ve kaynakların
tek cleanup yolu vardır. Bitir/route/izin değişiminde kamera, worker, STT,
ses/HTTP, RAF, timer, kişisel başlangıç ve sayısal oturum telemetrisi temizlenir.

## Göz yöntemleri; anatomik yön

- Kapalı: iki açık gözle uygun başlangıçta kişisel EAR ve blink katsayısı
  öğrenilir; göreli açıklık ve blink artışı, en az 600 ms süreklilikle incelenir.
  Blink katsayısı olasılık veya klinik ölçüm olarak sunulmaz.
  300 ms'den uzun gözlem boşluğu sürekliliği keser; eksik model katsayısı veya
  ölçülemeyen EAR sıfır gibi uydurulmaz. Başlangıçta da kesintisiz kare gerekir.
- El örtüsü: beklenen göz ROI'si üzerindeki palm polygon örtüşmesi, kişisel açık
  göz şablonunun güncel piksellerle görünüm kaybı ve diğer gözün açık olması
  birlikte gerekir. Yalnız el varlığı veya landmark kaybı yeterli değildir.
- Cisim örtüsü: el modelinden ayrı, geniş göz çevresinde opak görünüm değişimi,
  düşük şablon korelasyonu, görünür baş ve açık diğer göz kanıtı kullanılır.
  Bu konservatif yerel görünüm yöntemi nesne türünü tanıyan bir model değildir.
  **Gerçek cisimle pozitif kabulü henüz yapılmadı; destek doğrulanmış sayılmaz.**
- Yüz modeli kısmen kaybolursa en az üç bağımsız görünür baş patch'i yüksek
  korelasyonla takip edilmeli; ayrık ankraj çiftleri ölçek tutarlılığı sağlamalı.
  Yeterli kanıt yoksa uncertain/unknown kalır. Kaybın kendisi PASS üretmez.

RIGHT = MediaPipe 33…133 / eyeBlinkRight; LEFT = 362…263 / eyeBlinkLeft.
Önizleme aynasızdır. Sağ göz testinde sol kapalı/örtülü ve sağ açık; sol testte
tersi gerekir. Başlık/yönerge/ses aynı anatomik gözden türetilir. İki kapalı göz,
yanlış test gözü ve değerlendirilemeyen örtü ayrı açıklanır.
Katsayı adları ve model API'si: [Google FaceLandmarker kaynakları](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/cc/vision/face_landmarker/face_landmarker_graph.cc),
[HandLandmarker Web](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/web_js).

## Mesafe ve ölçüm dayanağı

Referans en az 1 saniye ve altı uygun kareden sabitlenir; test sırasında
güncellenmez. Forehead/nose/chin/cheek ankraj çiftlerinin 3D landmark uzaklıkları
kaynak piksel ölçeğinde median ile birleştirilir. Elin temas ettiği ankrajlar
dışarıda bırakılır. Gözler arası uzaklık veya crop/zoom tek başına kullanılmaz.
Baş pozu/kadraj ve mesafe UI'da ayrı nedenlerdir. Harf alanına bakmayı engelleyen
**kameraya doğru bakın** yönergesi kaldırıldı. Fiziksel ekran bakışı kabulü açık.

Başlangıç adayları: ±%15 ihlal / 600 ms; ±%10 geri dönüş / 350 ms.
Güvenilir olmayan ölçüm unknown olur, ihlal olarak adlandırılmaz. Daha önce
oluşmuş near/far ihlali unknown döneminden sonra tolerans bandında unutulmaz.
Bu değerler klinik veya donanımsal kalibrasyon değildir; gerçek derinlik
değişimi kabulü yapılmadan doğrulanmış mesafe sınırı sayılmayacaktır.

NMu11er **Head Shake**, CC BY-SA 4.0, kaynak SHA1
`fb35a2ecbf0771ab818c2ca336142c30b515a414`; gerçek video kareleri, sabit crop
900×675 / x90 y190 ve 640×480 ölçekleme. Landmark/yüz rotasyonu/kapı değiştirme
yok. Seçilen CPU tracker'da son 62 gerçek kare ölçümü: ölçek
**−%4,0343 … +%1,1436**; 62 stable, 0 near/far/unknown. Inference medyan
108,65 ms / max 146 ms; yaw proxy −0,11146 … +0,17112.
Ölçüm `motion-pixels.json` içindedir. Sabit portre fixture'ındaki yaklaşık sıfır
dalgalanma gerçek sabit insan jitter ölçümü değildir. Production açık-göz
kontrolünde CPU model inference medyan **114,85 ms**, max **214,5 ms**.
Bu video doğal baş yönü değişimini destekler, göz kapatma/el/cisim veya gerçek
derinlik değişimini içermez. [Kaynak/lisans](https://commons.wikimedia.org/wiki/File:Head_Shake.webm).

## Soğuk model hazırlığı

Aynı compiled worker, aynı gerçek portre pikselleri, Chrome ve model dosyaları;
CPU ardından GPU sıralı çalıştırıldı. Inference sonucu değiştirilmedi.

| Yol | Model initialize | İlk kare (mesaj dahil) | Sonraki 8 kare medyanı |
|---|---:|---:|---:|
| CPU — seçilen | 1869,1 ms | 487,9 ms | 144,8 ms |
| GPU | 1291,8 ms | 15342,2 ms | 65,0 ms |

GPU ilk kare eski 10 saniye deadline'ını aştı; önceki tek GPU ölçümü de
9372,9 ms idi. CPU bu cihazda soğuk ilk kareyi belirgin hızlandırdı, sıcak
karelerde GPU daha hızlı. Sıra/ağ önbelleği model yükleme değerlerini etkileyebilir;
genel hız garantisi verilmez. İlk kare için ayrı 30 saniye hazırlık bütçesi var;
sonraki deadline 10 saniye, cevap için güncellik kapısı hâlâ 750 ms. UI worker
beklerken yanıt istemez, hazırlanma açıklaması ve Bitir düğmesi görünür.

## Fiziksel giriş ve açık engel

Başlangıçta iki geçici hazırlık başarısızlığı görüldü; son görünür production
tekrarında ve son CPU production build'inde kamera ve worker çalıştı. 45 saniye
boyunca faceCount=0, başlangıç
oluşmadı, harf/STT/puan yoktu. Kaynak ayrıca enumerate/getUserMedia ile doğrulandı:
**UGREEN Camera (0c45:2283), 640×480**; başka mevcut cihaz Integrated Camera.
Fake-video bayrağı kullanılmadı. Kamera akışı kapatıldı, fotoğraf/ses kaydı ve
kamera dış servis aktarımı **0**. Kullanıcı hazır olma yanıtı henüz alınmadı.
Bu kayıt, yüz bulunmadığını gösterir; katılımcının gerçekten nerede olduğuna
veya kameraya bakıp bakmadığına ilişkin varsayım yapılmaz.

Mevcut lisanslı video pozitif örtme veya gerçek derinlik değişimi içermiyor.
Mevcut açık-göz portresi Google'ın upstream MediaPipe test fixture'ıdır,
SHA256 `a6f11efaa834706db23f275b6115058fa87fc7f14362681e6abe14e82749de3e`.
Fotoğrafın ayrı lisansı bu görevde doğrulanmadı; lisanslı kullanıcı kabul verisi
olarak sunulmaz, ürün veya Git içine dağıtılmaz. Yalnız mevcut teknik fixture
regresyonu ve sabit model ölçümüdür.
Aranan statik wink/hand görselleri aynı kişiye ait kişisel açık göz başlangıcı
ve zaman akışını sağlamıyor; bunlar pozitif kabul için kullanılmadı. Fotoğrafa
kapalı göz/el ekleyerek veya koşulu PASS yaparak kanıt üretilmedi. Katılımcılı
kamera sınaması yapılmadan 2–12 ve ilk gerçek harf kabulü kapanamaz.

## 18 maddelik matris

| # | Senaryo | Kanıt ve durum |
|---|---|---|
| 1 | İki açık göz başlangıcı | Gerçek portre pikselleri + production worker PASS; fiziksel yüz 0, pozitif kabul açık |
| 2 | Doğru tek kapalı göz | Kişisel/geometri/süre kapısı unit; gerçek piksel ve fiziksel pozitif AÇIK |
| 3 | Doğru el örtüsü | Ayrı palm+görünüm uygulandı; gerçek pozitif AÇIK |
| 4 | Cisim örtüsü | Ayrı opak görünüm uygulandı; gerçek pozitif AÇIK |
| 5 | Yanlış göz | Anatomik/skor kapısı unit; fiziksel AÇIK |
| 6 | İki kapalı | Kapı/neden unit; gerçek piksel/fiziksel AÇIK |
| 7 | Kısa blink | 200 ms/599 ms/600 ms süre sınırı unit; gerçek blink klibi AÇIK |
| 8 | Harf alanına bakış | Sıkı cilt hizası ayrıldı; fiziksel ekrana bakış AÇIK |
| 9 | Küçük baş hareketi | 62 gerçek hareket karesi stable; fiziksel jitter AÇIK |
| 10 | Gerçek yaklaşma/uzaklaşma | Hysteresis/süre/unknown unit; gerçek derinlik AÇIK |
| 11 | İlk/sonraki gerçek harf | Render/token/geometri kapısı var; gerçek production harf screenshot AÇIK |
| 12 | Göz değişimi | 12+12 skor/parser/simetri ve eski token unit; pozitif tam akış AÇIK |
| 13 | Görünmeden cevap istememe | Production açık göz fixture'ında yalnız prepare/right, 0 repeat ve 0 STT PASS |
| 14 | Koşul bozukken yanıt | Conditions/render/sunum kapısı unit; doğal spoken fiziksel AÇIK |
| 15 | Tekrar/göremiyorum/belirsiz | Parser/uyarlama/yeniden sunum unit; gerçek mikrofon AÇIK |
| 16 | Mute/pause/end/new cleanup | Negatif kamera/route/izin/sürüş/Bitir cleanup; pozitif dinleme boyunca tam akış AÇIK |
| 17 | Kayıt/yenileme/silme | Mevcut API/kayıt regresyonları PASS; yeni 24 gerçek geçerli yanıt sonucu AÇIK |
| 18 | Desktop/narrow/%200 harf | Gerçek kaynak SVG'de 30 harf/yön × 3 layout piksel kesilme kontrolü PASS; production göz kapısı sonrası harf ve gerçek tarayıcı %200 zoom AÇIK. CSS zoom simülasyonu ayrı |

280 unit test PASS; son süreklilik/katsayı düzeltmeleri ardından ilgili 41 test
yeniden PASS (28,87 saniye). Mevcut iki lint uyarısı Skin sayfası hook dependencies ve
CockpitHeader img; Görme'de yeni lint uyarısı yok. Production build/type kontrolü
geçti. Yalnız skor/parser numerical fixture'ları pozitif kamera kabulü değildir.
Yeni speech profile karşılaştırması veya OpenAI çağrısı yok: **0 istek / token /
ücretli retry / tahmini maliyet**. Onaylı **tr-TR-AhmetNeural, -10%, -10Hz,
edge-tts** korundu; real Edge/native ended teknik kontrolü bunun işitsel yeniden
kabulü olarak sunulmaz.

`npm audit`: **7 high / 0 critical**, geliştirme zincirinde açık;
`npm audit --omit=dev`: **0**. Bu bulgular gizlenmedi veya kapandı sayılmadı.

## Kanıt dosyaları ve teslim

- `audit-results/vision-usable/open-probe.json`: source hash/build, gerçek
  worker, sabit Edge kodları, native timing, 0 STT, layout.
- `both-open-desktop.png`, `desktop-blocked-area.png`, `narrow-blocked-area.png`,
  `zoom200-blocked-area.png`: **harf değil**, kabul bekleyen açık-göz açıklaması.
  Görüntüler gerçekten açılıp incelenir; kullanıcı fotoğrafı yerine geçirilmez.
- `motion-pixels.json`: 62 gerçek kare ve ölçüm; fixture lisansı yukarıdadır.
- `worker-cold.json`: aynı worker/piksel ile sıralı CPU/GPU karşılaştırması.
- `stimulus-geometry.json`, `stimulus-desktop.png`, `geometry-css200-A-upright.png`,
  `geometry-narrow-R-right.png`: gerçek kaynak bileşenin boyanmış SVG pikselleri.
  Görüntüler açılıp incelendi; uçlar/rotasyonlar görünür. Kamera, skor, TTS veya
  göz kapısı üretmez; production harf denemesi yerine sunulmaz.
- `physical-presence.json`, `camera-device.json`: katılımcısız gerçek giriş,
  0 saklanan/iletilen kare, ended tracks. Bu dosyalarda fiziksel kabul OPEN.
- `unit-final.log`, npm audit JSON'ları, negatif kamera proof/log'ları.
- `delivery.json`: normal LNK → installed launcher → mevcut repo → temiz SHA →
  BUILD_ID → bütün sunulan Next chunk'ları (worker dahil) SHA256, owned lifecycle,
  diğer Chrome'ların korunması. PR #2 Draft, main değiştirilmez.

Son fiziksel kontrol katılımcıyla yürütülecek: iki açık göz; sol gözü kapalı/el/
cisim; ekrana bakış/doğal hareket/gerçek near-far; bir harf yanıtı/tekrar/pause;
ikinci göz ve izinli sonuç. Bu adımları bir kullanıcıya bilinen yazılım kusuru
olarak devredip görevin tamamlandığı söylenmiyor. **Pozitif kabul hâlâ açık.**
