# Kuruluk bileşen teşhisi ve yeni sarkma kaynak kapsamı

Korunan üretim kaynağı `492949747554bd06ce06bb5ac2994949e54f4deb`, çalışan BUILD_ID `S4upFfAkW8XUxxoM25UK5`. Bu çalışma üretim analizini değiştirmedi. Yeni ilerleme, tek küçük bileşen denemesinin sonucunu ve önceki contour incelemesinin dışındaki sonlu yeni kaynak taramasını kaydetmektir. Önceki 207 PUL, 329 Dry-Skin ve 543 contour temsilcisinin incelemesi tekrarlanmadı.

Makine tarafından üretilen sonuç: `dry-sag-component-evidence-20261013.json`. Yerel ayrıntı/görseller: `audit-results/dry-sag-component-followup-20261013`. Kaynak fotoğraflar, API fotoğraf payload'ları ve izole tarayıcı kayıtları Git'e eklenmedi.

## Tek değişken ve fit öncesi ölçütler

Sabit 16 zor kaynak/ROI, önceki 8 train / 8 validation grup ayrımıyla korundu. Başarısız patch-CART tekrar çalıştırılmadı. Proposal veya parlaklık eşikleri değiştirilmedi. Değiştirilen tek unsur, yama-varlığı sınıflandırması yerine yerel native bağlı bileşenin incelenmiş materyal/gözenek/yansıma desteğiyle ayrıştırılmasıdır.

Protokol, görsel bileşen etiketlerinden ve fit'ten önce donduruldu: SHA-256 `7972bd0c420f868545c370470c7249c9e257fb372628e7ff9d105ab6560d891b`. Tek L2=1 lojistik gate, sekiz geometrik/fotometrik özellik, p>=0,5, en çok 60 Newton adımı; mevcut NumPy kullanıldı. Bu olasılık yalnız bileşenin kabul/ret kapısıdır; şiddet veya harita alpha'sı değildir. Kabul edilen alan unchanged proposal'ın optik desteğinden türetilir.

Önceden belirlenmiş lokal yakalama: kısmi görünür materyal poligonu içinde en az 3 özgün piksel ve en az %10 yerel destek. Mevcut/proposal tarafından yakalanan validation materyalini korumak, incelenmiş negatif desteği proposal'a göre en az %25 azaltmak ve hiçbir incelenmiş negatif ROI'yi mevcut v3 optik fonksiyonunun üstüne çıkarmamak gerekiyordu. Bileşen sürekliliği/boyutu, non-candidate ring kontrastı, doğal/işlenmiş ayrımı, native/yarım çözünürlük ve gerçek ürün skor/haritası ayrıca kaydedildi. Adayın kendisi ve diğer proposal pikselleri arka plan ring referansından çıkarıldı.

50 kısmi yerel etiket görsel incelemeyle kaydedildi: 21 görünür materyal, 24 incelenmiş gözenek/yansıma/doku bölgesi, 5 bilinmeyen. Bunlar uzman biyolojik kuruluk doğrusu veya tam segmentasyon değildir. Bbox/poligon dışı bilinmeyendir; pixel Dice/precision hesaplanmadı. Model çıktısı poligon çizmek için kullanılmadı. Native proposal bileşenleri de görsel incelendi; belirsiz üst-dudak/doku sınırındaki bir bileşen fit öncesi bilinmeyene alındı.

Kaynak/grup train-validation ayrımı korunuyor; aynı kaynağın yamaları farklı split'e dağılmadı. 64 cross-split kaynak pHash karşılaştırmasında en küçük 63-bit uzaklık 24'tür. Bu kişi kimliği kanıtı değildir; kişi bağımsız genel doğruluk iddiası yapılmaz. Önceki yakın kopya aileleri fitting kontrolüne eklenmedi.

## Sonuç: üretime alınmadı

| Native kısmi görünür materyal kapsamı | Nesne sayısı | v3 optik fonksiyonu | Unchanged proposal | Bileşen gate |
|---|---:|---:|---:|---:|
| İşlenmiş PUL | 12 | 1 | 1 | 1 |
| Doğal kökenli ROI | 9 | 0 | 1 | 1 |
| Toplam | 21 | 1 | 2 | 2 |
| Ayrılmış validation | 8 | 0 | 0 | 0 |

