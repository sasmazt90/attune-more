# Ürün Yol Haritası (ROADMAP.md)

Bu yol haritası, **Attune.more**'un yerel prototipten üreticiden bağımsız araç ve mobil entegrasyon hedeflerine uzanan gelişim basamaklarını tanımlar. Aşağıdaki ilk-MVP kapsamı tarihsel bir plan kesitidir; güncel teslim durumu için [README](README.md) esas alınır. Üretici ortaklığı veya gerçek araç entegrasyonu henüz doğrulanmış değildir.

---

## Aşama 1: Yerel Entegre MVP (Mevcut Doğrulanmış Durum)
* **Hedef:** Harici araç donanımına ihtiyaç duymadan, standart web kamerası ve mikrofonu ile çalışan 4 modüllü entegre bir ürün demosu.
* **Kapsam:**
  - Kamu malı optometri formüllerine dayalı Landolt C görme keskinliği ve ekran tabanlı kontrast duyarlılığı ön değerlendirmesi.
  - Apache-2.0 MediaPipe (`@mediapipe/tasks-vision`) tabanlı 6 anatomik ROI cilt analizi ve baz çizgi (baseline) karşılaştırması.
  - Sürüş vs. Park duyarlı, kriz protokolü entegre sesli mental asistan.
  - Playwright browser agent mimarisiyle salt-okunur arama ve erişimin kısıtlandığı hallerde güvenli devir (Safe Handoff).
  - `MockVehicleProvider` ile sürüş/park modu simülasyonu (`VehicleDataProvider` / `ToggVehicleProvider` soyutlaması).
  - Yerel localStorage ve JSON oturum belleği ile gizlilik mimarisi.

---

## Aşama 2: Araç Üreticisi PoC ve Araç İçi Entegrasyon Aşaması (Planlanan)
* **Hedef:** Erişim sağlanırsa hedef üreticinin test araçlarında veya kabin simülatöründe PoC doğrulaması.
* **Kapsam:**
  - Hedef üreticinin PoC kapsamında erişime açabileceği kamera, giriş, ses, navigasyon ve araç bağlamı API/SDK'larına göre uyarlama planlanır.
  - Direksiyon tuşları erişilebilir ise Landolt C yön seçiminde alternatif giriş yöntemi olarak değerlendirilebilir.
  - Araç içi mikrofon ve hoparlörler ile sesli diyalog entegrasyonu (uygun ses API/SDK erişimi kapsamında).
  - Araç ve eşlikçi mobil uygulama kullanıcı profili ile oturum açma soyutlaması.

---

## Aşama 3: Araç Bağlamı ve Harita / Rota Entegrasyonu
* **Hedef:** `MockVehicleProvider` yerine resmi API'lerle çalışan `ToggVehicleProvider` geçişi.
* **Kapsam:**
  - Togg bilgi-eğlence ekranı üzerinde uyumlu Web App veya optimize yerel entegrasyon olarak çalışma.
  - Araç Telemetrisi (`VehicleDataProvider` / `ToggVehicleProvider` soyutlaması üzerinden Togg tarafından sağlanacak resmi araç API/SDK'ları): Park/Sürüş modu, araç hızı ve bağlam verileri.
  - Kullanıcının tercih etmesi halinde hekim kliniğine rota yönlendirmesi (resmi navigasyon API/SDK desteği doğrultusunda).
  - Şarj molalarında isteğe bağlı 5 dakikalık "Mola Sağlık Kontrolü" önerileri.

---

## Aşama 4: Sağlık Kuruluşları ve Platform Entegrasyonları
* **Hedef:** Kamuya açık web tarayıcı aramasından doğrudan kurumsal hekim ağı ve API ortaklıklarına geçiş.
* **Kapsam:**
  - Türkiye'deki sağlık randevu platformları ve sağlık bilişimi sağlayıcıları ile resmi API entegrasyonu.
  - Özel sağlık kuruluşları ile HL7 / FHIR uyumlu güvenli randevu ve sevk köprüsü.
  - Kullanıcının açık rızasıyla, geçmiş görme veya cilt değişim özetinin hekime aktarımı.

---

## Aşama 5: Düzenleyici Değerlendirme ve Ticari Model
* **Hedef:** Sürdürülebilir ürün modeli ve regülasyon uyumu.
* **Kapsam:**
  - **Klinik Validasyon ve Düzenleyici Değerlendirme:** Ürün iddialarına ve hedef pazara göre gerekli klinik validasyon ve düzenleyici sınıflandırmanın değerlendirilmesi (tıbbi cihaz sınıflandırması gelecekteki kullanım amacına ve sağlık otoriteleri onay süreçlerine bağlı olarak belirlenecektir).
  - **Togg Kullanıcı Ekosistemi:** Tru.More platformu üzerinden isteğe bağlı premium iyi oluş ve sağlık asistanı aboneliği.
  - **Kurumsal Filo Sağlığı:** Filo sürücülerinin mola ve zindelik takibine yönelik kurumsal çözümler.
