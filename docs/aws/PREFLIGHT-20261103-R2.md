# Task 13 — izin güncellemesi sonrası gerçek AWS kontrolü

Son runtime ve taşınma kaydı: [CONTINUATION-20261103.md](CONTINUATION-20261103.md).

3 Kasım 2026, PR #22; başlangıç HEAD `7a26c134db7f8ca4a5c02357023865250f1bddd9`.
[Makinece okunur kanıt](evidence/live-preflight-20261103-r2.json),
[Pricing API ürün/term kanıtı](evidence/pricing-20261103.json),
[tek maliyet ve başlatma paketi](START-PLAN.md).

**Önceki IAM/Pricing engelleri kalktı. Kullanıcının eklediği AttuneExistingSecurityGroups
policy'sinden sonra üç ingress kuralı uygulandı ve AWS API üzerinden doğrulandı.
Kalan aktarım engeli Cloud HTTPS model indirme hostname iznidir; paid start yapılmadı.**

## Yeniden çalıştırılan kontroller

- Cloud network policy `enforced`, AWS outbound identity `ready`; manifest v1 alias
  `AWS`. Gerçek STS hesabı `798886013428`, assumed role `attune-codex-deployer`.
- EC2, tip/AZ offering, AMI, volume, SG/ENI, VPC/subnet, routes, NACL, IGW, NAT,
  VPC Endpoint, VPC DNS, instance profile, rol/trust ve managed/inline policy
  okumaları başarılı. Envanterde BLOCKED okuma yok.
- İki hedef stopped, `eu-central-1c` içinde. G6/M8i 8'er vCPU; G/VT kota 8,
  Standard kota 16, running/pending/stopping bölgesel kullanım boş. Kota/AZ offering
  anlık fiziksel EC2 kapasite garantisi değildir.
- Diskler 150 + 120 GiB gp3, encrypted, 3000 IOPS / 125 MiB/s; IMDSv2 required.
  M8i nested virtualization enabled. Ubuntu 24.04 amd64 AMI; guest KVM/agent testi
  stopped host üzerinde yapılmış sayılmadı.
- Aynı subnet/VPC, aktif internet gateway route, IPv4 allow NACL, DNS support ve
  hostnames true, IPv4 egress açık. NAT ve VPC Endpoint yok. İki SG başka ENI/workload
  ile paylaşılmıyor. Retained EIP yok; subnet boot sırasında public IPv4 atıyor.
- İki profile aynı `attune-ec2-ssm-role` rolünü taşıyor; EC2 trust doğru,
  `AmazonSSMManagedInstanceCore` bağlı, permissions boundary görülmedi.
- SSM managed instance listesi boş: stopped durumda agent online kanıtı yok.
  AWS-RunShellScript GetDocument, ListCommands ve ListCommandInvocations başarılı.
- Her iki ID için StartInstances/StopInstances dry-run `DryRunOperation` döndü.
  Mevcut inline policy SendCommand'ı yalnız iki EC2 ARN'i ve AWS-RunShellScript
  document ARN'i için Allow ediyor. Bu policy incelemesidir; boot sonrası gerçek
  SendCommand ve GetCommandInvocation testi yapılacak. SSM kurulum için SSH açmak,
  yeni instance profile veya PassRole yetkisi eklemek gerekmiyor.
- Pricing API'den G6/M8i/gp3/public IPv4/internet transfer fiyatları alındı.
  Budgets sorgusu başarılı fakat bütçe listesi boş; harcama hard cap'i yok.

## Tamamlanan IAM ve SG değişikliği

Kullanıcının bu sohbette verdiği kaynak: **91.14.212.184/32**.

| Hedef SG | TCP | Kaynak | Sonuç |
|---|---:|---|---|
| sg-023659b3a447ab759 (WEB) | 443 | 91.14.212.184/32 | APPLIED / API VERIFIED |
| sg-0476f580c44063a5d (AAOS) | 443 | 91.14.212.184/32 | APPLIED / API VERIFIED |
| sg-023659b3a447ab759 (WEB) | 8443 | sg-0476f580c44063a5d | APPLIED / API VERIFIED |

