# Tüm-yüz ordinal / lokal sarkma ayrımı — 2026-10-23

## Kapatılan hata yolu

Genel öğrenilmiş derece döngüsü, manifest’e ileride `sag` eklenirse lokal kontur/kıvrım değerini tüm-yüz ordinal skorla değiştirebiliyordu. Ardından overview kodu analitik lokal sarkma haritasını aynı satıra bağlayabiliyordu. Böylece skor ve harita farklı yöntemlerden geldiği halde tek lokal sonuç gibi görünebilirdi.

Bu yol artık kapalıdır:

- Generic tüm-yüz ordinal `sag`, lokal kontur/kıvrım sonucunu değiştiremez.
- Lokal görünüm değeri ve kendi analitik haritası korunur.
- Engellenen aday, `WHOLE_FACE_ORDINAL_CANNOT_REPLACE_LOCAL_SAG` nedeni ve aday scope’u ile kaydedilir.
- Bir tüm-yüz model satırı yine de oluşursa overview sarkma haritası ayrıca bağlanmaz.
- Diğer tüm-yüz ordinal başlıklarda ilgisiz analitik lokal harita temizlenir.

## Mevcut ürün etkisi

Mevcut kabul edilen ordinal model yalnız `redness` hedefini içeriyor; `sag` kabul edilmiş bir hedef değildir. Bu nedenle düzeltme mevcut merged sarkma çıktısını veya kullanıcı skorunu değiştirmez. Gelecekteki sessiz yöntem karışmasını engeller.

## Doğrulama

`skin_product_contract.py`, `appearance_analysis.py` ve ilgili test dosyası Python derlemesinden geçti. Paylaşılan ürün sözleşmesindeki sekiz davranış kontrolü geçti; bunlar tüm-yüz ordinal sarkmanın reddini, lokal değerin/haritanın korunmasını, diğer tüm-yüz derecelerde analitik haritanın temizlenmesini ve gerçek ürün akışının politika yardımcısını çağırmasını kapsıyor.

## Kabul sınırı

Bu, Task 12’nin veri kabulini tamamlamaz. Bağımsız kamera çiftleri, uzman lokal truth, poz/ifade dayanıklılığı ve gerçek lokal model değerlendirmesi hâlâ gereklidir. Bir lokal sarkma modeli ileride kabul edilirse generic tüm-yüz derece başlığından değil, kendi lokalizasyon sözleşmesi ve kanıt paketi üzerinden entegre edilmelidir.

Kalıcı kanıt: `docs/skin/evidence/sag-ordinal-local-separation-20261023-v1.json`
