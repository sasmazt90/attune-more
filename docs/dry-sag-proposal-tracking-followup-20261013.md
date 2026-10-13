# Kuruluk proposal ve çene takip residual düzeltmesi

Başlangıç: `5a40a1276c9eccc6bd099d42775dcd7eb4e3e604` / `S4upFfAkW8XUxxoM25UK5`. Üretim yöntem commit'i: `296ee550fd17cf3266ba15573f2d452426a93193`. Yeni normal kısayol BUILD_ID: `JO0Xyvupv72uoBiX42mWq`. Önceki build `.runtime/skin-before-chin-tracking-v9-20261013` içinde korundu.

Bu görev mevcut 50 yerel etiketi, 16 zor kaynak/ROI'yi ve kaynak/grup ayrımını kullandı. Kaynak taraması, etiket hazırlığı, model kimliği geliştirmesi veya classifier fit'i tekrarlanmadı. Görülmüş validation kaynakları **bağımsız final test değildir**. Makine makbuzu: `dry-sag-proposal-tracking-evidence-20261013.json`; ayrıntı/görseller: `audit-results/dry-sag-proposal-tracking-20261013`.

## Kuruluk: classifier olmadan bağlı bölge proposal

Tek deneme protokolü sonuçlar görülmeden donduruldu: `c17cabb0c94035112936669f1782ca33fbaa5ed49e512e4df5d74850f6c4a925`. Mevcut 50 etiket dosyasının SHA-256'sı `f0cec2daf46fd2f745dccf21e20c0f22c2bf59e1ff28b4039352091f984d7e34` değişmedi. Kabul için native materyalde en az 8/21, tanıdık validation materyalinde en az 3/8 yakalama ve incelenmiş negatif yerel alanın belirlenmiş sınır içinde kalması gerekiyordu. Negatif sınır, v3'ün iki katı veya v3 + 0,25 yüzde puanından büyük olanıdır; tek yanlış piksel otomatik ret değildir. Ürün alanında 0,5 görünüm-indeks puanından büyük yeni yanlış artış kabul edilmez.

Yeni değişken piksel tepelerini gate ile sınıflandırmak değil, native Lab-L üzerinde kararlı bağlı parlak bölge çıkarmaktır: MSER delta=5, alan 4–1500, variation=0,25; geometri, adayın kendisini dışlayan ring kontrastı, gerçek sınır kenarı ve küçük gözenek yanındaki karanlık ringing desteğiyle sınırlanır. Gerçek MSER piksel kümesi kullanılır; bbox/poligon doldurulmaz. Etiket, kaynak adı veya kişi/grup bilgisi inference girdisi değildir. Önceki CART veya lojistik gate tekrar fit edilmedi; proposal kabulü geçmediği için ikinci gate değerlendirmesine geçilmedi.

| Native materyal kapsamı | Önceki proposal → bağlı bölge proposal |
|---|---:|
| Küçük materyal, 9 kısmi alan | 2 → 5 |
| Geniş materyal, 12 kısmi alan | 0 → 5 |
| İşlenmiş PUL, 12 alan | 1 → 5 |
| Doğal kökenli ROI, 9 alan | 1 → 5 |
| Toplam | **2/21 → 10/21** |
| Görülmüş validation | **0/8 → 2/8** |

Yakalama, aynı önceden kayıtlı optik ölçüttür: kısmi materyal poligonunda >=3 özgün piksel ve >=%10 yerel destek. Klinik kuruluk, tam segmentasyon, pixel precision veya Dice değildir. Bütün bbox/poligon dışı alan bilinmeyen kalır.

İncelenmiş 24 negatif gözenek/yansıma/doku bölgesindeki native aktif piksel toplamı mevcut v3 optik fonksiyonunda 30, yeni proposal'da 4'tür; tanıdık validation negatiflerinde 13 → 0. Kalan 4 piksel C5'te %0,625 → %0,3125 yerel destek oluşturuyor; gizlenmedi, ancak önceden konan anlamlı-alan sınırını geçmiyor. Bu sayı tüm fotoğrafın FPR'si değildir; incelenmemiş alan negatif değildir.

Eski proposal'da materyal yakalama aşamaları: median tepe 21 → LBP 21 → MAD 2. Bu sabit materyal kümesindeki ana kopma LBP değil, MAD kapısıdır. Üretim native optik fonksiyonunda DoG 11 → LBP 11 → kontrast 10 → dark-ringing 1 → kompaktlık 1. Aşamaların toplam nesne sayıları, her poligon içindeki gerçek piksel/bileşen sayılarıyla birlikte kaydedildi; kompaktlık piksel desteğini ayrıca azaltabiliyor.

