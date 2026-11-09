# Mental ses gecikmesi — bağımsız inceleme ve GPU deney planı (9 Kasım 2026)

Taban: `main` = `2aff51e0931e7b4bc65db8bd60ba482fedb8dc06` (inceleme anında güncel main ile aynı).
Girdi: repo raporları, ekli `MENTAL-DECODER-PARTIAL-20261109.md`, kod yaması ve
"essential evidence" arşivi (repoda yok). Pinned Chatterbox kaynağı
`5de7a54aa4e5e2baadb0182dde554908b48b85c2` GitHub'dan alınıp okundu (50 `.py` dosyası).

## 1. Sonuç

- **Bu oturumda AWS erişimi yok.** Ortamdaki AWS anahtar değişkenleri 14 karakterlik yer
  tutucular; STS `GetCallerIdentity` → `InvalidClientTokenId`. AWS uç noktalarına ağ
  erişimi var, yalnız geçerli kimlik eksik. Bu nedenle **hiçbir instance başlatılmadı,
  oluşturulmadı veya durdurulmadı; güncel instance durumları doğrulanamadı.** Son bilinen
  durum (WEB/AAOS stopped, 9 Kasım 18:51:58 CET) önceki oturumun kaydıdır.
- Ekli kısmi derleme raporunun sayıları kanıt JSON'larından **yeniden hesaplandı ve
  birebir tuttu**. "Anlamlı kazanım yok" sonucuna katılıyorum.
- Yeni bulgular (ayrıntı §3–§4):
  1. **Canlı Mental konuşması `female-calm-v1` sesini kullanıyor; bütün sentetik ölçümler
     `official-default` ile yapıldı.** Canlı yol her parçada referans conditioning'i
     (referans WAV okuma/yeniden örnekleme, iki S3 tokenizer geçişi, CAMPPlus, voice encoder)
     yeniden hesaplıyor. Bu maliyet hiç ölçülmedi.
  2. Ölçülmüş satırlara uyan doğrusal model: toplam ≈ **3,56 s sabit + 2,31 s / ses-saniyesi**
     (R² 0,99). Sabit kısmın büyük bölümü decoder'da; kaynak, decoder'ın her istekte
     ~10 s'lik referans prompt'u da 10 CFM adımında yeniden işlediğini gösteriyor.
  3. Bu model 5 Kasım'da tarayıcıda görülen ~8 s parça arası boşluğu yeniden üretiyor.
     Mevcut CPU'da zamanlama veya parça bölme ile **boşluk kapatılamaz**; ilk sesi ~2 s'ye,
     boşluğu ~0,5 s altına indirmek için sentezin kabaca **4–6× hızlanması** gerekir.
  4. r7i.2xlarge **4 fiziksel çekirdek / 8 vCPU (Hyper-Threading)**; dört thread ölçümde
     medyan **3,96 çekirdek** kullanıyor. Önceki 8-thread ve ikinci-worker denemeleri
     fiziksel çekirdek eklemedi; "daha fazla çekirdek" hipotezi hiç test edilmedi.
- Güvenli küçük iyileştirme adayı: referans conditioning'in resident worker'da
  **opt-in yeniden kullanımı** (varsayılan kapalı). Byte-özdeş çıktı bekleniyor; gerçek
  runtime'da doğrulanmadan açılmamalı (§5).
- GPU ölçümü için kaynak/maliyet/kapanış planı §7'de. **Onay ve geçerli AWS kimliği
  olmadan uygulanmadı.**

## 2. Ekli rapor, yama ve kanıtın bağımsız incelemesi

Kanıt JSON'larından yeniden hesaplanan medyanlar (saniye, n = dil başına ölçülmüş segment):

