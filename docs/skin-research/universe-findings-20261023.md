# Attune.more — yeni cilt kaynakları ve uygulama değişiklikleri

23 Ekim 2026. Bu dosya araştırma ve geliştirme durumudur; OEM başarı belgesi değildir.

## İki veri kaynağının sonucu

| Kaynak | Yerel arşiv incelemesi | Kullanım |
|---|---|---|
| [dermatoloji_tespit_yz v5](https://universe.roboflow.com/zgr-mjbpf/dermatoloji_tespit_yz-cxlee) | 3.890 fotoğraf, 14 etiket, 5 sürüm. Yalnız 1.113 fotoğraf etiketli; 2.777 boş etiketli fotoğraf normal cilt sayılmadı. | Kutu tabanlı yer tespiti için araştırma verisi. |
| [skin-problem-multilabel v1](https://universe.roboflow.com/parin-kittipongdaja-vwmn3/skin-problem-multilabel) | 4.828 fotoğraf, 10 etiket, fotoğraf başına birden fazla etiket. Kendi içinde tam piksel kopyası yok. İlk kaynakla 112 birebir aynı fotoğraf var. | Fotoğraf düzeyinde yardımcı sınıflandırma; kutu veya kırışıklık çizgisi üretmez. |

İkinci kaynağın yayıncısı toplam %97,1 accuracy bildiriyor. Bu, Attune.more performansı veya aşağıdaki özelliklerin ayrı ayrı doğruluk oranı değildir. Kullanılan accuracy tanımı ve sınıf bazındaki precision/recall/F1 bağımsız olarak doğrulanmadı.

| İkinci setin etiketi | Eğitim | Doğrulama | Test | Özellik bazında doğrulanmış başarı |
|---|---:|---:|---:|---|
| Akne | 2.105 | 608 | 312 | Ölçülmedi |
| Siyah nokta | 72 | 22 | 12 | Ölçülmedi |
| Koyu leke | 190 | 46 | 21 | Ölçülmedi |
| Kuru cilt | 326 | 103 | 43 | Ölçülmedi |
| Göz altı torbası | 156 | 48 | 17 | Ölçülmedi |
| Normal cilt | 178 | 43 | 27 | Ölçülmedi |
| Yağlı cilt | 179 | 53 | 32 | Ölçülmedi |
| Gözenek | 197 | 53 | 13 | Ölçülmedi |
| Kızarıklık | 32 | 13 | 5 | Ölçülmedi |
| Kırışıklık | 297 | 82 | 38 | Ölçülmedi |

Sayım birimi fotoğraftır; çok etiketli oldukları için sütun toplamları fotoğraf sayısını aşabilir. Beyaz nokta, egzama, rozasea, uçuk, riskli ben ve göz altı morluğu bu ikinci sette ayrı etiket değildir. Koyu leke etiketi güneş lekesi veya göz altı morluğu diye yeniden adlandırılmadı.

## Hazırlanan eğitim

İlk kaynaktan mantar ve siğil çıkarıldı; diğer kaynak etiketleri korunarak **927 benzersiz etiketli fotoğraf** hazırlandı. Boş fotoğraflar negatif örnek yapılmadı. Tam kopyalar çıkarıldı; dHash mesafesi en fazla 3 olan adaylar aynı grupta tutuldu. 903 grup, 24 benzerlik çifti; bu işlem kişi bağımsızlığı kanıtlamaz.

| Bölüm | Fotoğraf | Kaynak işaretleme sayısı |
|---|---:|---:|
| Eğitim | 669 | 7.466 |
| Doğrulama | 117 | 891 |
| Test | 141 | 1.195 |

[Özel Roboflow projesi](https://app.roboflow.com/tolgar-sasmaz/attune-skin-findings-boxes-research), sürüm 1 hazır. Aktarım: 927/927 etiketli fotoğraf; 7 fotoğraf için `annotation:trimmed` uyarısı var. Orijinal arşiv korunmuştur; ithal geometri ile kaynak geometrisi eşit kabul edilmemelidir.

30 epoch RF-DETR NAS denemesi başlatılmak istendi. Platform `insufficient_train_credits` döndürdü; **eğitim başlamadı, yeni ağırlık veya başarı sonucu yok**. Epoch sınırı kredi harcama üst sınırı değildir. Yeni kredi kullanılabilir olduğunda önce bu tek araştırma eğitimi, sonra ayrılmış test değerlendirmesi yapılmalı; sonuç görülmeden tekrar eğitim açılmamalıdır.

## Uygulama dalındaki değişiklikler

- Sonuçlara bağlı Temizleme / Bakım / Nemlendirme / Güneş kremi önerileri; kalın başlık ve maddeler. Eksik ölçüm öneri üretmez; kızarıklıkta tahriş edici aktif önerilmez.
- T bölgesinde yağlılık ve her iki yanakta ölçülmüş yağsız görünüm varsa Karma; kuruluk şart değil, eksik yanak ölçümü yağsız kabul edilmez. Mevcut global modelin geçerli çıktısı ve karar izi korunur.
- Yan çekim alt yaw eşiği 0,28'den 0,40'a çıkarıldı; üst sınır 0,65. Bunlar açı derecesi değil, mevcut boyutsuz MediaPipe ölçüsüdür. Eski fotoğrafların arka uç kabulü korunur.
- Kuru mavi, yağlı yeşil, egzama koyu mavi, kızarıklık kırmızı; kenarsız yarı saydam kutu alanları. Noktasal bulgular küçük noktalar; kırışıklıklar yalnız ölçülmüş çizgi desteğinden izlenir. Kaynak fotoğraf/poz/boyut/model özeti eşleşmeyen bulgu çizilmez; göz/dudak dışlama maskesi uygulanır.
- Yeni kutu göstericisi hazırdır; yeni sınıflara ait eğitim tamamlanmadığı için bu bulguları üreten model veya çalışma zamanı adaptörü etkin değildir. Hastalık etiketleri cilt tipine dönüştürülmedi.

Kontrol: ilgili 53 davranış testi, TypeScript ve üretim derlemesi geçti. Son maske değişikliği ardından odaklı test ve TypeScript tekrar geçti. Tarayıcı görsel kontrolü tamamlanmadı: Chromium indirmesi geçersiz arşiv döndürdü. Türkçe yan dönüş seslerini seçerek güncelleyen komut hazır (`python scripts/build_guidance_cache.py --skin-side-only`), ancak Edge TTS `NoAudioReceived` döndürdüğü için ses dosyaları değiştirilmedi; EN/DE yan dönüş sesleri de bekliyor.

## OEM iddiası için zorunlu kalanlar

1. Eğitimden sonra her özellik için ayrı test sonucu: sınıflandırmada precision/recall/F1 ve örnek sayısı; kutuda mAP50, mAP50–95, precision/recall ve yanlış pozitifler. Toplam %97,1'i tüm satırlara yazmamak gerekir.
2. Kaynaklar arası ortak/benzer fotoğrafları ve aynı kişiyi testten ayıran, hedef araç kamerası/poz/ışık koşullarını içeren etiket kontrolü yapılmış bir son test. Özellikle 5 kızarıklık ve 12–17 siyah nokta/gözenek/torba test örneği kuvvetli özellik iddiası için yetersiz kanıttır.
3. Ticari kullanım için kaynak fotoğraf hakları ve etiketlerin anlamının teyidi. Yayıncı CC BY 4.0 bildiriyor; bazı görsellerde stok filigranı veya yüz dışı bölgeler var. Yayıncı lisansı tüm fotoğrafların hak sahipliğini ya da uzman tanısını kanıtlamaz. Riskli ben gibi klinik iddialar bu kanıt olmadan açılmamalıdır.

Ham arşivler, SHA-256 yeniden birleştirme manifestleri, özel fotoğraf kayıtları ve hazırlanan eğitim paketi Drive'da tutulur. Kamuya açık Git deposuna fotoğraflar veya özel indirme bağlantıları eklenmez.
