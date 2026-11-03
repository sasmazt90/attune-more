# Mevcut iki EC2 için tek başlangıç paketi

**2026-11-03 R2: maliyet hazır; model aktarımı/hazırlığı nedeniyle başlatma BEKLİYOR. Bu belge onay değildir.**

[Canlı R2 kontrolleri](PREFLIGHT-20261103-R2.md) · [API fiyat kanıtı](evidence/pricing-20261103.json).
Hesap `798886013428`, bölge `eu-central-1`, rol `attune-codex-deployer`.
Mevcut WEB `i-0b25450afc6633494` (g6.2xlarge) ve AAOS `i-0f4cca4e92e94c351`
(m8i.2xlarge), ikisi de stopped. Yeni altyapı, DNS ve main merge yok.

| Kalem | Canlı birim fiyat (USD) | İlk 2 saat (USD) |
|---|---:|---:|
| G6 Linux Shared On-Demand | 1.22249 / saat | 2.44498 |
| M8i Linux Shared On-Demand | 0.50716 / saat | 1.01432 |
| İki otomatik public IPv4 (boot sonrası tekrar doğrulanır) | 0.005 / IP-saat | 0.02000 |
| Mevcut 270 GiB gp3 | 0.0952 / GiB-ay | 0.07140 ayrılmış pay |
| Internet çıkışı, 10 GB planlama varsayımı | 0.09 / GB | en çok 0.90000 varsayımsal |
| Toplam AWS tahmini, 10 GB dahil | | **4.45070** |

Kasım 30 gün/720 saat: disk payı `270 × 0.0952 × 2 / 720`.
Disk zaten mevcut; başlatmanın artımlı ücreti değildir. Diskler stopped durumda da
**25.704 USD/ay** karşılığı ücretlenir. Temel artımlı compute + IP **3.47930 USD**;
10 GB çıkışla **4.37930 USD**. İndirmelerin AWS inbound ücreti sıfır. Aynı AZ'deki
private IP trafiği için transfer ücreti öngörülmez; public IP üzerinden hostlar arası
trafik kullanılmaz. İki disk 3000 IOPS / 125 MiB/s dahil seviyede; ek performans ücreti yok.
NAT ve VPC Endpoint yok; bu kaynakların saatlik ücreti yok. Yeni snapshot, EIP, LB,
CloudWatch log ingestion veya ücretli SSM advanced tier açılmayacak. Account genelindeki
başka harcamalar bu paket değildir; kredi/free tier ve vergi indirimi varsayılmadı.

**Tek önerilen operasyonel bütçe: vergi hariç 6 USD / en çok 2 saat.** Bunun 5 USD'si
AWS payı (4.45 USD senaryo + pay), 1 USD'si gerçek provider çağrıları için rezervdir.
Provider rezervi fiyat teklifi değildir: güvenli mevcut provider yapılandırması ve
model/ASR/TTS kullanımı doğrulanmadan maliyeti kesinleşmez veya çağrı başlatılmaz.
Bütçe AWS tarafından uygulanan bir hard cap değildir; hesapta Budgets kaydı bulunmadı.
Süre boot ile başlar, 115. dakikada durdurmaya geçilir, 120. dakikadan önce normal Stop
istenir ve AWS API `stopped` kanıtı alınır. AWS stopping gecikmesi/ölçüm farkı olabilir.
10 GB çıkış varsayımı aşılırsa test erken kesilir; fiyat tahmini gerçek kullanım sonrası
ölçümle uzlaştırılır. Sağlayıcı kullanımı ayrıca izlenir; sessiz süre/bütçe uzatımı yok.

## Tek paket içindeki teknik koşullar

- NACL/IGW/NAT/endpoint/VPC DNS/profile/trust/SSM policy envanteri tamamlandı.
- Start/Stop dry-run başarılı. SSM SendCommand iki ID ve AWS-RunShellScript belgesine
  mevcut policy ile izinli; agent registration ve gerçek komut çalışması boot sonrası ölçülür.
- Kullanıcının onayladığı 443 `/32` ve private 8443 kuralları
  uygulandı ve API ile doğrulandı. [Ek IAM policy](../../infra/aws/iam/existing-security-groups.json)
  kullanıcı tarafından eklendi; `configure_ingress.py` idempotent kontrol sağlar.
- APK indirildi ve hash doğrulandı; WEB production build başarılı, regional Skin
  paketi 24 parça + 31 üye hash'iyle doğrulandı. Kaynağı belirlenen iki Skin ONNX export'unun aktarımı, regional Skin ve
  Chatterbox runtime paketi, güvenli canlı provider ayarları tamamlanmalı. Ayrıntılı
  model hash ve kaynaklar R2 raporunda. TLS/mTLS ve SSM/KVM/AAOS image kontrolü host
  açılmadan uygulanamaz; bunlar onaylı kurulumun ilk aşamasıdır.
