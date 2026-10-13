# Kuruluk ve sarkma: sınırlı ürün teşhisi

Başlangıç `420d0e3814106a2ec77744a17e000ea1e8669cec`, build `2W5568tfxsQ8bEjHc6Nmy`. Yeni build `1aC6o1a2LcmeiWq3cBlEn`. Makine makbuzu: [dry-sag-product-evidence-20261013.json](dry-sag-product-evidence-20261013.json). Fotoğraflar, ham istekler ve koordinatlı görseller yalnız Git dışında `audit-results/dry-sag-product-20261013` altında tutuldu.

Bu teslim hesap, anatomik destek ve geçmiş uyumluluğu düzeltmesidir. Kurulukta güçlü bir doğal pozitif kabulü elde edilmedi. Sarkmada görünür alt yüz kıvrımı API ve gerçek geçmiş görünümünde yerelleştirildi; aynı kaynağın otomatik ön poz taraması tamamlanmadı. İki sınırlama teslimin açık işleri olarak korunuyor.

## Kaynak ve etiket kapsamı

Dokuz tekil SHA sabitlendi; altısında gerçek browser MediaPipe, ürün snapshot/crop işlevleri ve normal backend isteği üretildi. Bu yardımcı işlev zinciri, otomatik kamera hizalama kapısının da geçildiği anlamına gelmez. Fotoğraf/hash, mevcut grup, split, kategori, koşullar ve sonuçlar JSON makbuzundadır. Kaynak split'leri değiştirilmedi; bunlar küçük, daha önce görülmüş geliştirme kontrolleridir.

`515cc548` mevcut lisanslı, boyutlandırılmış fotoğrafta gözlenen alt yüz kıvrımı referansıdır; yaş/kırışıklık sınıfı sarkma etiketi yapılmadı. İlk işleme geçmişi bütünüyle doğrulanmış bir ham çekim değildir. `05619d0a` gölge/crop açısından belirsiz kalır. `e0ee9f0c` ve `d3e8bb60` doğal fotoğraf kökenli olsa da görünen döndürme ve seyrek nokta bozulmaları ayrı kaydedildi. `5bd42346` açıkça dönüştürülmüş/gürültülü kontroldür.

Kuruluk kaynağındaki PUL kutuları zayıf yerel görünürlük etiketidir; cilt tipi `dry` etiketi kullanılmadı. Mevcut pozitif grupların sınırlı görsel incelemesinde ağırlıkla CLAHE işlenmiş yakın cilt/alt yüz görüntüleri bulundu. `c31892d1` işlenmiş tam yüz adayıdır; pitch −0,33 ile otomatik ön tarama için uygun değildir. `4f3c28ac` ürün snapshot'ında `INCOMPLETE_HEAD_FRAME`, `8172863a` ve `fb752c94` ise gerçek MediaPipe ile `NO_SINGLE_FACE` verdi. Bu kaynaklardan yüz/ROI doğruluğu uydurulmadı. Kutu/poligon dışı bilinmeyen alanlar negatif yapılmadı; tam ROI Dice, şiddet veya genel doğruluk raporlanmadı.

## Değişiklikler

Kurulukta gri doku işlenirken `max(R,G,B)` doygunluğu kullanılması somut bir kapsam hatasıydı: `c31892d1` analizinde 17.665 renk-kanalı doygun piksele karşı sıfır luma doygun piksel vardı. Yalnız kuruluk ve alt yüz kontur fotometrisi luma doygunluğunu kullanır; eşik ve izin verilen oran değişmedi. Renk/yağlılık/diğer göz yöntemleri önceki girdilerini korur.

