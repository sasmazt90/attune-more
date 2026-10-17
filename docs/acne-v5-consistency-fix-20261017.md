# Sivilce nokta–bar–bölge–geçmiş düzeltmesi

Başlangıç `f230cce5adb074aca06fac201d6f2f1ba32f6cb6`; mevcut `research/acne-v5-integration-20261017` dalı ve checkout kullanıldı. Yeni checkout, eğitim, model karşılaştırması, kalibrasyon veya veri taraması yapılmadı.

## Neden ve düzeltme

Önceki gerçek kamera kaydı `a33dba69-120a-44b8-af2f-cdc27cc2f174`, FRONT kaynak kimliği `818a8528…` başlangıç vakasıdır. Alına atanmış `56880e848e54c8b957364652` adayının kaynak kutusu `(888.253,633.942,10.790,11.557)`, merkezi `(893.648,639.721)` idi. Staging mesafe fallback'i adayı alına atamıştı; merkez alın anatomik desteğinin dışında ve kutunun skor desteğiyle kesişimi **0 piksel** idi. Sabit payda 18.175 analiz pikseli; ham bar tam 0, görünen %0, nokta sayısı 1. Bu yuvarlama hatası değildir.

Model/staging çıktısının ardından normal yanıt adaptöründe tek bir nihai aday listesi oluşturuldu. Adayın değiştirilmemiş merkezinin aynı kaynak/analiz alanında, aynı bölgenin gerçek puanlanan anatomik cilt desteğinde olması ve kutunun o desteğe piksel katkısı vermesi gerekiyor. Kaynak → `(merkez-origin)*scale` → floor indeks dönüşümü kullanılıyor; sınır dışı merkezler kenara çekilmiyor ve başka bölgeye taşınmıyor. Reddedilen adayların kaynak koordinatı, gerekçesi, piksel katkısı, maskenin hash'i, origin/scale ve sabit payda metadata'da saklanıyor.

`measurements.components.bounds`, `acneCandidates`, Genel Bakış noktaları ve barın benzersiz kutu alanı aynı nihai listeden türetiliyor. Kutular geometrik olarak değiştirilmedi. Eşik, NMS, model olasılığı, minimum puan veya yeni şiddet ölçeği eklenmedi. Anatomik maske ve payda aday tahmininden bağımsız kaldı.

Ölçüm kapsamı daraldığı için yöntem `appearance-acne-step0-verifier-v5-2`, sampling `step0-staging-v5-scored-center-support-v2` oldu. Alan formülü/normalizasyonu `unique-detection-box-anatomical-area-v2` ve model hash'i değişmedi. Önceki v1 kayıtları okunabilir kalır; yeni v2 ile Genel Bakış ve bölgesel trend eşdeğerliği kurulmaz. Eski kayıtlar yeniden hesaplanmadı veya yazılmadı.

## Aynı girdide önce/sonra

Gerçek normal kamera UI'sında önceki iki kayıtlı görüntüden canvas video track'i kullanıldı. MediaPipe, kalite/gözlük/poz, otomatik üç açılı çekim, snapshot, normal API ve kayıt yolu gerçek uygulama fonksiyonlarıdır; bu **fiziksel kamera kanıtı değildir**. FRONT/RIGHT/LEFT kaynak piksel hash'leri önceki teslimle aynı çıktı. LEFT, daha önceki gibi RIGHT görüntüsünün aynasıdır; doğal fotoğraf genelleme kanıtı sayılmaz.

| Görünüm ve gerçek kaynak | Nokta önce → sonra | Ham bar önce → sonra | Ekran önce → sonra |
|---|---:|---:|---:|
| Genel Bakış / FRONT `818a8528…` | 22 → 18 | 1,612222 → 1,592719 | %2 → %2 |
| Alın / FRONT | 1 → 0 | 0 → 0 | %0 → %0 |
| Sağ Yanak / LEFT `004f9a28…` | 2 → 2 | 0,793909 → 0,793909 | %1 → %1 |
| Sol Yanak / RIGHT `5f05f92c…` | 4 → 4 | 1,631841 → 1,631841 | %2 → %2 |
| T-Bölgesi / FRONT | 1 → 1 | 0,176335 → 0,176335 | %0 → %0 |
| Çene / FRONT | 2 → 1 | 0,937042 → 0,937042 | %1 → %1 |
| Göz Çevresi / FRONT | Sivilce kriteri yok | Değişmedi | Mevcut dört kriter |

T-Bölgesi örneği gerçek küçük pozitiftir: 49 / 27.788 ×100 = 0,176335. Noktası korundu; mevcut tam sayı yuvarlaması %0 kaldı. %0, otomatik olarak “aday yok” anlamına getirilmiyor.

