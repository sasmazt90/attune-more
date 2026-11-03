# Task 13 — ücretli başlatma öncesi tamamlanan hazırlık

3 Kasım 2026. PR #22, `7ed4c52` devralındı. Bu kayıt önceki runtime'ın
model transferi/ağ engellerini günceller. **Ücretli start henüz onaylanmadı ve
bu çalışmada hiçbir EC2 başlatılmadı. Canlı kabul yapılmadı.**

## Dosya ve runtime doğrulaması

- Cloud policy `unrestricted/enforced`; gerçek GitHub ve bölgesel dosya indirmeleri başarılı.
  Proxy/TLS korunarak çalışıldı; environment değişikliği gerekmedi.
- Step0: 39,122,518 byte, SHA-256
  `9c87475d9302aed16f09abedc109211c2ac1b49f22f465f86aab408a5244d0be`.
- Skin Type 000–003 parçaları ayrı doğrulandı. `restore_onnx.py` ile birleşik
  343,341,982-byte model üretildi; SHA-256
  `99b4c2fa1e9ac013d539f635eb948c5a29f4c5f86f34fe26c380ad308c26c65a`.
- Regional Skin: 24 parça, 748,390,400-byte TAR ve 31 üye doğrulandı;
  arşiv SHA-256 `e0bbaa2a8ab685cdf542ce1eefe85681635e5fba51918bb40bbd33b45a370f04`.
- Chatterbox V3: 98 parça, 3,283,572,066-byte ZIP ve 117 pinli üye doğrulandı;
  arşiv SHA-256 `5e98c442627ad78ce22a9bff151b0badd2343f1392b590b42889a0beb679f3fc`.
  Dört config/referans dosyası orijinal byte/hash ile geri yüklendi.
- APK: run `41634882348`, artifact `13229474049`, 66,182 byte;
  SHA-256 `646f504b32b60ef9c670eef66e59a8923ddeb5ff9681c9e066ba6f78e54aa8b6`.
  ZIP digest de önceki kanıtla eşleşti. APK kaynakları değiştirilmedi.
- Node 22.20.0/npm 10.9.3 ile temiz `npm ci` ve WEB production build tamamlandı.
  Same-origin API, remote capture ve mevcut Acne V5 build bayrakları korundu.
- Ana backend ve TTS için ayrı wheel paketleri hazır. Ana backend offline
  kuruldu ve `pip check` geçti. Chatterbox offline kuruldu; pinli kaynak, bağımlılık
  sürümleri ve TR/EN/DE config preflight sonucu PASS. Bu inference/ses kabulü değildir.
- Chatterbox kurulumunda venv PATH düzeltildi; uygulamanın süreç iptal yardımcısı
  için backend ile aynı `psutil==7.2.2` hash pinli destek bağımlılığı eklendi.
  Model, generation, CPU yolu ve diğer mevcut sürüm pinleri değiştirilmedi.
- Caddy 2.10.2 resmi SHA-512 listesiyle; Node resmi SHA-256 listesiyle doğrulandı.
  CPython 3.11.17 mevcut yönetilen runtime'dan paketlendi; yerel arşiv SHA-256 kaydı var.
- Resmi AAOS API35/ext15 r04 x86_64 image, stable emulator 37.2.13, platform tools,
  command-line tools, API35 platform ve build tools 35.0.0 indirildi: toplam
  2,068,511,501 byte. Google katalog boyut/checksum kontrolü ve yerel SHA-256 kayıtları var.
- Özel demo CA ile TLS/mTLS hazırlama aracı, Caddy systemd birimi, offline runtime
  bootstrap ve secret değerlerini yazdırmayan host denetimi eklendi. WEB/AAOS Caddy
  yapılandırmaları test sertifikalarıyla `caddy validate` geçti. Gerçek IP sertifikaları
  onaylı boot sonrası üretilecek; test sertifikaları canlıya taşınmayacak.

Kanıtlar: [model dosyaları](evidence/model-verification-final.json),
[ONNX](evidence/onnx-verification-final.json), [122 parça](evidence/part-transfers-final.json),
[TTS preflight](evidence/tts-runtime-preflight-final.json),
[Android arşivleri](evidence/android-archives-final.json),
[wheel manifesti](evidence/wheel-manifest-final.json),
[runtime manifesti](evidence/runtime-manifest-final.json).

Yerel doğrulama: 28 AWS hazırlık testi ve WEB routing/locale kontrolleri geçti.
Shell/Python syntax ve whitespace kontrolleri geçti. Bu testler canlı AWS
entegrasyonunu, fiziksel girişleri veya gerçek provider çağrılarını kanıtlamaz.

## Paketler ve onay sonrası uygulama

Yerel kök `/workspace/attune-more/.aws-oem`. Model overlay `bundle/models`,
Chatterbox `mental-runtime`, wheel paketleri `wheels/backend` ve `wheels/tts`,
resmi runtime/SDK arşivleri `runtime` altında. APK `bundle/app-cloudDemo.apk`.
`package_deployment.py`, commit edilmiş kaynak + production WEB build + Node
bağımlılıklarını paketler; secret, model indirme URL'si ve runtime cache dahil etmez.
Büyük dosyalar Git'e konmaz. Aynı runtime korunmalı; başka runtime'a taşınırsa
kanıt dosyaları binary varlığı yerine geçmez.

1. Tek ücretli onayı kaydet; mevcut start aracının gerektirdiği taze inventory ile
   yalnız iki hedefi başlat. Önceki SG/Pricing kontrollerini yeniden oluşturma.