`scripts/aws/configure_ingress.py --identity-alias AWS --apply` önce eksik izinle
reddedildi. Kullanıcı policy'yi `AttuneExistingSecurityGroups` adıyla ekledikten sonra
aynı komut çalıştırıldı: altı dry-run başarılı, üç gerçek Authorize çağrısı başarılı,
son DescribeSecurityGroups kontrolü `verified: true`.

- WEB 443: `sgr-0898077334d3fcce9`
- AAOS 443: `sgr-01759f18cac427137`
- WEB 8443: `sgr-0490493a19b21de10`

Önceden var olan IPv6 SSH veya egress kuralları değiştirilmedi. Yeni SG oluşturulmadı.

Kullanıcının eklediği tam policy: [existing-security-groups.json](../../infra/aws/iam/existing-security-groups.json).
`attune-codex-deployer` rolüne ek inline policy olarak bağlandı; mevcut iki policy korundu.
Yalnız `ec2:AuthorizeSecurityGroupIngress` ve `ec2:RevokeSecurityGroupIngress`, iki
mevcut SG ARN'i ve Frankfurt ile sınırlıdır. Revoke yalnız bu görevde eklenen kuralın
geri alınması için gereklidir. IAM'ın bu aksiyonlardaki kaynak sınırı SG'dir; port ve
kaynak doğrulaması araçtaki sabit üç kural ve canlı envanter kontrolüyle yapılır.
Deployer'ın managed policy listesi boş, inline policy'lerinde IAM policy yazma Allow'u
yok; kendi yetkisini yükseltmeye çalışılmadı. AdministratorAccess, yeni AWS anahtarı,
CloudFormation write veya yeni kaynak oluşturma izni istenmiyor.

Araç tekrar çalıştırılabilir; bütün gerekli dry-run'lar geçmeden
tek bir kural eklemez. Uygulama sonrasında DescribeSecurityGroups ile üç kuralın
exact port/kaynak eşleşmesi kontrol edilir. Değişen hesap/ID/tip/Name/SG attachment
veya paylaşılan SG görülürse araç durur. Kısmi hata olursa yalnız kendi oluşturduğu
rule ID'lerini receipt'te korur; önceden var olan kuralları silmez.

## Kurulum varlıkları ve kalan teknik koşullar

