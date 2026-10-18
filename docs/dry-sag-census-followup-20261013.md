# Kuruluk / sarkma: genişletilmiş kaynak incelemesi ve oturum kimliği

Başlangıç: `129f661c52985ce43d32fc4476b602a5bed5e43d`.
Normal ürün frontend BUILD_ID: `S4upFfAkW8XUxxoM25UK5` korunuyor.
Sayısal makbuz: `dry-sag-census-evidence-20261013.json`.

## Gerçek yeni kapsam

| Kaynak | Envanter / önceki grup | Yeni görsel inceleme | Temsilci sonucu |
|---|---|---|---|
| PUL | 687 fotoğraf / 255 grup; önceki SHA kayıtlarıyla 48 grup (ilk 45 ve sonraki 3) | Kalan 207 grubun tamamı, 9 contact sheet; ayrıca 3 grupta 13 temsilci/alternatif | 78 yerel optik incelemeye uygun, 59 belirsiz, 62 pullanma pozitifi olarak reddedildi, 8 yüz dışı/birleşik |
| Alt yüz contour etiketleri | 573 grup; 30 önceki | Kalan 543 temsilcinin gerçek browser MediaPipe kalite/poz hesabı görsel incelemeden önce; ardından 23 sheet'in tamamı | 13 ayrıntılı inceleme adayı, 9 belirsiz, 521 nötr doğal ürün kabulü için reddedildi |
| Dry-Skin zayıf fotoğraf etiketi | 445 fotoğraf / 349 grup; 20 önceki | Kalan 329 temsilci, 14 sheet'in tamamı | 28 yerel incelemeye uygun, 41 belirsiz, 200 görünür pullanma pozitifi olarak reddedildi, 60 yüz dışı/illüstrasyon |

Bunlar bağımsız kişi sayıları değildir. Kalite kabulü görsel hedef etiketi olmadı. PUL'un işlenmiş/CLAHE provenance'ı korunuyor; alternatiflerde dönüşüm ve farklı fotoğraf kapsamları bulundu. Özellikle PUL92'nin chin ve cheek üyelerinin etiketi aynı kabul edilmedi. Temsilcinin sınıfı bütün grup üyelerine aktarılmıyor. PUL32/87/107 ile doğal `24031977` aynı kaynak ailesine yakın örneklerdir; fitting kontrolünde kullanılmadılar.

İncelenmeyen kapsam: bu üç alt-yüz contour etiketi dışındaki 2.093 face grubu ve bütün alternatiflerin tamamı. İnceleme biyolojik kuruluk/sarkma uzman doğrusu değildir. Yaş, Dry-Skin, nasolabial fold veya mental crease etiketi otomatik pozitif yapılmadı. Manifestteki publisher-declared / individual-photo-review-pending hak bilgileri yükseltilmedi; bütün işlemler yereldir.

## Sabit ROI, sonlu yerel aday

Fit öncesinde 16 kaynak ve incelenmiş yerel ROI sabitlendi. İki ilk ROI, model sonucu görülmeden kaynak piksel ızgarasında aynı fotoğraf üzerinde düzeltildi; ilk taslak korundu. 62 yerel yama tek tek görsel incelendi: 29 train, 28 validation, 5 bilinmeyen. Aynı kaynak/grup yaması iki split'e dağılmadı; kişi kimliği bulunmadığından kişi bağımsız doğruluk iddiası yoktur. İncelenmiş ROI dışı bilinmeyendir.

Mevcut native bright proposal değiştirilmeden kontrast, non-candidate arka plan, doku/LBP, kenar yönlülüğü, karanlık/parlak komşuluk ve bağlı bileşen özellikleri kullanıldı. Ücretsiz mevcut NumPy ile tek, derinliği 3 / minimum yaprağı 3 olan ağırlıklı CART fit'i 0,093 saniyede tamamlandı. Paket indirme, CNN veya parametre taraması yapılmadı. Model JSON hash'i `4cd81f1750fbee5a0fdb5bae279b2ae9bcf7437b9565502583cb11da18213f26`; accepted=false.

