# Geliştirme bağımlılığı advisory incelemesi

3 Ekim 2026: fresh full npm audit 7 high; production-only 0. Tek temel advisory [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm), braces <=3.0.3 recursive AST stack exhaustion/DoS. Güncel registry latest braces 3.0.3; advisory patched version none. Yedi package kaydı yedi ayrı kök CVE değildir; tek bulgunun bağımlılık zincirlerine yayılımıdır.

| npm audit kaydı | Durum / bağımlılık rolü |
|---|---|
| braces | Açık high; doğrudan temel advisory |
| micromatch | Açık high; braces tüketir |
| fast-glob | Açık high; micromatch tüketir |
| chokidar | Açık high; braces glob desteği |
| tailwindcss | Açık high; yukarıdaki üç Tailwind yolu |
| @next/eslint-plugin-next | Açık high; fast-glob yolu |
| eslint-config-next | Açık high; Next lint plugin yolu |

Gerçek installed package.json çözümlemesi (npm ls dedup düğümleri tek başına tüm yolları göstermediği için Node çözümleme konumlarıyla doğrulandı):

1. tailwindcss@3.4.19 → chokidar@3.6.0 → braces@3.0.3
2. tailwindcss@3.4.19 → fast-glob@3.3.3 → micromatch@4.0.8 → braces@3.0.3
3. tailwindcss@3.4.19 → micromatch@4.0.8 → braces@3.0.3
4. eslint-config-next@15.5.27 → @next/eslint-plugin-next@15.5.27 → fast-glob@3.3.1 → micromatch@4.0.8 → braces@3.0.3

## Erişilebilirlik

Build: Tailwind PostCSS plugin içerik globlarını çözer; Next build lint de çalıştırır. Dev: Tailwind watch/chokidar yolu etkindir. Lint/CI: Next lint plugin dosya arama kuralları fast-glob kullanır. Bu işlemler glob pattern/config/repo girişleriyle DoS yaşayabilir. Mevcut content kalıpları repodaki sabit kaynak yollarıdır; kullanıcı sohbet/cilt sonuçlarını doğrudan brace pattern'e taşıyan yol bulunmadı. Bu bir risk kabulü değildir.

Runtime: production npm audit bu yedi dev kaydını dışarıda bırakır; gerçek `.next/**/*.nft.json` server trace'lerinde bu yedi paket için eşleşme bulunmadı. Üretilen CSS servis edilir. Bu kontrol bütün bundled framework kodunun/başka açıkların temiz olduğu iddiası değildir ve build/dev/CI riskini kapatmaz.

## Somut seçenekler

| Seçenek | Değişiklik / maliyet | Sonuç / karar |
|---|---|---|
| Desteklenen patch/minor zinciri | Braces düzeltmesi veya Tailwind 3/Next 15 lint plugin'in braces kullanmayan uyumlu güncellemesi | Şu an registry'de yok. Tailwind 3 latest 3.4.19, eslint-config-next 15 latest 15.5.27. Dar kapsamlı çözüm uygulanamadı. |
| Tailwind 4.3.3 + @tailwindcss/postcss 4.3.3 | Major CSS geçişi: PostCSS plugin/import, kaynak tarama, JS config/theme bağlama ve eski utility/default davranışlarının kontrolü | İzole metadata-only lock/audit 0; ürün build'i/UI davranışı doğrulanmadı. ESLint yolu kaldığı için tek başına full audit'i çözmez. Kullanıcı kararı olmadan uygulanmadı. |
| Chokidar 4 override | Major sürüm glob desteğini kaldırır; Tailwind 3'ün beklediği davranış değişir | Uyumlu güvenlik düzeltmesi sayılamaz; uygulanmadı. |
| ESLint major yükseltmesi | Lint yapılandırması/plugin/rule uyumluluğu | Aynı Next 15 plugin fast-glob yolunu kendiliğinden kaldırmaz. Lint kuralları kaldırılmadan çözüm olduğu kanıtlanmadı. |
| İncelenmiş fork/vendor depth guard | Braces parse/compile/expand AST yürüyüşlerinde sınır; uyumlu glob çıktıları ve edge-case testleri; bakım sorumluluğu | Kaynak güvenliği ve güncelleme yükü ayrı inceleme gerektirir; npm advisory sürüm kaydı yine açık kalabilir. Adını değiştirerek audit yeşile çevirmek çözüm değildir. Otomatik uygulanmadı. |

Tailwind geçişinin bu repodaki somut etkisi: `postcss.config.js` ve `globals.css` girişi değişir; `tailwind.config.js` renk/font/touch theme'i ve `../../packages` content kapsamı korunmalıdır. V4 border/ring ve bazı shadow/radius utility davranışları değişir; sekiz route, 390/1280 viewport, Landolt piksel geometrisi ve cilt/mental modal/print ekranları yeniden görsel ve fonksiyonel sınanmalıdır. [Resmî v4 geçiş kılavuzu](https://tailwindcss.com/docs/upgrade-guide).

Next 16, React/Next güvenlik downgrade, eslint-config-next 14.2.35, force fix, audit suppression/continue-on-error veya lint/Tailwind kaldırma yapılmadı. Major/fork kararı ve olası risk kabulü kullanıcıya aittir. Mevcut full audit adımı başarısız kalır.
