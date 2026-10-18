# Yerel deneysel sivilce V5 fotoğraf önizlemesi — 2026-10-17

Ayrı worktree: `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-cdc-acne-v5-integration`.
Dal: `research/acne-v5-integration-20261017`. Başlangıç `5f11c111e3f6547e6420ddf37db477190d232f10`, temiz çalışma durumu; dondurulmuş araştırma `cb0948fa2ebc98eb69d22d1b7079752b69ae6cfb`.
Normal ürün/Claude/AG/araştırma kaynakları salt okunur tutuldu; dört HEAD/çalışma durumu ve üretim manifest hash'i `preservation.json` ile yeniden doğrulandı. Push/merge/genel üretim aktivasyonu yapılmadı.

## Açma ve kullanma

PowerShell'de tek komut:

```powershell
& "C:\Users\PC\Desktop\AI Workspace\TOGG\attune-cdc-acne-v5-integration\Start-Acne-V5-Preview.ps1"
```

Önizleme `http://127.0.0.1:3305/skin`, normal yerel API yolu ayrı 8305 portundadır. Fotoğraf seçin, fotoğrafın gerçek pozunu seçin, yalnız yerel işlemeye izin verin, **Fotoğrafı analiz et** düğmesine basın. Canlı kamera kullanılmaz. Tek yüz, mevcut kalite/poz ve gerçek gözlük kapısı gereklidir. Sonuç “sivilce adayı” olarak küçük noktalarla gösterilir; kutu, gradyen, şiddet veya doğruluk yüzdesi gösterilmez. Sonuç geçmişe yazılmaz; fotoğraf yalnız istek ve tarayıcı belleğinde tutulur. İzin geri çekilmesi, yeni dosya ve iptal eski sonucu temizler.

Başlatıcı mevcut normal Windows kısayoluna dokunmaz. Kendi PID/başlangıç zamanı/komut satırı makbuzuyla süreçleri doğrular; başka port sahibini kapatmaz. Yerel mevcut Node/Python bağımlılıkları kullanılır; node_modules bağlantıları salt okunur kullanım içindir, kurulum yapılması amaçlanmaz. Build/source/bundle ve model hash'i uyuşmazsa başlatıcı durur. Kullanıcı başlangıcında sayısal doğrulama izi kapalıdır.

Geri alma: `Stop-Acne-V5-Preview.ps1` yalnız bu önizlemenin kimliği doğrulanmış süreçlerini durdurur. Normal üründe geri alınacak aktivasyon veya kullanıcı kaydı değişikliği yoktur.

## Dondurulmuş model ve gerçek zincir

- Step0 SHA256: `18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655`.
- V5 SHA256: `0d7bf03ca4d9898ef1b2e78c6d54d61be6aff580329b20b78a9232f79cfd43bb`.
- V5 eşik: `0.15628215094908582`; özellik tanımı 1920 değer, standardizasyon ve lojistik işlem değişmedi.
- Sunulan ONNX SHA256: `9c87475d9302aed16f09abedc109211c2ac1b49f22f465f86aab408a5244d0be`.
- BUILD_ID: `gqtoifbRplhq0MXxiYb0r`.

Yeni seçilmiş ham dosya -> gerçek browser MediaPipe -> gerçek FRONT/RIGHT/LEFT koşulları/kalite/gözlük -> mevcut snapshot/origin/mesh/exclusions -> normal `/api/local-health/skin` endpoint'inde açık deneysel seçim -> aynı tile forward'dan Step0 kutuları ve P2/P3/P4/P5 -> obj*cls>=0.30 -> değişmeyen Hard-NMS 0.30 -> mevcut gerçek anatomik/hair filtre -> aynı-forward özellikleri -> V5 -> aynı final liste/API/sayı/noktalar. Hazır sonuç veya saklı landmark demo girdisi yoktur. Snapshot doğal kaynak çözünürlüğünü korur; yalnız normal kameradaki <=640 genişlikli kalite/landmark görüntüsü kullanılır. Yanlarda önden bakış `isAligned` şartı aranmaz; gerçek `matchesSkinAngle` koşulları kullanılır.

