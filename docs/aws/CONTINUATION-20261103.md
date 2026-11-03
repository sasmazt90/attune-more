# Task 13 — yeni Cloud runtime devam kaydı

3 Kasım 2026. PR #22'nin önceki CDC commit'i `5a82147` bu dala fast-forward
alındı. Önceki IAM, kota ve Pricing kontrolleri yeniden çalıştırılmadı.
Kullanıcı yeni Cloud ortamına geçmeden önce commit/push istediği için çalışma
bu noktada kaydedildi. **Kurulum paketi tamamlanmadı; ücretli start onayı yok.**

## Korunan kanıtlar

- [Bu runtime API/indirme/APK kanıtı](evidence/continuation-20261103.json).
  Üç SG kuralı mevcut ve exact port/kaynak eşleşmesi doğrulandı; yeni write gerekmedi.
  WEB `i-0b25450afc6633494` ve AAOS `i-0f4cca4e92e94c351` hâlâ stopped.
- Son uygulama kaynak commit'i `7a26c13` için APK yeniden indirildi.
  GitHub run `41634882348`, artifact `13229474049`; 66,182 byte;
  SHA-256 `646f504b32b60ef9c670eef66e59a8923ddeb5ff9681c9e066ba6f78e54aa8b6`.
  ZIP digest `417b99d519f11fd6ca330e504205d5dd1c3b8958e39e882de97aa0320dc1f79d`.
  Artifact 10 Kasım 2026 13:21 CET'te sona erer; kaynak ve build workflow Git'te.
  `5a82147` APK kaynaklarını değiştirmedi. Device install henüz yapılmadı.