| Ayrılmış optik validation kapsamı | Pozitif yama yakalama | İncelenmiş negatif yanlış kabul |
|---|---:|---:|
| İşlenmiş PUL | 3/8 | 2/4 |
| Doğal kökenli fotoğraf ROI'leri | 1/6 | 4/4 |
| Önceki doğal gözenek/yansıma kontrolleri | Pozitif yok | 2/6 |
| Toplam | 4/14 | 8/14 |

Bu yama varlık ölçümüdür; pixel precision/Dice, klinik başarı veya uygulama doğruluğu değildir. Reddedilme gerekçesi tek bir sıfırdan farklı piksel değil: görünür pulları içeren 10/14 yama kaçarken gözenek/yansıma dokuları kabul ediliyor. Pozitif bağlam içinde de native proposal geniş pul içlerini kaçırıp parlak gözenek kenarlarını bırakıyor. Yarım/nativе çözünürlükte sabit ROI alanı, bileşen boyutu, yoğunluk ve non-candidate referansa göre kontrast sayımları `candidate-local-comparison.json` içinde; yerel haritalar ayrı saklandı. Genel bulanıklaştırma, yeni parlaklık eşiği veya yapay %1 tabanı eklenmedi.

## Gerçek ürün girdileri

Her kaynak JPEG SHA'sı envanterden doğrulandı; gerçek kamera fotoğrafı video kodlamasından sonra ayrıca capture pixel SHA'sıyla eşleştirildi. SDK, kalite/poz, otomatik çekim, snapshot, normal API, yeni sonuç ve aynı kaydın fotoğraflı geçmişi izole profillerde çalıştı. Hiçbir skor/API cevabı önceden yazılmış referanstan doldurulmadı.

| Kaynak | Gerçek sonuç | Kapsam kararı |
|---|---|---|
| `24031977` | Kuruluk v3 Genel Bakış 0,024508; sağ/sol yanak 0/0. İzole native aday: 0,062384; sağ/sol 0/0,093036 | Görünür peeling materyali var, biyolojik neden doğrulanmış değil. Payda aynı; skor artışı materyali güvenilir yerelleştirmiyor. Aday ürüne alınmadı. |
| `f90e68f8` | Sarkma sağ yanak 0,428393; sol 0,012907; Genel Bakış 0,163993. Çene null: CONTOUR_TRACKING_UNSTABLE | Yeni nötr doğal alt-yüz kıvrım kaynağı. Küçük optik yerel destek; UI %0'a yuvarlansa da ham sinyal sıfır değil. Klinik sarkma veya güçlü çene pozitifi kanıtı değil. |
| `40d781eb` | Yanaklar 0/0, çene null: CONTOUR_TRACKING_UNSTABLE | Sıradan nasolabial görünüm ortak alt-jaw sarkma doğrusu yapılmadı. Sıfır sonuç pozitif yakalama başarısı değil. |
| `64b02ede` | Yanaklar 0/0, çene null: CONTOUR_TRACKING_UNSTABLE | Doğal nötr kaynak, uzman joint-target etiketi yok; kapsam sınırlaması açık. |
| `99f82af5` | Sarkma null: EXPRESSION_OPEN_MOUTH_OR_SMILE | Kamera kalite/poz geçse de gerçek hedef ifade kapısı reddetti. Nötr pozitif kabulü sayılmadı; override uygulanmadı. |
| `fc3a6b13` LEFT | Yalnız sağ yanak; sarkma null: ifade kapısı | Gerçek matchesSkinAngle/captureSkinAngle/API yolu; ters taraf ölçülmedi. |
| `be98fae6` RIGHT | Yalnız sol yanak; sarkma 0 | Gerçek yan poz yolu, olumlu tespit başarısı sayılmadı. |

