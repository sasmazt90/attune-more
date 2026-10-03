# İzole dependency göçü — incelemeye hazır sonuç ve karar planı

Branch experiment/attune-dependency-prototype, temel a733c23. Ayrı worktree: C:/Users/PC/Desktop/AI Workspace/TOGG/attune-dependency-prototype. Ürün fix/live-test-followup branch'ine taşınmadı; main merge yok. Bu **kısmi prototiptir**, güvenli audit0 veya ürün geçişi kabulü değildir.

## Gerçek kurulum sonucu

- Framework Next15.5.27, React/ReactDOM19.0.8 korunur. eslint-config-next15.5.27 ve @next/eslint-plugin-next15.5.27 korunur; downgrade/Next16 framework yok.
- Gerçek kilitli aday: Tailwind4.3.3 + @tailwindcss/postcss4.3.3 + PostCSS8.5.28; CLI ESLint9.39.5 + @eslint/eslintrc3.3.5 (uyumluluk denemesi; **bakım dışı**).
- Fresh manifest-only lock çözümlemesi ve gerçek npm ci exit0. npm ls --all exit0; peer invalid yok. JSON'da iki optional extraneous kaydı (@img/sharp-wasm320.35.5 ve @emnapi/runtime1.11.3) hâlâ var; prune/clean manifest çözümünden sonra da görülüyor. Lock içinde sürüm/integrity kayıtları var; tam sıfır problem graph iddiası yok.
- Full audit **5 high**, production-only **0**. Açık kayıtlar @next/eslint-plugin-next, eslint-config-next, fast-glob, micromatch, braces. Tek temel advisory hâlâ açık.
- npm lint/typecheck/fresh production build exit0; gerçek build ve kaynak UI testleri yapıldı. Yalnız metadata audit sonucuna dayanılmadı.

## Kaldırılan ve kalan zincirler

Tailwind3 → chokidar → braces, Tailwind3 → fast-glob → micromatch → braces ve Tailwind3 → micromatch → braces artık yok. Tailwind4 gerçek dependency metadata'sında bu yollar yok; graph ve installed module resolution ile kontrol edildi.

Kalan: eslint-config-next15.5.27 → @next/eslint-plugin-next15.5.27 → fast-glob3.3.1 → micromatch4.0.8 → braces3.0.3. Yedi eski npm advisory package kaydından Tailwind/chokidar kapanır; kalan beş **açık**. Production audit0 build/dev/lint/CI riskini kapatmaz.

3 Ekim2026 upstream: braces latest3.0.3, patched none; fast-glob latest3.3.3/micromatch4.0.8 de braces taşır. Next15 lint latest15.5.27. En yeni @next/eslint-plugin-next16.3.8 metadata'sı da fast-glob3.3.1 taşır; bu plugin kurulum/göç önerisi değildir, sadece registry araştırmasıdır. [Advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).

## Lint kapsamı / destek sınırı

Next15'in önerdiği FlatCompat + next/core-web-vitals yaklaşımıyla CLI ayarlandı. Dört temsilci TS/TSX dosyada52/52 kural, severity ve option semantiği aynı; 34/34 source dosyası lint edildi, aynı üç warning,0error. "warn"/1 gibi serializer farkları normalize edildi; hiçbir kural kaldırılmadı. Build sırasında lint korunur; ignoreDuringBuilds/continue-on-error/seviye düşürme yok. [Next15 ESLint belgesi](https://nextjs.org/docs/15/app/api-reference/config/eslint).