Somut örnekler:

- **C0/object 0–2** geniş materyali yeni yöntem 177/192/145 piksel ile buluyor. Önceki MAD desteği üçünde de 0. Üretim dark-ringing kapısında 40/39/47 piksel 5/13/0'a, komponent kapısında 1/8/0'a düşüyor.
- **C8/object 0**, **C9/object 0–2** geniş/düşük kontrastlı materyali yeni yöntemde ilk kararlı-bölge çıkarımı bile bulamıyor; sonraki geometri/ring/kenar kapıları kaybın nedeni değil. C11/object 0 ve 2 de aynı ilk aşamada kayıp. Tam source-polygon koordinatları ve SHA/grup kayıtları JSON'da.
- **C3/object 1** küçük materyalinde kararlı bölge 4 piksel buluyor; küçük gözenek/karanlık-komşuluk kapısı bunları sıfırlıyor. Bu gerçek materyal kaybı negatif azaltma kazanımı altında gizlenmedi.

Yarım çözünürlükte PUL 3/12 → 5/12, doğal kökenli ROI 2/9 → 0/9. Bu ölçek kaybı ve tanıdık validation'ın 2/8 kalması nedeniyle aday yeterli kabulü geçmedi. Parametre taraması veya ikinci fit yapılmadı.

Üç gerçek browser payload'ında yalnız izole dry proposal staging karşılaştırması yapıldı; bölgesel/geometrik payda aynı, diğer yöntemler aynı, validMask dışı aktif harita hücresi 0. Genel Bakış: `24031977` 0,024508 → 0,011140; `9bab7ab2` 0,045130 → 0,007221; `bffa2b0b` 0 → 0. Bunlar skor azalmasının başarı olduğu iddiası değildir. Native materyal desteği ürün crop/ölçeğinde hâlâ yeterince güvenilir yerelleşmiyor. Bu çıktı normal API'ye veya geçmişe etkinleştirilmedi; **kuruluk v3 aktif**.

## Çene: residual gerçek fold üzerinde hesaplanır

Gerçek üç kaynakta gözlenebilir örnek sayısı 64/64, geçersiz örnek 0'dır. Dolayısıyla bu üç kaynakta sorun gözlenmeyen satır değil, **fold olmayan satırın argmax koordinatının da takip kalitesine katılmasıdır**. Geçersiz satırlardaki varsayılan argmax da kontrollü regresyonla ayrıca doğrulandı; v9'da böyle bir koordinat ölçülmüş kaynak noktası olarak taşınmaz.

Çene v9 yalnız anatomik olarak gözlenen ve gerçek valley/fold desteği olan kesintisiz parçaları residual'a katar. Mevcut sigma=2 ölçeği için en az 5 örnek (2*sigma+1) gerekir. Her parça kendi içinde aynı guide-relative smoothing hesabını kullanır; boşluk üzerinden filtreleme veya süreklilik kurulmaz. 2,5 residual eşiği yükseltilmedi. Poz, ifade, exposure, alt-çene bandı ve bağımsız gerçek kontur doğrulaması değişmedi. Yanak v7 ve torbalanma bu yeni takip modunu kullanmaz.

Durumlar ayrı:

- Anatomik band gözlenmiyorsa mevcut görünürlük kapısı null üretir.
- Görüntü/band gözlenebilir ve hiçbir fold yoksa optik sonuç 0 olabilir; bu klinik sağlıklılık değildir.
- Yalnız kısa/kopuk fold parçaları varsa `fragmented-fold-support` / `CONTOUR_TRACKING_INSUFFICIENT_SUPPORT`, residual=null ve skor=null kalır.
- Yeterli kesintisiz parça varsa yalnız bu gerçek noktaların residual'ı hesaplanır; yüksek gerçek residual hâlâ `CONTOUR_TRACKING_UNSTABLE` ile reddedilir.

| Aynı taze gerçek browser payload'ında çene | Eski bütün-satır residual | Gözlenen fold / kabul edilen parça | Yeni residual | Ürün sonucu |
|---|---:|---:|---:|---|
| `f90e68f8` | 2,784979 | 19 / 0 | null | null; yetersiz kesintisiz fold |
| `40d781eb` | 2,898893 | 36 / 28 | **1,969289** | **null → ölçülebilir 0** |
| `64b02ede` | 2,635684 | 3 / 0 | null | null; yetersiz kesintisiz fold |

