# Güvenlik, Klinik Sınırlar ve Kullanıcı Onay Politikası (SAFETY.md)

Bu belge, **Attune.more** sisteminin tıbbi güvenlik, sürüş güvenliği, ruhsal iyi oluş koruma mekanizmaları ve otonom randevu asistanı onay ilkelerini tanımlar.

---

## 1. Klinik ve Tıbbi Güvenlik İlkesi (Non-Diagnostic Principle)

### 1.1. Tıbbi Teşhis İddiası Reddi
Attune.more **tıbbi teşhis koymaz** ve bir tıbbi cihazın yerine sunulmaz. Gelecekteki ürünün düzenleyici sınıflandırması, kullanım amacı ve hedef pazara göre ayrıca değerlendirilmelidir.
Sistem kullanıcıya doğrudan hastalık ismi, patolojik tanı veya kesin klinik hüküm vermez.

* **YANLIŞ DİL (Yasak):**
  - ❌ *"Akneniz var."*
  - ❌ *"Depresyondasınız."*
  - ❌ *"Gözünüzde miyopi / katarakt var."*
  - ❌ *"Cildinizde melanom şüphesi bulunmaktadır."*

* **DOĞRU DİL (Zorunlu):**
  - ✅ *"Önceki ölçümünüze göre bu bölgede görsel bir değişim gözlendi."*
  - ✅ *"Son görüşmelerinizde stres ve uyku tekrar eden temalar olarak öne çıktı."*
  - ✅ *"Önceki değerlendirmeye göre kontrast hassasiyetinizde değişim gözlendi."*
  - ✅ *"Bu sonuçlar bir tıbbi tanı niteliği taşımaz. Bir sağlık profesyoneliyle görüşmeniz faydalı olabilir."*

### 1.2. Değişim ve Eğilim Takibi
Sistem tek seferlik yargılayıcı "sağlık puanları" üretmek yerine, zamana yayılan baz çizgi (baseline) karşılaştırmasını temel alır. Kullanıcı her test ve taramada önceki kayıtlarıyla kıyaslanan eğilim raporunu görür.

---

## 2. Otomotiv ve Sürüş Güvenliği (Vehicle Context Integration)

Sürücünün yoldaki dikkatinin dağılmasını engellemek en yüksek önceliktir.

```
                  +--------------------------+
                  |  VehicleContextProvider  |
                  +-------------+------------+
                                |
             +------------------+------------------+
             |                                     |
   [ SÜRÜŞ MODU: Hareket ]               [ PARK MODU: Duruyor ]
             |                                     |
- Görme Testi: KİLİTLİ                 - Görme Testi: AKTİF
- Cilt Taraması: KİLİTLİ               - Cilt Taraması: AKTİF
- Mental: Yalnızca Ses (Kısa, Sakin)   - Mental: Detaylı Panel & Özet
- Ekran: Minimal, Uyarı Yok            - Randevu: Detaylı Liste & Onay
```

### 2.1. Sürüş Modu (Vehicle Moving / v > 0 km/s)
- **Görme ve Cilt Modülleri Kilitlenir:** Kamera tabanlı dikkat gerektiren tüm görme ve cilt taramaları otomatik olarak durdurulur ve başlatılması engellenir.
- **Mental Asistan (Voice-First):** Ekrana bakmayı gerektirmeyen, soru formu içermeyen, kısa ve sakin sesli yanıtlar verilir.
- **Konu Erteleme:** Derinleşen veya sürücünün dikkatini zorlayan konuşmalarda asistan şu yanıtı verir:
  > *"Sürüş güvenliğiniz için bu konuyu araç park edildiğinde daha detaylı ele alabiliriz."*

### 2.2. Park Modu (Vehicle Parked / v = 0 km/s)
- Tüm modüller (görme kalibrasyonu, cilt analizi, geçmiş karşılaştırmaları, otonom randevu slot eşleştirme) tam işlevle kullanılabilir.

---

## 3. Ruhsal İyi Oluş Güvenlik Politikası & Kriz Protokolü

### 3.1. Kimlik Sınırları
Yapay zekâ asistanı kendisini **asla psikolog, psikiyatrist, psikoterapist veya hekim** olarak tanıtmaz. Sağlanan destek yalnızca "ruhsal iyi oluş ve sohbet desteği" olarak çerçevelenir.

### 3.2. Profesyonel Desteğe Nazik Yönlendirme (Escalation)
Kullanıcının son seanslarında stres, yoğun kaygı, uyku problemleri gibi temalar kronik olarak tekrar ediyorsa, asistan yargılamadan profesyonel destek önerir:
> *"Son görüşmelerimizde uyku ve stres konularının tekrar ettiğini görüyorum. Bir uzman psikologla görüşmek faydalı olabilir. İsterseniz programınıza uygun uzmanları araştırabilirim."*

### 3.3. Acil Durum ve Kriz Protokolü
Asistan; kendine zarar verme, intihar düşüncesi veya akut şiddet belirten anahtar ifadeler tespit ettiğinde standart sohbeti derhal durdurur ve acil destek yönlendirmesi yapar:
> *"Söyledikleriniz benim için çok önemli ve şu an zor bir an yaşadığınızı anlıyorum. Ancak ben bir acil durum veya sağlık servisi değilim. Lütfen güvende kalmak için hemen 112 Acil Çağrı Merkezi ile iletişime geçin:*
> - *Acil Çağrı Merkezi: **112***

> [!IMPORTANT]
> **Kriz Desteği ve Poliklinik Randevu Ayrımı:**
> - Sağlık Bakanlığı MHRS randevu hattı bir kriz danışma servisi **değildir**; poliklinik randevu sistemidir. Bu nedenle kriz mesajlarında asla randevu hatları veya doğrulanmamış hayali kriz numaraları kullanılmaz. Acil kriz hallerinde yegane resmi acil destek kanalı **112 Acil Çağrı Merkezi**'dir. Rutin randevu kanalları yalnızca kriz dışı, rutin hekim randevusu planlama adımlarında listelenebilir.
> - **Araç Hareket Halindeyken Kriz:** Sürücüden ekrana bakması kesinlikle istenmez. Asistan sesli olarak sürücüye aracını güvenli bir yerde durdurmasını ve derhal 112'yi aramasını tavsiye eder.

## 4. Otonom Randevu Asistanı Sınırları & Açık Onay Kapısı

### 4.1. Geri Döndürülemez Eylem Yasağı (No Irreversible Action)
Browser Agent, teknik ve hukuki olarak erişilebilir kamuya açık kaynaklarda hekim ve görünür müsaitlik bilgilerini salt-okunur biçimde araştırabilir. Canlı müsaitliğin alınamadığı durumlarda kullanıcı ilgili randevu sayfasına güvenli biçimde yönlendirilir.
**Kullanıcı açıkça "Onaylıyorum" demeden hiçbir rezervasyon formu gönderilemez, randevu kesinleştirilemez ve ödeme yapılamaz.**

### 4.2. İnsan Devri (Human Handoff) & Güvenli Düşüş (Fallback)
Web sitelerinde CAPTCHA, SMS onay kodu, zorunlu kullanıcı girişi veya ödeme adımı ile karşılaşıldığında sistem kilitlenmez; kullanıcıya güvenli handoff mesajı ile ilgili sayfa sunulur:
> *"Sizin için en uygun randevu seçeneğini belirledim. SMS veya son doğrulama adımını tamamlamanız için randevu sayfasını açıyorum."*