19/21 materyal nesnesinde proposal yeterli aday desteği üretmiyor. Örneğin C0'daki büyük, düşük kontrastlı görünen pul içleri yerine küçük doku noktaları kalıyor; C11'de ince materyal boyunca parçalı destek var. Gate, hiç üretilmeyen desteği geri getiremez. Bu temel proposal sınırı, sınıflandırıcı hatasından ayrıdır.

Tek fit'e 4 train / 4 validation kaynak grubundan 8 train / 5 validation bileşeni girdi; bir belirsiz bileşen dışarıda tutuldu. Aday bileşeni üretmeyen diğer sabit kontrol kaynakları nesne paydasından çıkarılmadı. Validation'da tek pozitif proposal bileşeni kabul edildi, 4 incelenmiş negatif bileşenin 2'si de kabul edildi. Bu tek bileşenin korunması, validation materyal poligonunun yakalandığı anlamına gelmez: 8 nesnede yakalama 0. `positivePreserved=true` değeri boş küme üzerindedir; olumlu kabul kanıtı değildir.

Validation incelenmiş-negatif aktif native piksel toplamı proposal 43 → gate 8 (%81,40 azalma); fakat C12'de mevcut v3 4 piksel → gate 5 piksel olduğu için önceden konan negatif koruma koşulu geçmedi. Haritalarda C12 gözenek kenarı, C15 yansıma/doku noktası hâlâ kabul ediliyor. Azalan yanlış boyama tek başına başarı sayılmadı.

Yarım çözünürlük aynı kişinin ayrı örneği değildir: PUL'da proposal 3/12 → gate 2/12; doğal kökenli ROI'de 2/9 → 1/9. Bu kayıplar ve native başarısızlık, çözünürlük/süreklilik sorununu açık bırakıyor. Ek fit veya eşik taraması yapılmadı. Reddedilmiş model hash'i `9f097290a515077f0be4c4d44c729e7d2d4d92edaa1757d95a6542f206c165ce`; üretim loader/config'e eklenmedi.

Gerçek browser payload'ları ayrı Python staging sürecinde mevcut analiz fonksiyonundan geçirildi; sadece dry fotometrik desteği değiştirildi. API cevapları sabit referanslardan doldurulmadı. Diğer kriterlerin değer/reason/sürümü tam eşit; dry bölgesel paydaları aynı; tüm dry haritalarında validMask dışı aktif hücre 0. Kaynak renkleri, maskeler ve diğer gri girişler korunuyor.

| Gerçek capture kaynağı | Üretim v3 Genel Bakış → izole aday | Genel Bakış aktif harita hücresi | Önemli sınır |
|---|---|---|---|
| `24031977` | 0,024508 → 0,008912 | 11 → 4 | Çene 0,136071 → 0,049480; materyal yerelleştirme kanıtı iyileşmiş sayılmadı. |
| `9bab7ab2` | 0,045130 → 0,019857 | 25 → 11 | Sağ yanakta 0 → 0,079007 yeni destek var; skor azalması tek başına güvenilirlik değil. |
| `bffa2b0b` | 0 → 0 | 0 → 0 | Yerel kontrol korunuyor; pozitif yakalama kanıtı değil. |

Buradaki sayılar optik görünüm indeksidir, klinik şiddet değildir. Aday sonuçlar tarayıcıya/normal API'ye etkinleştirilmedi veya kullanıcı geçmişine yazılmadı.

## Contour etiketi dışındaki yeni kaynak taraması

2.666 face grubunun önceki contour-etiket kapsamı dışında 2.093 grup var. Bunların 3'ü önceki SHA kayıtlarında zaten incelenmişti; gerçekten yeni havuz 2.090 grup. Eksik contour etiketi hedef dışı kararı yapılmadı. Model/kalite sonucu görülmeden 96 eşit aralıklı grup-hash sırası ve grup başına en büyük native temsilci seçildi. Tam SHA, grup, hak kapsamı, seçim sırası ve tüm sonuçlar makbuzda.

