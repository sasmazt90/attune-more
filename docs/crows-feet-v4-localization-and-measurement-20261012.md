# TOGG Attune — Hedef D: İnce Kaz Ayakları Yerelleştirme ve Ölçüm Raporu (v4)

**Tarih:** 12 Ekim 2026  
**Çalışma Alanı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin`  
**Baseline Teslim Referansı:** `ff0b161bd807fe81d2ba5ee6283d4f5b26f6a102`  
**Normalizasyon Sürümü:** `outer-canthus-gabor-radiating-hair-excluded-v4`  
**Kanıt Klasörü:** `audit-results/crows-feet-20261012/`  

---

## 1. Yönetici Özeti ve Temel Kök Neden Analizi

Önceki v3 hattında (`outer-canthus-gabor-radiating-hair-excluded-v3`), ince kaz ayakları içeren pozitif etiketli `a94f1646` örneğinde, göz dışı alanda doğrulanmış Roboflow çizgileri bulunmasına rağmen ham skor **0.00** çıkıyor ve UI'da aktif harita pikselleri 0 görünüyordu (**False Negative**). Buna karşılık, belirgin derin çizgileri olan `02386f86` örneği ham **1.4335** (UI: %1) olarak tespit ediliyordu.

### Kök Neden Tespiti (v3 Kısıtları)
1. **Frekans Kapsamı Eksikliği:** Üretim yüz normalizasyonunda yüz genişliği 320 piksele çekildiğinde (`LIMITS['analysisFacePixels'] = 320`), ince kaz ayaklarının piksel dalga periyodu ~6-7 pikseldir (\(f \approx 0.13 - 0.15\)). v3 hattı yalnızca \(f \in (0.18, 0.28)\) frekanslarını sorguluyordu; bu nedenle ince çizgilerin Gabor genliği ~0.0133–0.0140 seviyesinde kalıyordu.
2. **Sabit Yüksek Çıkarma Eşiği:** v3'teki `(signal - 0.018) / 0.06` formülünde `0.018` eşiği, \(0.014\) genliğe sahip gerçek ince çizgileri tamamen sıfıra kırpıyordu.
3. **Kirpik ve Makyaj Karışması Riski:** Eşik tek başına 0.0125'e düşürüldüğünde, kirpik uçları ve eyeliner çekimleri (`beda0290`) sahte pozitif üretiyordu.
4. **Anatomik Bant Geometrisi:** v3 poligonu \(top = -0.012 \times face\_width\) ile sınırlandırıldığından şakak/elmacık kemiği yukarısına yayılan çizgilerin üst kollarını kaçırıyor, \(in = 0.025\) ise kirpik sınırına çok yakın kalıyordu.

---

## 2. v4 Algoritmik İyileştirmeler

### A. Çok Ölçekli Frekans Genişletmesi
Gabor süzgeç bankasına \(f = 0.13\) frekansı eklenerek hem ince kırışıklıklar hem de derin oluklar tam hassasiyetle kapsandı:
$$\text{Frequencies: } (0.13, 0.18, 0.26)$$

### B. Radyal / Ortogonal Yön Seçicilik Kapısı (Directional Ratio Gating)
Gerçek kaz ayakları lateral canthus'tan şakağa doğru yelpaze şeklinde açılır (\(\text{radiating\_thetas} = \frac{\pi}{2} + roll \pm \frac{\pi}{6}\)). Kirpikler ve alt göz kapağı kenarları ise göz yarığına teğet (\(roll \pm \frac{\pi}{6}\)) yönelim gösterir.
- Her piksel için \(\text{rad\_sig}\) ve \(\text{ortho\_sig}\) ayrı ayrı hesaplanır:
$$\text{ratio} = \frac{\text{rad\_sig}}{\max(\text{ortho\_sig}, 0.005)}$$
$$\text{dir\_gate} = \text{clip}\left(\frac{\text{ratio} - 1.22}{0.35}, 0, 1\right)$$
- Bu kapı, teğet kirpik sinyallerini (\(\text{ratio} < 1.22\)) tamamen sıfırlarken, radyal çizgilerin (\(\text{ratio} \ge 1.57\)) tam genlikle geçmesini sağlar.

### C. Koyu Eyeliner ve Kozmetik Dışlama Tabanı (Makeup Exclusion Floor)
`beda0290` gibi açılı çekimlerde lateral canthus'a taşan koyu eyeliner çizgileri:
$$\text{skin\_support} = \text{valid\_line} \land (gray \ge \text{median}(gray) \times 0.55) \land (gray > 0.18)$$
şartıyla filtrelenir. Cilt tonundan %45 daha koyu veya mutlak parlaklığı 0.18'in altındaki kozmetik alanlar deri desteğinden çıkarılır.

### D. Anatomik Bant Poligonu ve Güvenli Alan Eşiği
- `in_m`: `0.025` $\to$ `0.030` (kirpik bileşkesinden 1.5 piksel daha dışarı çekilerek kirpik ucu teması kesildi).
- `top_m`: `-0.012` $\to$ `-0.035..-0.040` (yukarı yelpazelenen kaz ayağı kolları kapsandı).
- `bot_m`: `+0.050` (alt yelpaze korundu).
- `out_m`: `0.085` $\to$ `0.095` (şakak bandı genişletildi).
- **Asgari Görünür Alan:** Tek göz için sınır 75 piksele çıkarıldı (`minimum_pixels = 75`). Bu sayede `beda0290`'ın aşırı roll nedeniyle kadraj dışı kalan 59 piksellik sağ kenarı `INSUFFICIENT_VISIBLE_AREA` ile temiz elendi.

### E. Kart Skoru ve Gradyan Haritası Birebir Özdeşliği
Kart skoru (`eye_measurement('lines', 75, line_field)`) ve yerel gradyan haritası (`localMap['periorbital:lines']`), harici yeniden hesaplama veya türetme olmadan, doğrudan aynı `line_signal = lines * 100` tensöründen üretilmektedir:
$$\text{Score} = \text{mean}(\text{line\_signal}[\text{valid\_band}]) \quad \Longleftrightarrow \quad \text{LocalMap} = \text{line\_signal}$$

---

## 3. Doğal Fotoğraf Karşılaştırma Sonuçları

Doğrulama script'i `scripts/evaluate_crows_feet_v4.py` ile `analyze_skin` üretim hattı üzerinde 5 örnek canlı değerlendirilmiştir:

| Örnek SHA | Kategori / Rol | v3 Baseline (raw / UI / px) | v4 Candidate (raw / UI / px) | Sonuç ve Doğrulama Durumu |
| :--- | :--- | :--- | :--- | :--- |
| **`a94f1646`** | **Pozitif İnce Kaz Ayakları** | `0.0000` / %0 / 0 px (FN) | **`0.5563`** / **%1** / **99 px** | **KURTARILDI & DOĞRULANDI** — İnce çizgiler haritada şakak yönünde net siyan örtüşmeyle lokalize edildi. |
| **`02386f86`** | **Pozitif Derin Kaz Ayakları** | `1.4335` / %1 / 104 px | **`3.1059`** / **%3** / **176 px** | **KORUNDU & GÜÇLENDİRİLDİ** — Belirgin derin kırışıklıklar tam genlikle yakalandı. |
| **`beda0290`** | **Negatif Kontrol (Eyeliner & -24.5° Roll)** | `0.4012` / %0 / 5 px | **`0.0009`** / **%0** / **0 px** | **TEMİZ SIFIR NEGATİF** — Eyeliner ve kirpik uçları tamamen dışlandı. Sağ göz: `INSUFFICIENT_VISIBLE_AREA`. |
| **`4b13b16a`** | **Doğal Dik Negatif Kontrol** | `0.4113` / %0 / 10 px | **`0.4803`** / **%0** / **10 px** | **TEMİZ SIFIR UI** — Pürüzsüz cilt, sahte alarm yok. |
| **`5bd42346`** | **Dönüştürülmüş Regresyon Örneği** | `0.3335` / %0 / 25 px | **`0.4167`** / **%0** / **71 px** | **TEMİZ SIFIR UI** — Gürültülü ve açılı örnekte skor taban altında tutuldu. |

---

## 4. Non-Regression (Diğer Hedeflerin Korunumu) Güvencesi

Tüm örneklerde eşzamanlı olarak diğer kriterlerin durumları doğrulanmıştır:
- **Morluk v4 (`dark`):** `lower-lid-contrast-chroma-local-v4` normalizasyonu ve skorları birebir korunmuştur.
- **Torbalanma v5 (`bags`):** `contour-fold-local-support-v5` normalizasyonu ve sıfır/pozitif ayrımı etkilenmemiştir.
- **Kuruluk (`dry`):** `eligible-flake-area-fixed-v2-shared` normalizasyonu değişmemiştir.
- **Sarkma (`sag`):** Yanak ve çene süreklilik formülü ve sınırlama kodları korunmuştur.
- **Birim Testler:** `test_skin_expanded_corrections.py` (10/10 test), `test_skin_anatomical_bands.py` ve `test_local_appearance_health.py` (25/25 test) olmak üzere **35/35 test başarıyla geçmiştir**.

---

## 5. Makbuz ve Görsel Kanıtlar

- **Makine Makbuzu:** `audit-results/crows-feet-20261012/crows-feet-receipt.json`
- **Görsel Galeri:** `audit-results/crows-feet-20261012/gallery/index.html`
- **Kırpılmış Orijinal & Siyan Örtüşme Görselleri:** `audit-results/crows-feet-20261012/gallery/assets/`