| Koşu | Dil | n | Toplam p50 | Token p50 | Decoder p50 | Ses p50 |
|---|---|---:|---:|---:|---:|---:|
| baseline-10 | EN / DE / TR | 20 / 20 / 20 | 8,495 / 9,297 / 10,741 | 3,481 / 4,013 / 4,991 | 4,971 / 5,156 / 5,688 | 2,12 / 2,46 / 3,10 |
| partial-10 | EN / DE / TR | 20 / 20 / 20 | 8,612 / 9,362 / 10,765 | 3,483 / 4,079 / 5,060 | 5,055 / 5,203 / 5,710 | aynı |
| baseline-reverse-2 | EN / DE / TR | 4 / 4 / 4 | 8,572 / 9,612 / 10,619 | — | 5,053 / 5,354 / 5,742 | — |
| partial-reverse-2 | EN / DE / TR | 4 / 4 / 4 | 8,418 / 9,548 / 10,591 | — | 4,984 / 5,298 / 5,717 | — |

Değerlendirme:

- Rapor tablosu kanıtla tutarlı. Değişimler ±%2 içinde ve yön sıraya göre dönüyor;
  bunu "etki yok" olarak okumak doğru, "yavaşlama" olarak okumak değil.
- Baseline sırasında `fwupd` ~0,73 çekirdek kullandı. Host 8 mantıksal / 4 fiziksel
  çekirdek olduğu için bu yük bir hyper-thread kardeşini paylaşmış olabilir; bu durum
  baseline'ı yavaşlatır, yani adayın lehine yanlılık yaratır. Kazanım yine çıkmadığı için
  sonuç sağlam.
- CPU'da FP32 Inductor'un düşük kazanç beklentisi kaynakla da uyumlu: süre oneDNN/MKL
  matmul/konvolüsyonlarında; derleme esas olarak eleman-bazlı işlemleri birleştirir.
- Ölçülen bütün satırlarda alt fazlar yalnız `speechTokens`, `waveDecoder`,
  `watermark`; `conditioning` yok. Yani probe yalnız `official-default` config ile
  çalıştı; canlı ses yolu ölçülmedi (rapor da bunu "ölçülmedi" diye belirtiyor).
- Yama yalnız offline QA aracını etkiliyor; fayda göstermediği için bu dala alınmadı.
  Probe'un GPU'ya hazırlanan yeni sürümü (§6) yamadaki probe değişikliğinin yerini alır.
  Derleme adayı gerekirse ayrı olarak yeniden uygulanabilir.

## 3. Darboğaz: ölçülen ve türetilen

**Ölçülen** (72 baseline satırı, r7i.2xlarge, 4 thread, `official-default`, ses 1,72–3,60 s):

| Faz | Sabit | Ses-saniyesi başına | R² |
|---|---:|---:|---:|
| Speech-token üretimi (T3) | 0,22 s | 1,535 s | 0,995 |
| Waveform decoding (S3Gen) | 3,32 s | 0,777 s | 0,941 |
| Toplam sentez | 3,56 s | 2,314 s | 0,990 |

İşlem başına CPU-saniye / duvar saati medyanı 3,96: dört fiziksel çekirdek dolu.

**Türetilen** (kaynak ve aritmetik; ölçüm değil):

- T3, 520M parametreli 30 katmanlı Llama; CFG için her adım batch 2. S3 token hızı
  25/s olduğundan ~61–63 ms/token çıkar. FP32 ağırlık ~2 GB; her token adımı ağırlıkları
  bir kez okur → ~31 GB/s. Bu, işlemin hesaplamadan çok bellek bant genişliğiyle sınırlı
  olduğunu gösteriyor.
- Decoder (`flow.py`), referans prompt token'larını üretilen token'ların önüne ekliyor.
  Conformer encoder ve 10 adımlı CFM (batch 2) her istekte prompt + yeni kareleri
  işliyor. Prompt en fazla 10 s; 2 s'lik bir parçada karelerin ~%80'i prompt. Ölçülen
  ~3,3 s sabit decoder maliyetinin en olası açıklaması bu. Prompt'u kısaltmak ses
  kimliğini değiştirir; onaysız seçenek değildir.
