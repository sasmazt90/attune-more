# İşletim ve ücret sınırı

> 3 Kasım final hazırlık güncellemesi: [doğrulanmış model/runtime paketleri ve onay sınırı](PREPARATION-20261103-FINAL.md). Önceki transfer engelleri giderildi; canlı kabul ve ücretli start onayı bekliyor. Aşağıdaki önceki runtime kayıtları tarihsel kanıttır.

> Güncel durum (2026-11-03 R2): önceki IAM okuma/Pricing engelleri kalktı.
> [R2 preflight](PREFLIGHT-20261103-R2.md) ve [sayısal başlangıç paketi](START-PLAN.md)
> önceki erişim/maliyet durumlarını günceller. Üç SG kuralı uygulandı/doğrulandı; model aktarımı ve canlı kabul bekliyor.


Güncel canlı preflight (2026-11-03): [PREFLIGHT-20261103.md](PREFLIGHT-20261103.md).
Kimlik ve EC2 erişimi artık doğrulandı; kalan IAM okuma ve Pricing ağ engelleri
giderilmeden ücretli başlangıç paketi tamamlanamaz.

## Mevcut kaynak incelemesi — oluşturma yok

1. `python scripts/aws/inventory.py --identity-alias <gerçek-alias> --output .aws-oem/existing.json`
2. `python scripts/aws/preflight.py --identity-alias <gerçek-alias> --output .aws-oem/account.json`
3. Hesap/instance Name/type eşleşmesi; mevcut AMI/OS, subnet/VPC/private IP, route/NACL,
   SG ingress/egress, ortak SG kullanımı, profile/role/policy, SSM ve volume özellikleri
   incelenir. İki hedef yalnız `i-0b25450afc6633494` ve `i-0f4cca4e92e94c351`.
   Hiçbir bilgi eksikse tahmini kimlik yazılmaz. Duran SSM ajanının offline olması normaldir.
4. 150 + 120 GiB gp3 doğrulanır; encryption/IOPS/throughput ve ek diskler kaydedilir.
   Şifrelenmemiş disk yerinde şifrelenemez; bu durumda kopya volume/snapshot oluşturmadan
   BLOCKED raporlanır. Mevcut shared SG/IAM policy değiştirmeden etki analizi yapılır.
5. Model manifestindeki path/byte/SHA-256 ile `verify_assets.py`; ardından
   `scripts/aws/build_bundle.sh`. Ağırlık ikamesi, yeni CUDA yolu, eşik/thread değişikliği yok.
   `install_host.sh` öncesi bundle, Node22.20.0, Python3.11, Caddy2.10.2 sağlanır.
6. Eksik SG kuralları için `cfn-lint infra/aws/stack.json`. Şablon yalnız mevcut SG'lere
   opt-in ingress ekler. Zaten var olan kural için parametre `no` kalır. 443 source CIDR
   ve 8443 için yalnız gerçek AAOS SG seçilir; SG'ler başka workload ile paylaşılıyorsa
   kural eklenmez. CloudFormation eski provisioning stack'ine UPDATE/IMPORT yapılmaz.
   Yeni altyapı, replacement, EIP allocation, disk resize veya resource deletion yok.
   Gerekirse ayrı rules stack'in DescribeChangeSet ve DescribeStacks JSON'u alınır:
   `python scripts/aws/check_changeset.py changeset.json stack.json`.
   Araç yalnız denetler; hiçbir change set yürütmez. Parametreler canlı inventory ile ayrıca karşılaştırılır.
7. IMDSv2 veya mevcut rol/policy eksiği canlı değerlerle düzeltme planına yazılır.
   Yetki bağlandıktan sonra yalnız bu task kapsamındaki mevcut kaynakta gerekli
   yerinde değişiklik yapılır; shared kaynak, SCP veya eksik yetki BLOCKED bırakılır.
   Hazır bir stack olması, mevcut kaynakların bu stack'e import edilmesi anlamına gelmez.

## Başlatmadan önce tek maliyet ve test paketi

[START-PLAN.md](START-PLAN.md) doldurulur. Şu an fiyatlar, IAM/ağ, var olan public IP
sayısı, bütçe ve disk özellikleri API'den okunamadı; sayısal toplam **BLOCKED**.
Kullanıcının mevcut EBS ve varsa EIP kaynakları stopped durumda da ücret doğurabilir.
Bu task kaynak oluşturmadı; AWS hesabının toplam harcaması sıfır olarak gösterilmez.

