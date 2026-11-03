# İşletim ve ücret sınırı

## Ücretsiz hazırlık

1. `python scripts/aws/preflight.py --identity-alias <gerçek-alias> --output .aws-oem/account.json`
2. `cfn-lint infra/aws/stack.json`; sonra hesabın `ValidateTemplate` API'si.
3. Aynı Frankfurt AZ'sinde G6 ve M8i offerings, nested virtualization özelliği,
   Ubuntu x86_64 AMI owner/root device, G/VT ve Standard kota boşluğu doğrulanır.
   AMI kimliği veya kapasite sonucu tahmin edilmez.
4. Model manifestindeki path, byte, SHA-256 listesiyle `verify_assets.py` çalıştırılır.
   Kaynak klasör Git modeli + ayrı onaylı ağırlıklardır. Arşivden farklı isimli
   ağırlık seçerek eşdeğer saymak yasaktır. CPU yürütme korunur; CUDA aktif edilmez.
5. `scripts/aws/build_bundle.sh` Next ve ayrı cloudDemo APK üretir. Android SDK
   lisansları operatör tarafından incelenir. AWS/KVM'e ihtiyaç duymayan build CI'de
   de çalışır; emulator boot kabulü bundan ayrı tutulur.

## Henüz verilmemiş tek ücretli onayın içeriği

- Hesap ID/rol, `eu-central-1`, doğrulanmış AZ ve AMI kimlikleri.
- `g6.2xlarge` + `m8i.2xlarge`, 150 + 100 GiB gp3, iki EIP.
- AWS API'den tarihli Linux On-Demand, gp3 ve IPv4 fiyatları.
- İlk test önerisi en çok **2 saat**; bu bir onay değildir.
- Bütçe email alıcısı ve aylık USD uyarı tutarı. Bütçe aksiyonu/shutdown yok.
- Başarısız launch/boot sonrası iki instance'ı durdurma; EBS/EIP saklama veya
  silme kararını açıkça içeren temizlik. Stop EBS/EIP ücretini bitirmez.
- DNS değişiklikleri bu onaya otomatik dahil değildir.

Maliyetler bilinmeden onay istenmez. Mevcut durumda hesap/fiyatlar BLOCKED;
harcama tutarı uydurulmadı. Bu task sıfır AWS kaynağı oluşturdu; tüm AWS hesabının
harcaması okunmadığı için hesap faturası sıfır denemez.

25 aylık oturum için, oturum süresi `h`, G6 saatlik `G`, M8i `M`, gp3 GB/ay `E`
ve public IPv4 saatlik `I` ise:

`25 × h × (G + M) + 250 × E + 2 × 730 × I`

Buna internet egress, snapshot, API/provider tüketimi ve vergi eklenir.
EBS/iki EIP, compute duruyorken kalır. İşlem betiği varsayılan model fiyatı
kullanmaz: `python scripts/aws/cost.py --g6 <AWS-rate> --m8i <AWS-rate> --ebs-gb-month <AWS-rate> --hours 2`.

## Onay sonrası kurulum sırası

1. Değişiklik setinde `infra/aws/stack.json` kaynaklarını ve parametrelerini incele.
   CloudFormation create/execute ücret doğurur: şu anda çalıştırılmadı.
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

`democtl.py` yalnız tam iki instance ID'sini ve task tag/type eşleşmesini kabul eder.
Start için mevcut kullanıcı onayını temsil eden özel JSON makbuz gerekir:
`account`, `region`, `instanceIds`, `paidStartApproved`, `expiresAt` (timezone ile),
`maximumSessionHours`, `approvalReference`. Bu belgeyi üretmek kullanıcı onayı yerine
geçmez; onay olmadan `true` yazılmaz. Makbuzlar `.aws-oem` içinde kalır.

```bash
python scripts/aws/democtl.py status --instances <web-id> <aaos-id> --receipt .aws-oem/status.json
python scripts/aws/democtl.py start --instances <web-id> <aaos-id> --approval .aws-oem/approval.json --receipt .aws-oem/start.json
python scripts/aws/smoke.py --web https://attune.sasmaz.digital --aaos https://aaos.sasmaz.digital --output .aws-oem/smoke.json
# Toplantı bittikten sonra, aktif işlerin bittiği doğrulanarak:
python scripts/aws/democtl.py stop --instances <web-id> <aaos-id> --receipt .aws-oem/stop.json
```

`smoke.py` parolayı ATTUNE_DEMO_USER/PASSWORD ortamından alır; argümanda veya logda
çıkarmaz. Beş modül HTTP erişimi ve kimliksiz erişim reddini ölçer. AI, native
PARK/DRIVE, sonuç/geçmiş ve ses testi yerine geçmez. Durdurma compute'u keser;
iptal/late-result ve kayıt temizliği uygulamada tamamlanmalıdır. Hiçbir timer
sunumu otomatik sonlandırmaz. Operatör bütçe süresini takip eder.

## DNS — ayrı onay sınırı

Hedefler uygun alt alan adlarıdır fakat IONOS yetkili zone envanteri okunmadı;
mevcut kayıt durumu BLOCKED. Ana siteye dokunulmaz. Endpoint'ler önce doğrulanır.
Hazır olduğunda incelenecek taslak yalnız `attune` A → Web EIP ve `aaos` A → Aaos EIP,
TTL önerisi 300; mevcut kayıt varsa üzerine yazmadan bildirilir. TLS için gerekiyorsa
DNS-01 TXT veya CAA değişikliği tam değerleriyle ayrıca gösterilir. EIP/sertifika
elde edilmeden bir DNS değeri veya canlı URL üretilmiş gibi raporlanmaz.
