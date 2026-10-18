# Yönergeli yön hizalama ve ses güncellemesi — 4 Ekim 2026

Bu belge kullanıcının güncellenen ürün kararını uygular. Önceki `continuous-vision-and-voice-decisions-20261004.md` belgesindeki v1 optik örtülme nedeniyle bütün ölçümü kapatma kararı **bu görev için geçerli değildir**. Tarihsel başarısız ücretli koşu ve kanıtları değişmez.

## Çalışan yön hizalama kapsamı

`landolt-orientation-guided-v2`: manuel ekran hazırlığı ve gerçek kamera/model kontrolü → kaydedilmeyen üç alıştırma → sağ/sol göz için ayrı yönerge → iki gözle kontrast → 24 geçerli deneme → açıklayıcı sonuç → yalnız açık yerel saklama tercihiyle kayıt. Önceki kayıtlar yeniden etiketlenmez. Optik örtülme `not-camera-verified-user-instruction` olarak, verilen göz yönergesi ile birlikte ayrı kaydedilir. Kullanıcı devam eylemi kamera doğrulaması değildir.

[Sürekli Landolt yön yanıtı araştırması](https://pmc.ncbi.nlm.nih.gov/articles/PMC12173087/) yön raporu ve dairesel hata için kavramsal dayanak sağlar. Farklı crowding deneyini bu cihazın klinik kalibrasyonu saymıyoruz. Dengeli üç koşulda sekizer sunum, yaklaşık kısa bir oturum için sınırlı betimleyici örnekleme tercihidir; psikometrik eşik veya klinik yeterlilik kaynaktan çıkarılmamıştır. 24 deneme bitişi sabit yük sınırıdır. Görünür yanıtta boyut/kontrast 1,25 oranında azaltılır; göremedi yanıtta boyut büyütülür, kontrast yükseltilir (en fazla %100). Bunlar klinik staircase/eşik değildir. Görünmeme açı/hata değerleri null, görünür ve görünmeme sayıları ayrı; ortalama yalnız görünür yanıtlar üzerindedir.

Tamamlanmayan yanıt ile teknik geçersiz sunum ayrıdır. Teknik geçersizlik sayılır, yanıt/staircase ilerlemez; koşul düzeldikten sonra yeni hedef ve sunum kimliğiyle yeniden başlar. Göz değişince poz yeniden stabil olmalıdır. Dairesel hata 0–180°, 359/1 → 2°; snap veya gizli sekizli kategori yoktur. Sonuç Snellen/logMAR/gözlük numarası veya eski referral eşiğine bağlanmaz.

[MediaPipe Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker) model landmark/blendshape çıktısıdır; fiziksel opaklık veya ışığın göze ulaşmamasını ölçmez. Kapalı/örtülü gözün landmark'ları model tarafından kestirilebilir; landmark bulunması görünür/açık göz kanıtı değildir. Kısmi örtme model takibini sürdürebilir veya tüm yüz güvenini düşürebilir. Baş/poz hesabında göz landmark'ları da kullanıldığı için örtme sırasında model belirsizliği artabilir. Bunu kesin örtme doğrulaması veya kesin yanlış göz ihlali diye etiketlemiyoruz. Kamera/model, kadraj/tek yüz, ışık/netlik, mevcut baş poz eşikleri, bir saniye kararlılık, %8 göreli ölçek ve 750 ms güncellik korunur. Takip/kalite kaybında duraklatılır; eşik gevşetilmez.

85,6 mm kart eşleştirmesi manuel fiziksel hazırlıktır; px/mm yapay tabanı veya sembol minimumu yoktur. DPR/zoom/ekran bağlamı değişimi geçerliliği kaldırır; aynı çözünürlüklü farklı fiziksel ekran otomatik ayırt edilemeyebilir. Mutlak kamera cm ölçümü yoktur; kayıt `relative-face-scale-only` der. Kullanım yönergesi opak kapatıcı ve göze baskı uygulamamayı belirtir; etkin akış açık doğrulama sınırlarını gösterir.

Mevcut projede ayrı açık görme sonucu saklama tercihi bulunmadı. Bu nedenle Gizlilik'te varsayılan kapalı, yalnız yerel sayısal deneme/metadata tercihi eklendi. Kamera izni saklama izni değildir. Tamamlanmış kayıt mevcut transaction/lock, stable ID, geçmiş/yenileme ve tek kayıt Sil yolunu kullanır. Ham kare kaydedilmez.

## Türkçe ses ve dinleme sınırı

AIswers salt okunur: mevcut TR Emma/Ava/Seraphina MP3'leri, manifest/verification, script/runtime ve önceki hash/süre kanıtı. Aynı metinli örnekler değildir. Claude TR MP3 yerel ses içerik aracıyla açılmaya çalışıldı; bu oturumda işitsel içeriği algılayıp değerlendirme yeteneği yoktur. **Subjektif dinleme yapılmış sayılmaz**; telaffuz/doğallık/sakinlik sıralaması çıkarılmadı. Süre veya tarihsel ASR benzerliği kalite oylaması değildir.

Tek otomatik profil: `gpt-4o-mini-tts`, `coral`, MP3, hız **0,95**. Talimat: doğal Türkçe, sakin sıcak sohbet; reklam/haber tonu yerine kısa cümle-sonu durakları; abartılı vurgu/coşku/uzatılmış hecelerden kaçınma; metne ekleme yapmama. Sohbet promptu bağlamı korur, genellikle iki kısa cümle ve en fazla bir takip sorusu ister. Model davranışı insan tarafından kabul edilmiş sayılmaz; kriz/112 kod yolu korunur.

Coral seçimi bir “en iyi Türkçe ses” iddiası değildir. Mevcut desteklenen backend API üzerinde aynı veri aktarımı kapsamı, gerçek native oynatması daha önce gözlenen tek ses ve belgelenmiş instruction/speed kontrolüyle dar kapsamlı düzeltme tercihidir. [OpenAI TTS kılavuzu](https://developers.openai.com/api/docs/guides/text-to-speech) kontrollü konuşma biçimini destekler; sesler İngilizce için optimize edildiğinden Türkçe doğallık kabulü ayrıca gerekir. [Microsoft resmi dil desteği](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support) Azure yolunu kapsar; AIswers consumer `edge_tts` erişimi Azure API/SLA/kurumsal lisans garantisi değildir. Yeni hesap, credential veya başka projeden anahtar taşınmadı. Voice/provider seçicisi eklenmedi. Son subjektif ses kabulü açık kalır.

## Gecikme teşhisi ve yeni kabul

Önceki onaylı paired koşu FAIL olarak kalır: 6 önce + 2 sonra dispatch, retry 0, özet 0, sonra n=1; eksik browser timestamp'leri doldurulmaz. Sonra gerçek headers/gövde süreleri yaklaşık 1391/1485 ms, yani aradaki 94 ms; kısa gövde native playing'den önce doğal biçimde bitebilir. Bu sonuç tek başına streaming'in çalışmadığını veya hızlanmayı göstermez. Önceki n=3 ve sonra n=1 sayıları/eşit olmayan instrumentation ayrıdır.

Dar kapsamlı düzeltmeler:

- SDK `iter_bytes(chunk_size=None)` decoded transport parçalarını biriktirmeden iletir; 4096-byte birikim eşiği kaldırıldı.
- Frontend ilk append sırasında play promise'ını başlatır. Bir chunk önden okuma network read ile SourceBuffer update'i üst üste getirir; sıralı append ve 8 MiB transport koruması kalır. MSE tam çözülebilen MP3 frame'i bekler; sabit keyfî saniye buffer'ı yoktur. Tek yanıt/tek istek, chunk başına ücretli istek yok.
- Direct cancel, sourceopen/updateend bekleyişini de uyandırır; reader/fetch/SourceBuffer/audio/URL cleanup ve STT gate korunur.
- Ses hatası uyarısı sessize geçişte veya yeni yanıtın ses aşamasında temizlenir; yeniden hata oluşursa yeniden gösterilir. Ücretsiz hata → native MPEG oynatma → tekrar hata → sessiz metin akışı, eski uyarının yeni başarılı duruma taşınmadığını doğrular.
- Üretim yolu içeriksiz in-memory zaman olayları yayınlar: gönderim, chat dönüşü, TTS isteği/headers/chunk, play isteği, playing, gövde sonu, ended ve cleanup. Yerel kalıcı telemetry veya dış aktarım yoktur.
- Yeni kabul aracında AST normalizer run başına önceden hazırlanır; request başına yeni Node süreci açılmaz. Success/failure finally arşivi tüm mevcut olayları tutar. Eski paired consumed alanları hiçbir modda yeniden hazırlanamaz.

Yeni kriter: kontrollü artımlı aktarımda **aynı üretim yolunun** gövdenin tamamını beklemediğini actual Chromium MPEG events ile doğrulamak; hızlı gövdede native playing/ended, sıralı tam ses, iptal ve gerçek kullanıcı-gönderim→playing sürelerini ayrı ölçmek. Her gerçek gövdenin sonundan önce ses çıkacağı evrensel koşul kaldırıldı; canlı gövde yapay geciktirilmez ve eski FAIL geriye dönük PASS olmaz. Browser `playing` fiziksel hoparlörün akustik başlangıcı değildir. Browser performance saatinden yalnız browser farkları, backend monotonic saatinden yalnız request duration farkları alınır.

4 Ekim tarihli resmi fiyat kontrolü: [gpt-4o-mini](https://developers.openai.com/api/docs/models/gpt-4o-mini) giriş/çıkış milyon token başına $0,15/$0,60; [gpt-4o-mini-tts](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts) metin girişi $0,60, ses çıkışı $12. TTS ailesi [1 Ekim duyurusunda](https://developers.openai.com/api/docs/deprecations) deprecated olarak işaretlendi; bildirilen kapanış 6 Ocak 2027. Mevcut dar kapsamlı kabul için model değişmedi; hesap/model erişimi yeni onaylı koşuya kadar doğrulanmış sayılmaz. Sonraki kalıcı kullanım için sağlayıcı bakım maddesi açık tutulur; bu görevde kontrolsüz API migration yapılmadı.

Ücretsiz fixture kabulü canlı sağlayıcı kabulü değildir. Yeni 3 sohbet + 3 TTS + 1 izinli özet için ayrı onay, exact final SHA/build, güncel resmi fiyat ve request/input/output/retry cap preflight gerekir. Önceki kullanılmamış çağrılar izin sayılmaz. Hedef US$1 bir hesap harcama garantisi değildir; enforceable speech audio-output token sınırı yoktur. Gerçek hızlanma ve yeni profil doğallığı yeni ücretli/insan kabulü olmadan tamamlandı sayılmaz.
