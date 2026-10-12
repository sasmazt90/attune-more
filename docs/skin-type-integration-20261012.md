# Dört sınıflı cilt tipi: seçici hosted entegrasyon

AG `8b9db4649148d421c4495c657e76273a6f1cd006` içinden yalnız cilt tipi adaptörünün sözleşmesi, gerekli SDK bağımlılığı ve config alındı. Ana checkout'taki CD değişiklikleri, kuruluk `eligible-flake-area-fixed-v2-shared`, sarkma `contour-fold-lower-face-local-support-v6` ve kabul edilmiş yerel global kızarıklık modeli korunuyor. AG worktree değiştirilmedi; toplu cherry-pick, yeni eğitim veya başarısız detector/maske etkinleştirmesi yapılmadı.

## Model ve kanıt kapsamı

Seçilen hosted kimlik `skin-type-axavj/1`; sınıflar Normal, Kuru, Yağlı, Karma. AG'nin iki aday arasındaki mevcut iç karşılaştırması: 20 development fotoğrafında 19/20 ve macro-F1 0.9495. Bu genel uygulama doğruluğu veya bağımsız son test değildir. Kaynak klasörün adı `test` olsa da bu örnekler model seçiminde kullanılmıştır. Kaynak yayıncı Apache-2.0 olarak işaretlemiştir; bu etiket bireysel stok görüntülerin haklarını ayrıca kanıtlamaz. Yeni bağımsız kontrollerde bu stok fotoğraflarını dış servise göndermedik.

AG'nin dört gerçek MediaPipe crop kontrolü ve mevcut cevapları değiştirilmeden yerel kanıta kopyalandı; bulut karşılaştırması yeniden çalıştırılmadı. Bunlar önceki Python pipeline kanıtıdır, gerçek tarayıcı kabulünün yerine kullanılmadı. Değişmez kaynak SHA-256:

| Kaynak AG kanıtı | SHA-256 |
|---|---|
| skin-type-models-comparison.json | 81f9c42bc62bf2af74616dbafb6d8254f6eadb8a6bcfc5d715ece98c8344dd8a |
| skin-type-crop-impact.json | c7c093e32489e8e1b21baa228cf27d9ba1aff0ad38c3688c45de8d9896ff4d8e |
| skin-type-access-probe.json | 423ecb428f1bbc0be17ebca5395e54fbdcaa1bb80b7922e5b819da00bda3b714 |
| skin-type-sdk-weights-check.json | ecdd909926918644b18c10cdf50d1f5f79987aea52a25d45885273e55d61265f |

Hosted inference önceki kayıtlı cevaplarda çalışıyor. Yerel ağırlık elde edilmedi; başarısız SDK indirme denemesinin kesin nedeni ayrıştırılmadı. Üyelik zorunluluğu veya mimari imkânsızlık sonucu çıkarılmadı. Hosted modelin yerel ağırlık hash'i bilinmediği için `modelHash=null`; sağlayıcı/model kimliği ve varsa sağlayıcı package kimliği ayrı tutuluyor.

## HTTP, izin ve kayıt davranışı

`inference-sdk==1.7.4` belgelenmiş V0 base64/header-auth isteğini hazırlar ve cevabı ayrıştırır. Uygulamaya ait transport yalnız sabit model endpoint'ine bir POST yapar; gerçek bağlantı timeout'u 3 saniye, socket okuma timeout'u 15 saniyedir. Yanıt boyutu ve body okuma deadline'ı sınırlıdır. 401/403/429/503/504, yönlendirme ve bağlantı hatasında retry veya endpoint fallback yoktur. Global requests patch'i, site-packages değişikliği ve arkada sınırsız çalışan Future kullanılmadı. Sağlayıcının active learning kaydı kapalıdır.

Mevcut Git dışı anahtar yalnız backend süreç ortamına yüklenir. Yeni kalıcı anahtar dosyası yoktur. Normal süreç kontrolü: backend'de anahtar var; frontend'de yok. Kaynak ve production build baytları mevcut anahtarla karşılaştırıldı, eşleşme bulunmadı. Terminal/rapor kanıtına yalnız boolean sonuçlar yazılır.

Gizlilik & İzinler'deki ayrı dış servis fotoğraf işleme izni varsayılan kapalıdır. Her kaynak isteği bu izni taşır; backend yalnız gerçek boolean `true` ile hosted client oluşturur. İzin kaldırma tarama neslini geçersiz kılar ve istemci isteğini iptal eder; sonraki çağrılar dış servise gitmez. İptal/değişimden kalan cevap yeni sonucu veya geçmişi değiştiremez. Tarayıcıda bulunan tek ön poz tamamlama yolundaki yakalanmayan AbortError da giderildi; geçersiz eski nesil hata durumunu değiştirmez. Çok açılı yolda da eski neslin hata/guidance güncellemesi engellendi.

Sınıf confidence'ı problem şiddeti yüzdesine dönüştürülmez. Dört Türkçe etiket mevcut Genel Bakış ve geçmiş kartlarında gösterilir. İzin/ağ/kota/auth hatasında sınıf `null`, kart `—`; eski sınıf veya sağlıklı Normal ikamesi yoktur. Diğer kabul edilmiş yerel ölçümler korunur. Eski kullanıcı kayıtları silinmez veya yeniden ölçeklenmez.

## Kota

