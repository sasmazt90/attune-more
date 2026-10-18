<!-- focused-current-release -->
# Güncel odaklı cilt teslimi

Sonlu eğitim, Genel Bakış ve güncel model/harita kabulü: [skin-focused-results-20261010.md](skin-focused-results-20261010.md). Aşağıdaki önceki beş-modül raporu eski build kanıtı ve korunmuş düzeltmelerin bağlamıdır; güncel final kabul değildir. Önceki merkez/çevre sivilce yolu artık normal API’da etkin değildir. Sağlanan yeni Roboflow/Kaggle kaynaklarıyla odaklı eğitim tamamlandığından eski ACNE-DET erişim sorunu güncel ana eğitim engeli değildir.

# TOGG Attune — beş modülün geliştirme ve kabul durumu

Bu teslim, bütün özelliklerin kabul edildiği anlamına gelmez. Özellik bazlı durumlar `all-health-feature-acceptance-20261010.md` içindedir. Yerel ayrıntılı CSV/JSON girdileri, birimleri, aktif üretim zincirlerini, lisansları, kusurları, düzeltmeleri, pozitif/negatif kanıtları ve kayıt ilişkilerini ayrı gösterir. HTTP 200, model dosyası veya kontrollü test geçişi doğal tespit başarısına dönüştürülmez.

Son üretim BUILD_ID: `ver47SJLWC-1R8Cx9AkTp`. Commit SHA ve kısayol/servis/JS/model/ses doğrulaması, commit sonrasında üretilen yerel `audit-results/all-health-20261010/delivery.json` içindedir. Eski build kanıtları yalnız önce/sonra bağlamıdır.

## Somut düzeltmeler

- Göz ve cilt/diş yüz hazırlığı için mevcut MediaPipe SDK 1.0.1 ve Face/Hand float16 v1 dosyaları aynı SHA256 ile yerelden sunulur. Ağırlıklar, eşikler ve anatomik sağ/sol eşlemesi değişmez. Soğuk çalıştırmada harici model/CDN adresleri engellenerek kontrol edilir.
- Mevcut 28 sabit göz yönergesi aynı Ahmet profiliyle yerel bankaya alındı. Metin, profil, boyut ve SHA doğrulanır; bozuk banka açık hata üretir. Önceki aralıklı Edge 403/503 göz başlangıcı hatası kayıtları korunur. Dinamik ruh sağlığı yanıtı hâlâ onaylı Emel yoludur. Teknik MP3/playback başarısı telaffuz kabulü değildir.
- Tam portre diş yüklemesinde gerçek statik FaceLandmarker sonucu yalnız görünür iç ağız anatomisini belirler. Yerel analiz, kaynak çözünürlüğündeki ağız crop'unda çalışır; kutu, kontur ve kalite koordinatları orijinal yönlendirilmiş fotoğrafa geri çevrilir. Kamera izni istenmez. Kısmi ağız girişi korunur.
- Yüz bulunmayan diş yüklemesinin yedek maskesi, uzun dikey duvar/pencere alanını diş sırası olarak kabul etmez. Diş görünmeyen gerçek portrede önce 7.456.776 arka plan pikseli değerlendirilmişti; bu yanlış kabul için somut negatif kontrol eklendi. Genel sağlıklı/zor negatif tespit kabulü hâlâ ayrı gerektirir.
- Diş-diş eti sınırındaki birikim görünümünün değerlendirilebilir tek-açı alan oranı üretime bağlıdır. Çoklu açı teyidi uydurulmaz. D/d, orijinal veri tanımındaki daimi/süt dişi sınıflarıdır; farklı hastalıklara eşlenmez. ONNX ve karar eşiği korunur.
- Cilt renk hesabında bölgesel LAB karşılaştırması, uzun koyu saç dışlaması ve pullanma sinyalinde koyu halka/JPEG kenarı dışlaması düzeltildi. Yakın RGB fotoğraf, gerçek arka plan, kaynak renkleri, altı ağ ve yerel harita ilişkisi korunur. Her kriterin doğal kabulü ayrı tutulur.
- Fotoğraf + sayısal tek kayıt silme, kalıcı IndexedDB geri alma kaydı ve yerel işlem günlüğüyle koordine edilir. Kota, yarım yazım ve yeniden başlatma kontrolleri gerçek izole depoda çalışır. Kullanıcının normal geçmişi test için silinmez.
- Ruh sağlığında açık bitirme/vedalaşma mikrofon ve oturum kapanışına bağlandı. Eksik süre ve ruh hali artık uydurulmaz. Özet/transkript izinleri ayrıdır; hata/izin iptalinde başlangıç yönergesi tekrarı engellenir.
- Uzman erişimi engellendiğinde demo liste/müsaitlik gerçek sağlayıcı sonucu gibi gösterilmez. Mevcut dış sağlayıcı bağlantısı ayrı yönlendirme işlevi olarak kalır; rezervasyon yapılmış sayılmaz.

