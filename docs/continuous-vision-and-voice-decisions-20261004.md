# Sürekli görme görevi ve ses kararları — 4 Ekim 2026

Bu sürüm Windows demosudur. Araç CAN/API bağlantısı, klinik doğrulama veya insan kabulü yoktur.

## Sürekli açı ve geçerlilik

[2025 Landolt C çalışması](https://pmc.ncbi.nlm.nih.gov/articles/PMC12173087/) sürekli 360° yön yanıtı ve dairesel rapor hatasını inceler. Sekiz katılımcılı çevresel crowding araştırmasının fiziksel ekran, sabit baş/çene desteği ve göz izleme koşulları bu MVP ile aynı değildir. Bu kaynak uygulamanın görme keskinliğini veya klinik yönlendirme eşiklerini doğrulamaz.

`landolt-orientation-continuous-v1` koordinatları: 0° sağ, 90° aşağı, saat yönü. Hedef ve başlangıç oku bağımsızdır. Yanıt snap edilmez; hata minimum dairesel farktır (0–180°). Görünmeme yanıtının açı/hata alanları null kalır; toplam geçerli denemelerden silinmez. Ortalama açı hatası yanında görünür/göremedi payı ve örneklem sayısı gerekir. Eski dört yönlü kayıtlara yeni etiket veya eşik uygulanmaz.

Hazırlanan veri sözleşmesindeki 24 denemelik, göz koşulu başına sekiz sunum; 1,25 boyut/kontrast değişimi; 750 ms güncellik; 1 saniye poz kararlılığı ve %8 göreli yüz ölçeği toleransı mühendislik parametreleridir. Yeterli klinik örneklem veya psikometrik eşik kanıtı değillerdir. Açısal hata doğru/yanlışa, Snellen/logMAR değerine veya klinik riske çevrilmez. Geçerli ölçüm kabul yolu henüz etkin değildir; bu parametrelerle üretilmiş kullanıcı sonuçları yoktur.

[MediaPipe Web kılavuzu](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js) yüz/landmark değerlendirmesini destekler; tam optik göz örtülmesini sertifikalandırmaz. İris veya blink skoru tek başına opak kapatıcı, el, gözlük, yansıma ve yanlış göz ayrımını güvenilir kanıtlamaz. Bu nedenle gerçek ölçüm kapalıdır. Kamera/model tek yüz, poz, kalite, göreli ölçek ve güncelliği izler; ayrı alıştırma sonuç kaydetmez. Tam kapatma doğrulaması açık ürün/araştırma maddesidir.

Manuel 85,6 mm kart eşleştirmesi cihaz ölçümü değildir. Gerçek pixelsPerMm değeri alt sınırla yükseltilmez. Ekran boyutu, DPR ve viewport scale bağlamı değişirse kayıt kullanılmaz. Aynı çözünürlüklü farklı fiziksel ekran otomatik ayırt edilemez; yeniden eşleştirme gerekir. Mutlak kamera santimetresi yoktur. Landolt çapı/çizgi/boşluk oranı 5:1:1 kalır. Fiziksel kalibrasyon klinik geçerlilik sağlamaz.

## Tek ses ve gerçek aktarım

AIswers yalnız okunmuştur. Week 15 ilk manifest İngilizce eşlemeleri içerir; Türkçe kanıt ayrı verification ve mevcut TR MP3 dosyalarıdır. Emma +%10, Ava +%10, Seraphina +%12 ayarları video projesine aittir. Mevcut ASR benzerlikleri sırasıyla 0,923207 / 0,977735 / 0,952503; dosyaların varlığı, hash ve süreleri yerel kanıtta doğrulanmıştır. Bunlar subjektif telaffuz/doğallık/sakinlik veya eş koşullu gecikme sıralaması değildir; yeniden dış ASR çağrısı yapılmamıştır. Verification güncel dosya hashlerine bağlanmış bir imza içermez.

[Microsoft dil/ses desteği](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support) resmi Azure Speech yolunu tanımlar. AIswers `edge_tts` consumer erişimi Azure API, SLA veya kullanım lisansı garantisi değildir. Bu çalışma yeni Azure hesabı, anahtar veya sağlık verisi aktarımı eklemez. Tek otomatik ses mevcut [OpenAI TTS API](https://developers.openai.com/api/docs/guides/text-to-speech) yolundaki coral olarak korunmuştur; en iyi Türkçe ses veya insan tarafından kabul edildiği iddia edilmez. Yapay ses açıklaması kullanıcıya görünür; hukuki/kurumsal onay açık kalır.

Backend SDK iter_bytes ile bir yanıtı parçalar; frontend aynı MP3 yanıtını sıralı MediaSource bufferına ekler. Yeni chunk için yeni ücretli istek yoktur. [W3C MPEG byte-stream biçimi](https://www.w3.org/TR/mse-byte-stream-format-mpeg-audio/) ve gerçek Windows Chrome audio/mpeg desteği doğrulanmıştır. Oynatma/bitirme HTML audio olaylarıdır; oynatma esnasında STT kapalıdır. İptal fetch/reader/buffer/audio yaşam döngüsünü kapatır. Gerçek ilk-ses/gövde-sonu kabulü ayrıca ölçülür; sentetik ton testi sağlayıcı kabulü değildir.

Markdown lexer/AST yalnız güvenli düz metin üretir. Yanıt HTML olarak çalıştırılmaz; ordered list numaraları ve anlamlı kod/Türkçe noktalama korunur. Aynı normalizasyon UI, TTS ve izinli dökümde kullanılır; sağlayıcı geçmişi ham gerçek yanıtlarla tutulur.

## Saklama ve cilt görüntüsü

Tam döküm ayrı tercihle, varsayılan kapalıdır; özet izni döküm izni değildir. Açılırsa tamamlanmış döküm aynı yerel seans kaydında zaman damgalarıyla tutulur. Geçmiş dialog'u sağlayıcıya çağrı yapmaz. Başlangıç/bitişi olmayan eski kayda uydurma saat eklenmez. Silme mevcut tek kayıt/durable deletion sözleşmesini kullanır.

Cilt kabul frame'i ve aynı frame'in gerçek ROI geometrisi yalnız RAM'dedir. Renkler bölge kimliğidir. Ön poz dört merkez bölge, anatomik sağa dönük poz sol yanak, sola dönük poz sağ yanak için kullanılır. Kalite ve poz eşikleri düşürülmemiştir; sonuçta kamera kapanır. Yeni tarama, iptal/izin/sürüş/unmount ve ilişkili kayıt silme RAM görüntüsünü temizler. Eski metrik kaydı fotoğraf üretmez. Hazırlık illüstrasyonu bu çalışma için kaynakta özgün çizilmiştir; Word'deki kimliği/hakkı belirsiz fotoğraflar dağıtılmaz.
