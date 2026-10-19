# Açık Kaynak ve Lisans Politikası (LICENSES.md)

Güncel model dosyaları ve kod/ağırlık/veri ayrımı için
[2026-10-18 runtime kaynak matrisi](docs/model-sources-20261018.md) esas alınır.
Aşağıdaki ilk-MVP/tarihsel değerlendirmeler güncel ağırlık envanteri değildir.
“Kısıtlanan/Yasaklanan” listesi proje politikasıdır; her üçüncü taraf lisansının
evrensel kullanım yasağı olduğu anlamına gelmez. Kaynak matrisindeki açık izin,
belirli eyleme bağlı kısıt ve eksik belge ayrı tutulur; ürün bayrakları değişmez.

Bu belge, **Attune.more** projesinde kullanılan, referans alınan veya ilerleyen aşamalarda entegre edilmesi planlanan kütüphane, model, veri seti ve araçların lisans durumlarını ve ticari uygunluk değerlendirmelerini içerir.

> [!IMPORTANT]
> **Proje Kodlarımızın Lisans Durumu:** Bu reponun public olması kodun açık kaynak/MIT lisanslı olduğu anlamına gelmez. Attune.more ürün ve uygulama kodları **UNLICENSED (Telif Hakkı Saklıdır / Özel Mülkiyet)** statüsündedir. Bu belge, yalnızca kullandığımız üçüncü taraf dependency/model/dataset lisanslarının uyumluluğunu şeffaf biçimde belgelemektedir. Third-party kütüphanelerin MIT/Apache-2.0 olması, ürün kodumuzun MIT olduğu anlamına gelmez.

---

## 1. Temel Lisanslama İlkeleri

1. **İzin Verilen Lisanslar (Permissive):** MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC.
2. **Kısıtlanan / Yasaklanan Lisanslar:** GNU GPL (v2/v3), AGPL, SSPL, CC-BY-NC (Gayri Ticari), Araştırma Amaçlı Özel Lisanslar.
3. **Model ve Veri Seti Ayrı İncelemesi:** Bir kütüphanenin kod deposunun MIT olması, eğitilmiş ağırlıklarının (weights) veya eğitim veri setinin ticari kullanıma uygun olduğu anlamına gelmez. Model ve veri seti lisansı her zaman koddan bağımsız doğrulanır.

---

## 2. Kullanılan Bileşenler Lisans Matrisi

| Bileşen / Kütüphane | Kategori | URL | Lisans | Ticari Kullanım Durumu | Açıklama / Kullanım Amacı |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Next.js** | Frontend Framework | [vercel/next.js](https://github.com/vercel/next.js) | MIT | **UYGUN** | Otomotiv arayüzü ve SSR/SPA katmanı. |
| **React / React-DOM** | UI Kütüphanesi | [facebook/react](https://github.com/facebook/react) | MIT | **UYGUN** | Reaktif bileşen mimarisi. |
| **Tailwind CSS** | Styling | [tailwindlabs/tailwindcss](https://github.com/tailwindlabs/tailwindcss) | MIT | **UYGUN** | Yüksek kontrastlı otomotiv koyu tema stilleri. |
| **Lucide React** | UI İkonları | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | ISC | **UYGUN** | Minimalist dokunmatik araç arayüz ikonları. |
| **FastAPI** | Backend Framework | [tiangolo/fastapi](https://github.com/tiangolo/fastapi) | MIT | **UYGUN** | Hafif, asenkron yerel API sunucusu. |
| **Pydantic** | Veri Modelleme | [pydantic/pydantic](https://github.com/pydantic/pydantic) | MIT | **UYGUN** | Tip güvenli sağlık profili ve araç bağlamı şemaları. |
| **Uvicorn** | ASGI Sunucusu | [encode/uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | **UYGUN** | Backend web sunucusu. |
| **Google MediaPipe** | Bilgisayarlı Görü | [google/mediapipe](https://github.com/google/mediapipe) | Apache-2.0 | **UYGUN** | Yüz tespiti, yüz bölütleme ve mesafe kestirimi. |
| **Microsoft Playwright** | Web Otomasyonu | [microsoft/playwright](https://github.com/microsoft/playwright) | Apache-2.0 | **UYGUN** | Randevu asistanı için otonom browser-agent altyapısı. |
| **browser-use** | Agent Kütüphanesi | [browser-use/browser-use](https://github.com/browser-use/browser-use) | MIT | **UYGUN** | Semantic DOM etkileşimleri için referans mimari. |
| **SQLite / aiosqlite** | Veritabanı | [sqlite.org](https://www.sqlite.org/) | Public Domain | **UYGUN** | Yerel, gizlilik odaklı kullanıcı ve sağlık geçmişi. |

---

## 3. Özel Durumlar ve Kritik Hukuki Analizler

### 3.1. FrACT (Freiburg Vision Test) ve Görme Metodolojisi İncelemesi
* **Durum:** Freiburg Visual Acuity & Contrast Test (FrACT), görme keskinliği araştırmalarında saygın bir altın standarttır. Ancak yazılımı **GNU GPL** lisanslıdır.
* **Karar ve Çözüm:** **FrACT kaynak kodundan tek bir satır dahi bu projeye kopyalanmamıştır.**
* **Mimarimiz:** Kamu malı (public domain) olan uluslararası optometri formülleri ($MAR = \frac{d}{D}$, $5 \text{ arcmin} = 1.0 \text{ Snellen / 0.0 LogMAR}$), Pelli-Robson kontrast basamakları ve psikofiziksel merdiven (adaptive staircase / best-PEST) algoritması **tamamen bağımsız ve özgün bir mimariyle sıfırdan yazılmıştır**.

### 3.2. Cilt Analizi Veri Setleri ve Yüz Bölütleme (Face Segmentation)
* **Risk:** Birçok akademik yüz bölütleme modeli (ör. CelebAMask-HQ tabanlı ağlar) yalnızca gayri ticari (CC-BY-NC) araştırma amaçlı yayınlanmıştır. Bu modellerin ticari araç yazılımına dahil edilmesi yasal risk yaratır.
* **Karar ve Çözüm:** İlk MVP'de yasal risk taşıyan üçüncü parti eğitilmiş siyah-kutu ağırlıklar kullanılmamıştır.
* **Mimarimiz:** Tamamı Apache-2.0 lisanslı Google MediaPipe Face Mesh topolojisi kullanılarak; alın, sağ yanak, sol yanak, burun, çene ve göz çevresi bölgeleri matematiksel konveks kabuk (convex hull) ile ayrıştırılmıştır. Bölgesel kızarıklık, pigmentasyon ve doku eğilimleri CIELAB renk uzayı ($a^*$ kanalı) ve Laplacian doku varyansı gibi deterministik, patent/lisans kısıtı bulunmayan algoritmalarla hesaplanmaktadır.

### 3.3. Ruhsal İyi Oluş ve Ses Mimarisi
* **Mimarimiz:** Tarayıcı yerel Web Speech API (SpeechRecognition & SpeechSynthesis) sıfır gecikme ve sıfır dış bağımlılık için öncelikli tercih edilmiştir. Sunucu tarafı ses modelleri için MIT/Apache-2.0 lisanslı yerel kütüphaneler hedeflenmiştir.
