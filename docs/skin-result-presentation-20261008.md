# Cilt sonuç kadrajı ve gösterimi — 8 Ekim 2026

Sonuç ekranı artık kabul edilen kaynak fotoğrafı canlı taramayla aynı yüz
kadrajı kuralında gösterir. `snapshotRawSkinFrame` hâlâ tam çözünürlüklü,
opak PNG üretir. Ayrı `previewCrop`, yalnız SVG görüntüleme dikdörtgenidir;
kaynak RGB, alpha, örnekleme, poz kabulü ve kayıt/referans verisi değişmez.
Fotoğraf ile seçili anatomik ağ aynı kaynak koordinatlarında kalır. Yanaklar
kendi kabul edilmiş yan pozunu kullanır. Canlı önizleme yumuşatma ve hareket
kontrollerinin davranışı değişmedi; kadraj fonksiyonu ortak yardımcıya taşındı.

Fotoğraf ve sağ bölüm üstten hizalanır. Ölçülen renk indeksleri iki kartta,
`Math.round` ile tam sayı gösterilir: 32,4 → 32; 32,5 → 33. Saklanan ölçüm
ve referans hassasiyeti değişmez. Bunlar belirti yüzdesi değildir. Ölçülemeyen
başlıklarda puan veya boş çubuk gösterilmez; başlıklar ve açılabilir gerekçeler
korunur. Göz çevresinde doğrulanmış gösterge yoksa bu açıkça yazılır.

## Tamamlanmamış yetenekler

Bu teslim aşağıdaki algoritmaları tamamlamaz. Mevcut `skinIndicators.ts`
yalnız görünür ağ üçgenlerindeki ton farkı ve kızarıklık renk indeksini hesaplar.
Diğer kriterler `method: unavailable, score: null` olarak kalır. Ekran
düzenlemesi bu eksikleri kapatmaz; genel cilt kabulü PASS değildir.

| Kriter | Kaynakta eksik olan |
| --- | --- |
| Yağlı görünüm | Işık yansıması ile yağlı görünümü ayıran, bu kamera ve ışık koşullarında doğrulanmış yöntem |
| Sivilce görünümü | Uygun ürün lisanslı model ağırlıkları ve ben/sakal/artefakt ayrımını doğrulayan değerlendirme |
| Sarkma | Poz/ifade etkisini ayıran ve bu kamera akışında doğrulanmış bölgesel geometri/şiddet yöntemi |
| Cilt kuruluğu | Görünen yüzey bulgularını doğrulayan yöntem; fotoğraf renginden nem/bariyer ölçümü çıkarılmaz |

Fotoğrafla sivilce değerlendirmesi araştırmada mümkündür; mevcut üründe
entegre ve doğrulanmış olması ayrı gerekliliktir. [AAD, cilt uygulamalarının
doğrulanması](https://www.aad.org/public/fad/digital-health/apps) farklı ten
tonlarında bilimsel değerlendirme gerekliliğini açıklıyor. Yağ ve nem için
[birincil çalışma](https://pmc.ncbi.nlm.nih.gov/articles/PMC4918584/) özel
kızılötesi spektroskopi kullanıp Sebumeter/Corneometer ile karşılaştırıyor;
bu sonuçlar uygulamanın normal RGB kamerasına aktarılamaz. Bu kaynaklar
TOGG algoritmasının klinik kabul kanıtı olarak kullanılmaz.

## Bu teslimin kanıtı

Production BUILD_ID: `CMVYJH8NBof8G5LUtc4FJ`.
Kontrollü fixture: `audit-fixtures/three-angle.y4m`, SHA256
`224074a52eaf606d02112829ea4b1ce5a93d063edfe006d197a37e6078a70a3c`.
Gerçek production MediaPipe kullanılır; poz/kalite kapıları değiştirilmez.
Fixture gerçek kullanıcı kabulü değildir.

Yerel ayrıntılı kanıt: `audit-results/skin-result-20261008/`.
Önceki fixture görüntüleri `before-*` olarak ayrıdır; önceki fiziksel kanıt
yeni build'e taşınmaz. Yeni görsellerde altı bölgenin kadrajı, seçili ağ,
tam sayı skorlar, opak kaynak fotoğraf ve referans korunumu kontrol edilir.
İkinci tarama native Chrome %200 zoom kullanır (`cssZoom: 1`, DPR 3).
Yakalama, native zoom'da CSS/cihaz piksel farkını koruyan
CDP `contentSize`, cihaz piksel oranı ve page zoom birlikte dönüştürülerek yapılır. Native ölçüm/screenshot JSON'ları
ayrı saklanır; CSS zoom testi native zoom kabulü sayılmaz.

İki tam üç-poz taraması geçti: her taramada üç ayrı kaynak frame token,
altı ayrı seçili ağ ve mevcut referans korunumu doğrulandı. Altı bölgede
gösterim kadrajı kaynak sınırları içinde; ağın tamamı aynı kadrajda kalır.
Yalnız sayısal renk indekslerinde meter bulunur ve görünen/erişilebilir
değerler tam sayıdır. PNG alpha tamamında 255, segmenter istek sayısı 0,
sayfa hatası 0. Native %200 ölçümü: `innerWidth=641`, `scrollWidth=635`,
`outerWidth=1298`, `devicePixelRatio=3`, `cssZoom=1`. Son yakalama
`1907 × 4694` pikseldir ve ölçülen CDP içerik boyutuna eşittir.
Masaüstü, dar ekran ve native %200 sonuç görselleri ayrıca görsel olarak
incelendi. Araç içi küçük yüz fixture'ında canlı önizleme %100/%200 geçti.

Kısa kaynak kontrolleri: 8 test geçti. Production build geçti; önceden
mevcut iki lint uyarısı (Skin effect bağımlılıkları ve CockpitHeader img)
değişmedi. Production bağımlılık audit sonucu 0 bulgu. Önceki rapordaki
7 high geliştirme bağımlılığı bulgusu bu UI teslimiyle kapanmış sayılmaz;
güncel tam audit de 7 high ve 2 moderate gösterir.

Onaylı ses profilleri ve kayıt sistemi değiştirilmedi. Görmenin son build'de
24 denemelik fiziksel kabulü ayrıca açık; bu cilt görsel kontrolü onun yerine
geçmez. Main'e merge yapılmaz, PR #2 Draft korunur.
