# Sonuç ekranlarının EN/DE çevirisi, diş çekimi ve cilt eğitimi

23 Ekim 2026. Değişiklikler `feat/skin-findings-routine-20261023`, PR #6 kapsamındadır.

## Çeviri düzeltmeleri

Türkçe karakter taraması tek başına `Kuru`, `Karma`, `Sarkma`, `Gergin`, `Yorgun`, `Rahat` gibi görünür etiketleri bulamıyordu. Kontrollü sonuç sözlükleri artık ASCII içeren etiketleri ve `as const` tanımlarını da envantere dahil eder. Tarayıcı izinlerinin `camera`/`microphone` makine kimlikleri çevrilmez.

| Kaynak etiket | İngilizce | Almanca |
|---|---|---|
| Cilt Tipi / Cilt tipi | Skin type | Hauttyp |
| Kuru | Dry | Trocken |
| Karma | Combination | Mischhaut |
| Sarkma | Sagging | Hauterschlaffung |
| Cilt parlaklığı / Cilt Parlaklığı | Skin brightness | Hauthelligkeit |
| Parlaklık | Brightness | Helligkeit |
| Dengeli | Balanced | Ausgeglichen |
| Gergin | Stressed | Angespannt |

Eski parlaklık etiketleri, büyük/küçük harf ve boşluk varyantları da kapsandı. Görünür aday birimi, sol yanak/kulak etiketleri ve ruh hâli etiketleri tamamlandı. Ruh hâli geçmişi ve birleştirilmiş tema özetleri görüntülenirken çevrilir; kayıt metni ve sayısal değerler değiştirilmez. Kullanıcının serbest metni ve konuşma dökümü çeviri servisine gönderilmez.

Katalogdaki kısa, kontrollü etiketlerin Türkçe büyük/küçük harf varyantları ön ve arka uçta eşleştirilir: `CİLT TİPİ`, `Cilt Tipi`, `KARMA`, `SARKMA` dahil. Envanter tüm `LABELS`/`GUIDANCE`/`UNITS` sözlüklerini, `headline`, `details`, `displayValue`, `badgeText` alanlarını da tarar. `Stabil (+4%)` gibi statik ve dinamik yüzdeli etiketler kapsanır; Almancadaki `Stabil` doğru çeviridir.

Boş dinamik alanlar da düzeltildi: örneğin değişim `0` olduğunda boş `+` alanı içeren cümle eski eşleştiricide çevrilemeyebiliyordu. Ön ve arka uç artık boş parametreyi kabul eder. Parametre yanındaki boşlukların normalleştirilmesi, cümlenin Türkçe kalmasına neden olmaz.

Doğrulama: 36 ilgili test geçti. EN/DE için gerçek React sonuç bileşenleri sunucu üzerinde render edildi: cilt özeti, diş kayıt detayı, harf tanıma sonucu ve yön hizalama sonucu. Ayrıca altı cilt bölgesinin demo, veri yok, güncel sonuç ve eski kayıt/referans durumlarındaki tüm görünür alanları tarandı. Parlaklık varyantları, sıfır/pozitif/negatif değişim, cilt tipi, ruh hâli, geçmiş birimleri ve kaynak kayıtların değişmemesi kontrol edildi. Çeviri envanteri 1.529 kaynakta PASS; TypeScript ve üretim derlemesi başarılı. Bu kontrol fiziksel kamera kabulü veya tarayıcı ekran görüntüsü testi değildir.

## Diş yan çekimi

Rijit yüz dönüşünün yan çekim alt sınırı `π/12` radyandan (15°) `0,40` radyana (yaklaşık 23°) çıkarıldı. Üst sınır `0,65` radyan (yaklaşık 37°); ön/kapanış bandı `±0,20` radyan. Cilt modülünün boyutsuz yaw değeri dişe derece diye aktarılmadı. Sağ/sol işareti, pitch/roll sınırları ve dişlerin görünürlüğü, netlik, ışık, parlama, dil/dudak kontrolleri korunur. Eski kayıtlar yeniden yorumlanmaz.

Mevcut onaylı sesli yönergeler kullanılır. Yeni ses üretimi bu çalışmanın kapsamından çıkarıldı; ses dosyaları değişmedi.

## Cilt eğitimi ve takip

Roboflow'daki gerçek sürüm 1 dışa aktarımı, yüklenen kaynak arşivine karşı eğitimden önce doğrulandı. **927 fotoğrafın tamamı etiketli; 0 etiketsiz.** Eğitim 669 / doğrulama 117 / test 141. Kaynak bölümleri değişmemiş; tam kopya ve kaynak benzerlik gruplarının bölümler arası çakışması 0. Tüm sınıf/işaretleme adetleri korunmuş. JPEG yeniden kodlaması kaynak fotoğrafla karşılaştırıldı; kutulardaki en büyük koordinat farkı 0,5 piksel.

`scripts/skin-research/verify_imported_boxes.py` bu kontrolü tekrarlar; fotoğraf, sınıf, bölüm, geometri ve boş etiket değişikliklerini reddeden testleri vardır. Bunlar uzman tanısını veya kişi bağımsızlığını kanıtlamaz.

**RF-DETR NAS, tek 30 epoch araştırma eğitimi başlatıldı.**

- Proje: `tolgar-sasmaz/attune-skin-findings-boxes-research`
- Sürüm: `1`
- Training ID: `8e239395ebda9996fe0f`
- Başlatma yanıtı: `running`
- [Eğitim sayfası](https://app.roboflow.com/tolgar-sasmaz/attune-skin-findings-boxes-research/1)

Kullanıcının seçimiyle ChatGPT üzerinden **saatlik kısa özet** otomasyonu kuruldu. GitHub zamanlayıcısı kurulmadı. Otomasyon yalnız bu eğitimi izler, terminal durumda son özeti verip kapanır; yeni eğitim veya otomatik üretim geçişi başlatmaz.

Kullanıcının Core hoş geldin e-postası, Roboflow'da eğitilen modelleri self-host etmek için ticari model lisansı içerdiğini açıkça bildiriyor; görsel kanıt özel Drive klasöründe korunur. Model mimarisinin kendi lisans kapsamı ve kaynak fotoğraf hakları ayrı kayıtlardır. [Resmî plan/model lisansı bilgisi](https://roboflow.com/pricing).