2. SSM online ve gerçek host kimliğini doğrula. Önce mevcut `/etc/attune` config ve
   servisleri `audit_host_config.py` ile değerleri göstermeden denetle.
3. Hash'i doğrulanmış application arşivini `/opt/attune`, model overlay'i aynı köke,
   bağımlılıkları `/opt/attune-staging` altına aktar. Chatterbox ZIP'ini mevcut
   `extract_verified` yordamıyla `/opt/attune-staging/mental-runtime/bundle` altına aç.
   Config/referans byte'larını koru. Transfer referansları özel ve kısa ömürlü kalır.
4. Mevcut uyumlu runtimeları kullan; eksikse `bootstrap_runtime.sh` ile doğrulanmış
   Node/Python/Caddy'yi kur. Var olan runtime'ın üzerine yazmayı reddeder.
5. `install_host.sh` için `ATTUNE_PYTHON311`, `ATTUNE_STAGING_ROOT`,
   `ATTUNE_WHEELHOUSE`, `ATTUNE_WHEEL_MANIFEST`, `ATTUNE_ASSET_MANIFEST` ayarla.
   Bu betik servis başlatmaz. WEB üzerinde `install_neural.py --service-group attune`
   ile ayrı TTS venv kur. Staging üst dizinine attune grubunun traverse erişimini sağla;
   arşivlerden kalan owner-only izinler servisi engellememeli. Kod/modeller root-owned
   ve servis grubuna read-only kalır; yalnız Next cache ve uygulama veri dizinleri yazılabilir.
6. SDK lisanslarını incele; mevcut `prepare.sh` akışıyla resmi API35 AAOS image'i
   ve AVD'yi kur. `/dev/kvm` yoksa yazılımsal emülasyona geçme. Guest 3072 MiB kalır.
7. Gerçek public IP'lerle iki günlük demo sertifikalarını üret. Yalnız gerekli
   leaf key/cert'leri hostlara taşı; CA private key'i hostlara dağıtma. WEB'e
   `clients-ca.crt`, AAOS'a `server-ca.crt` olarak public CA ver. Root/caddy dosya
   izinleri korunur. Caddy env ve `/etc/attune/Caddyfile` kurulur, validate sonrası
   `attune-caddy` ve uygulama servisleri başlatılır.
8. DNS değişmez. Gerçek kullanıcı tarayıcısında hostname eşlemesi ve özel CA güveni
   gerekebilir; TLS uyarısını atlamak güvenli kamera/mikrofon bağlamı sayılmaz.
   Mevcut 443 kaynak `/32` kuralı korunur; Cloud testleri için SG genişletilmez.

## Provider gereksinimleri ve canlı kabul

Mental OpenAI ve gerçek cloud ASR aynı `OPENAI_API_KEY`/isteğe bağlı
`OPENAI_BASE_URL` yapılandırmasını kullanır. Mental mevcut `OPENAI_MODEL`
(varsayılan `gpt-4o-mini`), ASR mevcut `gpt-transcribe` yolunu korur.
ASR için `ATTUNE_CLOUD_ASR_ENABLED=1`, doğru trusted origin ve uygulama içi
kullanıcı rızası gerekir. Model erişimi/provider authentication boot sonrası ölçülür.

Chatterbox ücretli harici TTS API'si değildir. Ayrı Python, doğrulanmış yerel model,
config, watermark/segmenter cache ve her frontend/backend çifti için aynı ≥32
karakter token gerekir; WEB/AAOS token'ları birbirinden farklı olmalıdır.
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `PKUSEG_HOME` hostta ayarlanır.
Eksik secret varsa host denetiminden sonra tek listede güvenli root-owned 0600
env/secret injection yolu bildirilecek; anahtar sohbete, Git'e veya SSM komut
metnine yazılmayacak. Cloud proxy placeholder'ı host secret'ı olarak kullanılmaz.

Canlı matriste hâlâ PASS yok: beş modül, TR/EN/DE, fiziksel kamera/mikrofon/ses,
sonuç/geçmiş/oturum, native PARK/DRIVE ve özellikle ATT-T03-05 (Skin WEB + AAOS
Hearing eşzamanlılığı), Vision WEB DE gerçek ASR, AAOS Vision 3 GiB ve Mental
partial-session persistence onaylı pencereye aittir. Gerçek girişli kabul için
kullanıcının tarayıcı/kamera/mikrofon katılımı gerekir; fixture kayıtlar bunu karşılamaz.

## Tek maliyet/onay sınırı

AWS alias `AWS` ile bu runtime'da iki hedefin stopped durumu API'den doğrulandı.
3 Kasım 12:44 UTC Pricing kanıtı aynı gün, aynı instance tipleri ve mevcut 270 GiB
gp3 için geçerli planlama girdisi olarak yeniden kullanıldı. Yeni kaynak veya
kalıcı ücret kalemi eklenmedi; indirmeler EC2 inbound olduğundan egress varsayımını
artırmaz. [START-PLAN](START-PLAN.md): temel 2 saat 3.55070 USD; 10 GB çıkışla
4.45070 USD; öneri vergi hariç 6 USD (5 AWS + 1 provider), hard cap değildir.
Mevcut EBS stopped iken 25.704 USD/ay devam eder. 115. dakikada durdurma başlar,
en geç 120. dakikada normal Stop istenir ve iki ID için API stopped kanıtı alınır.
Kapasite/SSM/KVM/secret/TLS veya kabul engelinde kalan süre boşuna tüketilmez;
süre/bütçe sessizce uzatılmaz. Yeni EC2/VPC/EBS, DNS değişikliği, yeni PR veya main
merge yok. Bu belge başlatma onayı değildir.
