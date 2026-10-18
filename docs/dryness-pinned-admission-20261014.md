# Dondurulmuş kuruluk paketi — kabul engeli

**Yeni head normal üründe etkinleştirilmedi.** Mevcut kuruluk v3, kaynak commit `72b90172084711cd200637cedab831f80e3fb973` ve BUILD_ID `9DheD3msEFSOMhjMp-kK8` korundu. Üretim kaynakları/config/model seçicisi değiştirilmedi; yeni build, model eğitimi veya hosted çağrı başlatılmadı. Başarısız kabul normal ürün entegrasyonu olarak sunulmaz.

## Sabit teslim kimliği

Kaynak referans commit `1db3cfdddbdcb0846b9219865d31cc5547413296` Git deposunda mevcut. Ancak istenen üç teslim dosyası bu commit'in Git ağacında yoktur. Dosyalar kullanıcının açık SHA-256 sabitlemesiyle okunup kendi `audit-results/dryness-integration-20261014/delivery-snapshot` klasörüne alınmış, yazılan byte'lar yeniden doğrulanmıştır. Git blob'undan gelmiş gibi gösterilmemiştir. AG çalışma dosyaları değiştirilmedi ve üretimde AG `sys.path`/dosya bağımlılığı oluşturulmadı.

| Dosya | Doğrulanan SHA-256 |
|---|---|
| calibrated-source-group-head.json | `a668840c2cd568bf91a03ad274a0def97c1185bb22f7856a9c504eeb01571c72` |
| dryness-head-comparison.json | `a946e65c2a10d8d5e1d374296cb19239e806029167c440cf0e00ec4a6939b75b` |
| cdc_skin_adapters.py | `711e8e8695cb89a89a2de45cc2d684798599106421e443a31625f0f94e75154a` |

Manifestte `workspaceContext.agHeadCommit=0d59361ee4500d0113739e983d73edf1034a6ad1`; gerçek istenen commit ile uyuşmaz. Aktarım makbuzunda ikisi ayrı kaydedildi. Adaptörün yalnız kuruluk sınıfı incelendi; sarkma/sivilce sınıfları veya dosyaları ürün koduna taşınmadı.

Head: threshold 0,50; C 0,15; `source-group-balanced-calibrated-v2`; TRAIN 63 satır; visual/geometry scaling 3,0/0,4; positive weight multiplier 3,0. Ölçekler head'in std vektöründe zaten uygulanmış; inference'ta ikinci defa uygulanmadı. Yeni fit yapılmadı.

## Aynı etiket kapsamının yeniden ölçümü

Mevcut bileşen/crop sırası eski cache imza SHA'sıyla doğrulandı. Cache yalnız çevrimdışı 21 etiketli alanın karşılaştırması için kullanıldı; kamera hızı veya normal API kanıtı sayılmadı. TRAIN/validation grupları, mevcut objectHit tanımı, proposal ve kaynak ölçeği değişmedi. Poligon dışı UNKNOWN kaldı. Fotoğraf düzeyi etiket bütün bileşenlere yayılmadı.

| Kapsam | Pozitif yakalama | İncelenmiş negatif destek |
|---|---:|---:|
| Native, TRAIN + görülmüş validation | **14/21** | **151 kaynak pikseli** |
| Native, validation negatifleri | Ayrıntı JSON'da | **0** |
| Yarım kaynak, aynı alanlar | **13/21** | **0** |
| C08 obj0, native | Yakalandı; bilinen pozitif poligonda **71 piksel** | Uygulanamaz |

AG karşılaştırma dosyasındaki `neg_1_va_pixels=0` validation'a özgüdür. Bütün incelenmiş negatiflerde sıfır anlamına gelmez. Ek yanlış destek C04 / `1d6c1b3cfd5fa2e22a85604bf20ae1b8ce35a0bf8c31abfa91851f4b9ff2a39a` kaynağında, native TRAIN'dedir. Kaynak CLAHE işlenmiştir; doğal kamera performansı veya bağımsız final test değildir. Aynı işlenmiş kaynak kapsamındaki olumsuz sonuç ayrıca gösterilir, kapsamdan çıkarılıp kazanım sayılmaz.

## Taze encoder ve kaynak koordinatı teşhisi

