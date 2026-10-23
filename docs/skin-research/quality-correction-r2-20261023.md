# Cilt modeli: zorunlu kalite düzeltmesi — 23 Ekim 2026

İlk uzman modelin 309 test görselinde AP50 sonucu: akne %62,31; siyah nokta %39,28; beyaz nokta %20,86. Ortalama %40,82; AP50–95 %14,20. Bu model üretime alınmadı.

## Tespit edilen sorun ve deneme

Kaynak görüntülerin tamamı 420×420. Eğitimde siyah nokta kutularının ortanca kısa kenarı 9 piksel, beyaz noktaların 10 piksel. Görsel incelemede yapay siyah/beyaz benek gürültüsü gerçek cilt detaylarının üzerine biniyor. Piksel kalitesi taraması tüm görüntülerde çalıştırıldı; bu tarama tıbbi etiket doğrulaması değildir.

Altı sabit doğrulama örneğinde toplam 22 inference çağrısı yapıldı. Bunların dört komedon görüntüsünde tam görüntü ile dört örtüşen 252×252 parçanın sonuçları eşleştirildi. Eşikler mevcut TAM doğrulama eğrisinden alındı (akne .38; siyah/beyaz nokta .32), IoU .50 ve aynı sınıf NMS .50 kullanıldı. Beyaz nokta TP 12→16, FP 5→18; siyah nokta TP 2→2, FP 0→5. Bu küçük örnekte kırpma tek başına kabul edilebilir bir iyileştirme göstermedi; ürün akışına eklenmedi. Bu sayılar tam doğrulama/test başarısı değildir. Üç istek sunucunun 300 aday sınırına ulaştı.

## Uygulanan düzeltme

Yalnız eğitimde, gri pikselin 3×3 medyandan farkı 60/255 üzerindeyken bu piksellerin oranı %1'i aşan 630 türev çıkarıldı. Eşik piksel/görsel kalite incelemesiyle belirlendi; test başarısına göre ayarlanmadı. Sınır çevresindeki 12 eğitim örneği ayrıca görsel olarak incelendi. Bu muhafazakâr eşik bütün gürültüyü kaldırdığı iddiası taşımaz; bir kalite filtresidir.

| Bölüm | Görsel | Kutu | Kaynak grubu |
|---|---:|---:|---:|
| Eğitim | 917 | 6.270 | 497 |
| Doğrulama | 345 | 2.024 | 108 |
| Test | 309 | 2.322 | 106 |
| Toplam | 1.571 | 10.616 | 711 |

497 eğitim kaynak grubunun tamamı korundu. Doğrulama/test kaynak fotoğrafları ve COCO dosyaları önceki hazırlanan paketle bayt düzeyinde aynı kaldı; hiçbir test örneği eğitime taşınmadı. Gruplar bilinen kaynak/kopya gruplarıdır, doğrulanmış tekil kişiler değildir.

Roboflow'a aktarımdan sonra gerçek sürüm-1 COCO paketi geri indirildi: 1.571 etiketli görüntü, 10.616 kutu; 0 etiketsiz ve 0 bilinen bölüm çakışması. Bütün kutu koordinatları tam eşleşti. JPEG yeniden kodlamasının en yüksek ortalama mutlak piksel farkı 1,396/255 altında. Yerel paketin kendi kendine karşı kontrolü platform kontrolü diye sunulmadı; ayrı gerçek platform ön kontrolü kaydedildi.

## Başlatılan tek eğitim

`attune-comedones-clean-train-r2/1` üzerinde RF-DETR NAS parent; 100 epoch, 640×640 Fit black edges, ek online augmentation yok. Eğitim kimliği `c2bcbeca2ab5719224fe`; 23 Ekim 2026 13:16 UTC'de başladı ve ilk kontrolde running. Yeni veri kalitesi, mimari ve çözünürlük birlikte değiştiği için ilerideki fark yalnız bir etkene atfedilmeyecek.

NAS adayı doğrulamayla seçilecek, test eşikleri veya çocuk seçimi test üzerinden ayarlanmayacak. Tam doğrulama ve test, gürültülü örnekler dahil raporlanacak. Temiz altküme gösterilirse ayrı başlık taşıyacak. Mevcut üretim kabul koşulları değiştirilmedi.

Gözenek eğitimi `66999f483e520c0353b9` sürüyor. Mevcut ChatGPT saatlik takip yeni NAS eğitimi ve gözenek işine güncellendi; yeni ücretli işleri kendiliğinden başlatmıyor.

Kod: aynı PR #6. Kalite filtresi holdout değişmezliği, kaynak grubunun silinmesini engelleme ve eksik kalite taramasını reddetme testleriyle kontrol edildi; 15 ilgili test geçti. Bu ekleme ürün çalışma zamanını değiştirmiyor. Üretime kabul hâlâ yok.