- `female-calm-v1` yolu her `generate` çağrısında `prepare_conditionals` çalıştırıyor:
  `mtl_tts.py` 253–278 ve 300–301. Tahmini maliyet ~0,3–1 s/parça; **ölçülmedi**.

İki parçalı oynatma için türetilmiş model: ilk ses ≈ `3,56 + 2,31·d1`, boşluk ≈
`3,56 + 2,31·d2 − d1`. 5 Kasım'daki iki kısa cümlede (d1 ≈ 2,5 s, d2 ≈ 3 s) boşluk
≈ 8,0 s çıkıyor; tarayıcıda gözlenen ~8 s ile tutarlı. Sonuçlar:

- Daha kısa ilk parça ilk sesi biraz düşürür (d1 = 1,5 s → ~7 s). Ancak her ek parça
  ~3,6 s sabit maliyet ekler ve boşlukları artırır.
- Tek tip k× hızlanmada (d1 = 2,5 s, d2 = 6 s): k = 2 → ilk ses 4,7 s, boşluk 6,2 s;
  k = 4 → 2,3 s / 1,9 s; k = 6 → 1,6 s / 0,4 s. Hedefe yalnız ≥4–6× hızlanma yaklaşır.

## 4. Seçeneklerin karşılaştırması

"Ölçülen" sütunu yalnız mevcut kanıtı içerir; diğer her şey hipotezdir.

