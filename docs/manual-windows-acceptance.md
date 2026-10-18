# Gözetimli Windows kabul adımları

Otomatik fiziksel mikrofon kaydı için yetki yoktur. Aşağıdaki mikrofon adımlarını kullanıcı kendisi yapmalıdır. Native browser/UI automation başlatımı Windows sandbox deny-read ACL helper hatasıyla sonlandı; bu bir approval-review ret kararı değildir.

## Native ses

Kurulu Chrome ön kontrolünde sürüm 132.0.6834.83 ölçüldü. `start(audioTrack)` parametresi Chrome 135'ten itibaren desteklenir; eski sürümde harness artık tanımayı başlatmadan UNSUPPORTED_TRACK_PARAMETER verir. [MDN uyumluluk verisi](https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/SpeechRecognition.json). Normal üretim mikrofon yolu `start()` kullanır; bu track testi normal mikrofon desteğinin bozukluğunu kanıtlamaz.

Bundled Chromium 148.0.7778.96 ile fiziksel mikrofon denied kalırken bir sentetik track gerçek native STT tarafından allowlist cümlesi olarak tanındı. Bu bir bağımsız kaynak ön kontrolüdür; normal .lnk/Chrome profilindeki üç gerçek mikrofon turu değildir. OpenAI istekleri 0.

Kullanıcının yapacağı kısa test:

1. Normal TOGG Başlat.lnk ile açın, PARK durumunu kontrol edin. OpenAI bulut aktarımı kapalı kalsın (LOCAL_DEMO; bu adımlarda ek ücretli sağlayıcı testi yok).
2. Gizlilik mikrofon iznini ve ayrı ses aktarımı onayını kendiniz açın; tarayıcı mikrofon isteğini bilinçli onaylayın. Kişisel/sağlık bilgisi söylemeyin.
3. Bir kez Görüşmeyi Başlat'a basın. Kitap/arkadaşlık örnekleriyle üç tur söyleyin. Her transcript'in doğru turda ve yalnızca bir kez görünmesini kontrol edin.
4. Asistan konuşurken dinleme yeniden başlamamalı; asistan sesi kullanıcı mesajı olmamalı. Türkçe TTS sesini kendiniz değerlendirin.
5. Görüşmeyi Bitir'e basın; geç gelen ses/yanıt veya yeni dinleme olmamalı. Saklama izni açıksa yalnızca tek özet bulunmalı.
6. Yeni ayrı, sentetik oturumda izin geri çekme/navigasyon/sürüş geçişi temiz kapanmayı doğrulayın. Uygulamayı kapatınca owned servisler kapanmalı, diğer Chrome pencereleri kalmalı. Test kayıtlarını yalnızca kendi test profilinizden kaldırın.

Tarayıcı güncellemesi burada otomatik uygulanmadı. Normal mikrofon izinleri gevşetilmedi veya kalıcı profil temizlenmedi.

## Takvim importu / alarm

Gerçek ürün .ics indirildi ve DISPLAY VALARM doğrulandı; bu bir kurulu bildirim değildir. Hassas veri içermeyen Planlanan takip başlığı, benzersiz UID, DTSTART UTC, DURATION 15 dakika, TRIGGER PT0M bulunur.

1. İzole test takvimi açın; ürünün test .ics dosyasını o takvime gerçekten import edin. Tarih/saat ve timezone dönüşümünü dosyadaki DTSTART ile karşılaştırın.
2. Gerçek alarmı kısa sürede sınamak için yalnızca bu test takvimindeki kopyayı beş dakika sonrasına taşıyın; başlangıçta bildirim/hatırlatma açık olsun. Windows ve takvim uygulamasının bildirim izinlerini ve eşzamanlamasını kontrol edin.
3. TOGG'u kapatın. Takvim alarmını gözleyin; import başarısı ile alarmın görünmesini ayrı kaydedin. Takvim/OS/push şartları sağlanmadan kapalı uygulama bildirimi iddiası yok.
4. Yalnızca geçici test eventini silin. Ürün içi plan iptali dış takvim eventini otomatik silmez.

## PDF Kaydet diyaloğu

Programatik Chromium PDF çıktısı, üretimin seçilmiş print HTML'inden hazırlanıp açılabilirlik/Türkçe/seçili kategori açısından ayrıca doğrulanır. Windows print-preview/Kaydet diyaloğunun tamamlanması bununla ispatlanmaz.

1. Hassas olmayan izole test profilinde Hekimle Paylaşılabilir Özet'i açın. İlk seçimler kapalı olmalı; yalnızca Cilt'i seçin.
2. Yazdır / PDF olarak kaydet'e basın; gerçek dialogda PDF hedefini seçip geçici bir dosyaya kaydedin (fiziksel yazıcı kullanmayın).
3. Kaydedilen PDF'yi açın. Türkçe karakterler, Cilt başlığı ve seçilen özet okunaklı olmalı; Görme/Ruhsal iyi oluş ve kimlik eklenmemeli.
4. Raporu dışarı göndermeyin; test dosyasını isterseniz silin. Dialog başarısı, açılabilir dosya ve kategori doğruluğu ayrı kabul maddeleridir.