96 kaynağın tamamında gerçek browser MediaPipe, kalite/poz ve snapshot uygunluğu hesaplandı; dört temas sayfasının tamamı görsel incelendi. Kompozit/siyah bloklu, ifade/poz/sakal/aksesuar engelli veya hedefi belirsiz kaynaklar ayrıldı. Hiçbir yaş veya sıradan nasolabial/mentolabial çizgi sarkma doğrusu yapılmadı. Kaynak hakları `publisher-declared; individual-photo-review-pending` düzeyinden yükseltilmedi; hosted fotoğraf gönderimi yok.

`f42a0640` daha geniş kadrajlı olsa da önceki `f90e68f8` ile aynı portredir; yakın kopya olarak karantinaya alındı, yeni bağımsız pozitif sayılmadı. Tarama dışında **1.994 grup hâlâ incelenmemiştir**. Bu sonlu seçimin içinde doğrulanmış güçlü nötr çene hedefi bulunmadı; kalan havuzda yokluğu iddia edilmez.

| Yeni doğal kaynak | Gerçek normal ürün yolu | Sarkma sonucu / kapsam |
|---|---|---|
| `9bab7ab2` | Gerçek MediaPipe → kalite/FRONT → otomatik çekim → snapshot → normal API → sonuç → aynı fotoğraflı geçmiş | Çene/yanaklar null, EXPRESSION_OPEN_MOUTH_OR_SMILE. Ağız açıklığı 0,004767 olsa da gerçek dikey ağız-köşesi oranı -0,091848, mevcut -0,07 kapısını geçmiyor. Nötr güçlü pozitif diye sunulmadı; kapı değişmedi. |
| `bffa2b0b` | Aynı tam FRONT ve geçmiş zinciri | Çene, yanaklar ve Genel Bakış 0. Olağan kontur kontrolü; sarkma pozitif başarısı değil. |
| `6d0d1b69` | Gerçek MediaPipe → kalite/LEFT → captureSkinAngle → snapshot → normal API | Yalnız görünür sağ yanak 0. Konuşma/ifade ve hedef belirsiz; güçlü çene pozitifi değil. Aynı kişinin tam üç açılı geçmişi kanıtlanmadı. |

İki yeni FRONT kaydı izole profillerde yedi sonuç ve geçmiş görünümünü, Türkçe etiketleri, doğru fotoğraf kimliğini, harita x/y/step dönüşümünü, kriter/bölge değişiminde temizliği, 720px dar pencereyi ve gerçek Chrome %200 görünümünü geçti. Geçmiş byte'ları açma sonrasında aynı kaldı. Kullanıcı profili/kayıtları kullanılmadı. Bu kontroller yeni kaynak zincirinin kanıtıdır; önce tamamlanan runtime/build çalışması yeni ana kazanım değildir.

## Korunan ürün ve somut açıklar

Kuruluk v3, çene v8, yanak v7, göz çevresi yöntemleri, Türkçe etiketler, gerçek ONNX session hash sözleşmesi, hosted izin/config, sesler ve tasarım değişmedi. Üretim kaynak/config farkı baseline'a göre boş; bu nedenle yeni typecheck veya production build gerektiren ürün değişikliği yok. İlgili makbuz zinciri, kaynak hash'leri, split/bilinmeyen kapsamı, gerçek payload scalar ve harita korunumları doğrulandı.

Bir sonraki kuruluk değişkeni aynı parlaklık eşikleri veya gate'i tekrar fit etmek değildir: sabit materyal nesnelerindeki eksik proposal desteğinin, komşu gözenek/yansımayı kabul etmeden oluşturulması gerekir. Yeni deneme bu görevde başlatılmadı. Sarkmada güçlü nötr çene hedefi ve kişi/grup kimliği doğrulanmış kaynak hâlâ açık; diğer 1.994 grubun kapsamı görünür kaldı.

AG alanına dokunulmadı; sivilce çalışması üstlenilmedi. Düzeltilmiş dondurulmuş AG teslimi bu görevde sağlanmadığından 4e747b3 paketi entegre edilmedi; CD'de zaten sabit acne_valid paydası yeni kazanım diye sunulmadı. Yeni uzun eğitim, büyük indirme veya ücretli/hosted çağrı yok. Araştırma araçları/kanıtlar mevcut fix/live-test-followup branch'inde teslim edilir; PR #2 Draft kalır, main merge yapılmaz.
