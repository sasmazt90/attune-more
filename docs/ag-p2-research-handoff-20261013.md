# AG sivilce P2: yalnız araştırma devri

Dondurulmuş commit `2d43cc62fe5e556e6a2889674a86b9857574b475` bir Git commit nesnesi olarak doğrulandı. Paket: `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin\audit-results\acne-candidate-p2-epoch02-cdc-delivery`; manifest `delivery-manifest.json`. Hareketli AG kodu/weights değiştirilmedi, paket yeniden üretilmedi, inference veya yeni sivilce eğitimi yapılmadı.

| Nesne | Tüm yerel byte'lardan SHA-256 | Boyut | Manifest ile eşleşme |
|---|---|---|---|
| Epoch 2 weights | `cf3a2ba4af5064c76391eadda5b7fd0d3cf39c32e864ec7ef8c47ee325e9123f` | 38.884.916 byte | Evet |
| Yeni ONNX | `2534ac5e9545aaba094828e685256a978e195a72afd57692f20d9e7259b03fe1` | 38.782.996 byte | Evet |

Manifestin bildirdiği YOLOX-S P2, stride [4,8,16,32], 384 tensor / 12.240 anchor sözleşmesi kaydedildi; bu görev mimariyi veya tahminleri yeniden test etmedi. conf=0,30: **15/53 IoU50**, 15 negatif fotoğrafta **3 FP**, <8 px odaklarda **0/7**. Bu bildirilen araştırma sonucudur; normal ürün doğruluğu veya etkin model değildir. `accepted:false`, `file:null` korunur. Ana checkout'a yeni AG graph/weights/config taşınmadı.

Mevcut ONNX kanıtının aynı toplam TP/FP vermesi **kutu kutuya eşleşme kanıtı değildir**. Gelecekte olası entegrasyondan önce gerçek yüz karolarında ayrı score ve coordinate toleransları, source-coordinate box matching, confidence ve NMS sınırındaki aday davranışı tamamlanmalıdır. Eski ağırlığın yeni P2 grafiğe sessiz yüklenmesi kabul edilmeyecek. Bu açık, kuruluk/sarkma görevine yeni sivilce kampanyası olarak eklenmedi.

`dualLockEnforced` alanı bağımsız güvenlik kanıtı sayılmadı. Gerçek kilit açıkları ve sonraki ortak sözleşme `heavy-compute-handoff-20261013.md` içindedir.
