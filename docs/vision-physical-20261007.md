# Görme ve Cilt kamera düzeltmeleri — 7–8 Ekim 2026

Bu çalışma `fix/live-test-followup` üzerinde 14cd2a5a8c8438c158655a29591e334c431e379c
kaynağından devam eder. Main'e merge yapılmaz; PR #2 Draft olarak korunur.
Cilt sonucu, segmentasyon, anatomik ağlar, Ruhsal İyi Oluş ve kayıt sözleşmesi
değiştirilmez. Kullanıcının son isteğiyle Cilt kamera önizlemesi ve kaynak
kadraj kabulü ayrıca güncellenir. Görme yönerge metni değişir; exact ses
profilleri değişmez. Kullanıcı tekrar tekrar fiziksel denemeye çağrılmaz.

## Gerçek denemede bulunan sorunlar

- CPU inference gerçek UGREEN oturumunda zamanla yavaşladı: ilk 30 saniye
  medyan 154,85 ms, 120–150 saniye aralığı 452,4 ms. GPU adayının 460 sayısal
  gözleminde medyan 94,05 ms idi. Bunlar aynı an ve aynı pozda eşleştirilmiş
  benchmark değildir; kesin hızlanma oranı üretilmez. GPU, bu cihazdaki gerçek
  kamera denemesine göre varsayılan oldu; explicit CPU teşhis seçeneği korunur.
- Fiziksel göz kapatmada diğer gözün göreli açıklığı .63–.72 ve düşük blink
  katsayısıyla görünür kalabiliyordu; eski .74 sınırı onu reddediyordu. Yeni
  .62 aday sınırı düşük blink, yerel görünür şablon ve örtü bulunmamasıyla
  birlikte gerekir. Kapalı sınırı .58, süreklilik 600 ms ve gözlem boşluğu
  sınırı 300 ms korunur. Bunlar klinik kalibrasyon değildir.
- Kısa blink/uncertain karesinde TTS ve STT hemen iptal ediliyordu. Güncel cevap
  kapısı hemen kapanır; kısa aralıkta aynı harf/yönerge ve recognition instance
  korunur. 800 ms sürekli uygunsuzlukta harf gizlenir, ses/mikrofon durur ve
  deneme puansız kalır. Koşul adının değişmesi bu süreyi yeniden başlatmaz.
- Geçerli yanıtın kabulü recognition instance, oturum/sunum/göz token'ı,
  güncel gerçek kamera koşulu ve görünür ölçülmüş SVG ile ayrı korunur.
  Geçersiz anda gelen gerçek final yanıt değerlendirme dışıdır. ASR'nin gerçek
  parsed harf/yönü ve kabul/ret nedeni ekranda gösterilir; ham konuşma tutulmaz.
- Gerçek `F / baş aşağı` yanıtı ayrıştırıldığı halde 1/12'de kalmasının kesin
  nedeni: `respond(...performance.now(),...,measureSymbol())` soldan sağa
  değerlendirildiğinde cevap saati gerçek DOM ölçümünden önce alınıyordu.
  `now < geometry.measuredAt` koruması bu yanıtı reddediyordu. Şimdi geometri
  önce ölçülür, cevap saati sonra alınır; gelecekteki/eski/boş geometriyi
  reddeden kontrol korunur. Artan saatli regresyon bu üretim çağrı sırasını
  sınar. Mikrofon hazırlığı/yönerge/dinleme durumu harfin yanında görünür.
- Harf görünürken mikrofon yönerge bitmeden başlar. Audio ended yalnız TTS
  kaynağını kapatır; aynı recognition instance, sunum token'ı ve bekleyen yanıt
  kalır. Geçerli yanıt yönergeyi keser. TTS süresi tepki süresine eklenmez.
- Native tanımanın ayrı final `R` ve `baş aşağı` parçaları aynı sunumda
  birleştirilir. İlk eksik parçada mikrofon kesilmez; kısa açıklama bekleyişi
  konuşma başlangıcında ertelenir. Pause, yeni harf, izin ve uzun koşul kaybı
  bu bekleyişi iptal eder. Hedef harften/yönden eksik alan tamamlanmaz.
- Sesli cevap yönergelerinde harf/yön örneği kalmaz; seçenekler yazılıdır.
  Böylece açık mikrofonun hoparlörden duyduğu yön, kullanıcının eksik alanını
  dolduramaz. Sabit yönerge yankıları ayrıca süzülür. Duyulan metin yalnız
  aktif ekran belleğinde gösterilir; dosyaya veya kalıcı kayda eklenmez.
- Yönergede sıra serbesttir. `baş aşağı R`, `R baş aşağı`, `sola yatmış P`
  ve şehir koduyla yanıtlar aynı ayrıştırıcı sözleşmesindedir.
