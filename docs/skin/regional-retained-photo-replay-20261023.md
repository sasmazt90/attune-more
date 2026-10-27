# Saklanan fotoğraf için bölgesel kaynak-piksel replay sözleşmesi

## Sonuç

Mevcut `SkinFacePanel`, bölgesel özet katmanını artık doğrudan gevşek snapshot alanlarından üretmiyor. `retainedRegionalSkinReplay` tek bir kapıda aşağıdakileri birlikte doğruluyor:

- sağlık kaydıyla ilişkili PNG fotoğraf ve 64 karakterlik `photoId`;
- FRONT poz ve kaynağın gerçek genişlik/yüksekliği;
- bölgesel özetin aynı `source-pixels` kimliğine bağlı olması;
- kaynak sınırları içindeki görüntü kırpımı;
- çizilecek her bölgenin sonlu, kaynak ve kırpım sınırları içindeki mesh noktaları.

Bu koşullardan biri bozulursa katman çizilmiyor. Yerel piksel haritalarının önceliği korunuyor. Fotoğraf veya başka ham kişisel veri Git'e eklenmedi.

## Doğrulama

Dört gerçek Python sunucu-özet fikstürü ve portre `720×1280`, yatay `1280×720`, kare `900×900` kaynak senaryoları toplam 78 çalıştırılabilir kontrolden geçti. Yanlış fotoğraf kimliği, sınır dışı kırpım/mesh ve harici görüntü URL'si kapalı kalma davranışıyla reddedildi. Bileşenin replay planından gelen kaynak kimliği ile `viewBox` kullandığı statik sözleşmeyle korundu.

Gerçek tarayıcı çalıştırması tamamlanmış sayılmadı: yerel Playwright kitaplığına karşılık Chromium ikilisi yoktu; bulut tarayıcısı da inline/local test sayfasını protokol güvenlik politikasıyla reddetti. Politika aşılmadı. Gerçek saklanan fotoğraf ekran görüntüsü replay'i, tam uygulama tip kontrolü ve bağımsız kamera kabulü açık kalmaya devam ediyor.

Makine-okunur kanıt: `docs/skin/evidence/regional-retained-photo-replay-20261023-v1.json`.