## Sivilce: tamamlanmayan tespit ve sonlu denemeler

Aktif merkez/çevre kuralının yanlış aday kusuru kapanmadı. Kart, sayı, çember ve dolgu aynı aday listesinden gelir; model güveni şiddet yapılmaz. Üç olgun Faster R-CNN + ResNet50-FPN denemesi öğrenme zinciri, validation seçimi ve sonlu durdurma kuralıyla yapıldı. Başarısız araştırma ağırlıkları üretime eklenmedi.

| Başlangıç / deney | Öğrenme kontrolü | Validation seçimi | Sonuç |
|---|---|---|---|
| Lisanslı timm sınıflandırma omurgası; yeni FPN/RPN/ROI | 99 adım, yaklaşık 307 sn | 5 epoch / 946 sn; F1=0 | Kabul edilmedi |
| Aynı omurga, dengeli ROI / foreground loss | 58 adım, 318,765 sn | 5 epoch / 893 sn; TP=1, FP=1, FN=17; F1=0,10 | Önceden ayrılmış test bir kez: TP=0, FP=3, FN=24; F1=0; kabul edilmedi |
| ResNet50-FPN 3x resmi tespit ön eğitimi; yeni görev başlığı | 100 adım, 218,047 sn | 8 epoch / 1.282,344 sn; seçilen epoch4 / eşik0,8: TP=2, FP=14, FN=16; precision=0,125, recall=0,111, F1=0,118 | Validation yetersiz; önce görülmüş test yeni deney için kullanılmadı; üretime eklenmedi |

25 özel mühendislik crop'u: train12/val6/test7, toplam89 odak işareti. Bilinen aynı-kaynak türevleri ayrıdır; bilinmeyen kişi bağlantıları çıkarılmadı. Validation'ın altı kaynağı pozitiftir; bütün-yüz negatif validation yoktur. İşaretler uzman tanısı değildir. Hedef P/R>=0,8 ve negatif başına FP<=1 mühendislik hedefidir. En fazla15 epoch/1.800 sn ve dört epoch iyileşmeme kuralı kullanıldı. Resmi Detectron2 ağırlık aktarımı Torchvision ROI/anchor uygulamasının birebir eşdeğeri olarak sunulmaz.

Kod, ağırlık ve veri koşulları ayrıdır: Torchvision BSD-3-Clause; timm başlangıç dağıtımı Apache-2.0; Detectron2 kodu Apache-2.0, resmi model zoo ağırlıkları CC BY-SA3.0. Uyarlanmış tespit ağırlıklarının dağıtımında atıf/share-alike gerekir; bu araştırma ağırlıkları teslim edilen üründe yoktur. Kesin hash ve kaynak revizyonları `THIRD_PARTY_NOTICES.md` ve yerel araştırma manifestlerindedir.

ACNE-DET orijinal depo kodu Apache-2.0. Yazarın Baidu veri bağlantısı/password sayfası incelendi; 393,3 MB arşiv listesi göründü fakat bu oturumda arşiv içeriği/izin dosyası alınamadı. Oturum açmanın zorunlu olduğu kanıtlanmadı; erişim koruması aşılmadı. Kod lisansı görüntü/etiket ticari hakkını sağlamaz. Gönderilmeyen, gönderime hazır talep: `acne-det-permission-request-20261010.md`.

Gerekli somut girdi: ticari eğitim/değerlendirme izni açık görüntü + odak anotasyonu arşivi, doğal tam-yüz pozitifler ve gözenek/ben/sakal zor negatifleri. Hazır yol: aynı kaynağın türevlerini ayır, yeni korunan test oluştur, öğrenme kontrolü → yalnız validation ile seçme → bir kez bağımsız değerlendirme. Dünyadaki bütün teknik seçeneklerin tükendiği iddia edilmiyor.

## Sınırlı doğal görünüm kanıtı ve açıklar

96 doğal kaynakta gerçek üretim snapshot/ROI/model/backend zinciri kullanıldı. Kabul edilebilir tam-yüz görüntüler yalnız üç ayrı kişiye aittir; video kareleri bağımsız kişi sayılmaz. NASA yüksek detaylı iki kaynak yalnız ön pozdur. SCIN crop'larının çoğu tam-yüz geometri koşulunu sağlamaz; sahte yüz noktası verilmedi.

