# TOGG Attune UAT kapsamı ve kanıt sınırları - 3 Ekim 2026

Bu çalışma ürün geliştirmesi ve doğrulamasıdır. Açık geliştirme bağımlılığı advisory'si nedeniyle koşulsuz "kullanıcı testine tamamen hazır" sonucu verilmez. Ürün `fix/live-test-followup`, PR #2 taslak; main merge kapsam dışıdır. Son SHA, Actions job/artifact sonuçları ve gerçekten açılmış screenshot envanteri yerel son teslim raporunda ayrıca kaydedilir.

## Gereksinim haritası

Sınıflar: U = uygulama, A = otomatik doğrulama, G = açılarak görsel inceleme, D = bağımlılık/güvenlik, W = Windows, K = son insan/yönetici kabulü.

| Word maddesi | Sınıf | Ürün davranışı / somut doğrulama |
|---|---|---|
| 1. Yüzde yeterli ışık | U/A/G | Yüz ROI luminance; karanlık yüz/parlak arka plan ve bilinmeyen kalite kontrolü. `skin_timing`, unit ve gerçek MediaPipe; klinik iddia yok. |
| 2. Netlik / sabit pozisyon | U/A/G | Netlik, durağanlık ve poz farklı koşullar; eşikler korunur. |
| 3. Sağ dönüş yönlendirmesi | U/A/G | Anatomik yön/yaw ve aynalama kontrolü; üç gerçek poz testi. |
| 4. Ön/sağ/sol üç kare | U/A/G | `skin_multi_angle_followup`: production MediaPipe, üç farklı frameToken, iki tarama ve v2 referans; elle baseline enjeksiyonu yok. |
| 5. Altı anatomik bölge | U/A/G | Şema vurgusu, bölge ve not eşleşmesi; altı gerçek UI bölgesi. |
| 6. İlk referans açıklaması | U/A/G | İlk geçerli taramanın sayısal metrikleri; ilk sonuçta değişim yok. Uyumlu/uyumsuz/eski/bozuk referans korunması. |
| 7. Dört hafta hatırlatması | U/A/G/W/K | 28 takvim günü; düzenleme, dedup, hata, iptal ve gerçek ICS. Dış takvim import/uyarı insan hesabında ayrıca doğrulanır. |
| 8. İşlevsiz ok kaldırma | U/A/G | Bakım/mola satırı yönlendirme oku içermez; yalnız gerçek Care handoff semantic button. |
| 9. Profilde gizlilik kopyası | U/A/G | Kopya aksiyon kaldırılmış; üst navigasyon sekmesi korunur. |
| 10. Tek Başlat / Bitir | U/A/G | Tam transcript, tur çiftleri, TTS sırasında dinleme kapalı, geç olay/izin/sürüş/unmount cleanup. 12 lifecycle kontrolü. |
| 11. Ses doğallığı | U/A/G/K | OpenAI TTS ayrı bulut onayı; decode, süre, sinyal, playing/ended/error/cancel teknik kontrolleri. Doğallık/telaffuz yalnız insan dinlemesiyle kabul edilir. |
| 12. Bağlamlı OpenAI yanıtı | U/A/G | LIVE/LOCAL/FALLBACK görünür; üç izinli sentetik turda gerçek provider geçmişi 0/2/4. Anahtarsız test canlı kanıt diye sunulmaz. |
| 13. Türkçe özet / yalnız bitiş | U/A/G | Türkçe mood, özet bekleme/iptal, bitiş öncesi kayıt 0; son anda izin guard. |
| 14. Tam görüşme akışı | U/A/G | USER/AI birer kez; uzun transcript; manuel geçmiş okurken zorlayıcı scroll yok. |
| 15. Başlangıçta sol / sağ | U/A/G | Başlat kontrolü solda; boş veya gerçek izinli kayıt istatistikleri sağda. |
| 16. Tema legend seçimi | U/A/G | Gerçek tamamlanmış izinli kayıtlar; iki görüşme/üç tema kaydı, pay/payda, yuvarlama, seçilen sosyal ilişkiler özeti. |
| 17. Tarihli geçmiş | U/A/G | Tamamlanmış kayıtlar tarih sırasıyla; ilk kullanıcıda 0, eski doğrulanamayan kayıt grafiğe girmez. |
| 18. Aktif görüşme düzeni | U/A/G | Solda kontrol; sağda sürekli transcript. Chat wait / audio wait ayrı; hazır metin korunur. |
| 19. Dört yönlü Landolt | U/A/G | Gerçek boyalı dört piksel yönü; mm/px/mesafe/logMAR aynı. Mobil 390, ara 820, desktop 1280 yan yana paneller; 2-down/1-up ölçüm kuralı korunur. |
| 20. Yalnız seçilen paylaşım | U/A/G/W | Başlangıçta seçilmemiş; mevcut olmayan kayıt disabled; aynı preview/print modeli. Gerçek Windows Chrome PDF Save/Open; hariç kategoriler ve örnek kimlik PDF/metadata'da yok. |