Kuruluk parlak bileşenleri görünür yüz birleşiminde bir kez seçilir; bölgesel ve Genel Bakış sonuçları aynı kabul edilmiş alanı kullanır. Burun kuruluk skoru artık yağlılık için kullanılan alın birleşimini ödünç almaz. Ölçülemeyen bölge Genel Bakış alanına eklenmez. Dört gerekli ön yüz bölgesinde yeterlilik gerekir. Pürüzlülük ve LBP tanıları da aynı kuruluk desteğinde ölçülür. DoG/LBP, koyu odak halkası ve bileşen eşikleri düşürülmedi. Normalizasyon `eligible-flake-luma-union-v3`, sampling `shared-luma-closed-cell-flakes-v3`.

Sarkmada önceki yollar seçili ağın dışındaki kıvrımları hesaplayabiliyor; çene yanak yollarını yeniden kullanıyordu. Yeni yanak yolları gerçek ağdaki iç anatomik düğümleri izler; çene kendi mentolabial kıvrımını kullanır. Merkez seçili görünür alanda olmak zorundadır. Sıfır destekli fakat gerçekten gözlenen merkezler hesaba katılır; gözlenmeyen merkezler ve ölçülemeyen taraflar sıfırla doldurulmaz. Tek koyu çizgi, tek kenar veya bağımsız sınır olmaması yeterli değildir: kıvrım × çift kenar × süreklilik × bağımsız çene sınırı kapıları birlikte korunur.

Skor ve gradyen aynı kabul edilmiş merkezlerden türetilir; aynı merkez ve ölçülen alan birleşimde bir kez sayılır. Yeni Genel Bakış sarkma haritası da bu yerel kanıttır. Formül/normalizasyon `contour-fold-visible-region-unique-centers-v7`, sampling `visible-region-unique-centers-v7`, Genel Bakış yöntemi `front-lower-face-unique-centers-v1`. Bu görünüm indeksi doku hacmi, olasılık veya şiddet yüzdesi değildir.

Kuruluk/sarkma için yalnız dört gerçek güvenli ağ kenarının kapattığı dışbükey hücreler doldurulur. Açık kenar, içbükey kestirme veya convex hull kullanılmaz. Browser SVG clipping yalnız yeni normalizasyon sürümlerinde aynı hücreleri kapsar; eski harita ve konturların üçgen desteği korunur; görünen ağın noktaları ve çizgileri değişmedi. Önceki torbalanma hücre/sampling v3, morluk ve kaz ayakları impuls düzeltmesi korundu.

## Aynı ürün girdisi, önce / sonra

Ham sayılar normal API cevaplarından gelir. Kuruluk görünür aday alan oranıdır; sarkma gözlenen kontur/kıvrım indeksidir. UI tam sayıya yuvarlar; UI %0, sinyal veya harita yok demek değildir.

| Kaynak | Kuruluk önce → sonra | Sarkma önce → sonra | Yeni Genel Bakış haritası: dry / sag aktif kaynak pikseli |
|---|---:|---:|---:|
| `515cc548` | null → 0,093897 (UI %0) | 0,091049 → 29,355062 (UI %29) | 29 / 353 |
| `05619d0a` | 0,170807 → 0,195653 | 0 → 0, kısmi ölçüm; etiket belirsiz | 92 / 0 |
| `e0ee9f0c` | 0,027930 → 0,036617 | null → null, ifade kapısı | 9 / 0 |
| `5bd42346` | 0,059666 → 0,058252 | null → null, ifade kapısı | 24 / 0 |
| `c31892d1` | null → 0,066794 (UI %0) | null → null, baş açısı | 36 / 0 |
| `d3e8bb60` | null → 0,006271 | 0 → 0,015954 (UI %0) | 3 / 13 |

`515cc548` sağ yanak ve çenede yerel destek verir; görünmeyen iki alt yanak yolu `ANATOMICAL_BAND_NOT_VISIBLE` kalır. Genel Bakış 127 tekil gözlenen merkez ve 5.158 tekil analiz pikselinden oluşan ölçüm desteğini kaydeder; bağımsız sınır da bu ölçüm alanına dahildir. Kişisel başlangıç kaydı gerekmez.