Model/servis hazırlıkları bitince önerilen ilk test penceresi **en çok 2 saat**.
İki EC2'nin tarihli Linux On-Demand fiyatı, gerçek gp3 toplamı (bildirilen 270 GiB),
IP/EIP adedi, IOPS/throughput, egress/provider tüketimi ve vergi ayrı gösterilir.
Mevcut EIP varsayılmaz. 25 oturum/ay için compute `25 × h × (G + M)`, kalıcı disk
`270 × E`, retained IPv4 `adet × 730 × I`; geçici public IPv4 yalnız aktif saatlerde.
`cost.py` fiyatları ve aktif/retained IP sayılarını zorunlu argüman olarak alır:

```bash
python scripts/aws/cost.py --g6 <dated-rate> --m8i <dated-rate> --ebs-gb-month <dated-rate> --ipv4-hour <dated-rate> --retained-ipv4-count <observed-count> --active-ipv4-count <observed-count> --storage-gb 270 --hours 2
```

## Başlatma onayı sonrası kurulum sırası

1. Taze inventory ve kullanıcı onayıyla yalnız iki mevcut stopped instance başlatılır.
   Yeni EC2/VPC oluşturulmaz. AMI/OS desteklenmiyorsa replacement yapmak yerine BLOCKED.
2. SSM ile **bu task instance'larında** OS/runtime ve hash'i doğrulanmış kaynak
   bundle'ını `/opt/attune` altına kur. Node22.20.0/npm10.9.3, ayrı Python3.11
   runtime ve Caddy2.10.2 gerekir; Ubuntu24.04'ün Python3.12'siyle sessiz değişim yok.
   `infra/aws/install_host.sh web|aaos` servis başlatmaz.
3. Caddy TLS dosyalarını ve private mTLS CA/client/server sertifikalarını sağla.
   Internal server cert SAN `attune-internal`, client cert clientAuth kullanımına
   sahip olmalı. `caddy validate` gerçek sertifikalarla çalışmadan ingress açma.
   Private key'ler root/caddy dışına okunmaz; Git/Drive'a yüklenmez.
4. G6'daki örnek env düzeni (gerçek secrets yalnız root-owned 0600 dosyalarda):

   - `api-web.env`: `PORT=8000`, `ATTUNE_TRUSTED_ORIGINS=https://attune.sasmaz.digital`
   - `api-aaos.env`: `PORT=8001`, `ATTUNE_TRUSTED_ORIGINS=http://127.0.0.1:3000`
   - `web-web.env`: `PORT=3000`, `ATTUNE_MENTAL_TTS_FRONTEND_ORIGIN=https://attune.sasmaz.digital`, `ATTUNE_MENTAL_TTS_BACKEND_URL=http://127.0.0.1:8000`
   - `web-aaos.env`: `PORT=3001`, `ATTUNE_MENTAL_TTS_FRONTEND_ORIGIN=http://127.0.0.1:3000`, `ATTUNE_MENTAL_TTS_BACKEND_URL=http://127.0.0.1:8001`
   - `capture.env`: `ATTUNE_CAPTURE_SENDER_ORIGIN=https://aaos.sasmaz.digital`
   - Caddy environment: domainlar, internal private IP, toplantıya özel kullanıcı ve Caddy hash'i.

   İki API'nin native worker geçici dizin/lease yolları da toplantı kabulünden önce
   gözlenmeli; ortak model asset'leri read-only paylaşılır. OMP/MKL/thread/model
   eşikleri değiştirilmez. TTS token gerekiyorsa ilgili frontend/backend çiftinde
   aynı secret, WEB/AAOS arasında farklı secret kullanılır. Gerçek Mental provider
   anahtarı/işleme onayı olmadan mock başarı iddiası yapılmaz.
5. M8i: KVM erişimi, SDK/AAOS image ve `prepare.sh`. `aaos.env` içinde ANDROID_HOME,
   ATTUNE_APK, ATTUNE_AVD ve ATTUNE_AAOS_EVIDENCE. Servis `attune` kullanıcısı ve
   kvm grubunda çalışır. KVM yoksa emülasyona düşülmez; BLOCKED.
