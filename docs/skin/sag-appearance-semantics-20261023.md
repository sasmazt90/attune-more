# Sarkma görünümü semantik sözleşmesi — 2026-10-23

## Sonuç

Mevcut alt yüz ölçümü bir öğrenilmiş lokal sarkma segmentasyonu veya elastikiyet ölçümü değildir. Ürün akışı bunu yalnızca görünür alt yüz kontur/kıvrım görünümü olarak taşır.

Zorunlu sözleşme:

- `appearanceSemantics = visible-lower-face-contour-fold-appearance-v1`
- `clinicalSeverity = false`
- `elasticity = false`
- `comparisonMode = same-person-compatible-capture-only`

Frontend, `sag` ölçümünde bu dört alan eksik veya farklıysa `INVALID_SAG_SEMANTICS` ile sonucu reddeder. Kullanıcı metni de elastikiyet ve klinik sarkma şiddeti iddiasını açıkça dışlar.

## Kapsanan akışlar

- Bölgesel cheek/chin üretimi: `services/core-api/instant_appearance.py`
- Ön yüz overview toplaması: `services/core-api/skin_general.py`
- Normal üründe kapalı araştırma kontur dalı: `services/core-api/contour_appearance.py`
- Ürün istemci kabul kapısı: `apps/vehicle-app/src/utils/appearanceMeasurements.ts`

## Doğrulama

Beş değişen Python kaynak/test dosyası derlendi. Overview toplamasında semantik alanların üretildiği ve eksik bölgenin yine bilinmeyen kaldığı çalıştırıldı. Frontend kapısının doğru sözleşmeyi kabul edip `elasticity=true` kaydını reddettiği odaklı davranış kontrolü geçti. Çalışma ortamında TypeScript derleyicisi olmadığı için tam frontend derlemesi bu çalıştırmada tekrarlanmadı.

## Kabul sınırı

Bu değişiklik Task 12’yi tamamlamaz. Poz/ifade dayanıklılığı için bağımsız gerçek kamera örnekleri, aynı kişi uyumlu çekim çiftleri, uzman semantiği ve uygun truth hâlâ gereklidir. Mevcut vekil öğrenilmiş lokal segmentasyon, doku elastikiyeti, doku hacmi veya klinik şiddet olarak sunulamaz.

Kalıcı kanıt: `docs/skin/evidence/sag-appearance-semantics-20261023-v1.json`