Runtime yalnız mevcut ONNX Runtime/NumPy yolunu kullanır. Doğrulanan API işlemlerinde `trainingFrameworkLoaded:false`; tile sayısı detector forward sayısına eşittir (ön 12, sağ 9). Normal üretim manifest'i `accepted:false, file:null` kalır. Modül/env varsayılanı kapalıdır; yalnız ayrı önizleme başlatıcısı opt-in açar.

## Parite ve düzeltilen export hatası

Toleranslar koşudan önce `protocol.json` içinde sabitlendi: kaynak koordinatı 0.05px; obj/class/score 1e-5; özellik atol0.003/rtol0.0001; V5 olasılık atol1e-4; tile/anchor kimliği, sayılar ve kabul kararları bire bir.

İlk export kontrolünde karışık birimli ham çıktı matrisine tek özellik toleransı uygulanmıştı. Test eşlemesi, zaten önceden kaydedilmiş koordinat ve olasılık toleranslarına ayrıldı; toleranslar değiştirilmedi. İlk iki başarısız makbuz korundu.

Tam zincirde ayrıca somut ORT Sigmoid sayısal hatası bulundu: negatif SiLU kuyruğundaki yaklaşık -1.43e-8 yanıt sıfırlanıyor, V5'in 7.893e-8 standardizasyon ölçeği farkı büyütüyordu. Olasılık farkı 0.0032524 idi. ONNX'te aynı sigmoid `1/(1+exp(-x))` biçiminde ifade edilerek küçük kuyruk korundu. 99 Sigmoid node eşdeğer işlemlerle yazıldı; özgün öğrenilmiş initializer'ların tamamı byte düzeyinde aynı, yeni olanlar yalnız scalar 1 sabitleri. Eğitim, parametre, eşik, özellik tanımı veya NMS değişmedi.

Son araştırma/runtime karşılaştırması **aynı gerçek browser payload'ları** üzerinde geçti: tile/anchor sırası, adaylar, kararlar bire bir; azami kutu farkı 0.0000344 kaynak pikseli; azami V5 olasılık farkı 0.00000209. Son build'in yeni gerçek istekleri, bu geçen parite sonuçlarıyla aynı özellik/olasılık/kararları üretti. Tüm 38 sunulan JavaScript dosyası yerel build hash'iyle eşleşti.

## Son build: aynı istekli tarayıcı/API sonuçları

| Kaynak / poz | Son aday / ekran noktası | İlk V5/Step0 yükleme | API toplam | Fotoğraf decode başlangıcından görünür sonuca |
|---|---:|---:|---:|---:|
| 77176e51db41 / FRONT | 20 / 20 | 0.569 sn | 4.238 sn | 6.325 sn |
| 313448754ade / RIGHT | 4 / 4 | 0 (sıcak session) | 2.775 sn | 3.575 sn |
| 2236701580ba / LEFT | Sonuç yok | Çalıştırılmadı | Analiz isteği yok | Mevcut baş eğimi kapısında reddedildi |

Süre başlangıcı analiz düğmesidir; ham dosya decode, gerçek MediaPipe/eyewear, API ve görünür paint dahildir, kullanıcının dosya seçme/izin verme düşünme süresi dahil değildir. İlk yükleme yalnız detector/V5 session yüklemesidir, diğer ön kontrol maliyetleri görünür süreye dahildir. Sayılar doğruluk veya lezyon yakalama metriği değildir. Bu çalışma bütün DEV'i yeniden değerlendirmedi, yeni eşik/model seçmedi. Sağ yan gerçek poz kabulü görüldü; geçerli LEFT ile başarılı sonuç bu üç kaynaklık smoke içinde doğrulanmadı.

