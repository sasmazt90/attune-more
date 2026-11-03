# PR #21 → Task 13 AWS uzlaştırması

İncelenen PR #21 başı: `c7f2168306797e4c0856d4f1dd7dbcd33f0d0f04`.
`cad318d`, `885cfdc`, `c7f2168` yalnız `codex/aws-oem-demo-20261103` dalına alındı.
Main ve Claude'un dalı değiştirilmedi; PR #22 Draft kalır.

| PR #21 değişikliği | AWS karşılığı |
|---|---|
| ONNX spin kapatma, OMP passive wait | G6 Linux worker aynı sınırlı thread sayılarıyla kullanır; model/90 saniye deadline değişmez |
| Windows worker/QEMU above-normal priority | Windows koşulu korunur; Linux nice/CPU politikası uydurulmaz, iki hostta gerçek yük altında ölçülür |
| LOCAL_MEMORY_RESERVE 503 ve TR/EN/DE mesajı | Ayrı hata kodu ve mesaj AWS sürümünde korunur; 400 MiB reserve değişmez |
| Native localeReadPending reset | cloudDemo MainActivity içine uzlaştırıldı; cloud işareti ve gate davranışı korunur |
| QA harness | Kaynak ve sentetik/mocked sınırları korunur; yerel PASS AWS PASS'e taşınmaz |

AWS QA için `infra/aws/aaos/qa-config.example.json` yalnız M8i üzerinde kullanılır.
`webview.cjs` bu config ile IMDSv2 host kimliğini doğrular, cloudDemo paketini ve
`127.0.0.1:3000` same-origin proxy'yi kullanır. `ATTUNE_QA_BUILD_ID` G6'da üretilmiş
Next BUILD_ID değeridir; `ATTUNE_QA_SHA` kurulan commit'tir. ADB devtools localhost'ta
kalır. Bu config'te QA helper yerel backend başlatamaz; lifecycle deneyi gerekiyorsa
G6'daki doğru systemd birimi SSM ile ayrı, gözlenebilir işlemle yönetilir.
Windows `aaos_session.py` AWS boot için kullanılmaz; `infra/aws/aaos/run.sh` kullanılır.

PR #21 Mental mock sağlayıcısı, scripted recognizer ve injected kamera testleri
yalnız harness sınırını doğrular. Bunlar tam OEM kabulü değildir. Vision'daki önceki
PARTIAL ve Hearing/Mental gerçek giriş açıkları AWS üzerinde yeniden doğrulanır.
Cloud Vision iki akışı da artık Skin/Dental ile aynı açık eşleştirmeli kamera
köprüsünü kullanır; geometri, freshness ve native güvenlik eşikleri gevşetilmez.

Yerel 40 odaklı Python kontrolü (mevcut kaynak guard'ları, PR #21 worker ve native
contract, route/origin) geçti. TypeScript ve route/error kontrolleri geçti.
Bu kontroller AWS runtime, gerçek model paritesi veya gerçek cihaz kabulü değildir.
Son birleşik commit için CI sonuçları PR #22 ve güncel kanıt kaydında tutulur.