[Güncel Roboflow fiyatlandırması](https://roboflow.com/pricing) kredi esaslıdır. Mevcut anahtarla resmi hesap ve workspace metadata GET çağrıları 200 döndü; erişilebilir alanlarda plan, kullanım veya kalan kredi yoktu. **Hesap kotası doğrulanamadı**; kalan kredi `null`. 10.000/9.946 tahmini kullanılmıyor. Ücretli işlem, kart, kredi satın alma veya yeni hosted fotoğraf smoke isteği yok. Yeni canlı hosted fotoğraf çağrısı: **0**.

## Odaklı kabul

28 odaklı kontrol geçti: actual HTTP header/body ve tek çağrı, 401/403/429/503/504/yönlendirme, socket timeout ve parçalı body deadline, consent yokluğu/revocation, dört sınıf ve sağlayıcı kimliği, bilinmeyen model/bozuk cevabın reddi, hosted hata sırasında yerel derecenin korunması, gerçek istemci modülü ve geçmiş sözleşmesi. Production build TypeScript/lint/prerender kontrollerini içerir; mevcut lint uyarıları ayrı tutulur.

Gerçek Chrome kontrolü `scripts/skin-research/verify_hosted_type_browser.py` ile yapılır: kullanım hakkı kayıtlı NMu11er Head Shake fixture'ı (CC BY-SA 4.0), gerçek MediaPipe ve mevcut kalite/poz kapıları, gerçek ürün crop'u, gerçek backend/API ve uygulama HTTP transport'u. İzole sağlayıcı sadece AG'nin kayıtlı cevaplarını döndürür. Normal kullanıcı profiline/kayıtlarına erişilmez. Bu kontrol fixture kişisinin cilt tipini ölçmez; model doğruluğu iddiası değildir. Dört sınıf Genel Bakış'ta ve aynı kaydın Sağlık Geçmişim ayrıntısında, varsayılan izin yokluğu, 401/429/15 saniyelik timeout, izin kaldırma ve iptal sonrası yeni tarama ile sınanır. Doğal fotoğraf, arka plan, altı anatomik bölge/ağ, seçili kriter ve tam sayı bar kontrolleri korunur. İlk zorlanmış yazılımsal GPU denemesinde mevcut kamera başlangıç deadline'ı aşıldı; standart Chrome GPU yolunda kalite/poz override yapılmadı.

Son BUILD_ID `ARidagCpm937U1rBWf1wb`. Aynı build/backend/config/fixture hash'lerinde tamamlanmış dört sınıf/geçmiş ve üç hata aşaması `completed-stages.json` ile korundu. Soğuk kamera başlangıcında bitmeyen aşamalar model/eşik değiştirilerek geçilmiş sayılmadı. Yalnız kalan runtime kontrolleri `verify_hosted_type_runtime_browser.py` ile tamamlandı: izin sayfası istekten önce hazırlandı, gerçek istek sürerken izin kaldırıldı, READY dönüşü 3 saniyede doğrulandı; 17 saniye sonraki geç cevabın geçmişi değiştirmediği, sonraki çağrının sağlayıcıya gitmediği ve iptal/yeniden taramanın ayrı kayıt oluşturduğu geçti. Son runtime kontrolünde kamera retry sayısı 0, page error sayısı 0, canlı hosted fotoğraf çağrısı 0. Kayıtlı cevap testi canlı sağlayıcı smoke'u veya fiziksel kamera kabulü olarak sunulmuyor.

Normal Windows kısayolu ayrıca sahipliği doğrulanmış backend/frontend, production BUILD_ID, 213 frontend kaynak hash'i ve sunulan 15 JavaScript hash'iyle kontrol edilir. Normal API kontrolünde hosted izin açıkça kapalı tutulur; kabul edilmiş global kızarıklık model hash'i `65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3`, manifest hash'i `accc9ff193030bccde572ded39b1878fc7919e33daf62f2ac560c3357a83abfb` olarak kalır.

Yerel ayrıntılı kanıtlar `audit-results/skin-type-integration-20261012`, `output/playwright/hosted-type-20261012` ve `audit-results/skin-selected-20261011/hosted-type-product` altındadır. Nihai build/kontrol özeti yanındaki `skin-type-integration-evidence-20261012.json` dosyasındadır. Draft PR2 devam eder; main merge yok.

Bellek/paging baskısı sırasında C: rezervi 3 GiB altına düştü. Kapanmış yedi staged build'in yalnız tekrar üretilebilir webpack pack önbellekleri kesin yol/süreç/reparse-point denetimiyle kaldırıldı; gerçek kazanım 973.508.608 bayt. Önceki kullanılabilir build'lerin server/static dosyaları, canlı build, eğitim verisi/cache ve checkpoint tensorları korunur. İki tamamlanmış fazda süreç yoktur; STORAGE_PAUSE koruması kondu, bitmiş seçimler yeniden başlatılmadı. Bu entegrasyon için yeni bulut arşivi veya eğitim yazımı yoktur.

Bu teslim sivilce, morluk, torbalanma, çizgi ve diğer yeni maske adaylarının başarısız özgüllük sonuçlarını çözmez veya etkinleştirmez. Önceki hedef bazlı sonuçlar [tamamlanma raporunda](skin-completion-20261012.md) korunur; o rapordaki cilt tipinin dış erişim beklediği ve eski BUILD_ID bilgisi bu yeni teslimle güncellenmiştir.
