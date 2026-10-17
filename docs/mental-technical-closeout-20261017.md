# Ruh Sağlığı teknik teslimi — 17 Ekim 2026

Kod düzeltmeleri ve kontrollü teknik doğrulama tamamlandı. İki gerçek OpenAI turu ve bir gerçek özet başarılıdır. **Canlı Emel uç noktası tek denemede HTTP 503 verdi; çevrimiçi dinamik ses erişimi açık engeldir.** Kayıtlı Emel ile native ses yaşam döngüsü geçti. Bu iki kanıt birbirinin yerine kullanılmaz. `physicalUserAcceptance:false`; kesintisiz doğal sesli görüşme kabulü tamamlandı denmiyor.

## Çalışma alanı ve başlangıç

Salt okunur kaynak HEAD `5f11c111e3f6547e6420ddf37db477190d232f10`, dal `fix/live-test-followup`. Kaynak görev tablosunun mevcut dirty değişikliği ve untracked durum dosyası başlangıç hash'leriyle korundu. Geçerli AGENTS.md bulunmadı. Kaynak HEAD'den ayrı worktree:

`C:\Users\PC\Desktop\AI Workspace\TOGG\attune-cdc-mental-technical-20261017`

Dal: `research/mental-technical-closeout-20261017`. Son BUILD_ID: `iWyABFO5oX3OLGs4tM6Vh`. Yerel teslim SHA'sı ilerleme klasöründeki `status.json` ve `delivery-receipt.json` içindedir. Push/merge, modül birleştirme veya normal başlatıcı değişikliği yapılmadı.

Başlangıç incelemesi: güncel F089–F106, `all-health-delivery-20261010.md`, `release/all-execution.json`, son başarılı mental-control/mental-asr log'ları ve eski sınırlı canlı ledger. Eski canlı kaydın bütün UI kabulü geçmediği, sonradan geçen kontrollü tekrarların ayrı olduğu korundu. Başlangıçta yeniden üretilmiş güncel hata yoktu; bekleyen yanıt, yeni build bağlam/kayıt ve ses yaşam döngüsü doğrulaması açık işti. Eski fiziksel mikrofon/telaffuz açığı teknik hata sayılmadı.

## Gerçek hatalar ve aynı vakada önce/sonra

| Hata / işlem | Önce | Sonra / kanıt |
|---|---|---|
| Yanıt beklerken duraklat/devam | İki kullanıcı kartına yalnız bir tamamlanmış asistan turu; devam bekleyen turu sürdürmüyordu. Bitirmede error, 0 özet/0 kayıt. | Bekleyen kullanıcı/tur kimliği ve tamamlanmış önceki bağlam bellekte korunur. Açık Devam eylemi aynı turu sürdürür; kart çoğalmaz, iptal edilmiş eski yanıt kabul edilmez. İki kullanıcı/iki asistan; bir özet/bir kayıt. `pause-pending-before.json`, `pause-pending-after.json`. |
| Bekleyen sesin devamı | Duraklatılan sesin mantıksal devam durumu saklanmıyordu. | Aynı mevcut yanıt seslendirmesi devamda yeniden başlatılır; yeni sağlayıcı turu veya yinelenen asistan kartı üretilmez. Mute bu bekleyen sesi temizler. Vedalaşma bekliyorsa mikrofon yerine finish yolu korunur. `conversation-browser.log`, `controls-proof.json`. |
| Bozuk / sınırsız bağlam | System/orphan/yarım history, aşırı uzun context/sessionId ve boşluk mesajı kabul edilebiliyordu. Sekiz yeni probe başlangıçta başarısızdı. | 422 ile sağlayıcıdan önce ret. History en fazla 40 mesaj ve sıralı tamamlanmış user/assistant çiftleri; mesaj en fazla 6000 karakter; sessionId en fazla128; özet en fazla200 mesaj/toplam120000 karakter. Frontend tamamlanmış son40 mesajı gönderir; sağlayıcının önceki son40 davranışı korunur. `before-context.xml`, `focused-tests.xml`. |
| İzole kayıt/gizlilik taşıması | Sabit normal API origin'i izole silme/gizlilik işlemlerini başka servise götürebilirdi. | Opsiyonel yalnız loopback portu; bu build 8307 kullanır. Normal `localhost:8000` varsayılanı aynı kalır. Yeni test kötü port/external URL'yi kabul etmez. Kullanıcı kayıtlarına yönelik bakım/silme yapılmadı. |
| Ruh hâli kaynağı | Özetin model yorumu kaynağı ayrıca işaretlenmiyordu. | Yeni kayıtta mevcut moodTrend varsa `moodTrendSource:assistant-inferred`; kullanıcı beyanı veya önce/sonra ölçümü gibi kaydedilmez. Eski kayıtlar yeniden yazılmaz. Gerçek canlı kayıtta bu işaret doğrulandı. |