LAB düzeltmesinin karşılaştırılabilir örneğinde genç ön pozda alın kızarıklık indeksi 38,9→8,81, yanaklar 34/43→3,3/3,15 oldu. Bu azalma klinik doğruluk kanıtı değildir. Aynı kaynaktaki sivilce yanlış adayları 20→23 ve T-bölgesinde22→24 arttı; bu kusur gizlenmez. Doğal yaşlı portrede alt göz torba/çizgi/koyu bant ve bazı destekli katlanma değerleri üretildi; bazı sarkma bantları hâlâ null. Yalnız karanlıktan hacim iddiası üretilmez.

- Yağlı görünüm ve pullanmanın kontrollü sinyal pozitifleri vardır; doğal tam-yüz pozitif ve uygun mat/JPEG/gözenek/yansıma karşılaştırması tam kapanmadı. Edinilen parlak alın/scalp/kapak crop'ları otomatik tam-yüz kabulünün yerine geçmez.
- Sivilce tespiti başarısızdır; doğal yanlış aday ve kaçırılan odaklar vardır.
- Torbalanma, kaz ayakları, morluk, renk ve sarkma yolları çalışır ancak ışık/poz/ifade/ten ve doku karıştırıcılarına karşı doğal kabul sınırlıdır.
- Göz yumma, el ve opak cisim örtüsünün güncel fiziksel pozitif kabulü tamamlanmadı. Eski DOCX içindeki sıkıştırılmış görüntüler başlangıç kalite/baseline koşulunu sağlayamadı. Kontrollü state/ASR/SVG geçişi fiziksel örtü başarısı sayılmaz. Gerekli kanıt doğal çözünürlükte aynı konumdaki açık başlangıç ve her anatomik taraf için kapalı/örtülü çiftlerdir.
- Diş d sınıfının önceki korunan sette P=0,517/R=0,476/F1=0,496 sonucu zayıftır; güçlü D sınıfıyla ortalamalanıp gizlenmez. Bu eski performans, yeni build doğal kabulü değildir. Taş/birikim ve contour ayrımı için gerçek doğal pozitif/zor negatif kabulü sınırlıdır; yiyecek/leke/dolgu ve perspektif karıştırıcıları açık kalır.
- İşitmede PCM, dijital dBFS ve bankaya özgü dB SNR doğrulanır; fiziksel kulaklık kanalı/duyma ve klinik eşik kabulü uydurulmaz.
- Ruh sağlığında üç gerçek sağlayıcı isteği başarılı oldu: 1.213 prompt +156 completion =1.369 token; tahmini0,00027555 USD, fatura değildir. İlk buffered ses denemesi ve yanlış opt-out beklentisiyle biten UI testinin başarısızlığı kayıtlarda korunur. Kesintisiz iki canlı frontend turu ve fiziksel mikrofon/telaffuz kabulü yapılmış sayılmaz. Ek ücretli çağrı yapılmadı.
- Canlı uzman listesi/müsaitlik erişimi dış sağlayıcıya bağlıdır. Engellenen erişimden slot/rezervasyon üretilmez.

## Kanıt ve güvenlik

Son build'in sıralı üretim kontrolleri: `audit-results/all-health-20261010/release/all-execution.json`; düzeltme sonrası tekrarlar `release/rechecks.json`. Her satır BUILD_ID ve kapsam taşır. Test görüntüleri, kontrollü yanıtlar ve PCM gerçek fiziksel kullanıcı kabulü değildir. Genel sayfa sessizliği, hazırlık/mute/route iptali, masaüstü/dar pencere ve native Chrome %200 kontrolleri ayrıdır. Gerçek normal kullanıcı profiline sahte kayıt eklenmedi; silme testleri izole profilde/serviste yapıldı.

Üretim npm audit:0 bulgu. Geliştirme bağımlılıklarında **7 high +2 moderate açık**: high `@next/eslint-plugin-next`, `braces`, `chokidar`, `eslint-config-next`, `fast-glob`, `micromatch`, `tailwindcss`; moderate `postcss-nested`, `postcss-selector-parser`. Production sıfırı bunları gizlemez. İki mevcut lint uyarısı cilt effect dependency ve CockpitHeader img kullanımıdır. Büyük zorunlu paket değişimi/force fix uygulanmadı.

Kaynaklar ve kişisel belgeler/araştırma görüntüleri/ağırlıkları `audit-results` ve `audit-fixtures` altında ignored kalır. API anahtarı yalnız mevcut güvenli sunucu yapılandırmasındadır. Aynı çalışma branch'i kullanılır; PR#2 Draft tutulur ve main'e merge yapılmaz.