Bu eski/yeni karşılaştırma taze browser payload'ını başlangıç commit'inin donmuş fonksiyonuna ve gerçekten sunulan yeni API'ye geçirir. Mevcut kaynak-koordinat görselleri, anatomical guide, observed/fold/invalid ayrımı ve bütün eski seçilmiş koordinatları saklar. Yeni canlı cevap aynı payload üzerinde mevcut kaynak fonksiyonuyla tam eşleşir. Hedef dışındaki bütün değer/quality/reason/normalization alanları eşittir.

`40d781eb`'de ordinary çene konturu bağımsız lokal fold'u doğrulamadığı için sonuç 0 ve pozitif harita desteği 0'dır; sağlıklı tanısı veya sarkma pozitif yakalama kanıtı değildir. `f90e68f8` yanakları 0,428393 / 0,012907, Genel Bakış 0,163993 korunuyor; UI %0'a yuvarlanması ham sinyalin yokluğu sayılmadı. Normal mentolabial çizgi regresyonu 0 kaldı; kontrollü gerçek alt-çene fold sinyali korundu.

Skor/harita aynı kabul edilen gerçek fold merkezlerinden türetilir; gözlenen sıfır-destek örnekler paydadan çıkarılmaz. Anatomik koridor alanı tahmine bağlı değişmedi. Genel Bakış ve bölgeler mevcut unique-source-center birleştirmesini kullanır; mükerrer kaynak merkezleri bir kez sayılır. Mesh dışında aktif harita yok, skor tabanı yok, fotoğraf/renk/arka plan değişikliği yok.

## Sürüm, geçmiş ve teslim

Yeni normalization `contour-fold-lower-chin-observed-runs-v9`, sampling `lower-chin-observed-fold-runs-unique-centers-v9`, takip kalitesi `observed-fold-runs-v2`. Çene ve Genel Bakış geçmiş karşılaştırmaları bu farkı ayırır. Eski v8 render desteği korunur; eski kayıtlar yeniden hesaplanmaz.

26 ilgili regresyon geçti. Typecheck ve tek izole production build geçti. Normal TOGG penceresi kapatılarak launcher API isteklerini doğal olarak boşalttı; eski S4 build korundu, yeni build normal `TOGG Başlat.lnk` ile açıldı. Üç gerçek kaynak izole profillerde MediaPipe → kalite/poz → otomatik çekim → snapshot → normal API → sonuç → aynı fotoğraflı geçmiş akışını geçti. Yedi görünümde harita x/y/step, kriter/bölge değişiminde temizleme, 720px dar pencere ve gerçek Chrome %200 kontrolü geçti; hosted çağrı 0.

Önceki gerçek izole `40d781eb` v8 kaydı yeni build üzerinde açıldı: çene hâlâ “—”; yeni v9 kaydı 0. Her iki profilin geçmiş SHA'sı açılıştan önce/sonra eşit. Reanalysis isteği 0. Aynı gerçek kayıtların comparison fonksiyonu hem Genel Bakış hem çenede canCompare=false ve iki ayrı seri üretir; yeni normalization eski kayda yazılmadı.

Normal kısayol teslim makbuzu 115 frontend kaynak hash'ini staged build ile, 18 sunulan JavaScript hash'ini yerel build ile ve 5 yüklü backend kaynağını commit/çalışma dosyasıyla eşleştirdi. Mevcut ONNX kimlik/hosted izin sözleşmesi korundu; bu bir yeni model kimliği çalışması değildir. Kullanıcı kayıtları, sesler, diğer sağlık modülleri ve AG dosyaları/modelleri/süreçlerine dokunulmadı. Sivilce veya reddedilmiş maskeler etkinleştirilmedi.

Somut açıklar: kurulukta ilk kararlı bölge aşamasında kalan geniş/düşük kontrast ve ince materyal kayıpları, küçük gerçek materyalin pore gate'inde reddi ve doğal kaynakta ölçek dayanıklılığı; sarkmada `f90e68f8`/`64b02ede` için yeterli kesintisiz gerçek alt-çene fold desteğinin bulunmaması. Yeni kaynak taraması veya classifier ile bu engeller gizlenmedi. PR #2 Draft kalır; main merge yok.