Peer uyumu bakım desteği demek değildir: config15 peer ESLint7/8/9 kabul eder. ESLint9 resmî EOL2026-08-06; ESLint8 de EOL. Güncel10.12.0 + config15.5.27 izole metadata çözümü **ERESOLVE** verdi; force/legacy-peer-deps kullanılmadı. ESLint10'u desteklenmiş gibi override etmedik. Doğrudan standalone Next plugin yaklaşımı da aynı fast-glob yolunu taşır; config paketini çıkarmak advisory'nin kökünü kapatmaz. [ESLint support](https://eslint.org/version-support/).

Bu nedenle şu anda kullanıcının koşullarını birlikte sağlayan **desteklenen audit0 sürüm önerisi yok**. Test edilen9.39.5 promotable çözüm değildir. Ürün lint'i mevcut hâliyle korunur. Fork/vendor/paket adı değişikliği/suppression/uyumsuz chokidar override yapılmadı.

## Değişecek dosyalar ve CSS etkisi

1. apps/vehicle-app/package.json: v4/PostCSS plugin/ESLint CLI ve exact aday sürümleri.
2. package-lock.json: gerçek graph; npm ci ile yeniden kuruldu.
3. apps/vehicle-app/postcss.config.js: @tailwindcss/postcss.
4. apps/vehicle-app/src/app/globals.css: v4 import, mevcut JS theme için @config, packages için @source; v3 border/ring default uyumluluk katmanı.
5. apps/vehicle-app/eslint.config.mjs: FlatCompat/core-web-vitals. Legacy .eslintrc inceleme için korunur; ESLint9 flat config'i kullanır.

Touch minimumları, özel Togg/cockpit renkleri/font ve packages kapsamı legacy theme/source ile korunmaya çalışıldı. Bu tüm CSS davranışlarının eşdeğerliğini kanıtlamaz. V4 yeni palette/color, shadow/radius/ring, Preflight ve kaynak tarama farkları vardır. [Tailwind upgrade guide](https://tailwindcss.com/docs/upgrade-guide).

Gerçek UI karşılaştırması:7route ×1280x900/390x844 =14snapshot; main/h1/h2/button/header/nav computed styles. 78element/property kayıt farkı (renk serileştirme ve pill-radius dahil;78hata değildir).15sampled element bbox değişti; en büyük coordinate delta16px.14shadow ve14radius farkı bulundu. Desktop home ve mobile vision görseli ayrıca incelendi. Görme canlı follow-up testinin dört yön gerçek Landolt pixel/kalibrasyon assertion'ları PASS; bu bütün major migration kabulü değildir.

Somut sonraki CSS işi: mevcut shadow-sm sınıflarını v4 shadow-xs eşdeğerine, eski shadow/rounded/blur/outline utility'lerini uygun v4 isimlerine eşleştirmek; kullanılan v3 renk token'larını gerekiyorsa exactRGB ile korumak; border/ring ve packages source kapsamını yeniden doğrulamak. Sonra skin/mental modal/print/görüşme/dynamic states, cilt actualMediaPipe/ref, mobile/desktop screenshot farkları, gerçek Landolt ölçüsü ve bütün ürün matrisi gerekir. Ölçü/kontrast değişimi otomatik kabul edilemez.

## Karar planı

**Ürüne taşıma önerilmiyor.** Braces içermeyen resmî Next15-uyumlu lint zinciri ve güncel desteklenen ESLint peer/config çözümü prerequisite. Bunlar çıkmadan Tailwind4'ü tek başına taşıma full-audit hedefini karşılamaz; audit5 ve bakım dışıCLI ile risk kabulü gerektirir, kullanıcı böyle onay vermedi.

Güvenli upstream zincir yayımlandığında: exact sürümleri kilitle, peers/npmci/npmls/audit0 doğrula, yukarıdaki CSS eşdeğerlik değişikliklerini bitir, tam fonksiyonel ve görsel/ölçümsel matrisi çalıştır, somut diff'i kullanıcıya sun. Kullanıcı ürüne major migration'ı onaylamadan cherry-pick/merge yapılmaz. Fork/vendor ve risk istisnası bu talebin dışında kalır.

## Kanıt dosyaları

- audit-results/registry-proof.json, eslint10-peer-check/result.log.
- clean-install-status.json, clean-ci.log, prototype-npm-ls-final.json, prototype-npm-audit-final.json, prototype-npm-audit-production-final.json.
- prototype-path-proof.json, lint-coverage-proof.json, prototype-final-checks.json; lint/typecheck/build-final.log.
- css-comparison-proof.json, css-ui-probe/metrics.json ve14PNG; live-followup/first-group.json ve log.

Kaynak/privatekey/Chromeprofile/kullanıcı record kopyalanmadı; yalnız repo manifest/source ve anahtarsız sentetik UI kanıtları kullanıldı.
