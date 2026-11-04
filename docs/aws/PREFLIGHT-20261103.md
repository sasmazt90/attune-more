> Tarihsel ilk kontrol. Güncel sonuç: [R2 preflight](PREFLIGHT-20261103-R2.md).

# Task 13 — canlı AWS devam kontrolü

**Sonuç: OIDC/STS ve EC2 erişimi çalışıyor; eksik okuma yetkileri ve Pricing ağ izni nedeniyle BLOCKED.**
Gözlem: 3 Kasım 2026, 13:15–13:20 CET. Kaynak commit: `7233e9c2c3246575e184df3d29701bd802654399`,
PR #22 / `codex/aws-oem-demo-20261103`. Yeni PR, main merge, DNS veya production değişikliği yok.
Makinece okunur, credentials içermeyen özet: [live-preflight-20261103.json](evidence/live-preflight-20261103.json).

## Doğrulanan kimlik ve mevcut kaynaklar

- Cloud runtime güncel gözlemde `running/connected`, ağ politikası `enforced`, outbound identity `ready`.
- `OIC_MANIFEST_PATH` version 1: AWS alias `AWS`, rol `attune-codex-deployer`, bölge `eu-central-1`.
  Runtime alias bağlantının kullanıcıya görünen adından farklıdır; seçici manifestten alındı.
- Gerçek STS `GetCallerIdentity`: hesap **798886013428**, assumed role **attune-codex-deployer**.
  Credential dosyası/token/anahtar içeriği okunmadı veya rapora eklenmedi. Yeni anahtar oluşturulmadı.
- Boto3 ve AWS CLI geçici yerel venv'e kuruldu; mevcut OIDC profilini kullandı.

| Hedef | AWS API durumu | CPU / RAM | Root disk | Ek gözlem |
|---|---|---|---|---|
| `i-0b25450afc6633494` / attune-web-ai | stopped, g6.2xlarge | 8 vCPU / 32 GiB | 150 GiB gp3, encrypted | IMDSv2 required |
| `i-0f4cca4e92e94c351` / attune-aaos-demo | stopped, m8i.2xlarge | 8 vCPU / 32 GiB | 120 GiB gp3, encrypted | NestedVirtualization enabled, IMDSv2 required |

İki disk de 3000 IOPS / 125 MiB/s; ek bağlı EBS görülmedi. AMI `ami-04de259f26cbf4c1e`,
Canonical Ubuntu 24.04 amd64. Guest OS paketleri, `/dev/kvm`, modeller veya servisler
stopped host içinde incelenmedi. CPU ayarı, çalışan KVM/AAOS kanıtı değildir.

İki hedef aynı `eu-central-1c` AZ, `subnet-0522052d105ce2ff3` ve `vpc-074768071df6b9266` içinde.
AZ `available`, iki tip bu AZ'de sunuluyor. G/VT kota **8**, Standard kota **16** vCPU;
bölgedeki running/pending/stopping envanteri boş. Başlangıç için sırasıyla 8 ve 8 vCPU gerekir.
Offerings/kota kontrolü anlık fiziksel kapasite rezervasyonu değildir.

Yalnız iki hedef için `StartInstances(DryRun=True)` ve `StopInstances(DryRun=True)`
**DryRunOperation** döndü: o anki API yetkileri doğrulandı, gerçek start/stop yapılmadı.

## Ağ, IAM ve SSM bulguları

- WEB private IP `172.31.11.240`, AAOS private IP `172.31.10.53`.
- Subnet public IPv4 atamasını açıyor; route table'da local route ve aktif
  `0.0.0.0/0 → igw-0a723e386eeb4c4a7` var. Stopped hedeflerde public IP yok;
  hedeflere bağlı EIP sorgusu boş. Başlatma sonrası adres ayrıca doğrulanmalı.
- SG'ler `sg-023659b3a447ab759` (WEB) ve `sg-0476f580c44063a5d` (AAOS).
  ENI sorgusunda bu SG'leri kullanan yalnız ilgili iki hedef görüldü.
- İkisinde IPv4 tüm outbound açık; inbound yalnız IPv6 `2003:cd::/32` kaynağından TCP 22.
  Hedef ENI'lerde IPv6 yok. Mevcut SSH kuralı değiştirilmedi.
- **443 ingress ve AAOS SG → WEB SG TCP 8443 eksik.** Mevcut mimaride bunlar
  doğrulanmış kaynak CIDR/TLS/mTLS ile tamamlanmalı; bu oturumda kural eklenmedi.
- İki instance'ta `attune-ec2-ssm-role` instance profile ARN'i bağlı görünüyor.
  Profile içindeki rol/trust/policy/boundary ayrıntıları yetki eksikliği nedeniyle doğrulanamadı.
- SSM `DescribeInstanceInformation` hedefler için boş döndü. Bu, SSM hazır kanıtı değildir;
  durmuş host üzerinde agent çalışması kontrol edilemez. SSM için outbound HTTPS,
  DNS, instance role policy, IMDS erişimi ve boot sonrası agent registration doğrulanmalı.