API işletim sistemi tepe çalışma kümesi 400,994,304 bayt (382.4 MiB); ölçüm noktalarındaki en yüksek private tahsis 947,183,616 bayt (903.3 MiB). Bunlar ayrı bellek ölçüleridir. Browser heap ve kendi süreç kimlikleri de makbuzdadır.

## Odaklı davranış kontrolleri

- Gerçek ön fotoğrafta Genel Bakış+altı bölgede API sayıları/merkezleri bire bir; gradyen yok. Dar 520px görünümde taşma yok ve nokta yarıçapı yaklaşık 3.5 CSS px, tahmin kutusu boyutundan bağımsız.
- Gerçek devam eden API isteği iptal edildi; beş saniye sonra sonuç/nokta yok, açık iptal durumu var. Fotoğraf/poz değişimi önceki noktaları temizliyor.
- Eksik model: gerçek normal API yolu 503; tarayıcıda yerel model kullanılamıyor uyarısı, düğme kapalı, sonuç/nokta yok. Kendi model dosyasının geçici yokluğu sonrası özgün hash geri doğrulandı. Kapalı mod da 503; izin yoksa mevcut politika 422, sıfır aday sonucu üretilmiyor.
- İki son gerçek istekte localStorage anahtarı/IndexedDB veritabanı/gerçek geçmiş kaydı yok; hosted izni false. Sadece seçilmiş mevcut geliştirme fotoğrafları kullanıldı.
- MediaPipe'ın ilk profilde görülen Google telemetri denemesi nedeniyle preview-only CSP eklendi; belge ve worker yanıtları sadece aynı origin ve 127.0.0.1:8305 bağlantısını kabul ediyor. Son gerçek isteklerde dış tamamlanmış istek yok; kişisel fotoğraf veya bulut inference çağrısı yok.
- `python -m pytest tests/unit/test_acne_v5_preview.py -q`: 5 geçti (3.66 sn). Typecheck ve production build geçti. Yeni lint uyarısı yok; mevcut sayfa effect bağımlılığı ve header img önerisi kaldı.
- Başlangıçta Next typegen eksik app-level @types çözümlemesi nedeniyle otomatik kurulum başlatmaya çalıştı; ekleme tamamlanmadan durduruldu (pnpm added0, iki küçük paket indirmesi bildirdi). Sonrasında mevcut app bağımlılıkları doğrudan kullanıldı. Yeni model/veri indirilmedi, eğitim bağımlılığı runtime'a eklenmedi.

## Kullanım hakları ve üretime geçiş engelleri

Mevcut YOLOX kod lisansı Apache-2.0'dır; lisans dosyası/hash'i `usage-rights.json` içindedir. Step0 yerel araştırma türevidir; kod lisansı bütün ağırlık/veri/fotoğraf haklarının temizlendiği anlamına gelmez. Üç kaynak için mevcut envanter SmartSkinCare.v8i.coco.zip yayıncı beyanını kaydeder; bireysel fotoğraf hakları ve rıza bağımsız doğrulanmış değildir. Kişi kimlikleri bilinmiyor. Bu entegrasyon ticari kullanım/yeniden dağıtım izni veya klinik/ürün kabulü değildir. Bağımsız final set ve ürün kabulü hâlâ açıktır. Bu nedenle genel üretim aktivasyonu yapılmadı.

## Kanıtların konumu

`C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\acne-v5-integration-20261017`

`status.json`, `model-hash-index.json`, `build-receipt.json`, `parity-results.json`, `final-browser-api-validation.json`, `ui-boundaries.json`, `preservation.json`, `usage-rights.json`, `api-front.json`, `api-right.json`, `screenshots/` ve yalnız kendi süreçlerinin `preview-processes.json` makbuzu. Tam geliştirme browser payload'ları worktree'nin Git dışı `output/playwright` klasöründedir; kullanıcı kayıtları veya fotoğrafları Git'e alınmadı. Son yerel commit SHA'sı `delivery.json` içinde kaydedilir.