- DNS değişmeden HTTPS için başlatılan public IP'lere uygun demo TLS ve tarayıcı
  güveni sağlanır; yerel testlerde hostname eşleme kullanılabilir. Geçersiz TLS'yi
  atlamak kamera/mikrofonun güvenli bağlam koşulunu karşılamış sayılmaz.

Başlatma sorusu yalnız teknik koşullar giderilince tek seferde bu **aynı paket** için
sorulur. Kullanıcı şimdi yalnız mevcut SG değişikliklerini yetkilendirdi; bu paid start
onayı olarak yorumlanmadı. `.aws-oem/approval.json` oluşturulmadı.

## Önerilen ilk pencere: en çok 2 saat

1. 0–20 dakika: mevcut host boot, SSM, sürüm/asset hash, private mTLS/HTTPS, CPU/RAM
   ve G6 worker ölçümü. Kurulum önkoşulu eksikse kalan pencereyi tüketmeden durdurma.
2. 20–40 dakika: M8i `/dev/kvm`, gerçek API35 automotive image, cloudDemo APK hash,
   canlı emulator görüntüsü/input, AWS içi adb reverse; localhost'un laptopa gitmediği kanıtı.
3. 40–100 dakika: beş modülün WEB ve AAOS gerçek girişli akışları; Skin üç poz/fusion,
   Dental model sonucu, Vision göz/mesafe/geometri, Hearing ses ve seviye kontrolü,
   Mental gerçek provider/ASR/TTS. İzin yoksa, model eksikse veya süre yetmezse ilgili
   satır BLOCKED/PARTIAL; fixture, mock provider veya scripted recognizer ile PASS yok.
4. 100–115 dakika: sonuç/geçmiş/yeniden açma/silme; izin iptali, bağlantı kaybı,
   PARK→DRIVE, native UX restriction, geç sonuç düşürme; TR/EN/DE kontrolleri.
5. 115–120 dakika: aktif işlemleri bitirme/iptal, yalnız iki EC2'yi normal Stop;
   durumu API'den doğrulama. EBS/var olan EIP korunur; kalan ücret kalemleri kaydedilir.

Bu süre bütün kabul maddelerinin tamamlanacağı sözü değildir. Uzatma sessizce
yapılmaz. Otomatik shutdown eklenmedi; operatör test penceresini takip eder.
Başlatma/kurulum başarısız olursa yalnız bu testte başlatılan hedefler durdurulur;
terminate/delete/force-stop yapılmaz. Hesaptaki başka workload'a dokunulmaz.

## AWS sınırı ve gerçek giriş

Backend ve modeller G6'da, gerçek AAOS/WebView/emulator M8i'de çalışır. G6'nın GPU'su
mevcut CPU model yolunun otomatik CUDA'ya çevrilmesi anlamına gelmez. Laptop yalnız
HTTPS tarayıcı ve izinli fiziksel kamera/mikrofon giriş cihazı olabilir; backend,
model worker, ADB veya emulator çalıştırması gerekmez. Vision'ın mevcut WEB geometri
hesabı tarayıcıdadır; AAOS'ta aynı hesap AWS guest WebView içinde çalışır.

Hearing için uzaktan ses seviyesinin kalibrasyonu, Vision için noVNC ölçeklemesinin
geometriye etkisi ayrıca ölçülür. Klinik doğruluk veya cihaz kalibrasyonu varsayılmaz.
Geçmişin bazı bölümleri browser/guest storage'ına, Mental bazı kayıtları process
belleğine bağlıdır; merkezi kalıcı hasta veritabanı vaat edilmez. Yeniden başlatma
sonucu gerçekten gözlenir; mevcut veri davranışı kabul ihtiyacını karşılamıyorsa
ayrı eksik olarak kaydedilir.

## Tek bildirim/onay kaydı

Canlı veriler geldikten sonra kullanıcıya tek mesajda hesap/ID, gerekli mevcut-kaynak
ayar değişiklikleri, iki saatlik sayısal tahmin ve devam eden kalıcı ücretler, yukarıdaki
test kapsamı, stop planı ve kalan BLOCKED maddeleri sunulur. Kullanıcı onayı ancak
bundan sonra `.aws-oem/approval.json` içinde referanslanır. Örnek belgeye sahte `true`
yazılmaz. DNS değişikliği, main merge veya üretim yayını bu pakete dahil değildir.