Bekleyen tur vakasında üçüncü HTTP denemesi, duraklatmada iptal edilmiş ikinci isteğin **açık Devam** sonrasındaki aynı-tur devamıdır; üçüncü kullanıcı turu veya otomatik sağlayıcı retry değildir. Tam kontrollü karşılaştırmada üç tamamlanmış kullanıcı turu için context uzunlukları `0,2,2,4`; özete yalnız altı tamamlanmış user/assistant mesajı girdi.

Ağ iptali browser'ın sahip olduğu isteği ve geç yanıtın işlenmesini durdurur. Daha önce gönderilmiş isteğin sağlayıcı tarafındaki işlemesinin geri alındığı iddia edilmez; gerçek SDK isteği mevcut25 saniye timeout/retry0 ile sınırlıdır.

## Doğrulama ve sınırları

- Başlangıçtaki57 ilgili regresyon geçti. Son durumda **68 benzersiz odaklı test geçti**, ilgisiz cilt karşılaştırması içeren bir test seçilmedi. Kriz Unicode, kriz+vedalaşma önceliği, gündelik negatif ifade, teşhis/ilaç sistem politikası, izinler, kayıt doğruluğu, sağlayıcı hatası ve stream kapatma kapsandı. Kontrollü politika testi klinik güvenlik garantisi değildir.
- `next typegen` + `tsc --noEmit` geçti. Production build geçti. Önceden mevcut cilt effect dependency ve header img lint uyarıları kapsam dışında korundu.
- Bekleyen tur/ses, kontrollü ASR ve 11 yaşam döngüsü vakası ilk production build `KStBAlggVtmSveA-DN6E0` üzerinde çalıştı. Son build, yalnız izole gizlilik/kayıt API taşımasını ekledi; `useMentalConversation.ts` iki build'de aynı SHA-256'dır. Son build üzerinde 390px izin/geçmiş, sesli duraklat/mute/vedalaşma ve gerçek canlı iki tur/özet çalıştırıldı. Son kaynak/build/servis kimlikleri ayrıca doğrulandı; değişmeyen kontroller sebepsiz yeniden çalıştırılmadı.
- ASR olayları testte kontrollüdür. Interim ve tekrar final kullanıcı turu üretmedi; asistan sesi sırasında eski callback reddedildi; native recorded Audio gerçekten ended olduktan sonra yeni dinleyici açıldı. No-speech normal sona erme ve izin/ağ hatası ayrı sınandı.
- On bir ayrı vaka: ASR hataları, başlangıç izin bekleme iptali, sağlayıcı hatası, ses hatası, özet hatası, özet iptali, özet sırasında hizmet onayı iptali, mikrofon iznini kaldırma, gerçek izole araç API'sinde sürüş geçişi, SPA çıkışı, eski oturumdan geciken yanıt. Hiçbiri başarısız/iptal edilmiş görüşme kaydı üretmedi; sahip olunan ASR/audio kapandı. Sürüş API'si tekrar park durumuna getirildi.
- Güncel sesli kontrol: normal yanıtta mute sesi kapatıp mevcut giriş akışını sürdürdü; gerçek `conversation_control` yolu “Görüşmeyi duraklat” ile durdu; Devam aynı oturumdaydı. “Hoşça kal” seslendirmesi sırasında mute, dinleyiciye dönmek yerine bitirme/tek özet yolunu tamamladı.
- Masaüstü ve 390×900 dar görünüm incelendi. Dar sayfa genişliği384; yatay sayfa taşması yok. Son gerçek özet penceresi x16/y251,33/w358/h397,33 ile viewport içindeydi. MentalPage markup/metinleri kaynak commit ile aynı. Full-page ekranların sticky-header/modal birleştirme konumları viewport geometrisi yerine kullanılmadı; ayrıca gerçek viewport ekranları alındı.
- Özet varsayılan açık, transkript varsayılan kapalı kaldı. Özet+transkript opt-in: dört sıralı/timestamp'li metin aynı kayıtta; yeniden yüklemede aynı kayıt; silme kalıcı. Özet off/transkript on: **0 kalıcı kayıt**. Özet opt-out tam konuşmanın gizli bir backend kaydını oluşturmadı; normal backend oturum deposu boş doğrulandı. Yanıt/özet için izinli bulut işleme, kalıcı döküm izninden ayrı tutulur.
- Psikolog yönlendirmesi gerçek `from=mental&specialty=Klinik Psikoloji` route/context ile doğrulandı. Diğer modül/normal-port API'leri bu yönlendirme testinde engellendi; canlı uzman arama veya randevu yapılmadı.

