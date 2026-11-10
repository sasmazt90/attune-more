# KOL A ↔ KOL B — yalnız ortak ölçütler (2026-11-10)

Kurallar: aynı girdiler; iki kolun test girdileri farklılaştırılarak üstünlük iddia edilmez; KOL A'nın sonuçları yalnız
**yayımladıkları** dosyalardan (paylaşılan başlangıç `4b3f596`) veya salt okunur yeniden üretimden alınır; hazır olmayan
sonuç **beklemede**. Donanımlar farklıdır (aşağıda her satırda). Seçim sahibindir.

| Ölçüt (aynı girdi) | KOL A | KOL B (bu prototip) | Not |
| --- | --- | --- | --- |
| Ürettiği kişisel satırın yanlış kabulü, 37 paylaşılan kullanıcı girdisi | **Beklemede** (KOL A'nın sağlayıcısı bu girdilerle bu oturumda çağrılmadı — ücretli API yasak) | 24 söylendi: 22 doğru, 1 dilbilgisi, **1 yanlış kabul** (`de-tempo`); 13'te hiçbir şey söylenmedi (9 doğru ret, 4 gereksiz ret) | KOL B satırları host CPU'da üretildi |
| Aynı satırlar KOL A'nın round-6 doğrulayıcısıyla (`7dcf505`, salt okunur) | — | 23 söylenir, 0 yanlış kabul (`de-tempo` reddedilir) | KOL A'nın dalı hareket ediyor: **geçici** |
| 94 aday satır — ürün doğrulayıcısı (iki kol için aynı kod) | Taban `4b3f596`: 4 yanlış kabul, 4 gereksiz ret. Round-6 `7dcf505`: **0** yanlış kabul, aynı 4 gereksiz ret (salt okunur yeniden üretim; KOL A'nın 102 vakalık güncel fixture'ında da 0) | Aynı doğrulayıcıyı değiştirmeden kullanır; tarayıcıda Pyodide ile 94/94 aynı karar | Doğrulayıcı KOL A'nın işi; KOL B onu cihazda çalıştırır |
| 4 açık yanlış kabul (`en-role-reversal`, `en-added-thing-modifier`, `de-added-thing-in-compound`, `tr-added-thing-modifier`) | Round-6'da 4/4 reddediliyor (salt okunur, geçici) | Taban doğrulayıcı + prototipin Qwen doğrulayıcısı: **4/4 hâlâ kabul** (Qwen doğrulayıcısı 58 yanlış satırın 0'ını yakaladı) | Bu kapanış KOL A'nın doğrulayıcı işine bağlı |
| Yazılı özet doğruluğu / konu kapsamı | KOL A yazılı özeti bulut sağlayıcısıyla (`gpt-4o-mini`) üretiyor; aynı 18 konuşmada sonucu **beklemede** | Uydurma 0 (yapı gereği: yalnız kullanıcının cümleleri), düzeltme 3/3; gruplama: 4 tam, 11 kısmi, 2 yanlış, 1 JSON yok | Farklı tasarım: KOL B serbest metin özet üretmez |
| Kapanış: tetik → ilk kişisel ses (toplam bekleyiş) | Yayımlanmış round-4 canlı WEB (CPU TTS + bulut): sıcak 20,2–22,9 s, soğuk 30,0–32,8 s | EN 3,57 s, DE 3,58 s; TR kişisel satır reddedildi (n = 3, tarayıcı ses + aynı VM'de host LLM) | KOL A katalog kayıtlarıyla (`7dcf505`) yeni ölçüm **beklemede** |
| Kapanış: hazır köprü bitişi → kişisel ses boşluğu | Round-4 canlı: C sonrası 11,5–12,5 s sıcak, 19,8–21,9 s soğuk | Köprü sonrası EN 0,24 s, DE 0,02 s (köprü ~3,1–3,6 s) | KOL A 3 hazır kayıt (A/B/C, `female-calm-v1`), KOL B 1 hazır köprü cümlesi (Piper prototip sesi) |
| Hazır cümle hızlı başlıyor mu | A: tetikten 17–19 ms sonra | Köprü: tetikten 9–13 ms sonra | Hazır cümlenin hızlı başlaması, kişisel yanıtın hazır olması değildir |
| Ses kimliği | Onaylı profil `female-calm-v1` (kayıtlar sahip dinleme onayı bekliyor) | **Farklı** prototip sesleri (Piper); eşdeğer sayılmaz; TR sesi ticari değil | |
| Ücretli API | Bulut sağlayıcı (özet/satır) | Yok | |
| Platformlar | WEB, GPU, AAOS emülatörü (canlı ölçümler var) | WEB CPU: FAIL; WEB GPU: BLOCKED (yalnız emülasyonda işlevsel); AAOS: derlendi, çalıştırma BLOCKED | |

KOL A'nın son test paketi yayımlandığında aynı tablo, aynı girdilerle ve değiştirilmeden yeniden doldurulur.

Not: KOL B'nin kapanış sayıları daha hızlı küçük bir TTS (Piper, prototip sesi) ve 4 vCPU VM'deki LLM ile; KOL A'nınkiler onaylı ses profilinin sunucu tarafı üretimiyle. Ses kalitesi/kimliği ve gecikme ayrı değerlendirilmelidir; dinleme onayı her iki kolda da bekliyor.
