# Gözlüksüz cilt taraması: yeni kabul kapsamı

Koşul `glasses-free-skin-capture-v1`: yeni Cilt Sağlığı çekimleri gözlüksüzdür. Önceki fotoğraflar, raporlar, sonuçlar ve kullanıcı kayıtları değişmez. Göz Sağlığı ve diğer modüllere yeni kapı uygulanmaz. TRAIN/validation kaynak-grup ayrımı korunur.

9bab7ab2 artık normal kuruluk puanı kabulü değil, gözlük kapısının çekim/API/sonuç/geçmişi engelleme kontrolüdür. Önceki 73→440 gözlük çerçevesi pikseli korunmuş araştırma sonucudur; bunu kapsamdan çıkarmak model doğruluğu kazanımı değildir. Gözlük için yeni kuruluk fit'i yapılmaz. Gözlüksüz 24031977'nin iki materyal kaçırması, C0/C9 ve native/yarım-kaynak kararsızlığı açık kalır.

Geometrik çerçeve/köprü denemesi gerçek gözlüksüz kaş/göz altı desteğini reddettiği için kabul edilmedi. Ürüne bağlanacak yerel algılayıcı: [FrameFind](https://github.com/moraxh/FrameFind), dondurulmuş upstream `3c69676cbcd44a47ab083b541b56c050dbc0b1b5`, MIT bildirimi model yanında korunur. Yalnız 6.402.858 byte hazır ONNX alındı; yeni eğitim, veri seti indirme, hesap veya fotoğrafın dış serviste işlenmesi yok. Model SHA-256 `66f75c686974a04bf956d0ed6411315309afcabd36c400edec743953adafccb9`.

Sözleşme: mevcut MediaPipe'nin 34 göz/kaş/burun köprüsü noktası; 1,25 kare margin; yalnız algılayıcı için RGB112 ve ImageNet mean/std; tek logit→sigmoid. Kaynak fotoğraf, snapshot, cilt proposal'ı, görüntüleme renkleri ve anatomik koordinatlar küçültülmez. Yüz noktaları yoksa merkez-crop veya sağlıklı fallback yok. Upstream 0,5 karar sınırı korunur; ≤0,3 açık, arası belirsizdir. Confidence cilt şiddeti değildir.

Fit yapılmadan küçük gerçek kaynak kontrolü: 9bab7ab2 gözlüklü 0,9839; gözlüksüz NASA 0,0498, 24031977 0,0006, 29cc4ba7 0,0104, 4d05d72b 0,0435. Tek benzersiz gözlüklü kaynak + dört gözlüksüz kontrol genel doğruluk veya bütün çerçeve/ışık/poz türlerinin garantisi değildir. Normal üründeki gerçek browser crop/API kontrolü ve teslim kanıtı [kesinti sonrası raporda](material-closeout-recovery-20261014.md) ayrıca kayıtlıdır.

Çekimde poz/ışık/netlik kapıları sürer. Gözlük veya belirsiz kare kararlılığı sıfırlar; açık görüntü 900 ms kararlı kalmadan mevcut otomatik ilerleme başlamaz. Geç/iptal edilen yanıt yeni taramayı değiştiremez. Gözlük uyarısı mevcut yönerge alanındadır; her karede seslendirilmez. AhmetNeural, rate -10%, pitch -10Hz ile başlangıç `skin-front` yönergesinde “Gözlüğünüzü çıkarın” bir kez söylenir. Kullanıcının sözlü onayı görüntü yerine geçmez.

Normal API tam kabul edilen fotoğrafın gerçek aynı crop'unu yeniden kontrol eder; gözlükte 409/`SKIN_EYEWEAR_PRESENT`, belirsizde 422; analiz fonksiyonu çalışmaz. Başarılı ölçümler `captureConditions.skinCapturePolicy` ve gerçek algılayıcı model hash'ini taşır. Genel Bakış ve bölgesel geçmiş karşılaştırmaları eski kapsamı ayrı tutar; eski kayıtlar yeniden hesaplanmaz. Bu dosya nihai build/teslim kabulünü tek başına sağlamaz.
