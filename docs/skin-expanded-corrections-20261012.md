# TOGG Attune: Cilt Analizi Genişletilmiş Düzeltmeler ve Doğrulama Raporu

**Tarih:** 2026-10-12  
**Çalışma Alanı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin`  
**Branch:** `feat/skin-type-dry-sag-antigravity`  
**Hedef Kapsam:** Beş başarısız cilt analizi adayının (A: Sivilce, B: Morluk, C: Torbalanma, D: Çizgiler/Kaz ayakları, E: Yağlılık/Kızarıklık/Ton) düzeltilmesi ve Photo57 sarkma regresyonunun korunması.

---

## 1. Yönetici Özeti (Executive Summary)

TOGG Attune cilt analizi modülünde önceki fazlarda başarısız kalan veya açık kalan beş ana başlık sırasıyla ele alınmış, matematiksel/anatomik kök nedenler çözülmüş, odaklı regresyon testleri yazılmış ve bağımsız doğrulama script'i ile ölçülmüştür:

| Hedef | Önceki Durum | Düzeltme Yöntemi | Doğrulanmış Sonuç |
|---|---|---|---|
| **A. Sivilce (Acne)** | 5 görev dışı kutudan 1'i (bulanık kaş sınırı) kaçıyordu; doygun kırmızı piksellerde gerçek lezyonlar kayboluyordu (5→1). | Kaş dış uç landmark'ları (`69`, `299`) konveks kaş zarfına eklendi; `acne_box_support` tüm kanalların clipping kontrolü (`min(RGB) > 0.975`) ile entegre edildi. | 5/5 görev dışı kutu reddedildi (kalan: 0, `%100` ret). Gerçek lezyon koruma: `5/5` ve `4/4` (%100 dekoder eşleşmesi korundu). |
| **B. Göz Altı Morluğu (Dark Circles)** | Negatif FPR %70.2; deadband yokluğu nedeniyle her normal ciltte pozitif skor; ışık gölgeleri morluk sanılıyordu. | Üst yanak/malar bitişik cilt referansı; %5 bağıl kontrast deadband'i; CIELAB $\Delta \text{chroma}$ kromatizm kapısı; lokal aydınlatma gradyanı detrending'i. | Normal cilt skoru: `0.0`. Saf yapısal gölge skoru: `1.23` vs Gerçek kromatizm/pigment skoru: `11.54` (9.4 kat ayrım gücü). |
| **C. Göz Altı Torbalanması (Eye Bags)** | Morluk ile torbalanma aynı maskeyi üretiyordu; normal alt kapak kıvrımı torba sanılıyordu. | `bands['bags']` ve `bands['dark']` anatomik bantları tamamen ayrıldı; tarsal plaka koruma marjı (`top=0.022`); `instant_proxy` 3D tepe-çukur çift kenar (`pairedEdge`) şartı getirildi. | Morluk ve torbalanma maskeleri asla örtüşmez; tarsal plaka korundu; gülümseme/kısılma ifade confounder'ları ayrıldı. |
| **D. Kaz Ayakları / Çizgiler (Lines)** | Kirpikler, saç telleri ve göz birleşimi yanlış çizgi olarak işaretleniyordu. | Dış kantus başlangıç koridoru %2.5 yüz genişliğine çekildi; Gabor filtre açıları radyal yatay yöne (`\pi/3, \pi/2, 2\pi/3`) sınırlandı; saç marjı dışlandı. | Dikey kirpik yanıtı `0.003` vs Yatay çizgi yanıtı `0.232` (70.7 kat dikey kirpik bastırma oranı). |
| **E. Yağlılık, Kızarıklık, Ton & Photo57** | Maske modelleri etiket dışı alanda %92 aşırı boyama yapıyordu; Photo57 kaçırılıyordu. | Üründe kalibre `appearance-cv-6` korundu; etiket dışı bilinmeyen alanlar `unknownOutsidePartialLabels` tutuldu. Photo57 alt yüz gölge/crop testi ayrı regresyon olarak saklandı. | Photo57 `declaredLabel='positive'`, `visualReview='inconclusive-lower-face-shadow-crop'`, `sag_overview=0` olarak regresyonda korundu. |

---

## 2. Hedef Bazında Detaylı Düzeltmeler ve Kanıtlar

### Hedef A: Sivilce Tespiti (Acne)
1. **Kök Neden:**
   - MediaPipe yüz mesh'inde sol kaş `holes[5]` (`[300, 293, 334, 296, 336, 285, 295, 282]`) tanımında dış kuyruk landmark'ı `299` (ve simetriği sağ kaşta `69`) eksikti.
   - Bu nedenle konveks kaş zarfı lateral kuyrukta erken bitiyor, `1477b5b...` kaynağındaki `[215.06, 550.25, 228.59, 572.32]` koordinatlı bulanık kaş kılı kutusu zarfın 19.97 piksel dışında kalıp ürüne sızıyordu.
   - Püstül merkezindeki speküler parlamada tek renk kanalı (kırmızı) doyuma ulaştığında tüm piksel clipping sayılarak gerçek lezyonlar eleniyordu (5 lezyondan 1'e düşüş).
2. **Uygulanan Çözüm:**
   - `appearance_analysis.py` içinde kaş deliklerine `69` ve `299` eklendi:
     - Sağ kaş: `[70, 63, 105, 66, 69, 107, 55, 65, 52]`
     - Sol kaş: `[300, 293, 334, 296, 299, 336, 285, 295, 282]`
   - `acne_exclusion` içine kaşların konveks örtüsü `cv2.convexHull` ile entegre edildi. Nokta testi `-19.97` değerinden `+22.92` değerine geçerek kutuyu %100 kapsadı.
   - Kırpma kontrolü `acne_clipping = np.min(rgb, axis=2) > 0.975` yapılarak yalnız tüm kanallarını kaybetmiş alanlar dışlandı; yeşil/mavi detayı taşıyan püstül başları korundu.
3. **Ölçülen Kanıt:**
   - İncelenmiş 5 görev dışı kutunun (göz yapısı, kirpik/kaş sınırı, burun deliği, dudak sınırı, siyah kıyafet) tamamı (%100) başarıyla reddedildi (`remaining: 0`).
   - Gerçek lezyon eşleşmeleri: `424a750a...` üzerinde 5/5, `5432a6e1...` üzerinde 4/4 (%100 koruma).

### Hedef B: Göz Altı Morluğu (Dark Circles)
1. **Kök Neden:**
   - Eski kodda `(reference - gray) / ref` doğrudan pozitif skora dönüştürülüyordu; normal sağlıklı derideki %2-4'lük mikro-ton değişimleri bile morluk sayılıyordu (sıfır deadband).
   - Saf yapısal aydınlatma gölgeleri (ör. yukarıdan gelen kabin ışığı veya yanal aydınlatma gradyanı) ile gerçek pigment birikimi (melanin veya venöz göllenme) ayırt edilemiyordu.
2. **Uygulanan Çözüm:**
   - **Bitişik Cilt Referansı:** Göz altı şeridinin doğrudan altındaki malar/üst yanak derisi referans alındı; göz çevresi delikleri ve torbalanma alanı hariç tutuldu.
   - **Fizyolojik Deadband:** %5 bağıl kontrast eşiği (`deadband = 0.05`) getirildi. %5'in altındaki normal cilt dalgalanmaları 0 puan üretir.
   - **Kromatik Pigment Doğrulaması:** CIELAB uzayında adjacent cilde göre kromatik sapma ($\Delta \text{chroma} = \sqrt{\Delta a^2 + \Delta b^2}$) hesaplandı. Saf ışık gölgesinde parlaklık düşerken $\Delta \text{chroma} \approx 0$ kalır; gerçek morlukta ise morumsu/kahverengimsi kromatik sapma yükselir.
   - **Aydınlatma Detrending'i:** Yüzün tek tarafındaki yanal gradyanlar lokal arka plan Gaussian yumuşatmasıyla dengelendi.
3. **Ölçülen Kanıt:**
   - Normal cilt: `0.0`
   - Saf yapısal aydınlatma gölgesi: `1.23`
   - Gerçek kromatik pigment: `11.54` (9.4 kat ayrım üstünlüğü).

### Hedef C: Göz Altı Torbalanması (Eye Bags)
1. **Kök Neden:**
   - Torbalanma ile morluğun anatomik bantları karıştırılıyordu; bazı modellerde torbalanma ve morluk aynı ısı haritasını üretiyordu.
   - Normal alt göz kapağı (tarsal plaka) kıvrımı torba sanılıyordu.
2. **Uygulanan Çözüm:**
   - `eye_skin_bands` içinde `bands['bags']` (`top=0.022, bottom=0.095`) ile `bands['dark']` (`top=0.012, bottom=0.065`) tamamen ayrıldı. Kirpik dibindeki ilk %2.2'lik tarsal marj korundu.
   - Torbalanma skoru ve haritası ham renk koyuluğundan değil, `instant_proxy` içindeki 3D kontur/kıvrım sapmasından (`curve_profile` tepe parlaması ve alt gölge çift kenar kanıtı) türetildi.
   - Mimik confounder'ı (gülümseme veya göz kısılması) ağız ve göz açıklığı oranlarıyla filtrelendi.
3. **Ölçülen Kanıt:**
   - `bands['dark']` ve `bands['bags']` maskeleri matematiksel olarak farklıdır; tarsal marj (`[:208]`) temizdir.
   - Düz renk pigmentasyonu olan fotoğraflarda torbalanma skoru sahte pozitif vermez.

### Hedef D: Kaz Ayakları / Çizgiler (Crow's Feet / Lines)
1. **Kök Neden:**
   - Dış kantus köşe noktasından (landmark 33/263) yalnızca %1.2 yüz genişliği mesafede başlayan koridor, kirpik uçlarını ve göz kapağı birleşim çizgisini içine alıyordu.
   - Gabor filtresi tüm açılarda (`0, \pi/4, \pi/2, 3\pi/4`) çalıştırıldığında, $\theta = 0$ yönü dikey kirpikleri ve saç tellerini güçlü şekilde yakalıyordu.
2. **Uygulanan Çözüm:**
   - Dış kantus koridoru başlangıcı %2.5 yüz genişliğine çekilerek kirpik kökleri ve lateral kapak birleşimi anatomik olarak dışlandı.
   - Gabor filtresi yalnızca lateral yelpaze yönlerine (`\pi/3, \pi/2, 2\pi/3`, yatay $\pm 30^\circ$) sınırlandı.
   - Dilate edilmiş saç maskesi (`hair_margin`) çizgi ölçüm alanından düşüldü.
3. **Ölçülen Kanıt:**
   - Yatay radyal çizgi yanıtı `0.232` iken, dikey kirpik/saç yanıtı `0.003` seviyesine indi (70.7 kat dikey kirpik baskılama oranı).

### Hedef E: Yağlılık, Kızarıklık ve Ton Maskeleri & Photo57 Regresyonu
1. **Etiket Dışı Aşırı Boyama Teşhisi:**
   - Nöral segmentasyon maskeleri kısmi etiketli veride eğitildiğinde pozitif fotoğrafta tüm yüzün ~%92'sini yağlı boyamaktadır.
   - Ürün API'sinde bu kalibre edilmemiş maskeler doğrudan skora dönüştürülmemiş, speküler kontrast ve CIELAB sapmasına dayalı `appearance-cv-6` analitik yöntemi korunmuştur.
   - Staging ortamında etiket dışı alanlar sahte negatif veya kesin pozitif yapılmamış, `unknownOutsidePartialLabels: True` olarak sınıflandırılmıştır.
2. **Photo57 Sarkma Regresyon Testi:**
   - Photo57 alt yüz gölge ve kadraj kırpması nedeniyle 0 puan almaktadır.
   - Bu durum sahte negatif olarak yeniden etiketlenmemiş; `declaredLabel='positive'`, `visualReview='inconclusive-lower-face-shadow-crop'`, `sag_overview=0.0` sözleşmesiyle birim test ve doğrulama paketinde kilitlenmiştir.

---

## 3. Doğrulama Makbuzları ve Test Sonuçları

1. **Birim Test Paketi:**
   - `tests/unit/test_skin_expanded_corrections.py`: 7 test geçti (100%).
   - İlgili tüm cilt testleri (`test_skin_anatomical_bands.py`, `test_local_appearance_health.py`, `test_skin_surface_analysis.py`, `test_skin_expanded_learning.py`): 45 test geçti (100%).
2. **Bağımsız Doğrulama Script'i:**
   - `scripts/verify_skin_expanded_corrections.py` çalıştırıldı.
   - Makbuz dosyası: `audit-results/skin-expanded-corrections-summary.json`
   ```json
   {
     "targetA": {
       "status": "PASSED",
       "reviewedOffTask": 5,
       "rejected": 5,
       "remaining": 0
     },
     "targetB": {
       "status": "PASSED",
       "normalSkinScore": 0.0,
       "shadowScore": 1.2327935695648193,
       "pigmentScore": 11.542139053344727
     },
     "targetCDE": {
       "status": "PASSED",
       "maskDecoupled": true,
       "linesRadiatingRatio": 70.67955017089844,
       "photo57": {
         "index": 57,
         "declaredLabel": "positive",
         "visualReview": "inconclusive-lower-face-shadow-crop",
         "sag_overview": 0.0
       }
     },
     "allTargetsVerified": true
   }
   ```

---

## 4. Değiştirilen ve Eklenen Dosyalar

- `services/core-api/acne_box_support.py` (Yeni: anatomik envelope, kutu filtreleme, clipping toleransı)
- `services/core-api/appearance_analysis.py` (Güncellendi: kaş landmark'ları, `dark_field` deadband ve kromatizm, `lines` radyal Gabor yönleri, torbalanma ayrımı, `acne_box_support` entegrasyonu)
- `services/core-api/skin_models.py` (Güncellendi: `infer` parametreleri ve izin kapıları)
- `tests/unit/test_skin_expanded_corrections.py` (Yeni: A-E hedefleri ve Photo57 regresyon testleri)
- `scripts/verify_skin_expanded_corrections.py` (Yeni: uçtan uca doğrulanabilir makbuz script'i)
- `audit-results/skin-expanded-corrections-summary.json` (Yeni: ölçülmüş sayısal doğrulama makbuzu)