Otomasyon sorunları uygulama kusuru sayılmadı: mevcut dialog adı “Ruh Sağlığı sonucu” ve erişilebilir silme adı seçicileri düzeltildi. Aynı tamamlanmış kaydın geçmiş/silme kontrolü devam edilerek kapatıldı; uygulamanın metni değiştirilmedi. No-speech testinde doğal `onend`, test aracında “aborted” yerine “ended” olarak işaretlendi. Ara başarısız otomasyon log'ları korunur.

## Gerçek sağlayıcı ve canlı ses

Mevcut sunucu yapılandırması ve **gpt-4o-mini** korundu. Anahtar yalnız backend belleğinde mevcut kaynak yapılandırmasından yüklendi; başka dosyaya, Git'e, browser'a veya build'e kopyalanmadı. Node başlatıcısına OPENAI_API_KEY aktarılmaz; çağıranın ortamı sonunda geri yüklenir. Yeni hesap/anahtar/abonelik/model/sağlayıcı yok.

Bu görevdeki gerçek OpenAI kullanım: **2 konuşma +1 özet**, üçü de HTTP200/LIVE_OPENAI. İkinci istekte iki önceki tamamlanmış mesaj vardı; mevcut konu etiketi hatırlandı. İki görünür yanıt API cevabıyla eşleşti. Dört gerçek mesajdan özet üretildi, tek izinli kayıt saklandı, yenilemeden sonra aynı kayıt açıldı. Döküm, durationSeconds, moodBefore/moodAfter saklanmadı. Ledger yalnız hash/rol/usage/süre içerir; konuşma metni/anahtar içermez. Tahmini ücret veya fatura uydurulmadı. SDK'nin timeout25 saniye/max_retries0 sözleşmesi değişmedi.

Mevcut Edge/Emel için **bir** kısa, kişisel veri içermeyen `Merhaba.` erişim denemesi yapıldı. Aynı isteğin konsol kaydı HTTP503 gösteriyor. Browser makbuzundaki TypeError test aracının native Fetch `ok/status` özelliklerini metot gibi çağırmasından kaynaklandı; araç düzeltildi. Bu yüzden yanıt gövdesinin ayrıntısı tutulamadı; 503'ün alt nedeni ayrıştırılmadı. Yeni istek, otomatik retry, farklı ses, fallback sağlayıcı veya yeni ücretli TTS yapılmadı. `live-tts-observation.json` ile özgün `live-proof.json` birlikte okunmalıdır. Ledger'daki `failed:false` yalnız üç OpenAI işleminin durumudur; TTS başarısı anlamına gelmez.