FRONT'ta elenen dört adayın üçü 0 katkılıdır (alın, çene ve ön kare sağ yanak). Dördüncü adayın merkezi ön kare sağ yanak desteği dışındadır fakat kutusu 12 analiz pikseli kesiyordu. Bu kısmi katkı da çıkarıldı: ön kare sağ yanak bileşeni 12 → 10 aday, 422 → 410 destek pikseli, ham 4,447255 → 4,320792. Genel Bakış değişimi bu 12 pikselden gelir; payda sabittir. Bu ön-kare bileşeni, bölgesel sağ yanağın LEFT fotoğrafıyla karıştırılmadı. Yan çekimlerin 4 ve 2 adayı aynen kaldı; farklı fotoğraflar birleştirilmedi.

Bu dört kapsam reddi “dört klinik yanlış pozitif düzeldi” diye sunulmaz. Kısmi destekli adayın gerçek lezyon doğrusu bu entegrasyon görevi kapsamında incelenmedi; gerçek lezyon kaybının sıfır olduğu iddia edilmez. Kaybolan aday kimlikleri/koordinatları ve 12 piksel etkisi makbuzda açıktır.

## Sonuç, geçmiş ve korunum

Yeni gerçek test kaydı `25b5c2d4-0413-4155-bfda-bdbade281939`. Yedi görünümde kriter listesi, kaynak fotoğraf, ham bar, nokta sayısı/koordinatı, sabit ekran yarıçapı ve kriter/bölge değişiminde temizlenme API/DOM üzerinden doğrulandı. Genel Bakış 18 noktayı gösteriyor. Tarayıcı sayfası yenilenerek volatil görüntü hafızası kaldırıldı; aynı kayıt IndexedDB'den tekrar açıldı. Genel Bakış, alın ve küçük pozitif T-Bölgesi geçmişinde yukarıdaki değer/noktalar/metot bire bir eşleşti; sayısal kayıt açılmadan önce/sonra aynı kaldı.

Sivilce dışındaki bölgesel değerler, Genel Bakış, cilt tipi metadata'sı, haritalar ve konturlar aynı kaynaklar için önceki teslimle bire bir eşleşiyor. Ayrı çalıştırmalarda yalnız `drynessRuntime.timings`, `profile`, `fullAnalysisSeconds` değişti. Adaptör öncesi/sonrası tüm bu runtime dahil diğer kriter hash'i her üç istekte eşit. Kaynak fotoğraf, maske, kamera kapıları, tasarım ve ses kodu değiştirilmedi. Hosted izin kapalı kaldı; dış fotoğraf çağrısı yapılmadı.

## Kontroller ve teslim

- 13 odaklı regresyon geçti: destek dışı/kenar/kısmi kutu, kaynak origin/scale, yan bölge kimliği, küçük pozitif, eski/yeni geçmiş kimliği, harita yaşam döngüsü ve Genel Bakış sözleşmesi.
- Production build ve içindeki TypeScript kontrolü geçti. İki önceki lint uyarısı korunuyor. BUILD_ID: `9uW4ePXeJGtj1yrzXP8kL`.
- 38 sunulan JavaScript dosyası HTTP bayt hash'iyle build'e eşleşti. Step0, V5, ONNX ve mevcut model kimlikleri/eşikleri değişmedi. Kaynak/build/model/süreç zinciri `delivery-chain.json` içinde.
- İlk UI testinde seçili Genel Bakış barının ikinci tıklamayla kapanması ve geçmişin farklı DOM seçicisi nedeniyle test otomasyonları düzeltildi; uygulama koduna bunu geçirmek için override eklenmedi. Tek üç açılı analiz yapıldı; bu DOM kontrolleri yeniden analiz başlatmadı.
- Fotoğraf enjeksiyonu yalnız test sekmesindeydi; o sekme kapatıldı. Aynı izole profilde yeni native `getUserMedia` sekmesi açık, bir test geçmiş kaydı korunuyor. İki geçici public JPEG kaldırıldı.
- `accepted:false, file:null` korunuyor. Ana ürün/AG/Claude çalışma alanlarına yazılmadı; push, merge ve genel üretim aktivasyonu yok.

Adres `http://127.0.0.1:3305/skin`; başlatıcı bu checkout'taki `Start-Acne-V5-Preview.ps1`.
Fotoğraf içermeyen rapor, karşılaştırma ve durum: `C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\acne-v5-consistency-fix-20261017`.
Ekran kanıtları ayrı PNG'lerdir: `overview-acne.png`, `history-overview.png`, `history-forehead.png`, `history-nose.png`, `cheek.png`, `eyes.png`, `ready-native.png`. Tam fotoğraf payload'ları yalnız yerel ignored test çıktısında tutuldu; Git'e alınmadı.

**Fiziksel kullanıcı testine kalan tek madde:** gerçek PC/telefon/araç kamerasında son kullanıcı kabulü. Bu aşamada kullanıcıdan kamera testi istenmedi.