6. Opsiyonel ses: `loginctl enable-linger attune` ve attune kullanıcı servisi olarak
   PulseAudio socket kurulumu; `aaos.env` içinde `ATTUNE_AUDIO_ENABLED=1`,
   `XDG_RUNTIME_DIR=/run/user/<attune-uid>`, `ATTUNE_AUDIO_ORIGIN=https://aaos.sasmaz.digital`.
   `attune-audio` servisi `/audio` sayfasına WSS PCM sağlar. Browser mic izni ayrı
   seçilir; provider consent uygulamada kalır. Guest mixer/input ve kalibrasyon
   doğrulanmadan Hearing/Mental PASS verilmez. noVNC sayfasını açık tutup `/audio`
   sayfasında bağlanın; toplantı sonunda bu sayfada disconnect yapın.
7. Dosyalar ve servisler doğrulandıktan sonra `systemctl enable` ile sonraki boot
   için API/frontend/capture/AAOS ve Caddy birimlerini etkinleştir. İlk `start`
   işlemi onaylı test süresi içindedir. Sistem servisleri ağır modeli otomatik
   indirmez; asset doğrulaması ve mevcut Skin prepare akışı kullanılır.

## Toplantı başlat/durdur

`democtl.py` yalnız kullanıcı tarafından verilen iki sabit ID ve bunların Name/type eşleşmesini kabul eder.
Elle oluşturulan instance'larda henüz olmayan Task etiketlerine güvenmez.
Start için mevcut kullanıcı onayını temsil eden özel JSON makbuz gerekir:
`account`, `region`, `instanceIds`, `paidStartApproved`, `expiresAt` (timezone ile),
`maximumSessionHours`, `approvalReference`, `estimatedSessionUsd`, `testScope`,
`configurationReviewed`, `inventorySha256` (canlı inventory dosyasının SHA-256 değeri).
Task 13 kapsam genişletmesinde kullanıcı sabit süre sınırını kaldırdı. Bu onay
`executionPolicy: until_completion_or_unrecoverable_blocker`,
`noFixedDurationLimit: true`, `monitorCosts: true`, `maximumSessionHours: null`
ile temsil edilir; eski 2 saat/6 USD hesabı bir bütçe referansıdır. Otomatik kesme
yoktur. İş bitince veya ilerlemeyi engelleyen kalıcı engelde normal Stop uygulanır.

Start için en fazla 30 dakika önce alınmış tam OBSERVED inventory gerekir; bu
kayıttaki ağ/IAM bulguları ayrıca incelenmelidir. API okuması başlı başına hazır olma kanıtı değildir. Bu belgeyi üretmek kullanıcı onayı yerine
geçmez; onay olmadan `true` yazılmaz. Makbuzlar `.aws-oem` içinde kalır.

```bash
python scripts/aws/democtl.py status --receipt .aws-oem/status.json
python scripts/aws/democtl.py start --inventory .aws-oem/existing.json --approval .aws-oem/approval.json --receipt .aws-oem/start.json
python scripts/aws/smoke.py --web https://attune.sasmaz.digital --aaos https://aaos.sasmaz.digital --output .aws-oem/smoke.json
# Toplantı bittikten sonra, aktif işlerin bittiği doğrulanarak:
python scripts/aws/democtl.py stop --receipt .aws-oem/stop.json
```

`smoke.py` parolayı ATTUNE_DEMO_USER/PASSWORD ortamından alır; argümanda veya logda
çıkarmaz. Beş modül HTTP erişimi ve kimliksiz erişim reddini ölçer. AI, native
PARK/DRIVE, sonuç/geçmiş ve ses testi yerine geçmez. Durdurma compute'u keser;
iptal/late-result ve kayıt temizliği uygulamada tamamlanmalıdır. Hiçbir timer
sunumu otomatik sonlandırmaz. Operatör bütçe süresini takip eder.

## DNS — ayrı onay sınırı

Hedefler uygun alt alan adlarıdır fakat IONOS yetkili zone envanteri okunmadı;
mevcut kayıt durumu BLOCKED. Ana siteye dokunulmaz. Endpoint'ler önce doğrulanır.
Hazır olduğunda incelenecek taslak yalnız `attune` A → mevcut doğrulanmış Web adresi ve `aaos` A → mevcut doğrulanmış AAOS adresi,
TTL önerisi 300; mevcut kayıt varsa üzerine yazmadan bildirilir. TLS için gerekiyorsa
DNS-01 TXT veya CAA değişikliği tam değerleriyle ayrıca gösterilir. Mevcut adres/sertifika
doğrulanmadan bir DNS değeri veya canlı URL üretilmiş gibi raporlanmaz.
