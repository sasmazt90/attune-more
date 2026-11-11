# Mental kapanışı: onay ve dağıtım devri — 11 Kasım 2026

## Durum ve yetki

PR #29 `dd3025ad7acdf15a05bd27a31e8ad2928a677e55` ile main'e birleşti; birleşme CI'ı başarılı
([run 42939829265](https://github.com/sasmazt90/attune-more/actions/runs/42939829265)). PR #30 kapalı ve kullanılmıyor.
Kullanıcı 144 kaydın tamamının kullanımını, dağıtımı ve WEB/AAOS kısa kontrolünü açıkça onayladı.
Onay kaydı: [OWNER-APPROVAL-20261111.json](OWNER-APPROVAL-20261111.json).
45 A/B/C ve 99 katalog kaydının manifest onayları işlendi. Sesler, metinler, hash'ler ve DE_C21'deki
3 kırpılmış PCM örneği bulgusu değişmedi. Yeni üretilen sesler kendiliğinden onaylanmaz.

Yerel hazırlık doğrulaması: mevcut kapanış köprüsü seti 15/15, katalog manifesti ve yeni üretilen
dosyaların otomatik onaylanmadığı kontrolleri 3/3 geçti. 144/144 WAV'ın boyut/SHA-256'sı doğrulandı;
manifest farklarının yalnız onay alanları olduğu kontrol edildi. Bunlar canlı dağıtım testi değildir.

**Bu belge dağıtım yapıldığı anlamına gelmez.** Hazırlayan oturumda AWS kimlik sağlayıcısı/federasyon,
AWS profili veya CLI yoktu. Kaynak başlatılmadı; canlı WEB/AAOS durumu bu oturumda okunamadı.
İşi, daha önce STS ve SSM erişimi çalışan `attune-codex-deployer` federasyonlu Codex Desktop Cloud
ortamında sürdür. Local Windows oturumunun aynı federasyona sahip olduğu varsayılmamalı.

## Dağıtım öncesi

1. Güncel main'i oku, dağıtılacak tam SHA'yı sabitle ve o SHA'nın CI sonucunu doğrula. Bu hazırlık
   commit'i yukarıdaki birleşme commit'inin devamıdır. Güncel olmayan bir PR dalını dağıtma.
2. STS ile hesap `798886013428` ve yetkili rolü, `eu-central-1` bölgesini doğrula. Kimlik değerlerini
   yazdırma. WEB `i-0b25450afc6633494`, AAOS `i-0f4cca4e92e94c351` durumlarını API'den kaydet.
3. Repo `docs/aws/OPERATIONS.md`, `OPERATIONS-CONTROL.md`, `scripts/aws/deploy_host.py`,
   `deploy_release.py`, `infra/aws/existing-instances.json` ile gerçek host envanterini karşılaştır.
   WEB iki uygulama yüzeyini de barındırır: web/aaos API ve frontend servisleri. AAOS'a yalnız
   dosya kopyalamak ya da yalnız web frontend'ini güncellemek tamamlanmış dağıtım değildir.
4. Başlatmak gerekiyorsa WEB, ardından AAOS. AAOS'ta mevcut yönlendirme üzerinden
   `127.0.0.1:3000` HTTP 200 olmadan kontrol başlatma. Geçerli DNS/mTLS/8443 yolunu koru;
   önceki deneylerin 8190/8191 portlarını üretim gereksinimi sayma. Yeni port veya kaynak açma.
5. Canlı kaynak/build kimliğini, .next build'ini, ilgili servis drop-in'lerini ve gizli ayarları
   **host üzerinde, erişimi kısıtlı** yedekle. Gizli ortam dosyalarını GitHub/Drive'a yükleme.
   Başarısız dağıtımda önceki build ve servis ayarlarına dönebilen adımı restart öncesi hazırla.

## Açılması gereken ayar

Her iki yüzeye sunulan Next.js build'i şu değerle oluşturulmalı:

```text
NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE=approved
```

Bu bir **build-time** ayardır. Eski build'i yalnız yeniden başlatmak veya systemd ortamına değer
eklemek yeterli değildir. `technical-preview` canlı hedef değildir. Genel kaynak varsayılanı
`off` kalır; bu dağıtımın build ortamına verilen `approved` değeri kalıcı dağıtım tanımında tutulur.
Diğer mevcut NEXT_PUBLIC/API/TTS ayarlarını aynen koru; normal konuşmanın ses profilini değiştirme.

Mevcut `deploy_host.py` incelendi: kaynakları `/opt/attune` üzerine rsync eder, .next'i yeniden kurar;
kendiliğinden rollback yapmaz. `BUILD_ENV` kapanış bayrağını içermiyor. SSM'den çağıran süreç bu
değeri gerçekten build alt sürecine geçirmeli; yalnız operatörün yerel shell'ine export etmek yetmez.
Ayrıca script `ensure_skin_runtime()` ile ilgisiz Python paketleri kurar ve `speech.conf` drop-in'ini
yeniden yazar. Bu yüzden script'i körlemesine çalıştırma: mevcut runtime/ayarlara göre gerekli küçük
dağıtım uyarlamasını hazırla; kapanış için ilgisiz paket kurulumu veya TTS ayarı kaybı yaratma.
Servis/port listesini gerçek hostta doğrula; APK değişmediyse yeniden APK kurma veya kullanıcı verisi silme.

Önce yeni build'i ve 144 WAV'ın boyut/hash eşliğini doğrula; sonra ilgili servisleri kontrollü geçir.
Servis sağlığı, sunulan commit/build ve gerçek sayfadaki kapanış modu birlikte doğrulanmalı.
Kapanışta A/B/C ile seçilen kişisel satır hazır dosyalardan gelir; dinamik TTS çağrısı beklenmez.
Eşleşme yoksa kişisel cümle uydurulmaz, yazılı özet kalır.

## Kısa kabul kontrolü

Yeni bir geniş benchmark veya GPU deneyi açma. Mevcut ölçüm aracının düzeltmelerini kullan:

- WEB'de TR/EN/DE birer tam kapanış; AAOS'ta TR/EN/DE birer tam kapanış. Gerçek dağıtılan
  sayfa/API kullanılsın; sentetik kullanıcı metni kullanılabilir, sonuç replay ile değiştirilmesin.
  Her parça kendi kimliğiyle playing/ended eşleştirilsin; A→B→C→uygun kişisel kayıt sırası,
  çakışmama ve C→kişisel geçiş raporlansın. Seçim reddi başarısızlık diye gizlenmesin veya
  beklenen dört parça eksikken PASS verilmesin.
- AAOS'ta bir A-çalarken izin geri çekme ve bir C-çalarken sürüşe geçme: eylem öncesi
  gerçekten başlayan oynatıcı kanıtı, ≤1.000 ms duruş ve sonradan kayıt başlamaması.
- Önceden BLOCKED kalan başlamadan-izin-geri-çekme vakasını yalnız bir kez uygun önkoşulla
  kontrol et. Önkoşul oluşmazsa BLOCKED yaz; testi sonsuz tekrar etme.
- Eski L3 FAIL kayıtları silinmez. Yukarıdaki yeni tam kapanış kontrolleri düzeltilmiş aracın
  canlı kanıtıdır; eksik olay/süre varsa PASS verilmez. Ölçüm kusuru ile ürün kusuru ayrılır.

Gerçek hata çıkarsa yalnız o hatayı düzelt ve etkilenen kontrolü tekrarla. Güvenlik/oynatma
regresyonunda önceki build'e dön. Kriz, park, izin, sessize alma, iptal ve arka plan kontrollerini koru.

## Kaynaklar ve teslimat

Mevcut WEB/AAOS başlatma ve dağıtım yetkisi var. Yeni GPU/instance/tip değişikliği, model veya ses
değişikliği yok. Mevcut otomatik kapanış politikasını bozma; test için açılan kaynakların kapanışını
oturumdan bağımsız mekanizmayla sınırla ve AAOS → WEB sırasıyla doğrula. Kalıcı build/approved
ayarı kapanışta geri alınmaz. Son rapor, "kuruldu ve yeniden açıldığında etkin" ile
"şu anda çalışıyor ve erişilebilir" durumlarını açıkça ayırsın; sürekli çalışma onayı uydurulmasın.

Yeni teslimat: mevcut round6 klasörü
[Review-2026-11-10-round6-final](https://drive.google.com/drive/folders/1AneO-HMWz0RaXZpDPCaBeHE6aVRUMsPY)
altında ayrı `Deployment-2026-11-11` klasörü. Onay kaydı, bu plan, son commit/CI, WEB/AAOS
kısa kontrol sonuçları, gizli değer içermeyen zaman çizelgeleri, rollback/kaynak son durumu ve
maliyet hesabını koy. Dosyaları geri okuyup boyut ve SHA-256 doğrula; eski raporları değiştirme.
144 WAV zaten Drive'da, değişmediyse tekrar yükleme veya üretme.

Dağıtımın ardından normal konuşma gecikmesi için [DYNAMIC-TTS-REVIEW-20261111.md](DYNAMIC-TTS-REVIEW-20261111.md)
üzerinden dar kapsamlı karar ver. Kapanış dağıtımını yeni araştırmanın bitmesini bekleterek geciktirme.