- [ONNX kaynakları ve tam beklenen hash'ler](evidence/model-recovery-sources.json)
  korundu. Bu runtime'da parça 002 indirildi: 100,663,296 byte,
  SHA-256 `40cf2b5e711e8921ab747c2f638f57de964f6d74e8233fa435c75ea63b6d33a3`.
  Step0 ve 000/001/003 aktarımları proxy CONNECT 403 ile engellendi.
  Birleşik model üretilmedi; beklenen hash doğrulanmış sonuç olarak gösterilmedi.
- [Regional bundle kanıtı](evidence/regional-model-staging.json) önceki `5a82147`
  commit'inden korunuyor. O runtime'da 24 parça, birleşik arşiv ve 31 üye
  doğrulanmıştı. Bu yeni runtime'da bu binary dosyalar bulunmuyor.
- [Chatterbox 98-parça kaynak manifesti](evidence/chatterbox-recovery-sources.json)
  kaydedildi. Kaynak manifest hash'i doğrulandı; bu devam çalışmasında tamamlanmış
  parça indirme makbuzu yok. TTS arşivi/bundle hazır sayılmamalı.
- [Önceki tam AWS preflight](PREFLIGHT-20261103-R2.md),
  [maliyet kanıtı](evidence/pricing-20261103.json) ve [başlatma planı](START-PLAN.md)
  korunuyor: 2 saat + 10 GB çıkış varsayımıyla AWS 4.45070 USD;
  önerilen AWS/provider operasyonel bütçe 6 USD, vergi hariç, hard cap değil.

Binary dosyalar `.aws-oem`/attachments içinde yereldir; yeni runtime'a otomatik
taşındıkları varsayılmamalı. Git'e yalnız kaynak kimlikleri, tam hash'ler, sonuçlar
ve devam araçları alındı. İmzalı indirme URL'leri, secret değerleri ve modeller
Git'e eklenmedi. Yeni ortam Drive kaynaklarından tekrar indirme yapabilir.

## Ağ ve servis denetimi

[26 hostname kontrolü](evidence/network-audit-20261103.json) ve
[gerçek kurulum indirme yolları](evidence/download-probes-20261103.json).
Cloud policy enforced, AWS identity ready; Cloud secret binding/runtime variable yok.

- Eklenen `sdmntprnortheu.oaiusercontent.com` ve
  `sdmntprpolandcentral.oaiusercontent.com` erişilebilir; Poland üzerinden parça 002
  gerçek indirme ile doğrulandı. Domain root HTTP 400 bir dosya doğrulaması değildir.
- Drive bu sefer Step0/000 için `sdmntprcentralus.oaiusercontent.com`, 001 için
  `sdmntprsoutheastus3.oaiusercontent.com`, 003 için
  `sdmntpreastus2.oaiusercontent.com` döndürdü. Üçünde CONNECT 403 var.
  Kullanıcıdan bu üç domain ve sonraki servis denetimi için `api.openai.com`,
  `attune.sasmaz.digital`, `aaos.sasmaz.digital` Cloud HTTPS izinleri istendi.
  Son üçü de bu runtime'da CONNECT 403 aldı. Bu, EC2 egress testi değildir.
- Küçük kontrol ZIP'i ve APK, desteklenen dosya indirme aracıyla alındı;
  onların dönen `sdmntprukwest.oaiusercontent.com` ve
  `sdmntpritalynorth.oaiusercontent.com` adresleri büyük dosyalarda da dönerse
  ayrıca izin gerekir. Drive bölgesel hostname'i sabit değil; URL yeniden
  alınırken hostname kaydedilmeli, URL/token loglanmamalı. Proxy atlanmadı.
- Android SDK ve AAOS XML katalogları (`dl.google.com`), Ubuntu security Release
  ve Caddy 2.10.2 checksum indirmeleri gerçek yollarında HTTP 200 döndü.
  Bazı domain root HEAD istekleri 403 döndüğünden gerçek yol sonucu esas alınmalı.
  Caddy binary, SDK image, Python wheel ve HF snapshotlarının tamamı henüz indirilmedi.
- Mental: `OPENAI_API_KEY`, isteğe bağlı `OPENAI_BASE_URL` (varsayılan
  `https://api.openai.com/v1`), `OPENAI_MODEL` (varsayılan `gpt-4o-mini`).
  Anahtar yoksa yerel fallback canlı-provider kabulü sayılmaz.
- ASR: aynı provider anahtarı/base URL, `ATTUNE_CLOUD_ASR_ENABLED=1`, doğru
  `ATTUNE_TRUSTED_ORIGINS`, mevcut `gpt-transcribe` modeli. Model erişimi ve gerçek
  TR/EN/DE transkripsiyon testi yapılmadı; uygulamadaki açık kullanıcı rızası korunur.
- TTS: yerel Chatterbox V3, `ATTUNE_MENTAL_TTS_CONFIG`, gerekiyorsa
  `ATTUNE_MENTAL_TTS_FEMALE_CONFIG` ve ayrı runtime için `ATTUNE_MENTAL_TTS_PYTHON`.
  `ATTUNE_MENTAL_TTS_TOKEN` en az 32 karakter; her frontend/backend çifti aynı
  token'ı, WEB ve AAOS farklı token'ları kullanmalı. Backend URL/origin eşleşmeleri
  [OPERATIONS.md](OPERATIONS.md) içinde. TTS model/config/source hash kontrolleri
  korunur; ücretli harici TTS sağlayıcısına geçilmedi.

EC2 secret varlığı stopped host üzerinde incelenmedi. Önceki kullanıcı talimatı:
onaylı boot sonrası `/etc/attune/api-{web,aaos}.env` ve servis yapılandırmalarında
varlık kontrolü; değerler yazdırılmayacak. Anahtar yoksa güvenli injection yolu
belirlenecek. Cloud proxy placeholder'ı EC2'ye gerçek secret olarak kopyalanmamalı.
TLS/mTLS, public IP, SSM, KVM, AAOS15, fiziksel kamera/ses ve beş modül kabulü bekliyor.
Demo domainlerine Cloud izni verilmesi DNS/TLS veya SG erişiminin hazır olduğunu
kanıtlamaz; DNS değişikliği yetkilendirilmedi.

## Yeni ortamda devam

1. PR #22'nin son commit'ini fetch et; runtime policy ve gerçek transfer erişimini doğrula.
2. Eksik ONNX kaynaklarını manifestteki isimlerle `.aws-oem/recovery` altına indir.
   Her parça hash'ini ve boyutunu doğrula. `restore_onnx.py`, manifest sırasından
   bağımsız olarak 000 → 001 → 002 → 003 birleştirir, birleşik hash'i doğrulamadan
   hedef model yayımlamaz ve farklı mevcut modelin üzerine yazmayı reddeder:

   ```bash
   python scripts/aws/restore_onnx.py --parts .aws-oem/recovery \
     --output-root .aws-oem/bundle/models \
     --manifest docs/aws/evidence/model-recovery-sources.json \
     --receipt .aws-oem/bundle/onnx-verification.json
   ```

3. Regional/TTS paketlerini kaynaklarından restore et, APK'yı digest ile doğrula;
   tam model/bundle manifesti ve production WEB build paketini tamamla.
4. Hazırlık tamamlandıktan sonra iki mevcut EC2 için tek nihai ücretli başlatma
   onayı iste. Onay henüz verilmedi. Start sonrası endpoint/secret ve gerçek
   WEB + AAOS15 kabulüne geç. Yeni PR/EC2, DNS değişikliği veya main merge yapma.

## Ayrı ilk runtime'dan tamamlanan staging kanıtı

[Chatterbox staging](evidence/chatterbox-model-staging.json): 98 parça, birleşik
3,283,572,066-byte ZIP, 117 pinli üye ve dört referans/config dosyası tamamen
byte/SHA-256 doğrulandı. Bu çalışma, yukarıdaki yeni runtime kaydıyla eşzamanlı
olarak ilk Cloud runtime'da tamamlandı; yeni runtime'da binary bulunduğunu iddia etmez.
İlk runtime staging yolu `/workspace/attune-staging/mental-runtime`, regional yolu
`/workspace/attune-staging/regional-skin`. Git'e model byte'ları veya imzalı URL
konmadı. Runtime'lar arasında bu yolların paylaşıldığı varsayılmamalı.

İlk runtime'ın güncel network snapshot'ında hiçbir `oaiusercontent.com` hostname'i
yok; ONNX binary transferi burada proxy 403 ve 32 MiB materialization sınırında
kaldı. Yeni runtime'ın yukarıdaki parça 002 kanıtı korunur. İki ONNX'in kaynakları
bulunmuş durumda; full restore/combined hash henüz tamamlanmadı. AWS kontrolleri,
SG uygulaması veya fiyatlar bu son staging adımında tekrar çalıştırılmadı.
