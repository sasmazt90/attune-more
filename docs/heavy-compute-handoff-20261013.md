# CDC / AG ağır-iş devir sözleşmesi

AG'nin `2d43cc62fe5e556e6a2889674a86b9857574b475` sürümündeki `heavy_job_lock.py` incelendi; dosyası değiştirilmedi. `check_cdc_lock` kendi busy RuntimeError'ını genel except ile yutabiliyor ve AccessDenied süreç yokmuş gibi değerlendiriliyor. Manifestteki `dualLockEnforced:true` **güvenlik kanıtı değildir**.

CDC artık şu iki yolu sabit sırada **gerçekten sahiplenir**; yalnız iki dosyanın varlığını kontrol etmekle yetinmez:

1. `C:\Users\PC\Desktop\AI Workspace\TOGG\coordination-notes\heavy-compute.lock.json`
2. `C:\Users\PC\Desktop\AI Workspace\TOGG\heavy_job.lock`

İki exclusive-create tamamlanmadan ağır iş başlamaz. İkinci create yarışını kaybederse yalnız kendi tam ve kimliği doğrulanabilir ilk lease'i bırakır. Yabancı, eski, bozuk veya yarım lease otomatik silinmez. İki dosyada aynı `pid`, gerçek `processStarted`, çözümlenmiş gerçek `workspace`, `jobId` ve rastgele `nonce` bulunur. PID yeniden kullanımı, farklı workspace/job/nonce, okunamama veya AccessDenied ağır işe giriş reddidir. `startTime` uyumluluk alanıdır; process creation time yerine tahmini job-clock kullanılmaz.

Mevcut sahiplik ön kontrolde gerçek Windows process PID/name snapshot'ı, creation time ve process CWD / gerçek script yolu ile doğrulanır. Inline Python metninde geçen AG yolu sahiplik değildir. Python/node/ffmpeg adaylarında AccessDenied yokluk olarak yorumlanmaz. Başlangıç denetiminde AG ağır süreçleri görülmedi; başka projelerin süreçleri yönetilmedi.

Çalışma sırasında iki lease tekrar doğrulanır. Ayrı **salt-okunur, CDC tarafından yaratılmış** gözlem süreci her 0,25 saniyede process sahipliği tarar; parent PID/creation time/nonce bağlı cevabın yaşı en çok 1 saniyedir. Tarama hatası, yanlış kimlik veya eski cevap analiz için durma nedenidir. Inference thread'inde psutil'in Windows process/thread sayımının takıldığı stack kaydı bulundu; yalnız iş sınırlarında tarama önerisi otomatik güvenlik incelemesince reddedildi ve uygulanmadı. Sürekli gözlem korundu; Windows Toolhelp PID/name snapshot'ı kullanılarak psutil `pids()` takılması atlandı. Process creation/CWD yetki kontrolleri korunur. Canlı salt-okunur gözlem denetimi başarılıdır.

Kapanışta yalnız kendi lease'leri bırakılır; gözlemci bunların kalkmasını izleyip doğal çıkar. Gözlemci takılırsa yalnız CDC'nin bu işte yarattığı, creation time'ı doğrulanan salt-okunur helper durdurulabilir. Trainer/AG süreçleri veya başka uygulamalar kapatılmaz. RAM rezervi en az 400 MiB'dir; her işin RSS veya private-memory bütçesi makbuzda açık yazılır. Çok-process RSS ortak sayfaları birden fazla sayabilir; private ölçüm kullanılsa da gerçek kullanılabilir RAM rezervi ayrıca korunur.

Alt süreçlerin parent kimliği de tek Windows process handle'ı üzerinden sorgulanır; global `ppid_map` takılması tekrar kullanılmaz. Kısa salt-okunur gözlemci `ABOVE_NORMAL`, yalnız CDC build/test alt süreçleri `BELOW_NORMAL` önceliğindedir. CPU/SWC/Rayon paralelliği 1 ile sınırlıdır; bir saniyelik gözlem yaşı veya 400 MiB rezerv gevşetilmemiştir. Production build başlangıcı için 1.300 MiB kullanılabilir RAM gerekir. Kesinti sonrası tek 180 saniyelik beklemede bu koşul oluşmadı (son ölçüm 523,99 MiB); yeni build başlatılmadı. CDO'nun depolama/RAM bakımına veya kullanıcı uygulamalarına müdahale edilmedi.

**AG'nin sonraki işi için gerekli düzeltme:** aynı sabit acquire sırasını ve v2 kimliğini kullan; busy/parse/permission hatalarını genel except ile geçme; AccessDenied'i yokluk sayma; foreign/stale lease'i otomatik kaldırma; yalnız kendi PID + creation + workspace + job + nonce eşleşmesinde release et. CDC kaynaklarını AG alanına kopyalamak veya bu notu AG tarafında uygulanmış saymak doğru değildir. AG manifesti bu düzeltme doğrulanana kadar koordinasyon kabulü sağlamaz.