- Başlangıç HEAD için genel CI, Automotive ve AWS preparation başarılı.
  [AWS run 41634882348](https://github.com/sasmazt90/attune-more/actions/runs/41634882348).
  `attune-cloud-demo-apk` artifact 13229474049 indirildi. ZIP SHA-256
  `417b99d519f11fd6ca330e504205d5dd1c3b8958e39e882de97aa0320dc1f79d` eşleşti.
  APK 66,182 byte, SHA-256 `646f504b32b60ef9c670eef66e59a8923ddeb5ff9681c9e066ba6f78e54aa8b6`.
- Dental ve Dryness encoder dosyaları mevcut, güncel Git manifest hash'leri eşleşti.
  Bu bir inference veya tam model bundle doğrulaması değildir.
- Kullanıcı exact iki Skin export'unun 27 Ekim Windows yedeğini sağladı.
  [Drive ID / parça hash / birleşik hash listesi](evidence/model-recovery-sources.json).
  Eski recovery kaydının "iki export eksik" bulgusu artık geçerli değildir.
  Kontrol ZIP'i indirildi; dört model parçasının ve Step0'nun beklenen byte/hash
  değerleri çıkarıldı. Step0 39,122,518 byte, birleşik Skin Type 343,341,982 byte.
  Drive binary fetch Step0'yu sağladı; executor'a materialize aracı 32 MiB üzerinde
  hata verdi. Normal HTTPS indirme denemesi Cloud proxy CONNECT 403 aldı.
  Büyük dosyalar için gereken görülen Cloud hostname'leri
  `sdmntprnortheu.oaiusercontent.com` ve `sdmntprpolandcentral.oaiusercontent.com`.
  Bu ağ izinlerini değiştiren araç oturumda bulunmuyor. Policy/proxy atlanmadı;
  model yokluğu değil **transfer erişimi** bekleniyor. Parçalar birleştirilmeden
  önce her biri, sonra birleşik dosya mevcut Git manifestiyle doğrulanacak.
- Aynı kayıt regional Skin bundle için
  [24 parçalı kaynağı](https://drive.google.com/drive/folders/11gEVDp-Vo2gQTnMSzVOxW_wA7B_a5u2L)
  gösteriyor; 748,390,400 byte, SHA-256 `e0bbaa2a8ab685cdf542ce1eefe85681635e5fba51918bb40bbd33b45a370f04`.
  24 parça, birleşik arşiv ve 31 üyenin hash'leri doğrulandı;
  [staging kanıtı](evidence/regional-model-staging.json).
- [Mental recovery kaydı](https://drive.google.com/file/d/1OnjGDR8rWu-sQhud6tcDws3-NAG3NovG/view)
  Chatterbox ZIP ID `1rc2zoLLhozG_SD9S7GI-3YwciqpyeNHx`, 3,283,572,066 byte,
  SHA-256 `5e98c442627ad78ce22a9bff151b0badd2343f1392b590b42889a0beb679f3fc`
  ve 98 parçalı alternatifini tanımlıyor. Tek ZIP binary fetch 256 MiB connector sınırında 413 döndü;
  desteklenen 98 ayrı 32 MiB parça yoluyla staging tamamlandı.
  98 parça, birleşik ZIP, 117 pinli üye ve dört referans/config dosyasının byte/hash
  kontrolleri geçti: [Chatterbox staging kanıtı](evidence/chatterbox-model-staging.json).
  Python ortamı/inference henüz çalıştırılmadı.
- Cloud environment'da secret binding yok. Kullanıcı EC2 üzerindeki mevcut
  OpenAI anahtar konumunu bilmiyor ve onaylı boot sonrası secret/env varlığı kontrolünü
  istedi. Varsa kullanılır; yoksa kesin güvenli injection yolu bildirilir. Anahtar
  değeri log/rapor/sohbete yazılmaz. Model/provider olmadan mock PASS yok.
- TLS/mTLS kurulumu, gerçek public IP, Caddy/Node/Python, SSM agent, `/dev/kvm`, API35
  image, guest memory 3 GiB, kamera/mikrofon/ses ve PARK/DRIVE ancak onaylı boot sonrası
  doğrulanabilir. DNS değişmeyecek; TLS trust/erişim yolu kabul testinin önkoşuludur.

## Sınır ve devam

AWS üzerinde yalnız üç onaylı ingress eklendi; iki EC2 başlatılmadı. Model aktarımı/hazırlığı
tamamlanmadan ücretli başlatma sorusu sorulmadı; sayısal tek paket hazırlandı.
İzin verme ve model erişim konumu dışında kullanıcıya AWS kurulum işi devredilmedi.
Onaylı testte beş modül WEB + AAOS15, TR/EN/DE, gerçek model/provider, sonuç/geçmiş,
Skin WEB + AAOS Hearing concurrency, Vision DE gerçek ASR, AAOS Vision 3 GiB,
Mental partial persistence ve native gates ölçülecek. İki saat her kabulün kesin
tamamlanma garantisi değildir; bitmeyen test PARTIAL kalır. Test sonunda iki hedef
StopInstances ile durdurulur ve DescribeInstances ile `stopped` doğrulanır.

Yerel doğrulama: ingress kaynak/attachment/paylaşılan ENI/red durumunda sıfır write
kontrolleri ve mevcut EC2 korumaları **9 test geçti**. JSON parse ve diff whitespace
kontrolü başarılı. Bunlar gerçek AWS/AAOS kabul testleri değildir.

Ek kurulum hazırlığı: Node 22.20.0 ile same-origin/remote-capture/Acne-v5 build flag'leri
korunarak WEB production build başarılı. AAOS launcher'ın sabit 8192 MiB ayarı,
Task 13 Vision kabulü için varsayılan 3072 MiB ve açık 8192 MiB tanılama seçeneğine
çevrildi. İstenen bellek ve guest `/proc/meminfo` kanıt dosyalarına kaydedilir;
3 GiB testinin yerine sessizce daha büyük guest kullanılmaz. Shell syntax kontrolü başarılı.
