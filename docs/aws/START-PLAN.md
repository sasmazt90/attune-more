# Mevcut iki EC2 için tek başlangıç paketi

**Durum: TASLAK / BLOCKED — başlatma onayı değildir.**
Canlı AWS inventory, güncel fiyatlar ve eksik model/servis varlıkları tamamlanmadan
start istenmez veya uygulanmaz. Mevcut kaynaklar kullanıcı tarafından oluşturuldu;
yeni EC2/VPC/subnet/volume/EIP/IAM kopyaları kapsam dışıdır.

| Kalem | Başlatmadan önce doldurulacak kanıt | Şimdiki durum |
|---|---|---|
| Hesap/rol | STS Account ve seçilen yetkili rol | BLOCKED |
| WEB | i-0b25450afc6633494, g6.2xlarge, Name, stopped | Kullanıcı beyanı; API BLOCKED |
| AAOS | i-0f4cca4e92e94c351, m8i.2xlarge, Name, stopped, nested enabled | Kullanıcı beyanı; API BLOCKED |
| Mevcut altyapı | SG/subnet/route/NACL/volume/profile ve gerekli yerinde düzeltmeler | BLOCKED |
| Runtime | AMI/OS/CPU mimarisi, Python/Node/Caddy, KVM desteği | BLOCKED |
| Model/sağlayıcı | Güncel manifest SHA/byte doğrulaması; canlı Mental/ASR/TTS izinleri | BLOCKED |
| Saatlik compute | Tarihli Frankfurt Linux Shared On-Demand G6 + M8i fiyatları | BLOCKED |
| Disk | Bildirilen 270 GiB gp3; gerçek IOPS/throughput/ek diskler | BLOCKED |
| IP/ağ | Gerçek retained/aktif IPv4 adedi, var olan NAT/endpoint/egress maliyeti | BLOCKED |
| Test toplamı | 2 saat compute + artımlı ağ/provider + vergi; kalıcı disk/IP ayrıca | BLOCKED |
| Bütçe | Mevcut uyarı alıcısı ve aylık sınır; bütçe bir hard cap değildir | BLOCKED |
| Yetki | İki ID ile sınırlı Start/Stop/SSM; yeni kaynak oluşturma yetkisi yok | BLOCKED |

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