- Kapalı/örtülü sınıf geçişi kapalı-göz sürekliliğini sıfırlamaz. Göz yumma,
  el ve opak cisim aynı kabul kapısına gider; sınıf/metot kanıtı ayrı kalır.
  Açık/uncertain kare veya >300 ms gözlem boşluğu sürekliliği sıfırlar; 600 ms
  blink ayrımı ve karşı gözün açıklığı korunur.
- Gerçek örtü kaydında bir baş-çifti .426 saparken diğer altı .039–.183
  aralığında kalmıştı. Tek aykırı çift dışlanabilir; en az üç kalan çift,
  mevcut .24 yayılım ve rakip kümeler için mevcut .10 toparlanma bandı gerekir.
  Çelişen/az ölçüm hâlâ unknown'dur. Yakın/uzak eşikleri .15/.10 değişmez.
- Her koşul duraklatmasındaki modal, örtü tutulurken akışı kilitliyordu.
  Durum açıklaması harf alanında görünür; güvenilir koşul döndüğünde otomatik
  devam eder. Kullanıcının Duraklat/Bitir/izin kapatma davranışı korunur.
- Ham tam karede yüz yüksekliğinin %25 olması, yerel göz ayrıntısından farklı
  bir şarttı. Kadraj şimdi tam yüz sınırları ve gerçek okunabilir göz ROI
  pikselleriyle kontrol edilir. Işık/netlik, sabit göreli baş referansı ve
  yakın/uzak hysteresis kontrolleri korunur; crop/zoom analiz girdisi değildir.
- El modeli tarafından algılanan avuçla örtülü göz, açık göz başlangıcına
  alınmaz. Gerçek fiziksel örtüde el modelinin palmCoverage değeri bazı
  denemelerde 0 kaldı; bu palm-model pozitif kabulü değildir. Opak örtü için
  geniş ROI değişimi/NCC ve dar ROI kaybı kullanılır. Dar NCC tesadüfen yüksek
  kaldığında daha güçlü geniş ROI kanıtı (> .75 değişim, NCC < .08) gerekir.
  Diğer açık göz, görünür baş ve süreklilik şartları kaldırılmaz.
- Yalnız göz büyüklüğündeki opak cisim kaşı da örtmek zorunda değildir.
  Dar gerçek göz ROI'sindeki güçlü RGB değişimi (> .65) ve şablon kaybı
  (NCC < .18), geniş ROI'de kaş korunurken de örtü adayı olabilir. Bunlar
  mevcut geniş ROI sınırlarıdır; anatomik taraf, kaynak ayrıntısı, görünür baş,
  diğer açık göz ve 600 ms süreklilik ayrıca gerekir. Doğal açık göz hareketi
  lisanslı gerçek video pikselleriyle yanlış örtü sınıflaması için sınanır.
- Anatomik taraf, aynasız kaynakta burun köprüsü–burun orta hattına göre de
  doğrulanır. Burun veya el varlığı tek başına örtülü göz kabulü üretmez.
- Test penceresindeki emüle 1530 CSS piksel viewport, bu Windows ekranında
  gerçek 1280 CSS piksel pencereye sığmıyordu. Fiziksel test artık native
  pencere kullanır. Görme grid'inde genişlik sınırları, kompakt harf alanı ve
  yeni harf dışarıdaysa görünür alana kaydırma bulunur. Gerçek native ölçümde
  harf alanının sağ kenarı 1134,17 < 1280; yatay document genişliği 1274'tür.
  Video computed transform `none`; CSS zoom `1` idi.
- Başlangıç devam ederken yeni kamera açılışı başlatılamaz. Bekleyen eski
  getUserMedia/worker yanıtlarının token koruması sürer. Gerçek tekrar
  denemesinde görülen NotReadableError izin reddi gibi raporlanmaz; diğer
  kamera kullanımını bitirip yeniden deneme açıklanır.

## Cilt kamera önizlemesi

Canlı video ve gerçek SVG noktaları aynı kaynak katmanında, aynı yumuşatılmış
yüz crop'u ile büyütülür. Ham analiz/çekim tuvali ve kalite ölçümü tam decoded
karede kalır; sonuç SVG/portre/maske/ağ dalı değiştirilmez. Alın ve çene crop
payları korunur; aynalama eklenmez.

Tam karedeki .28–.68 yüz oranı yerine gerçek landmark sınırlarından eksiksiz
kaynak kadrajı kullanılır. Bu yeni ölçüm hem ön hem üç poz kapısına gider.
Yaw/pitch/roll, gerçek yüz ROI ışık/netlik, duplicate-frame ve referans uyum
kontrolleri korunur. `scaleRatio` ham kaynak oranı olarak kalır; ekran zoom'u
onu veya kaliteyi değiştirmez. Detay eklenmez; düşük çözünürlük uyarısı sürer.
Canlı önizleme en fazla ekran yüksekliğinin %65'ini kullanır.