Mevcut doğrulanmış yerel encoder, yeni fotoğraf özellik cache'i olmadan yalnız bu iki ilgili bileşenin gerçek yakın/çevre crop'larında çalıştırıldı. Kaynak safetensors bütün dosya SHA'sı `e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a`; gerçek ORT dosyası `a93e5445326c8071cd4d013b6fde494d9054dd4842dacf97028ceaefc9eb1987`. Önceki export/parity makbuzu eşleşti; export veya indirme tekrarlanmadı.

| Kontrol | Bileşen / kaynak kutusu x,y,w,h | Taze p | Cache p | En büyük feature farkı |
|---|---|---:|---:|---:|
| C04 bilinen negatif | 29 / `[392,347,58,41]` | 0,52700686 | 0,52700826 | 0,00002971 |
| C08 obj0 materyal | 50 / `[35,292,21,17]` | 0,59049502 | 0,59050461 | 0,00004900 |

Head her iki durumda da aynı sabit dosyadır. C04 sınıflandırıcısının kabul ettiği desteğin 151 pikseli mevcut **incelenmiş negatif poligonun içindedir**; kutunun geri kalan bilinmeyen alanları yanlış tespit sayılmadı. C04 görselinde bu destek burun deliği/kenarındaki parlak doku üzerindedir. C08 pozitif bileşeninin 71 piksellik yerelleştirmesi kaynak konumuyla eşleşir. Bunlar tam ROI segmentasyon doğruluğu/Dice veya biyolojik kuruluk şiddeti değildir.

Normal anatomik görünürlük ve çekim kapıları ayrı kapsamdır: bu ham bileşen yanlış desteği tek başına normal ürün haritasında 151 piksel yanlış işaretleme oluştuğunu kanıtlamaz. Ancak istenen bütün incelenmiş negatiflerde sıfır head kabulü yeniden üretilemedi. Yeni pozitif için poligon doldurma, eşiği fotoğrafa göre değiştirme veya C04'ü etiketsiz/sağlıklı sayma yapılmadı. Kaynak/head/encoder aktarım hatası kanıtı bulunmadı; olumsuz karar aynı head/feature/eşikle taze inference'ta yeniden üretildi.

Encoder ilk yükleme 0,422 sn; C04 iki crop 0,079 sn, C08 iki crop 0,047 sn. **Bunlar encoder alt adımıdır; yeni head'in normal API ilk/sonraki istek süresi veya 45 sn kabulü değildir.** Ön kontrol başarısız olduğundan yeni head'le normal API/Genel Bakış/harita/geçmiş ve production build teslimi yapılmadı; eski teslimin kontrolleri yeni head'e mal edilmedi.

## Karar ve kalan adım

Aktivasyon engeli: sabit head, mevcut incelenmiş C04 negatifini threshold 0,50'de kabul ediyor. Verilen hash ve feature sözleşmesini korurken bu ölçümü sıfırmış gibi raporlamak doğru olmaz. Yeni paket veya doğrulanmış genel düzeltme bu aynı kontrolü de karşılamadan normal seçici etkinleştirilmemeli. Validation'daki sıfır, TRAIN hatasını gizlemek için kullanılmamalı.

Bu rapor bir kuruluk teslimi değildir. Başarılı paket geldiğinde normal ürün seçicisi, açık head/encoder ürün config'i, yeni yöntem/sampling kimliği, birleşik benzersiz kaynak paydası ve gerçek soğuk/sıcak normal kamera API/harita/geçmiş zinciri hâlâ tamamlanmalıdır. AG sarkma/sivilce değişiklikleri bu iş kapsamında alınmadı. Kullanıcı kayıtlarına, önceki raporlara, seslere, diğer yöntemlere veya uygulamalara dokunulmadı.

Yerel ayrıntılı kanıtlar:

- `audit-results/dryness-integration-20261014/delivery-snapshot/transfer-receipt.json`
- `audit-results/dryness-integration-20261014/reviewed-head-replay.json`
- `audit-results/dryness-integration-20261014/C04-C08-fresh-encoder-diagnosis.json`
- `audit-results/dryness-integration-20261014/C04-reviewed-target-and-accepted-support.png`
- `audit-results/dryness-integration-20261014/C08-reviewed-target-and-accepted-support.png`
