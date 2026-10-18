# Native kuruluk ve kontur: sonlu takip, kamera kapsamı açık

Başlangıç `ed3cd37dd59a300e5071c403ce1e3788197ccd58`; korunan BUILD_ID `JO0Xyvupv72uoBiX42mWq`. Makbuz: `native-camera-material-followup-evidence-20261013.json`. Bu teslim **araştırma hızlandırması ve reddedilmiş aday kanıtıdır**. Normal kuruluk v3, çene v9 ve yanak v7 seçicileri değişmedi. Kamera bütçesi ve gerçek dış-kontur pozitif kabulü tamamlanmış değildir.

## Çıktıyı koruyan proposal hızlandırması

Native kaynakta gray/Lab dönüşümleri tile başına tekrarlanmak yerine aynı istek içinde paylaşılır. Adayın yalnız mevcut tile core'undaki anatomik eligible alana hiçbir katkısı yoksa pahalı ring/kenar/gözenek ölçümü atlanır. Halo, bağımsız ring referansı, 512 core/256 stride, native kaynak-origin, eşikler ve max-union korunur. Debug rastrları yalnız istenirse oluşturulur. Bileşen geometrisindeki tekrar `isin` işlemi lookup'a dönüştürüldü; zaten elenen <3-piksel bileşenlerde gereksiz ring kurulmaz.

16 sabit optik kontrolün native ve kontrollü yarım-source toplam **32** karşılaştırmasında field byte'ları ve varsayılan 12 bileşen özelliği aynıdır. Toplam proposal süresi 17,160 → 10,513 saniye; her kaynakta eşit hızlanma iddiası yoktur. Bu küçük crop/eligibility deneyi tek başına normal kamera kabulü değildir.

Gerçek ürün geometrisinin **1944×2592 e1646fda** stress girdisinde native proposal **89 → 9,453 saniye**; skorlar, Genel Bakış ve lokal haritalar eski kaynak çıktısıyla birebir eşleşir. ROI 956×1256, origin [549,831], face span 845,5303 px, metric 1,32114, halo 53, 12 tile değişmedi. 61.550 aday-region işleminin 46.808'i core eligibility dışında kaldığı için atlandı; 14.742'si ölçüldü. Fotoğraf küçültülmedi. **Bu koşu encoder içermedi:** eski 1.236 bileşen/2.472 crop encoder yüküne yeni tam-pipeline süresi atanmıyor.

Korunmuş dengeli iki-crop head ile baştan, cache'siz küçük ürün payload'ları:

| Kaynak | Kaynak / face span | ROI / tile / bileşen / crop | Önce / şimdi tam süre | Şimdi proposal / encoder | Korunum |
|---|---|---|---|---|---|
| 9bab7ab2 | 640×640 / 360,784 px | 443×509 / 1 / 74 / 148 | 16,234 / 9,890 s | 0,578 / 5,563 s | Kartlar, maps, Genel Bakış byte-değer eşit |
| 24031977 | 408×612 / 283,168 px | 361×436 / 1 / 29 / 58 | 6,672 / 2,609 s | 0,219 / 1,860 s | Kartlar, maps, Genel Bakış byte-değer eşit |

Encoder tekrar export edilmedi; mevcut doğrulanmış ONNX ve akışlı/per-request reuse yolu kullanıldı. Bu iki küçük isteğin geçmesi Full-HD kaynak ailesinin tamamının ≤45 s olduğunu göstermez. CPU/RAM arka plan yükü değişebildiği için saniyeler tekrarlanabilir benchmark garantisi değildir; aynı kaynak/output kapsamındaki gerçek ölçümlerdir.

## Bir encoder iş yükü azaltma denemesi; admission reddi

Değişken önceden kaydedildi: iki unconditioned crop yerine bir kaynak-ölçekli context crop; yalnız gerçek proposal bileşeni foreground, bağımsız ring medianı encoder background'u. Yakın/çevre fotoğraf içeriği küçültülerek hız iddiası yapılmadı; özgün görüntü/maskeler değiştirilmedi. Kesirli crop merkezi source-edge sözleşmesine göre korunur; yarım-source'ta tamsayı başlangıç nedeniyle oluşan 1-piksel pencere kayması bu **yeni deneysel temsil** için giderildi. Eski eğitilmiş iki-crop sözleşmesi değişmedi.

63 incelenmiş TRAIN bileşeni / 15 grup, tek L2 fit, C=1 ve p≥0,5. Yeni head frozen 1280 encoder + mevcut 12 geometri özelliğidir. Val/UNKNOWN fit'e alınmadı, fotoğraf F/PUL etiketi bileşenlere yayılmadı. Kaynak/grup/yakın-kopya ayrımı korundu. Encoder yükü teorik olarak bileşen başına iki → bir crop; gerçek yeni normal-kamera kabulü yapılmadı.