LEFT/RIGHT örnekleri iki farklı bağımsız kaynaktır; aynı kişinin üç açılı geçmiş kabulü diye sunulmaz. Başarılı FRONT akışları yedi görünümü, Türkçe etiketleri, eski haritanın temizlenmesini, dar pencereyi ve gerçek Chrome %200 görünümünü kapsıyor. İlk `24031977` profilinde fotoğraf izni işlemi bitmeden navigation yapılmıştı; sayısal kayıt vardı, fotoğraf satırı yoktu. İkinci izole profil gerçek checkbox işlemini bekledi; fotoğraflı geçmiş geçti. Ürün kayıt kodu veya kullanıcı izinleri değiştirilmedi, ilk kanıt korundu.

Aynı gerçek 5 payload tekrar normal API'ye gönderildi; mevcut bütün sayısal yöntemler korundu. Kabul edilmiş contour merkezleri ve anatomik destek görselleri üretildi. 47 dry/sag haritasında validMask dışı aktif hücre 0; kaynak-grid rounding karşılaştırmasında 12 hücre iki kaynak piksel raster farkı içinde, bunun dışı 0. Kesin annotation Dice türetilmedi. SVG harita x/y/step/ölçek ve capture kimliği gerçek tarayıcıda doğrulandı.

## Runtime kimliği: disk / oturum / kullanılan cevap

`skin_models.load()` model byte'larını SHA-256 ile doğruluyor ve aynı byte dizisini ORT'ye veriyor. Yalnız başarıyla oluşturulmuş oturum immutable sessionMetadata alıyor. Çıktının modelHash'i manifestten değil bu metadata'dan geliyor. Başarısız yükleme ve kullanılmayan/uygun olmayan payload ayrıdır; başarısız type yüklemesi modelHash=null döndürür. Loaded oturum varken config değişirse gerçek loaded hash gizlenmez; matchesConfiguredHash bunu ayırır.

Normal backend'de gerçek FRONT cevabı için degrees fileHashVerified=true / sessionLoaded=true / usedInResponse=true; hash `65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3`. Uygun olmayan ilgili FRONT ve SIDE payload'larında aynı yüklü oturum status=not-used / usedInResponse=false. Reddedilmiş type/acne/bags ONNX başlıkları not-accepted; hosted cilt tipi izin/config davranışı değişmedi ve bu kontrollerde fotoğraf gönderimi yapılmadı. UI'a teknik metin eklenmedi.

## Teslim ve kalan işler

39 ilgili regresyon geçti; config-drift ve unavailable hash assertion sonrası 8 ilgili test yeniden geçti. Typecheck ve izole production build geçti (staged `-R7Sw4_huHGv9rb3-KF7k`); frontend kaynakları değişmediğinden çalışan S4 build korunuyor. Normal kısayol backend'i yeni oturum metadata koduyla yeniden yükledi. Güncellenmiş delivery verifier gerçek cevap modelInference/hash ile runtime alanlarını çapraz doğrular; disk hash veya boş model listesi tek başına başarı sayılmaz.

Kuruluk v3, çene v8/yanak v7, torbalanma sampling v3, lines v4 sampling, morluk, onaylı sesler, tasarım ve kullanıcı kayıtları korundu. AG alanına müdahale, uzun eğitim, büyük indirme, ücretli/hosted çağrı yok. PR #2 Draft olarak devam eder; main merge yok.

Kuruluk iyileştirmesi tamamlandı diye sunulmaz: bulunan hata, patch bağlamı ile gerçek pul bileşenini ayıramamak ve geniş düşük-kontrast materyalin içini kaçırmaktır. Sonraki değiştirilecek tek unsur, bu sabit zor kaynakları koruyarak yama-varlığı yerine incelenmiş pul/gözenek bileşeni etiketinin kullanılmasıdır; bu görevde ek fit başlatılmadı. Yeni tarafsız kişi/grup etiketli doğal kontroller ve çene ortak-target pozitifi halen somut açık kapsamdır. Sarkmada sıradan çizgiyi sarkma yapan veya ifadeyi geçiren kural eklenmedi.