- Budgets API yanıtında bütçe kaydı dönmedi; bir uyarı alıcısı veya harcama sınırı doğrulanamadı.

## Giderilmesi gereken gerçek erişim engelleri

AWS API reddi gözlenen işlemler:

| İşlem | Sonuç |
|---|---|
| `ec2:DescribeNetworkAcls` | UnauthorizedOperation |
| `ec2:DescribeInternetGateways` | UnauthorizedOperation |
| `ec2:DescribeVpcEndpoints` | UnauthorizedOperation |
| `ec2:DescribeNatGateways` | UnauthorizedOperation |
| `ec2:DescribeVpcAttribute` | UnauthorizedOperation |
| `iam:GetInstanceProfile` | AccessDenied, iki hedef profile kontrolü |
| `iam:GetRole` | AccessDenied, deployer ve SSM rolü |
| `iam:ListAttachedRolePolicies` | AccessDenied, SSM rolü |

IAM hata metni `GetRole`/`ListAttachedRolePolicies` için identity-based Allow bulunmadığını
belirtti. Role/policy audit zincirindeki diğer IAM okumaları henüz çalıştırılamadı.
Mevcut [preflight-read-only.json](../../infra/aws/iam/preflight-read-only.json) bu incelemenin
tam salt okunur izin setidir; NAT ve VPC attribute okumaları da eklendi. Yetkili hesap
yöneticisi bu izinleri `attune-codex-deployer` için sağlamalı. AdministratorAccess,
yeni kullanıcı anahtarı veya yeni altyapı izni gerekmiyor. Bu oturum IAM policy değiştirmedi.

Pricing için runtime allowlist'te `pricing.us-east-1.amazonaws.com` bulunuyor,
ancak boto3'ün gerçek endpoint'i **`api.pricing.us-east-1.amazonaws.com`**.
Sorgu `ProxyConnectionError`, alttaki CONNECT ise **403 Forbidden** döndü.
Cloud ortamının HTTPS izinlerine tam SDK hostname'i eklenmeli ve çalışan runtime'a
uygulandığı doğrulanmalı. Proxy/TLS atlanmadı; alternatif kimlik denenmedi.

## Maliyet ve tek başlatma onayının durumu

G6, M8i, gp3 ve IPv4 güncel fiyat sorgularının tamamı ağ engelinde kaldı.
Bu nedenle sayısal fiyat, toplam veya maliyet üst sınırı **doğrulanmış değildir**;
ücretli başlangıç onayı henüz istenmedi ve onay makbuzu yazılmadı.
270 GiB mevcut gp3 stopped durumda da ücretlidir. NAT/endpoint envanteri eksik;
hesabın toplam harcaması veya kalıcı altyapı maliyeti sıfır sayılmaz.

Mevcut [iki saatlik test/stop planı](START-PLAN.md) korunuyor. Erişim giderilince
canlı fiyatlar ve tam inventory, gerekli yerinde ayarlar ve model/servis hazırlığıyla
birlikte tek somut onay paketine dönüştürülecek. Paket Skin WEB + AAOS Hearing concurrency,
Vision WEB DE gerçek ASR, AAOS Vision 3 GiB guest, Mental partial persistence,
beş modül sonuç/geçmişi, TR/EN/DE ve native vehicle gates kapsamını açıkça içerecek.
Önceki mock/scripted/injected testler gerçek entegrasyon PASS'i sayılmayacak.

Bu oturum paid start yapmadığından stop/cleanup gerektiren yeni çalışma yok.
Sonraki onaylı testte yalnız bu oturumun başlattığı iki hedef normal Stop ile durdurulacak,
durum API'den doğrulanacak; mevcut EBS/EIP korunacak, terminate/delete/force-stop yapılmayacak.

## Kod ve CI devralma

PR #22 başı doğrulandı ve yerel çalışma bu dala geçirildi. Baş commit'in genel CI,
AWS hazırlığı/APK ve Automotive çalışmaları GitHub API'ye göre başarılı:
[CI](https://github.com/sasmazt90/attune-more/actions/runs/41619731646),
[AWS hazırlığı](https://github.com/sasmazt90/attune-more/actions/runs/41619731536),
[Automotive](https://github.com/sasmazt90/attune-more/actions/runs/41619731524).
Bu kontroller canlı AWS runtime kabulü değildir. Bu devam değişikliği yalnız erişim
belgelerini, salt okunur policy önerisini ve canlı gözlem kanıtını günceller.
AWS kurulumu ve beş modülün gerçek kabulü **NOT RUN / BLOCKED** kalır.

Devam değişikliği yerel doğrulaması: `tests/aws/test_existing.py` **6 passed**;
policy ve kanıt JSON parse kontrolü ile `git diff --check` başarılı. Bu testler
AWS model/servis kabulü değil, mevcut hedef ve onay korumalarının birim kontrolleridir.