| Aynı sabit etiket kapsamı | Korunan dengeli iki-crop | Tek-crop deney |
|---|---|---|
| Native TRAIN materyal hit | 5/13 | 8/13 |
| Görülmüş validation hit | 7/8 | 7/8 |
| Native toplam | 12/21 | 15/21 |
| Native incelenmiş negatif destek | 30 px | 508 px (TRAIN 431 / val 77) |
| Yarım-source toplam | 13/21 | 15/21 |
| Yarım-source incelenmiş negatif destek | 0 px | 656 px |
| Eski altı hit'in korunması | 3/6 | 5/6 |

Hit ≥3 kaynak-eşdeğer piksel ve kısmi materyal alanının ≥%10'u; full ROI Dice/precision veya biyolojik kuruluk doğruluğu değildir. Görülmüş validation bağımsız final test değildir. Piksel negatifleri yalnız incelenmiş yerel alanlar; poligon dışı UNKNOWN'dır. **508-piksel yanlış destek artışı nedeniyle aday reddedildi**; sınıflandırıcıya rağmen C0/object0 native hit kaybı ve C9/object0 proposal kaçırması sürer. Native/yarım-source kararsızlığı kapanmadı. Aynı koşullarda ikinci fit, uzun parametre araması veya yeni CNN yoktur. Head ve normalization v6-staging normal ürüne seçilmedi.

## Gerçek kaynak-konum kaybı

24031977'nin düzeltilmiş iki materyal poligonunda proposal **143/16 px**, anatomik triangle-union sonrası **38/8 px**. Exclusion, saç ve pozlanma bu kalanlara ek kayıp yaratmaz; classifier **0/0** bırakır. Bu nedenle sorunun tamamı saç/gözlük maskesine yüklenemez. Kapsam dışındaki kaynak sinyali normal karta geri eklenmedi, ağ genişletilmedi. Eski yanlış y-konumlu poligonlar doğruluk kanıtı yapılmadı. Kaynak-anatomi overlay ve aşama sayımları `material-eligibility-diagnosis.json` / `24031977-anatomy-hair-stage.png` içindedir.

Korunan dengeli head'in gözlük rimindeki **73 px** yanlış yerel desteği aynı çıktıyı koruyan hızlandırma ile değişmedi; bütün periorbital alan kapatılmadı. Yeni tek-crop head'in tam eyewear fotoğrafındaki sayı ölçülmediği için 73 → 0 kazanımı iddia edilmez. Görünür materyalin biyolojik pul mu kozmetik film mi olduğu bilinmeyen alanlarda etiyoloji etiketi uydurulmadı.

## Kamera kapsamı: tamamlanmayan kabul

Güncel `skin/page.tsx` video isteği width/height **ideal 1920×1080**, resizeMode **ideal none**. Snapshot gerçek `videoWidth/videoHeight` boyutunu korur. Bunlar maksimum girdi sınırı değildir. Mevcut backend boyut sınırı her boyut ≤4096 ve toplam ≤8.400.000 pikseldir; 1944×2592 stress kaynağı bu sınırın içindedir ve yalnız yavaş olduğu için kapsam dışına çıkarılmadı.

Güncel kaynak modülleri gerçek izole Chrome'da, yerel gerçek MediaPipe task ile çalıştırıldı. Kayıtlı lisanslı native videonun sanal track'i **1280×720, 30 fps, resizeMode none**; device capabilities maksimumu da 1280×720. Snapshot canvas track boyutuyla aynı. Fiziksel kullanıcı kamera kontrolü değildir; Full-HD track kontrolü olarak sunulmaz. Bu karede yaw 0,18 / pitch −0,06 / roll −0,18, face span **167,449 px**. Açı kabulü roll nedeniyle geçmedi; native minimum 180 px de sağlanmıyor. Pose/quality override yapılmadı, API/sağlıklı sıfır/geçmiş kaydı üretilmedi.

Dolayısıyla **desteklenen normal kamera ailesi ve cache'siz ≤45 s kabulü henüz kapatılamadı**. Önceden tamamlanan gerçek HTTP 45 s deadline/disconnect kanıtı ve cooperative çalışma kodu korundu (`material-runtime-followup-20261013/api-budget.json`); burada tekrar ana kazanım yapılmadı. Timeout reddi healthy-zero veya yarım kayıt değildir. Yeni bir çözünürlük/face-span cutoff'uyla bu açık gizlenmedi. Native aday normal seçicide OFF kalır.

## Sarkma hedefi ve kaynak bütçesi

