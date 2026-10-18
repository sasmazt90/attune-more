# Canlı mikrofon olayı: kapsam ve önlem

## Korunan bulgular ve kanıt sınırı

İlk ücretli koşunun yolu `tests/e2e/live_provider_voice_followup.py` idi. Önceki koşuda native `SpeechRecognition.start()` ve mikrofon izni etkinleştirildi; Chrome `--use-file-for-fake-audio-capture` bayrağının bu native servis yolunu sentetik WAV'a bağladığı varsayıldı. Gerçekte beklenmeyen transcript oluştu ve provider çağrısına ulaştı. Dosya bayrağı getUserMedia için kullanılan test kaynağını native STT servisinin OS mikrofon kaynağıyla aynı kılmadı. Kaynak kimliği/allowlist, ilk sağlayıcı isteğinden önce doğrulanmamıştı.

Bu, test harness'inin kullanıcı tarafından verilen sentetik veri sınırını ihlal etmesidir. Üretim UI'sındaki mikrofon gizlilik izni, ayrı ses aktarım onayı ve OpenAI bulut onayı test tarafından açılmıştı; tarayıcı mikrofon izni de harness tarafından verilmişti. Mevcut production `cloudConsent: StrictBool = False` backend sınırı, kriz preguard ve izin geri çekme/epoch kontrollerinde bir bypass bulmadık. Bu, olayın zararsız olduğu veya bütün production izin yollarının güvenliğinin kesin olarak ispatlandığı anlamına gelmez.

Güvenli kalan metadata üç LIVE_OPENAI sohbet dönüşü ve üç TTS yanıtı/playing-ended olayını gösterir. Eski otomasyon görüşmeyi bitirme/özet yoluna da ilerlemiş olabilir; özet isteği ve başarılı yerel kayıt için tam ayrı sayaç korunmadığından kesin toplam verilemiyor. Normal kalıcı kullanıcı profilinde kayıt oluştuğuna dair bulgu yok; koşu izole browser context ve geçici backend veri dizini kullanıyordu. İzole context kapatıldı, ham transcript/screenshot'lar silindi. Tam provider tarafı istek envanteri ve silinme durumu doğrulanamadı. Eksik ledger nedeniyle başka istek hiç olmadı denmez.

Eski güvensiz harness sürümü ilk commit'ten önce değiştirildi; Git'te kalan 81b428d sürümü artık yazılı girdi harness'idir. İlk koşunun ham içeriği incelemede yeniden gösterilmedi/üretilmedi. Güvenli metadata `audit-results/live-provider/results.json` içinde INVALID_TEST_SOURCE olarak tutulur. Yerel dosyaların silinmesi OpenAI tarafında silinme kanıtı değildir.

## Tekrarı önleyen kontroller

- Fiziksel mikrofon CDP ile context/origin düzeyinde denied; SpeechRecognition/getUserMedia girişimleri ayrıca test harness'inde reddedilir. Native ses aktarımı checkbox'ı kapalı kalır.
- Kullanıcı metni tam üç sentetik cümleye eşit olmalı. Önceki her kullanıcı/asistan mesajı yalnızca aynı oturumun doğrulanmış gerçek yanıtlarıyla bire bir eşleşir.
- Browser isteği gönderilmeden ve backend HTTP transport gönderiminden hemen önce ayrı admission gate vardır. Bunlar sonuç üretmez; izinli istek gerçek FastAPI/OpenAI SDK/network yoluna gider.
- TTS input yalnızca o oturumun son gerçek provider yanıtıdır. Özet input tamamlanan tam altı mesajdır.
- Kesin sınır 3 conversation + 3 speech + 1 summary. Başarısız gönderim bütçeyi tüketir; SDK max_retries=0 korunur. Kalıcı run-consumed işareti aynı onayla ikinci koşuyu reddeder.
- Kaynak doğrulanmadığında, beklenmeyen mesaj/geçmişte veya ek istekte gate kapanır. Rejected content/header/key loglanmaz. Anahtarsız unit ve gerçek UI olumsuz kontrolleri ayrı kanıttır.

## OpenAI saklama koşulları (3 Ekim 2026 kontrolü)

Kod sohbet ve özet için `/v1/chat/completions`, ses üretimi için `/v1/audio/speech` kullanır. Resmî tabloda her ikisi training için kullanılmaz; varsayılan abuse-monitoring saklaması 30 gün, uygulama durumu saklaması istisnalarla none olarak belirtilir. Loglar prompt/response içerebilir; hukuki/güvenlik istisnaları süreyi uzatabilir. ZDR/MAM özel onay ve organizasyon/proje ayarı gerektirir. [Resmî data controls](https://developers.openai.com/api/docs/guides/your-data).

Bu TOGG projesinin ZDR/MAM, data sharing ve residency ayarları doğrulanamadı: browser kontrolü başlatılırken Windows sandbox deny-read ACL helper hatası verdi. Anahtar sağlayıcı ayarlarını okuma/yönetme yetkisi kanıtı değildir. Verinin sağlayıcıdan silindiği, ZDR aktif olduğu veya lokasyon garantisi verilmez. Store parametresi kodda true değildir; bu abuse-monitoring saklamasını kapatmaz. Proje yöneticisi Organization → Data controls ve proje override/data-sharing ayarlarını kontrol etmelidir.

## Ek yazılı koşu: bir istekten sonra durdurma

3f7e05c üzerindeki izinli ek koşuda yalnızca ilk sentetik kitap cümlesi gönderildi: 1 gerçek sohbet HTTP 200 / LIVE_OPENAI, 0 gerçek TTS, 0 özet. Provider HTTP süresi 2672 ms, UI yanıt süresi 5375.1 ms. Fiziksel mikrofon denied; ses aktarımı onayı kapalı; geçmiş uzunluğu 0. Browser response callback içinde JSON okuma event pump çalıştırdı. UI gerçek yanıtı alıp TTS isteğini başlatırken admission gate henüz önceki yanıtı tamamlamamıştı; TTS yanlışlıkla CONCURRENT_OR_RETRY_REQUEST olarak backend'e ulaşmadan engellendi. Bu, kaynak/izin ihlali değil test callback sırası hatasıdır. İzole context ve geçici backend kapatıldı; başarılı bitiş/özet kaydı oluşmadı.

Düzeltme gerçek isteği route.fetch(max_retries=0) ile gönderir; gerçek backend yanıtını doğrular, gate'i tamamlar ve ardından aynı yanıtı route.fulfill ile UI'ya bırakır. Yanıt üretilmez/değiştirilmez. Anahtarsız gerçek backend/UI kontrolü anında sonraki TTS isteğinin admission'a ulaştığını ve eksik anahtarın gerçek 503 hatasını UI'nın dürüst gösterdiğini doğrular. Unit kontrolleri yanıt teslim sırası ve gerçek fallback teslimi sırasında sonraki isteğin kapanmasını da doğrular.

run-consumed işareti korunur. İlk ek koşunun bütçesi ikinci bir ücretli koşu için yeniden kullanılmaz. Tam 0/2/4 + 3 bulut TTS + tek özet kabulü tamamlanmadı; ayrı kullanıcı onayı olmadan ek sağlayıcı çağrısı yapılmaz. Kanıt: audit-results/live-provider/controlled-text/{egress-proof,ui-proof,run-consumed}.json ve anahtarsız audit-results/live-harness-order.json.