| Seçenek | Ölçülen | Beklenen etki (hipotez) | Uygulanabilirlik / risk | Doğrulama maliyeti | İşletme maliyeti |
|---|---|---|---|---|---|
| Aynı model, FP32, GPU | Yok | Decoder'da büyük kazanç; T3 eager modda kernel başlatma yüküyle sınırlı. EN segment ~1,5–2,5 s (bugün 8,5 s); RTF ~0,5–1. Boşluk azalır, tamamen kapanmayabilir. | Upstream `cuda` destekliyor; worker `device: cuda` kabul ediyor. Risk: 3 Kasım'da eu-central-1c'de G kapasitesi yoktu; G/VT kotası 8 vCPU idi; CUDA tohumları CPU ile aynı token'ları üretmez. | Ayrı instance, ~1–2,5 saat, ≲ $5 (§7) | g5.xlarge ~$1,26/s, g6.xlarge ~$1,01/s; demo saatleri boyunca açık |
| `female-calm-v1` conditioning yeniden kullanımı (bu dal, varsayılan kapalı) | Yok | Canlı yolda parça başına ~0,3–1 s; ilk ses ve boşluk ikisi de. Tek başına hedefe yetmez. | Upstream kaynak değişmez. Conditioning rastgelelik kullanmaz → byte-özdeş çıktı beklenir. Bütünlük kontrolleri her istekte sürer. | WEB'de ~1 saat; ek kaynak yok | Yok |
| Daha çok **fiziksel** çekirdekli CPU (ör. c7i/r7i.4xlarge) | Yok (8 thread HT'ydi) | Decoder kısmen ölçeklenir, T3 bant genişliğiyle kısmen; ~1,3–1,8× tahmini. Boşluk sürer. | Instance tipi değişikliği onay gerektirir. | Orta | Saatlik ~2× |
| Parça bölmeyi değiştirmek | Yok | İlk ses biraz iner, toplam süre ve boşluk sayısı artar (sabit 3,6 s) | Prozodi/birleşme dinleme onayı gerekir | Orta | Yok |
| Inductor derlemesi (CPU) | **Var**: ±%2, kazanç yok | — | Reddedildi | — | — |
| 8 thread / ikinci worker | Önceki kayıt: kazanç yok | 4 fiziksel çekirdekte beklenen sonuç | Yeniden önerilmiyor | — | — |
| CFM adımını, prompt'u, hassasiyeti azaltmak; turbo/başka model | Yok | Büyük | Model/kalite/ses kimliği değişikliği; ayrı onay ve dinleme | Yüksek | — |
| Segment içi akış (streaming) | Yok | CPU'da RTF > 2 olduğu için cümle ortasında boşluk yaratır | Pinned kaynak dışı kod gerekir | Yüksek | — |

Öneri sırası: (1) WEB'de canlı ses yolunu ölç ve conditioning yeniden kullanımını
byte-özdeşlikle doğrula. Mevcut izin kapsamında, yeni kaynak yok. (2) Onay sonrası ayrı
GPU instance'ta aynı model/FP32 ölçümü. (3) GPU kazancı yeterliyse ürün entegrasyonu
için ayrı mimari/maliyet onayı. Ardından ilk oynatma ve boşluk tarayıcıda yeniden
ölçülmeli. Sentez hızlanması ürün gecikmesi iyileşmesi sayılmaz.

## 5. Kod değişikliği: conditioning yeniden kullanımı (opt-in)

`services/core-api/mental_neural_worker.py`:

- `ATTUNE_MENTAL_TTS_REUSE_CONDITIONING=1` **ve** resident runtime varsa, referans sesin
  conditioning'i model nesnesi + doğrulanmış referans SHA-256 + exaggeration anahtarıyla
  bir kez türetilir. Sonraki istekler aynı upstream `generate` ayarlarıyla
  (`exaggeration`, `cfg_weight`, `temperature`) bu tensörleri kullanır.
- Değişmeyenler: config/model/referans hash kontrolleri (her istek), konfigürasyon
  değişiminde `BATCH_CONFIGURATION_CHANGED`, `official-default` yolu, tek-seferlik worker,
  watermark, iptal (worker'ı öldürme), PARK/consent kontrolleri, upstream kaynak.
- Bayrak tanımsız, `0` veya `true` ise davranış birebir eskisi gibi. Deploy betiği
  bayrağı ayarlamıyor.
- Neden byte-özdeş bekleniyor: `prepare_conditionals` → resample, mel, S3 tokenizer,
  CAMPPlus, voice encoder; hiçbiri RNG tüketmiyor (`randn` yalnız CFM/HiFT'te). Aynı
  tohumla T3 örneklemesi aynı RNG durumundan başlar. Bu bir kaynak çıkarımıdır;
  **kabul ölçütü, gerçek runtime'da aynı seed/metinlerle tüm WAV SHA-256 değerlerinin
  eşit olmasıdır.** Eşit değilse bayrak açılmaz.
- Testler: tek türetim, aynı upstream argümanları, dil başına ayrı runtime, varsayılan
  kapalı, tek-seferlik ve `official-default` yolunun etkilenmemesi, hata/hash/model
  değişiminde yeniden kullanmama. `test_mental_neural_worker.py`: **31 geçti**.
- Kalan riskler: gerçek kazanç ölçülmedi. Byte-özdeşlik doğrulanmadı. Bellekte kalan
  conditioning tensörleri birkaç MB. Etkinleştirmek bir servis ortamı değişikliği ve
  deploy'dur; onaysız yapılmayacak.

## 6. Kod değişikliği: CPU/GPU karşılaştırılabilir probe

`scripts/qa/realistic/mental_resident_probe.py`:

- Cihaz doğrulanmış config'ten okunur. Yüklenen modelin cihazı eşleşmezse
  `PROBE_DEVICE_MISMATCH` ile durur.
- CUDA'da her zamanlanan aralık (toplam, T3, decoder, watermark, conditioning) önce ve
  sonra `torch.cuda.synchronize()` ile çevrilir. Böylece asenkron kuyruktaki iş doğru
  faza yazılır. CPU'da ek çağrı yoktur.
- Model yüklenmeden önce TF32 kapatılır (`matmul` ve `cudnn`). Ampere ve sonrası GPU'lar
  cuDNN konvolüsyonlarını varsayılan olarak TF32 ile çalıştırır; bu ilk karşılaştırma
  katı FP32 kalır. Değerler `runtime.json`'a yazılır.
- `runtime.json`: torch/CUDA/cuDNN sürümü, GPU adı/yeteneği, `nvidia-smi` sürücüsü, CPU
  modeli, mantıksal CPU sayısı, thread ayarı, conditioning bayrağı.
- Satır başına: `speechTokensIncludingStop` (token başına süre için), süreç CPU-saniyesi,
  önce/sonra host load, GPU tepe belleği (allocated/reserved), RSS.
- `--seed-start` ve `--order forward|reverse`: aynı metin/tohumlarla ters sıra kontrolü.
  Varsayılanlar eski davranışla aynı (seed 42, ileri sıra).
- Testler: sahte torch/worker ile alt süreç. Kuyrukta bekleyen 50 ms'lik işin yalnız
  senkronizasyonla decoder fazına yazıldığı, CPU'da CUDA çağrısı olmadığı, TF32'nin
  kapalı kaydedildiği, ters sıranın aynı girdileri ölçtüğü ve cihaz uyumsuzluğu
  doğrulanır: **5 geçti**. Bunlar sinirsel ölçüm değildir.

Yerel doğrulama: worker 31, probe 5, resident + timing 16 test geçti.
`test_mental_neural_tts.py` bu ortamda tüm uygulama bağımlılıkları (OpenCV vb.)
kurulamadığı için çalıştırılamadı; CI'da çalışmalıdır.

## 7. GPU deney planı — onay bekliyor

### 7.1 Hipotez ve karar kuralı

**Hipotez.** Aynı ağırlıklar, aynı onaylı sesler ve aynı çıkarım ayarlarıyla katı FP32
CUDA, segment başına sentezi ≥4× kısaltır. Ölçülecek fazlar: speech-token üretimi
(ms/token), decoding (sabit ve ses-saniyesi başına), toplam ve RTF; ısınma ve bellek
ayrıca.

**Karar kuralı.** Dil başına medyan toplam ≥4× hızlanma **ve** yapısal/ASR kontrollerinde
gerileme yoksa ürün entegrasyon tasarımı ayrı onaya sunulur. Aksi halde GPU
önerilmez.

### 7.2 Kaynak ve süre

| Kalem | Öneri |
|---|---|
| Bölge | eu-central-1 (WEB'in VPC/subnet'i). AZ sırası: mevcut subnet AZ'si (1c), sonra VPC'de varsa a/b subnet'i. Yeni VPC/subnet yok. |
| Instance | 1 adet, **g5.xlarge** (A10G 24 GB, 4 vCPU, 16 GiB). Gerekçe: xlarge seçenekleri içinde en yüksek FP32 bellek bant genişliği (T3 bant genişliğine bağlı); kotaya sığar. Yalnız kapasite yoksa sırayla g6.xlarge (L4), g4dn.xlarge (T4). Başarısız `RunInstances` ücretsiz. |
| AMI | AWS Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04). Güncel ID başlatma anında SSM public parametresinden alınıp kaydedilir. |
| Disk | 100 GiB gp3, şifreli, `DeleteOnTermination=true` |
| Ağ | Yeni, **ingress kuralı olmayan** geçici Security Group (SSM inbound istemez); public IPv4 yalnız indirmeler için |
| Erişim | SSM. WEB'in mevcut instance profile'ı (`iam:PassRole` gerekir). Yoksa yeni rol ayrıca onaya sunulur. |
| Kanıt aktarımı | Geçici S3 bucket (Block Public Access, SSE-S3, 7 günlük lifecycle). Instance, bu oturumda üretilen **presigned PUT URL**'leriyle yükler; IAM değişikliği gerekmez. İndirme ve hash doğrulaması sonrası bucket silinir. |
| Azami süre | GPU **2,5 saat**: user-data `shutdown -h +150` ve `InstanceInitiatedShutdownBehavior=terminate` ile kendini sonlandırır. WEB **1,75 saat**: OS'te `shutdown -h +105`, yalnız WEB'in shutdown davranışı API'de `stop` olarak doğrulanırsa. |

### 7.3 Güncel saatlik ücret ve tahmini toplam

Bu oturumda AWS Pricing API'ye kimliksiz erişilemedi; fiyat sitelerine ağ politikası
izin vermiyor. Aşağıdaki fiyatlar web aramasındaki aggregator değerleri ve 3 Kasım
AWS API kaydıdır. **Başlatmadan önce Pricing API ile yeniden sorgulanıp onay mesajına
yazılacak.**

| Kalem | Saatlik (USD) | Azami süre | Azami tutar |
|---|---:|---:|---:|
| g5.xlarge On-Demand Linux, Frankfurt | ~1,258 (aggregator; 3 Kasım API: g5.2xlarge 1,5156) | 2,5 s | ~3,15 |
| Yedek: g6.xlarge / g4dn.xlarge | ~1,006 / ~0,658 | 2,5 s | ~2,52 / ~1,65 |
| WEB r7i.2xlarge (CPU baseline, mevcut) | < 1,16 (önceki kayıt: WEB+AAOS birlikte 1,16) | 1,75 s | < 2,03 |
| EBS gp3 100 GiB (~0,0952 $/GiB-ay) | ~0,013 | 3 s | ~0,04 |
| Public IPv4 | 0,005 | 3 s | ~0,02 |
| S3 + istekler + çıkış trafiği (<100 MB) | — | — | < 0,05 |
| **Toplam üst sınır (vergi hariç)** | | | **≈ 5,3** |

Beklenen tipik toplam ~3 USD. AAOS başlatılmaz. Fatura ölçümü değildir.

### 7.4 Ortam ve runtime farkları (kayda geçecek)

- Aynı: Python 3.11.17, chatterbox-tts 0.1.7 @ `5de7a54` (50 dosya hash'i
  `verify_runtime_source` ile), transformers 5.2.0, safetensors 0.5.3. Altı model
  dosyası HF `ResembleAI/chatterbox` @ `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`'den
  indirilir ve WEB'deki SHA-256 değerleriyle (`runtime-preflight.json`) eşleşmezse durulur.
  Referans `LJ001-0001.wav`, pinned GitHub URL'sinden alınır ve
  `4d2bd83f…86dc5` ile doğrulanır. Diğer paketler WEB'deki `pip freeze` ile eşlenir.
- Farklı: `torch/torchaudio 2.6.0+cu124` (CPU'da `+cpu`), CUDA/cuDNN/sürücü, host CPU,
  config'te yalnız `"device": "cuda"`. Config hash'i bu nedenle WEB'dekinden farklı
  olur; fark diff olarak kaydedilir. TF32 kapalı. Quantization veya düşük hassasiyet
  yok.
- WEB'de ürün dosyalarına dokunulmaz. Probe ve dal worker'ı `/var/tmp/attune-latency-…`
  altına kopyalanır; ürün servisleri yeniden başlatılmaz.

### 7.5 Ölçüm sırası

- **WEB (CPU), GPU kurulumuyla paralel.** Uygulama hesabı, 4 thread, seed 42–51 ×
  6 metin = dil başına 20 segment/koşu.
  - R1 `official-default`
  - R2 `female-calm-v1` (bayrak kapalı)
  - R3 `female-calm-v1` (bayrak açık; R2 ile WAV SHA eşitliği beklenir)
  - R4 ters sıra kısa kontrol: seed 42–43.
- **GPU.** Aynı R1–R3 ve R4.
  - Isınma ayrı satırda: model yükleme, CUDA bağlam, ilk çağrı.
  - Yeniden derleme veya ayıklama yok. Yavaş satırlar silinmez.
- Raporlanacaklar: sıra, örnek sayısı, host load, CPU-saniye, RSS ve GPU tepe belleği.

### 7.6 Kalite ve bütünlük

- CUDA RNG CPU'dan farklı olduğu için aynı seed CPU ile GPU'da **farklı token
  dizileri** üretir. Byte veya PCM eşdeğerliği beklenmez. Karşılaştırma RTF, ms/token
  ve ses-saniyesi başına decoder süresi üzerinden yapılır.
- Objektif kontroller: WAV biçimi, süre/token dağılımı, tam-ölçek örnek sayısı, RMS ve
  sessizlik oranı. İsteğe bağlı olarak ayrı onayla, yalnız değerlendirme için Whisper
  ASR ile EN/DE/TR kelime eksiksizliği (WER/CER).
- Dinleme: eşleşmiş CPU/GPU örnek paketi (dil başına ≥3 çift) sahibin dinlemesi için
  hazırlanır. **Dinleme yapılmadıkça kalite eşdeğerliği iddia edilmez.**

### 7.7 Kapatma ve temizlik

- Normal akış: kanıt S3'e → yerelde SHA-256 doğrulaması → GPU `TerminateInstances` →
  SG silme → bucket boşaltma/silme → WEB `StopInstances`.
- API ile nihai doğrulama:
  - GPU `terminated`, WEB ve AAOS `stopped`.
  - Etiketli volume/SG/bucket kalmadı.
  - Etiketli çalışan instance yok.
- Oturum koparsa:
  - GPU en geç T+150 dk'da kendini sonlandırır; disk birlikte silinir.
  - WEB T+105 dk'da durur.
  - Kalabilecek ücretsiz/kuruşluk kaynaklar (SG, S3 bucket) `Purpose=attune-mental-tts-gpu-20261109`
    etiketiyle bulunur ve sonraki oturumda silinir.
- Kapasite veya kurulum hatasında en fazla bir yeniden deneme yapılır, sonra
  raporlanır. Kota artırımı veya başka bölge ayrı onaydır.

### 7.8 Gereken erişimler

- Bu oturuma **süreli STS kimliği**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `AWS_SESSION_TOKEN` ortam secret'ı olarak. Ayrıca `AWS_DEFAULT_REGION=eu-central-1`.
  Anahtarlar sohbete veya Git'e yazılmaz.
- Rol izinleri:
  - Okuma: `sts`, `ec2:Describe*`, `servicequotas:GetServiceQuota`, `pricing:GetProducts`
  - WEB: `ec2:StartInstances` / `StopInstances`
  - GPU: `ec2:RunInstances`, `TerminateInstances`, `CreateTags`, `CreateSecurityGroup`,
    `DeleteSecurityGroup`; WEB profili için `iam:PassRole`
  - SSM: `ssm:SendCommand`, `ssm:GetCommandInvocation`
  - S3: `s3:CreateBucket`, `PutBucket*`, `GetObject`, `DeleteObject`, `DeleteBucket`
- 3 Kasım kaydında daha geniş tip değişikliği IAM tarafından engellenmişti. İzinler
  başlatmadan önce `DryRun` ile doğrulanır.
- GPU host'tan çıkış: PyPI, `download.pytorch.org`, GitHub, Hugging Face. Bu oturumun
  ağ izinleri değişmez; indirmeler instance üzerinde yapılır.

## 8. Ürün seviyesi sınırlar

Bu çalışma ürünün ilk sesini veya parça arası boşluğunu ölçmedi; sentez hızlanmasını
ürün iyileşmesi olarak sunmuyorum. Ürün iddiası için şunlar gerekir: seçilen değişikliğin
onaylı deploy'u, tarayıcı/akustik ilk oynatma ve boşluk dağılımı (TR/EN/DE) ve
PARK/DRIVE, consent/mute, kriz önceliği, iptal ve 429 regresyonları. Maske mantığı,
güvenlik kontrolleri, ses kimliği ve iptal mekanizması bu dalda değişmedi.
