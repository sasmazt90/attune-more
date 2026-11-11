# Üç saniyelik hibrit görüşme — dağıtım ve devir

Taban: `ca1372a449d8b7dd227133a04e46a176bff0a016` (11 Kasım 2026 güncel main).
Üretimde doğrulanmış kapanış build'i: `OLG8XIgqIM4wlCU5IkigE`.
Bu dal otomatik merge/üretim dağıtımı yapmaz.

Tamamlanmış ASR metni alındığında mutlak T0 alınır. Hazır katalog seçimi/indirme/SHA-256
ve oynatılabilirlik hazırlığı ile kişisel yanıt/tam ses hazırlığı paralel başlar. Hazır
aday yalnız seçilen en fazla iki kaydı indirir. Dinamik yanıtın tamamı tek WAV olarak,
aynı `female-calm-v1` profiliyle istenir; HTTP/URL/metin veya ilk parça hazır sayılmaz.

T0+3000 ms'den **önce** tamamen oynatılabilir kişisel ses kazanır. Diğer durumda hazır
A+B kazanır; erken kişisel yol hatası geçişi öne alabilir. Hazır ses de zamanında
hazır değilse bu gerçek kusurdur; beklenen fallback başarılıdır ve hata bildirimi değildir.
Karar ile gerçek `playing` zamanı ayrı ölçülür. Tarayıcı/Android gesture kısıtı gevşetilmez.

Kişisel yol canlı modelin kullanıcının sözlerine dayanan kısa karşılığını, mevcut
katalogdan bağlama uygun seçilmiş **aynı tam takip sorusuyla** birleştirir. Böylece
kullanıcının duyduğu soru amacı ile sonraki turdaki answered/skipped durumu tutarlıdır.
Nötr netleştirme/dinleme ve yalnız dinlenme yolları mevcut katalog kurallarını korur.
Adayların state nesneleri isteğe özeldir; yalnız kazanan state ve metin kaydedilir.
Kişisel karşılık kullanıldığında kullanılmamış A kaydı aHistory'ye eklenmez.

İptal, kapanış, sürüş, izin, sessiz mod, arka plan ve ses odağı iki kolu geçersiz kılar.
Kaybeden ağ/medya iptal edilir; geç sonuç başka tura taşınmaz. Resident iptali halen
worker sonlandırır ve yeniden ısınma planlar. Hazır oynatım bu işlemi beklemez.
Worker/model/compile/thread mimarisi değiştirilmez.

Hibrit normal konuşma structured-v1 kapanışını açmaz. `approved` A→B→C ve sunucuda
kontrollü kişisel katalog kaydı korunur; dinamik summaryReady kullanılmaz. F01
kazandığında ikinci veda oynatmadan tek mevcut kapanış başlatılır. Yazılı özet yalnız
seçilen gerçek görüşme metninden oluşturulur. 414 konuşma/144 kapanış WAV'ı değişmedi.

## Sonradan onaylı dağıtım adımları

1. PR CI ve ayrı test build'i kanıtlarını inceleyip dağıtılacak SHA'yı sabitleyin.
2. Mevcut release/config/build kimliklerini geri alma kaydı olarak saklayın.
3. Core API dal kodunu WEB/AAOS servislerine dağıtın; iki API ortamında
   `ATTUNE_MENTAL_HYBRID_ENABLED=1` ayarlayın. Katalog onay kontrollerini koruyun.
4. İki frontend için `NEXT_PUBLIC_MENTAL_CONVERSATION_ENGINE=hybrid-3s-v1` ve
   `NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE=approved` ile build alın. PUBLIC değerler
   build zamanındadır; yalnız runtime env değişikliği yetmez.
5. Mevcut same-origin/mTLS, TTS token, female-calm-v1 config/reference ve nesil
   ayarlarını koruyun. Yeni secret, model, ses hızı/perdesi gerekmez.
6. Mevcut deployment prosedürüyle release'i etkinleştirip build/flag ve tek görüşmeyi
   kontrol edin. DNS doğrulaması emülatör kontrolünden ayrı bir operasyonel adımdır.

Geri alma: önce önceki frontend build/release'i etkinleştirin (hibrit bayrağı olmayan
mevcut üretim build'i); ardından önceki API release/config'ine dönün veya
`ATTUNE_MENTAL_HYBRID_ENABLED` değerini kaldırın. `approved` kapanışı açık tutun.
Bu değişiklik şema/veri göçü veya yeni AWS kaynağı gerektirmez.

## Dar yerel doğrulama

`pytest tests/unit/test_mental_hybrid.py tests/unit/test_mental_structured.py -q`
ve frontend typecheck/build. Node alt testleri kontrollü saat/medya ve sağlayıcı
fixtürleridir; gerçek performans ölçümü değildir. Canlı kanıtlar ayrıca Drive'a
aktarılır. Gerçek mikrofon ve sentetik ASR ayrımı raporda açıkça korunur.
