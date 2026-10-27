# Bölgesel replay için fotoğraf saklama kapısı

`skinPhotoHistory`, bölgesel özet taşıyan saklanan fotoğrafları artık ekrandakiyle aynı `retainedRegionalSkinReplay` sözleşmesinden geçiriyor. Böylece başka fotoğrafa ait `photoId`, kaynak boyutu, FRONT poz, kırpım veya mesh koordinatı içeren katman verisi IndexedDB'ye yazılmıyor.

Yükleme tarafında önce kayıt boyutu ve SHA-256 doğrulanıyor, ardından tipli diziler geri kuruluyor ve aynı replay doğrulaması tekrar çalışıyor. Sözleşmeyi geçmeyen satır mevcut hata akışıyla siliniyor ve sonuç gösterilmiyor. Bölgesel özet içermeyen mevcut fotoğraf kayıtlarının davranışı değiştirilmedi.

Dört gerçek sunucu özeti, üç kaynak en-boy oranı ve bozuk kimlik/kırpım/mesh örnekleriyle toplam 82 kontrol geçti. Tam IndexedDB tarayıcı testi repoda genişletildi; bu çalışma ortamında Python Playwright ve Chromium bulunmadığı için burada çalıştırılmış sayılmadı.

Makine-okunur kanıt: `docs/skin/evidence/regional-photo-storage-gate-20261023-v1.json`.