Lisanslı Head_Shake tam kaynak karesiyle kontrollü production kamera testinde
ham yüz oranı .21, kaynak kadrajı ve ön poz kabulü true oldu. Önizleme crop
genişliği .348934 idi. SVG/video dönüşümü ve nokta hizası gerçek DOM'dan
ölçüldü. Chrome native zoom 100%/200% için DPR 1.5/3 ve CSS viewport
1266/633 olarak doğrulandı; yatay taşma yoktu. İptalde tracks ended idi.
Bu, fiziksel kullanıcı/üç poz/portre yüksek-detay kabulü değildir. Yalnız
segmentasyon hazırlığı görüntüyü incelemek için ertelendi; yüz modeli veya
kalite/poz cevabı değiştirilmedi. Görsel PNG'ler ayrıca açılıp incelendi.

## Kanıt sınırları

Yerel `audit-results/vision-physical-20261007` altında gerçek kamera sayısal
oturumları, yalnız harf alanının PNG'leri ve cleanup kayıtları vardır. Yeni
kamera fotoğrafı, yüz görüntüsü veya ham konuşma kaydı alınmaz. OpenAI çağrısı
0; gerçek Edge çağrıları yalnız sabit kişisel olmayan yönerge kodlarıdır.

Önceki 14cd CPU sürümünde gerçek A harfi görüldü. GPU/önceki düzeltme
denemelerinde harf görülse de sıra 1/12'de kaldı; tamamlanmış kabul verilmez.
`after5` gerçek kamerada yerleşim, kapalı göz koşulu, actual SVG ve native
recognition onstart doğrulandı; kullanıcı yanıt verdiğini bildirmesine rağmen
sıra ilerlemedi. Kısa blinkte recognition iptali bundan sonra düzeltildi.
`after9` native ASR `R` (199862 ms) ve `baş aşağı` (208392 ms) parçalarını
aynı sunumda birleştirip gerçek sırayı 2/12'ye ilerletti. Tam 24 deneme kabulü
verilmez. Bu kabul önceki build'e aittir; son kaynak continuous recognition,
konuşma kesilmeyen parçalama ve örtü sürekliliği düzeltmelerini ayrıca içerir.
Yönerge sırasında tam erken yanıt, gerçek cisim örtüsü ve bütün kabul matrisi
son build için fiziksel olarak doğrulanmış sayılmaz. Kullanıcıyı tester olarak
tekrar denemeye çağırmak bu açıkları kapatma yöntemi değildir.

Fiziksel denemede gönderilen Ctrl+zoom tuşları bu Chrome otomasyonunda native zoom'u
değiştirmedi (1280/DPR 1.5 kaldı). Bu %200 kabulü değildir. Ayrı kontrollü
Cilt denemesinde gerçek native %200 yukarıdaki DPR ile doğrulanmıştır. Önceki CSS zoom
fixture'ı da native browser zoom veya gerçek kullanıcı kabulü sayılamaz.

60 ilgili durum/skor/geometri/integration ve Cilt kadraj regresyonu geçti.
Son küçük-örtü değişikliği ayrıca 4 ilgili kontrolden geçti. Sayısal son
sonuç ayrı teslim kanıtıyla kaydedilir. Bunlar fiziksel
kamera, opak cisim veya konuşma kabulünün yerine geçmez. Fixture negatif
testleri actual model kullanır; sabit Google portrait dosyasının lisansı
doğrulanmamıştır, dağıtılmaz ve fiziksel kullanıcı kanıtı gibi sunulmaz.

## Son production build kontrolleri

`BUILD_ID: tS6OTztI_j4P0XXQoCfmU`. Son production build ile Cilt kaynak
kadraj/zoom, iki göz açık negatif akış, kamera/privacy/voice-failure
ve lisanslı doğal hareket pikselleri kontrollerinin dördü de geçti.
62 doğal hareket karesinde yanlış kapalı veya örtülü göz sayısı 0 idi.
Bu negatif kontrollü kanıt, gerçek erken konuşma veya dört fiziksel
örtme yönteminin tam kabulü değildir. Korunan sekiz sonuç/kayıt/ses
kaynak dosyası 14cd2a5 ile LF-normalize karşılaştırmada aynıdır.

## Güvenlik ve teslim

Bağımlılıklar bu kapsamda değiştirilmedi. Önceki 7 high dev bulgusu kapatılmış
sayılmaz. 7 Ekim güncel npm audit: 8 high + 2 moderate; omit=dev audit'te
source-map-js için 1 high bulunur. Yeni advisory'ler nedeniyle önceki 0 prod
iddiası güncel değildir. Bu bulgular gizlenmez ve bu Görme değişikliğiyle
giderilmiş sayılmaz.

Exact SHA/BUILD_ID, push, normal Unicode Windows kısayolu → launcher → ürün
klasörü → served chunk hash zinciri, ayrı yerel teslim kanıtında kaydedilir.
Fiziksel kabul ve subjektif ses kabulü, kısayol teknik başarısından ayrıdır.