Kontrollü testler gerçek API route'larında yalnız sağlayıcı/audio seam'ini değiştirir; bu kod `tests/e2e` altındadır. Native Audio/MSE ile kullanılan dosya mevcut **mental-complete Emel** kaydıdır; dinamik yanıtın o anda üretilmiş ses kaydı değildir. Normal teslim sunucusunda `/__test__/ledger` 404 doğrulandı; üretim bundle'ında fixture anahtarı/yanıtı yok. Bu teknik fixture kanıtı gerçek sağlayıcı, doğal ASR veya telaffuz kabulü diye yeniden adlandırılmadı.

## F089–F106 durum tablosu

| ID | Durum | Bu teslimin kanıtı / açık sınır |
|---|---|---|
| F089 Ayrı izinler | TEKNİK GEÇTİ | `permissions-proof`, lifecycle consent/mic revoke; varsayılanlar korundu |
| F090 Başlat/Türkçe ASR | KONTROLLÜ TEKNİK GEÇTİ | Interim/final/yeniden başlama; fiziksel mikrofon ve doğal ASR açık |
| F091 Yazılı giriş/backend | CANLI GEÇTİ | `live-proof`, iki gerçek normal frontend/API/provider turu |
| F092 Bağlam | DÜZELTİLDİ / CANLI GEÇTİ | Aynı tur devamı,0/2/2/4; gerçek0/2 context. Eski oturum callback'i yeni oturumu etkilemedi. Backend history istemci tarafından sağlanır; yeni kimlik/oturum doğrulama sistemi eklenmedi. |
| F093 Türkçe yanıt/Emel | KISMİ — CANLI TTS ENGELLİ | Gerçek Türkçe metin geçti; kayıtlı Emel/native playback geçti; dinamik uç nokta HTTP503 |
| F094 Kullanıcı/sistem sesi ayrımı | KONTROLLÜ TEKNİK GEÇTİ | Sistem sesi sırasında ASR kapalı/eski callback etkisiz; fiziksel yankı açık |
| F095 Parçalı/gecikmiş yanıt | KONTROLLÜ TEKNİK GEÇTİ | Interim/duplicate/oturum nesli kontrolü, `conversation-browser`, lifecycle old-session |
| F096 Mute/duraklat/devam | DÜZELTİLDİ / TEKNİK GEÇTİ | Pending turn/speech belleği; mute ve pendingFinish kontrolü |
| F097 Bitir/iptal | TEKNİK GEÇTİ | Gerçek farewell kontrol route'u, tek özet; iptal/yarım görüşmede kayıt yok |
| F098 Sağlayıcı/ağ hatası | TEKNİK GEÇTİ; SES ERİŞİMİ AÇIK | Kontrollü503 görünür; demo yanıt/başarılı sahte özet yok; canlı503 ayrıca kaydedildi |
| F099 Gerçek özet | CANLI GEÇTİ | Dört gerçek tamamlanmış mesaj, tek kayıt/aynı geçmiş; model mood yorumu ayrı işaretli |
| F100 Özet/transkript ayrımı | TEKNİK GEÇTİ | Varsayılan döküm off; opt-in4 mesaj; summary-off/transcript-on0 kayıt |
| F101 Geçmiş/silme | GERÇEK YEREL YOL GEÇTİ | İzole localStorage/IndexedDB, reload ve kalıcı tekil silme; normal kullanıcı kaydı kullanılmadı |
| F102 Kriz/gündelik ifade | KONTROLLÜ TEKNİK GEÇTİ | Backend kriz önce gelir,112; gündelik negatif kontrol. Klinik evrensel garanti değil. |
| F103 Teşhis/ilaç sınırı | POLİTİKA / TEKNİK TEST GEÇTİ | Mevcut sabit sistem sınırları kontrollü client ile; iki canlı nötr tur klinik güvenlik testi sayılmaz |
| F104 Süre/uzunluk/döngü | TEKNİK GEÇTİ | Alan/bağlam sınırları,25/30sn deadline,SDK retry0, sonlu canlı bütçe; otomatik çağrı kampanyası yok |
| F105 Psikolog yönlendirmesi | ROUTE/CONTEXT GEÇTİ | Klinik Psikoloji doğru; uzman sağlayıcı/randevu kabulü kapsam dışında |
| F106 Fiziksel mikrofon/telaffuz | AÇIK | Tek son ortak doğal konuşma/duyma kabulü; canlı Emel engeli önce giderilmeli |