Word'ün 34 paragraf öğesi (25 metin içeren paragraf) ve 18 gömülü görseli yeniden okunup açıldı. Görseller 1-2 tarama; 3-8 altı bölge; 9 not; 10 trend; 11 aksiyon; 12 paylaşım; 13-14 eski mental; 15 başlangıç tasarımı; 16 aktif tasarım; 17 görme; 18 seçimli paylaşım ile eşleştirildi. Kaynaktaki yüz içeren türetilmiş PNG'ler inceleme sonrası silindi; orijinal Word değiştirilmedi ve CI/Git'e konulmadı. Örnek kimlik/sayım hasta verisi olarak kullanılmaz.

## Bu turun kök neden düzeltmeleri

- Mobil logo/PARK flex çakışması: header satır sarma, sabit PARK hedefi ve footer sarma.
- Kısa ekran modal taşması / odak kaçışı: ortak bounded dialog, background inert, Tab trap, Escape, çağırana focus dönüşü; başlık/close kaydırma sırasında görünür.
- Ara genişlik profil değer sıkışması: açık aralık, satır hizası ve uzun metin sarma.
- Privacy ekranında iki kayıt yerine tek latest gösterimi: gerçek izinli geçmiş sayımı ve saklanan özet/tema/mood/tarih açıklaması. OFF ve explicit UI ON ayrı gerçek UI kontrolleri.
- Ses beklerken yanlış "yanıt hazırlanıyor": ayrı chat/audio durumu; metin hazır kalır. Pending TTS mute gerçek request abort eder; summary beklerken iptal late response'ı dışlar.
- Her provider isteğinde SDK istemcisi/connection pool tekrar kuruluyordu: thread-safe reuse, config değişince close, shutdown close, timeout 25s ve retry 0. Güncel FastAPI ile kaldırılan event handler yerine [resmî lifespan](https://fastapi.tiangolo.com/advanced/events/) kullanılır; normal/exceptional çıkışta kapanma testlidir. Güvenlikten geçmemiş metin veya kısmi audio erkenden yayınlanmaz.
- Backend/egress/browser zaman sınırları ayrı: provider generation aktarım ile örtüşür; saf üretim ve network süresi uydurulmaz. Anahtarsız construction benchmark canlı E2E iyileşmesi değildir.
- Care yükleme görünmezdi: anlaşılır wait, 12s abort deadline, stale response guard, retry/unmount cleanup; kesintide örnek seçenek açıkça ayrılır. Ham exception loglanmaz.
- Mobile görme yön paneli alta düşüyordu: iki kolon, en az 44px touch genişliği; optotype hesabı ve 2-down/1-up değiştirilmedi.
- Mobil tur sayacı üç satıra bölünüyordu: başlık/ilerleme wrap ve kesintisiz sayaç; üç viewport'ta tek satır assertion, dört gerçek boyalı yön kontrolü.
- Üç açılı referans sonucu eski sabit 'tek karşı açı' açıklamasını gösteriyordu: açıklama gerçek comparisonScope değerine bağlı; gerçek tek/üç açılı MediaPipe UI akışlarında metin ve scope birlikte doğrulanır.

## Otomatik ve görsel doğrulama

Yeni `uat_ux_followup.py` gerçek keyless production UI/API ile explicit OFF/ON, başka sekmede last-write revoke, summary cancel, TTS failure/cancel, 7 route x 3 viewport, kısa dialog focus, loading/error/driving, gerçek uzun transcript ve CSS 200% reflow kontrollerini çalıştırır. Kapı açmak için kullanılan provider-status capability fixture açıkça fixture'dır; gerçek chat LOCAL_DEMO ve TTS 503'tür. Bu test canlı OpenAI/STT kanıtı değildir. Skin kısa-modal demo yalnız tasarım kontrolüdür; kabul baseline'ı `skin_followup`/`skin_multi_angle_followup` gerçek MediaPipe taramalarıdır.

`skin_followup.py` gerçek UI taramasından altı bölge/not screenshot'ı ve default-28/edit/dedup/error/ICS/cancel üretir. `windows_pdf_followup.py` gerçek Windows Chrome 132 ile disposable test-profile preference kullanarak kiosk Save-as-PDF yapar, dosyayı gerçek Chrome viewer'da açar ve sayfayı render eder. Bu manuel OS dialog tıklama iddiası değildir; genel Chrome profili veya sistem printer ayarı değişmez.

`windows_zoom_followup.py` disposable Chrome 132 profilinin partition zoom preference'ını kullanır; gerçek devicePixelRatio iki kat ve innerWidth yarıya iner. CSS zoom değildir; aynı üretim DOM'u gerçek browser media query reflow ile incelenir. Anahtarsızdır ve fiziksel capture girişimi 0 kalır. Global Chrome ayarı/profil değişmez.

Tam final Actions artifact verifier: `scripts/verify-uat-delivery.py`; 39 broader, 14 focused, 5 lifecycle, 23 browser, 8 timing, 157 unit (150 eski + 7 yeni, skip 0), 54 safety, 5 dependency, 12 mental, actual-three-angle/reference, native üç tur, 10 yeni UAT; her sayı ve SHA bağımsız okunur. Windows launcher 9 ve gerçek normal `.lnk` ShellExecute kanıtı yerelde ayrıdır. Yakalanmış screenshot, açılıp incelenmiş screenshot değildir; son rapor gerçek açılan envanteri verir.

Son takip: kokpitte araç simülasyonu sağlık demosundan ayrı etiketlenir; bağlı olmayan rota ve doğrulanmayan donanım hazır gösterilmez. API kaybı/senkronizasyon durumu gerçek VehicleContext üzerinden gösterilir; kilitler korunur. Care takvim/ulaşım/eşleşme alanları örnektir; onay yalnız yönlendirme hazırlar. Profilde aynı disabled koşulu korunarak kapalı PDF stili, hover ve erişilebilir açıklama eklenmiştir. `uat_truthfulness_followup.py` gerçek anahtarsız backend ile 390/820/1280'de üç ek akışı, boş çıktı yokluğunu ve seçilmiş çıktı kapsamını doğrular; `--before` yalnız gözlem üretir, PASS sayılmaz. CI verifier bu üç ek sonucu ve exact SHA'yı da zorunlu okur. Yeni önce/sonra ve Windows %200/PDF kanıtları `audit-results/uat-closure-20261003` altında eski envanterden ayrı tutulur. Yeni ücretli koşu yapılmaz.

Güncel peer zincirleri ve uygulanmamış exact-version alternatif için [dependency closure decision](dependency-closure-decision.md). Tailwind major / lint mimarisi değişikliği için ayrı izole araştırma kararı gerekir; bu belge bir güvenlik kapatma veya ürün yükseltmesi değildir.

## Açık dependency blocker ve dış koşul

3 Ekim resmî npm registry/advisory/support refresh: [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) hâlâ <=3.0.3, patched none. braces latest 3.0.3; fast-glob 3.3.3 ve micromatch 4.0.8 zinciri sürüyor. Tailwind/@tailwindcss/postcss 4.3.3 yalnız Tailwind zincirini azaltır. Next 15.5.27 ve 16.3.8 ESLint plugin'i fast-glob 3.3.1 kullanır. Next 16 bu bulguyu kapatmaz. eslint-config-next 15.5.27 peer eslint 7/8/9; current ESLint 10.12.0 bu peer aralığına girmez. [ESLint support](https://eslint.org/version-support/) 8 ve 9'u EOL gösterir (2024-10-05 / 2026-08-06).

Ürün fresh audit 7 high; prototype a617a675 full 5 high; her iki production-only audit 0. Prototype EOL ESLint 9 ve kabul edilmemiş CSS/ölçü farkları nedeniyle promote edilmez. Gerekli dış koşul: resmi patched braces/chain yayını ve uyumlu desteklenen ESLint peer/konfigürasyonu; ardından exact-version isolated migration, lint parity, iki temiz audit ve tam davranış/görsel matris. Advisory suppression, force, legacy peers, unsupported overrides, downgrade, fork/vendor/risk exception uygulanmadı. Aynı başarısız major kombinasyonları tekrar denenmedi.

## Provider incident ve son kabul sahipliği

Eski mikrofon olayının yerel silinmesi sağlayıcı silinmesi değildir. Eski anahtar revoked veya ZDR/MAM etkin sayılmaz. API kullanım yetkisi organizasyon admin yetkisi sağlamaz; yetkili admin connector yok. Proje/organizasyon yöneticisi eski exposed key ID'yi API Keys ekranından revoke durumuyla doğrulamalı; Organization Data controls + project overrides/data sharing ve incident request envanterini incelemeli; gerektiğinde OpenAI destek/privacy talebiyle retention/deletion sonucunu yazılı doğrulatmalıdır. Güvensiz transcript yeniden üretilmez veya yayınlanmaz.

Yalnız son kabul: Türkçe ses doğallığı/telaffuzunu insan dinlemesi; kullanıcının açıkça seçtiği fiziksel mikrofon ve kendi cihaz/izin yolu; kullanıcının takvim hesabında ICS import, gerçek alarm ve dış kayıt silme; yönetici provider incident/old-key işlemleri. Gerçek araç donanımı ve klinik doğruluk doğrulanmış sayılmaz. Normal Chrome 132 ve bundled Chromium 148 sonuçları ayrıdır; sistem tarayıcısı güncellenmedi.