Kurulukta `c31892d1` için native aday 1.209, ölçeklenmiş aday 830, anatomik seçim öncesi kabul 266 pikseldi; nihai ürün haritası yalnız 36 kaynak pikselidir. Yanlış parlama reddi düzeldi, fakat gözlenen soyulmanın güçlü yakalanması çözülmüş sayılmaz. DoG/kontrast/bileşen elemesi ve uygun kaynak kapsamı kalan somut sınırlamadır. Kontrollerdeki 24/9/3 kuruluk mikro-adayı ve 13 piksellik zayıf sarkma desteği doğrulanmış pozitif olarak sunulmaz.

Dar native impuls filtresinin yalnız kuruluk fotometrisine uygulanması sınırlı bir denemede karşılaştırıldı. Pozitif adayı iyileştirmedi; `e0ee9f0c` desteği 9'dan 12 piksele çıktı. Bu deneme ürüne alınmadı; genel bulanıklaştırma, eşik indirme veya fotoğrafa özel kural eklenmedi.

## Gerçek ürün ve geçmiş kontrolleri

Normal kısayolun sunduğu build'de izole profilde mevcut lisanslı `20031f35` video girdisiyle gerçek browser/MediaPipe/kalite kapıları/otomatik tek ön tarama/API/yeni sonuç/geçmiş akışı tamamlandı. Bu test farklı YUV/JPEG ve landmark girdisi oluşturur; tablodaki PNG girdileriyle aynı skor beklenmez. Yeni sonuç ve geçmişte yedi görünümün etiketleri, Genel Bakış ve bölgesel dry/sag map koordinatları, kapalı hücre clipping sayıları, kriter/bölge değişiminde harita temizliği ve gerçek %200 görünümü kontrol edildi.

`515cc548` doğrudan aynı ürüne kamera kaynağı olarak verildiğinde gerçek MP 478 nokta buldu ve ışık/netlik uygun kaldı; yaw yaklaşık 0,30, mevcut ön poz sınırı ise ±0,20. Otomatik tarama tamamlanmadı; kalite/poz override veya fotoğrafı bu sınırı geçirecek dönüşüm yapılmadı. Bu fotoğrafın gerçek MP/snapshot/API ve gerçek geçmiş görünümü kanıtı, tamamlanmış otomatik ön tarama kanıtıyla karıştırılmaz.

Eski doğru ve bozuk Türkçe etiketli izole kayıtlar açıldı. Eski/yeni kuruluk ve sarkma, hem Genel Bakış hem çenede iki ayrı geçmiş serisine ayrılıyor; referans delta engelleniyor. Eski kayıtların baytları açma/inceleme sonrasında aynı. Kullanıcı profiline, fotoğraflarına veya kayıtlarına işlem yapılmadı.

Altı gerçek fotoğraf girdisinde API/çalışan kaynak eşitliği kontrol edildi. Raster makbuzları gerçek seçili kapalı hücre alanının, ölçüm desteğinin ve otomatik göz/dudak/burun/brow dışlamalarının dışında aktif piksel olmadığını hesaplar. Dokuz önceki kaz ayakları/torbalanma girdisinde 207 bölgesel ve 63 Genel Bakış hedef dışı ölçüm, ayrıca hedef dışı haritalar başlangıç kaynakla birebir aynı kaldı. Bu mühendislik korunumu doğal fotoğraf doğruluğu metriği değildir.

İlgili 33 regresyon geçti; son kuruluk destek/metadata düzeltmesinin yedi sözleşme kontrolü de geçti. Typecheck ve production build başarılı. Normal kısayol → backend sahipliği/gerçek cevap → kaynak/build/sunulan JS ve model/config hash zinciri ayrı teslim makbuzunda kontrol edilir. Yeni eğitim, hosted çağrı, model entegrasyonu veya AG çalışma alanı değişikliği yapılmadı; PR #2 Draft kalır.