## Kimlik, koruma ve yerel teslim

`served-protection-receipt.json`: son build'in **38 sunulan JS dosyası** bütün baytlarla disk SHA-256'sına eşleşti; HTML script zinciri bu dosyalara bağlı. İki mevcut Emel giriş/tamamlama kaydı HTTP üzerinden aynı hash'e sahip. `mental_provider.py`, `openai_client.py`, `tts_profiles.py`, `vision_speech.py` ve MentalPage kaynakla aynı kaldı. Ses `tr-TR-EmelNeural`, rate `-10%`, pitch `-10Hz`.

Koruma doğrulaması: kaynak live-test HEAD/dirty dosyalar ve iki görev dosyası hash'i değişmedi; cilt2637d1b, göz1cdb95e, AG ve Claude HEAD/çalışma ağaçları başlangıçla aynı. Onların servis portları kullanılmadı veya durdurulmadı. Stop işlemleri yalnız bu teslimin PID + başlangıç zamanı + komut + checkout makbuzunu iki kez doğrulayan sahiplik kontrolüyle yapıldı. Yeni eğitim, veri indirme veya normal başlatıcı/profil değişikliği yok.

Çalışan izole URL: **http://127.0.0.1:3307/mental**, backend8307. Son teslim normal API wrapper'ını kullanır; kontrollü test sunucuları kapandı. Temiz ayrı browser profilinde test override'ı/kayıt yoktur. Bu URL metin/özet yolunda doğrulandı; canlı dinamik Emel sesinin çalıştığı iddia edilmiyor.

Sunucular çalışırken tekrar başlatmak gerekmez. Gerektiğinde yalnız bu checkout'ta:

```powershell
.\Stop-Mental-Technical.ps1
.\Start-Mental-Technical.ps1
```

Başlatıcı kaynak/build/ses hash'lerini kontrol eder, yalnız loopback3307/8307 açar ve ayrı `cdc-progress/mental-technical-closeout-20261017/browser-profile` kullanır. Port başka sahibe aitse değiştirmez. Default sunucu başlatma/durdurma `-NoBrowser` ile gerçekten çalıştırıldı. Mevcut kaynağın `.env.local` dosyasına yazılmaz; kullanıcıdan yeni anahtar istenmez.

İlerleme/kanıt klasörü: `C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\mental-technical-closeout-20261017`. Atomik status, başlangıç/proses/build/koruma makbuzları, XML/log'lar, canlı ledger ve bu raporun `report.md` kopyası buradadır. Fotoğraf, ham ses veya kişisel konuşma rapora eklenmedi. Browser makbuz/UI ekranları bu checkout'ta `output/playwright/mental`; toplu metin/hash kanıtı `docs/mental-technical-closeout-20261017.json`.

## Bütün modüllerin sonunda yapılacak tek fiziksel kullanıcı kontrol listesi

Bu aşamada ara test istenmiyor. Canlı Emel erişimi tekrar sağlandıktan ve diğer modüllerin teknik işleri tamamlandıktan sonra:

1. Gerçek mikrofonla doğal Türkçe, duraklamalar, parçalı/düzeltilmiş cümleler ve normal çok turlu bağlam; her mesaj tek tur olmalı.
2. Gerçek hoparlörde mevcut Emel sesinin duyulabilirliği, telaffuzu, hızı/pitch'i ve doğallığı; kayıtlı fixture bu kabul yerine geçmez.
3. Mikrofon–hoparlör yankısı: asistanın kendi sesi yeni kullanıcı mesajına dönmemeli; gerçek ses bittikten sonra dinleme güvenle açılmalı.
4. Doğal kesintisiz görüşmede pause/devam/mute/vedalaşma; bekleyen ağ/ses, izin iptali, sayfa çıkışı ve sürüş kilidi güvenle kapanmalı.
5. Gerçek tamamlanmış görüşmenin izinlere uygun özeti/geçmişi; döküm opt-in/off ve tekil silme; iptal/başarısız görüşmeden kayıt olmamalı.
