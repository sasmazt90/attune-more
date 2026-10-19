# Attune.more

**Kişiselleştirilmiş sağlık ve iyi oluş ön değerlendirmesi ve değişim takibi.**

Kaynak depo: [sasmazt90/attune-more](https://github.com/sasmazt90/attune-more).

Attune.more, Windows üzerinde çalışan, Türkçe arayüzlü bir sağlık ve iyi oluş uygulamasıdır. Cilt Sağlığı, Diş Sağlığı, Göz Sağlığı, İşitme Sağlığı ve Ruh Sağlığı modülleri; yerel sağlık geçmişi, hizmet bazlı izinler ve uzman/randevu yönlendirmesiyle aynı ürün içinde sunulur.

Ürün adı bir araç üreticisine bağlı değildir. Depo/klasör adlarında, eski teknik kimliklerde ve tarihli geliştirme belgelerinde bulunan TOGG/Togg ifadeleri geçmiş bağlam ve geriye uyumluluk içindir; sahiplik, resmî ortaklık veya araç entegrasyonu iddiası değildir.

## Gerçekte çalışan kapsam (REAL)

- Kamera/mikrofon tabanlı etkileşimler ve her hizmet için ayrı izin akışı.
- Cilt için doğal fotoğraf, anatomik bölgeler, yerel görünüm haritaları ve sürümlü yöntemler; diş için fotoğraf tabanlı ön değerlendirme.
- Göz için kamera destekli yön hizalama görevi; işitme için sesli görev akışı. Bunlar klinik muayene veya kalibre tıbbi ölçüm yerine geçmez.
- Ruh Sağlığı için izin ve yapılandırmaya bağlı sesli/metinli görüşme; ağ/sağlayıcı hataları başarılı sonuç sayılmaz.
- İzin verilen kayıtların cihazdaki geçmişi, kayıtla ilişkili sonuç ayrıntıları ve kullanıcının başlattığı paylaşım/yönlendirme.
- Next.js arayüzü, FastAPI yerel backend'i ve hash doğrulamalı normal Windows başlatıcısı.

Her modelin kabul kapsamı ayrıdır. Bir modülün çalışması tüm modellerin doğruluk, klinik geçerlilik veya her görüntüde başarı iddiasını oluşturmaz. Güncel model/config sözleşmeleri `services/core-api/models` altında; tarihli deney ve teslim kanıtları `docs` ve `audit-results` altındadır. Eski raporların değerleri güncel build kanıtı gibi kullanılmamalıdır.

## Simülasyon ve ayrı doğrulamalar (DEMO / PLANNED)

- Araç park/sürüş telemetrisi yerel simülasyondur. Gerçek araç API/CAN, kabin donanımı, navigasyon veya OEM bağlantısı bulunmaz. Park durumuna bağlı güvenlik kontrolleri korunur.
- Açıkça seçilen demo modu ve örnek veriler gerçek kullanıcı ölçümü veya sağlık kaydı değildir.
- Gerçek araç/mobil donanım entegrasyonu, fiziksel cihaz kabulü ve klinik/düzenleyici doğrulama ayrı işlerdir.
- Uzman seçenekleri ve dış sayfaya devir, tamamlanmış randevu veya sağlık kuruluşuyla ortaklık anlamına gelmez.

## Gizlilik ve güvenlik

Kamera, mikrofon, dış servis işleme ve saklama izinleri birbirinden ayrıdır. Anahtarlar yalnız backend ortamında tutulur; frontend/build/Git içine eklenmez. Fotoğraf saklama davranışı ilgili hizmetin açık tercihine bağlıdır. Marka güncellemesi kayıtları yeniden yazmaz, izinleri sıfırlamaz ve depolama kimliklerini değiştirmez.

**Tıbbi teşhis içermez; ön değerlendirme ve değişim takibi amaçlıdır.** [Klinik güvenlik ve kriz kuralları](SAFETY.md) geçerlidir. Akut bir durumda profesyonel/acil yardım akışı uygulamadaki bilgilendirmeden bağımsızdır.

## Geliştirme ve doğrulama

- Node.js **22.20.0**, npm **10.9.3** (`packageManager`/`engines` ile sabit).
- Python 3.11 ve backend'in kayıtlı bağımlılıkları.
- Windows'ta build/lint, mevcut atomik ağır iş kilitleri, RAM/sahiplik kontrolleri ve sonlu Windows Job korumasıyla çalışır. Güvenlik sınırını aşmak için raw Next çağrısı kullanılmaz.

```powershell
npm ci
npm run lint
npm run typecheck
npm run build
```

Temiz checkout tek başına bütün yerel model/konuşma varlıklarını içerdiği anlamına gelmez; eksik varlık ve yapılandırma ayrıca doğrulanmalıdır. Normal Windows kısayolu doğrulanmış yerel checkout/build descriptor'ını açar; kendiliğinden Git güncellemesi veya yeni model indirmesi yapmaz. Üretim profili, kayıtları ve kimlik bilgileri geliştirme/test ortamına kopyalanmamalıdır.

Bu depodaki iç paket, route, storage ve ortam değişkeni adları marka adına göre topluca yeniden adlandırılmamıştır. Üçüncü taraf lisansları ve tarihli kanıtlar korunur. Lisans durumu `UNLICENSED` olarak kalır.