Önceki statik dudak-biçimi / ifade ayrımı, fotoğraf-id bağlı yerel blendshape desteği, pose/açık-ağız/kalite ve gerçek exterior boundary ölçümü korundu. Bu görevde algılama eşiği yükseltilmedi, iç yanak kıvrımı dış silüet hedefine çevrilmedi. Araştırma contour fonksiyonuna yalnız cooperative resource-check kancası eklendi; varsayılan hesap aynı.

Yerel mevcut envanterden sonlu **16** SHA/grup kayıtlı kaynak görsel olarak incelendi; beş doğal tam-yüz adayının gerçek capture kontrolü planlandı. Bu tarama bütün envanter değildir; eski 543 contour temsilcisinin yeniden incelemesi değildir ve her seçimin daha önce hiç görülmediği iddia edilmez. Stock yakın çekim kabul dışında, örtülü/yandan kaynakların kapsamı ayrı. Yaş, yüz yuvarlaklığı veya sıradan nasolabial çizgi pozitif etiket yapılmadı.

**29cc4ba7**, native 2316×3088 kaynakta gerçek browser MediaPipe → quality → FRONT açı kabulü → özgün snapshot zincirinden geçti: face span 1108,961 px, yaw/pitch 0, roll 0,01. Bu kaynak doğal/nötr görünür sıradan kontur veya UNKNOWN hedef adayıdır; doğrulanmış lokal outward prominence doğrusu değildir. Sonraki kaynağa geçmeden bellek koruması durdurdu. Aynı snapshot'ın contour/API/history değerlendirmesi ve diğer dört kaynak capture'ı **tamamlanmadı**; pozitif yakalama metriği uydurulmadı.

Ortak atomik lease yolu `TOGG/coordination-notes/heavy-compute.lock.json`; PID + process-start + job-id + nonce denetlenir. Foreign/stale lease kaldırılmaz. AG'nin sözleşmeyi kullandığı doğrulanmadığından gerçek process-CWD/script ownership guard'ı ayrıca vardır; inline kodda geçen klasör metni sahiplik sayılmaz. AG'nin yeni **176480 / diagnose_p2_contribution.py** süreci görüldüğünde ağır CD işlerine devam edilmedi; hiçbir AG süreci/dosyası yönetilmedi.

Tek kaynak ve en fazla 16 encoder crop'luk akışlı denemede peak RSS 471,449 MiB; tamamlanan gerçek native profile 534,043 MiB. Browser + kendi alt süreçlerinin muhafazakâr RSS toplamı büyük doğal fotoğrafta 1380,672 MiB ile 1000 MiB sınırını aştı; o anda 522,625 MiB rezerv vardı. Yalnız kendi test tarayıcısı kapatıldı, sonraki kaynak başlamadı. Son AG kontrolünde RSS 1627,637 MiB, kullanılabilir RAM 596,590 MiB; ek ağır CD koşusu güvenli değildir. Arşivlenmiş SCIN açılmadı/indirilmedi, kullanıcı uygulamaları kapatılmadı. Ortak kilidin AG tarafından kullanılan gerçek yolu sorusu yanıtsızdır; başka bir kilit varsa bu path otomatik eşdeğer varsayılmaz.

## Kontroller ve teslim sınırı

29 ilgili regresyon geçti: ROI çıktı korunum/ortak fotometri, immutable fotoğraf ve non-self ring, kesirli crop source ölçeği, foreign/own lease güvenliği, native map/payda/null, akışlı reuse/deadline ve contour/ifade regressions. Testler bittikten sonra AG'nin başlaması resource guard'a yakalandı; daha fazla ağır iş başlatılmadı. Normal kaynak/build için **115 pinned hash değişmedi**; BUILD_ID korundu. Frontend, normal API seçicisi, gerçek ONNX kimliği, tasarım, sesler, izin/config ve kayıtlar değişmedi. Bu nedenle yeni production build/typecheck/UI kampanyası başlatılmadı; eski runtime kanıtı bu görevin kamera kabulü gibi sunulmadı.

Kalan somut işler: güvenli seri pencerede kabul edilen gerçek kamera track'inde tam native 45 s koşusu; 73-piksel eyewear yanlışı, 24031977 iç-ROI classifier kaybı ve C0/C9 ölçek/hit kaybını TRAIN-only bir değişkenle çözmek; gerçek kaynak-konum etiketli nötr **dış-kontur prominence** pozitifi ve blendshape negatif kalibrasyonu. Reddedilmiş tek-crop aday üretime alınmayacak. Yeni dondurulmuş/değerlendirilmiş AG paketi bu görevde sağlanmadı; hareketli P2 kaynakları veya ağırlıkları taşınmadı. PR #2 Draft kalır, main merge yoktur.
