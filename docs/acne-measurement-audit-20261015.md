# Sivilce ölçüm ve kapsam kaybı denetimi — 2026-10-15

**Tanısal, sonradan yapılmış (post-hoc) yeniden değerlendirme.** Yeni sivilce algoritması, aday koşusu, eşik, fit, AUC, eğitim veya ürün aktivasyonu yok. Kod referansı dondurulmuş `5f11c111e3f6547e6420ddf37db477190d232f10`; korunan BUILD_ID `mlOb9YC5JKNnbE_1xzdjD` (girdi kökünde okundu). Üretim sivilcesi `accepted:false, file:null` kalır; ürün kabul kararı değişmez. Dondurulmuş A/B aday listeleri yetkili kaynaktır; hiçbiri yeniden yazılmadı.

## Kısa sonuç

- **Eski sonuçlar aynen yeniden üretildi:** Scope B kaynak-kutusu IoU≥0,50 A 0/14, B 0/14; bire bir kutu-içi merkez A 1/14, B 0/14. 13/13 ürün-geçerli fotoğrafta iki yöntemin dondurulmuş aday listesi, üretim `acne_candidates`/dondurulmuş `detect` ile ve kayıtlı `eligible.png` maskeleriyle bit düzeyinde aynı çıktı.
- **0/14'ün çoğu metrikten değil, ölçüm desteğinden kaynaklanıyor.** 14 Scope B hedefinin 10'unun merkezi seçili anatomik bölge desteğinin (beş bölge triangle-union) dışında. Kalan 4 hedefte: 2 aday üretimi yok, 1–2 bileşen filtresi, 1 (yalnız A) yerelleştirme IoU<0,50.
- **Metrik değişikliğiyle açıklanabilen üst sınır:** Scope B'de A için 1/14, B için 0/14; uygun kontrollerde her yöntem için 1/29. Herhangi bir örtüşmeyi (IoU>0) kabul eden gevşek eşleşme bile bu sayıları aşmıyor. “0/14 büyük ölçüde metrik yüzünden” hipotezi desteklenmiyor.
- **A/B crop asimetrisinin bu çıktılara fiili etkisi sıfır.** 32/32 A adayı crop içinde; A desteğinin crop dışındaki pikseli 0/633.804; B yanıt alanı tam kaynakta ve crop'ta filtrelendiğinde crop içinde 0 piksel değişiyor, eşikler 13/13 fotoğrafta aynı.
- **Bölge kaybının üç geometrik kaynağı var** (sonradan eklenen ayrım, amendment 1): yan pozda yalnız tek yanak meshinin dışa aktarılması, beş bölgenin konveks zarfı dışında kalan perioral/üst dudak/glabella alanları ve sunum meshinin dama tahtası gibi boş kalan üçgen hücreleri. Kaynak üstü incelemede bölge dışı kalan 29 hedefin 28'inde hedef görünür ciltte ve görünür bir örtücü yok; 1 hedef UNKNOWN.

## Hedef başına ilk kayıp (merkez, sıralı)

Sıra önceden kaydedildi: ürün kapısı → photo_input crop → anatomik bölge → otomatik dışlama → anatomik dışlama → kıl/saç → parlama/pozlama → gray eşiği → aday üretimi → bileşen/şekil/boyut/sahiplik filtreleri. Her hedef yalnız bir kez sayılır; örtüşen nedenler ayrıca bağımsız bayrak olarak tutulur.

| İlk kayıp | Scope B A | Scope B B | Uygun 3 kontrol A | Uygun 3 kontrol B | Reddedilen 25 kontrol |
|---|---:|---:|---:|---:|---:|
| Ürün kalite/poz/gözlük kapısı | 0 | 0 | 0 | 0 | 126 (alt aşamalar ölçülmedi) |
| photo_input crop | 0 | 0 | 0 | 0 | — |
| Anatomik bölge (triangle-union) | 10 | 10 | 19 | 19 | — |
| Otomatik / anatomik dışlama, kıl, parlama, gray | 0 | 0 | 0 | 0 | — |
| Aday üretimi (kutuda ham yanıt yok) | 2 | 2 | 1 | 0 | — |
| Bileşen filtreleri | 1 | 2 | 8 | 9 | — |
| Yerelleştirme, IoU<0,50 | 1 | 0 | 1 | 1 | — |
| IoU≥0,50 | 0 | 0 | 0 | 0 | — |
| **Toplam** | **14** | **14** | **29** | **29** | **126** |

Alan tabanlı ikincil atıf (kutuda hiç uygun piksel kalmadığında kayıp): Scope B aynı; kontrollerde A 17 bölge / 2 üretim / 9 filtre / 1 yerelleştirme, B 17 bölge / 11 filtre / 1 yerelleştirme. İki kontrol hedefinin (f2ed24a9#14, #16) merkezi bölge dışında ama kutusunun %2'si ve %36'sı uygun destekte.

Ölçek bantları (Scope B, A): mikro 1 hedef → üretim; küçük 10 → 8 bölge, 1 üretim, 1 filtre; orta 3 → 2 bölge, 1 yerelleştirme. B'de orta banttaki yerelleştirme yerine filtre var.

Ölçülen 43 hedefte merkezi crop, otomatik/anatomik dışlama, kıl, parlama veya gray aşamasında kaybedilen hedef yok. Kısmi alan kayıpları da çoğunlukla bölge desteğinden (ör. f2ed24a9#8 kutusunun yalnız %34'ü uygun); 4a1762ee#1'de parlama kutunun %7'sini ayrıca kaldırıyor. Analiz tuvalinin dışında kalan 9 hedefte kıl/parlama/gray/dışlama bağımsız bayrakları değerlendirilmemiş sayılır (UNKNOWN), geçti veya reddedildi diye yazılmaz.

### Anatomik bölge kaybının geometrik ayrımı (sonradan, yalnız geometri)

| Kategori | Scope B | Uygun kontroller |
|---|---:|---:|
| Yan poz, tek bölge dışa aktarılmış (55d380f7 RIGHT → yalnız leftCheek; 2ed3716e LEFT → yalnız rightCheek) | 6 | 5 |
| Dışa aktarılan beş bölgenin konveks zarfı dışında (üst dudak, perioral, glabella/kaş kenarı, dudak sınırı) | 2 | 8 |
| Zarf içinde ama triangle-union hücre boşluğunda | 2 | 6 |

Ön yüz fotoğraflarında üçgen birleşimi her bölgenin üretim konveks zarfının yalnız %25–52'sini dolduruyor (burun ≈%25–31, yanaklar ≈%33–41, alın/çene ≈%40–52). Neden ön yüz mesh üretimi: `skinMesh.ts` satır köşegenini yalnız `c%2===r%2` hücrelerinde ekliyor; `polygon_mask` yalnız üç kenarı da bulunan üçgenleri dolduruyor. Zarfın bir kısmı cilt değildir; bu oran cilt kapsamı diye okunmamalı. Önceki `audit_product_box_support.py` aynı durumu “sparse presentation mesh support” diye kaydetmişti. Klasik A/B'nin ortak kapsamı bu triangle-union'ı kullanır; YOLOX ürün yolu ise konveks zarf (`region_envelopes`) kullanır.

**Kapsam tanımı uyuşmazlığı:** `annotation-scope-manifest.json`, RIGHT pozdaki 55d380f7'nin burun ve çene hedeflerini `IN_SCOPE_VISIBLE_REGION` sayıyor; ürün snapshot'ı bu pozda yalnız bir yanak meshi üretiyor. Bu yüzden “14 kapsam içi hedef” ile “ürünün ölçtüğü destek” aynı payda değil. 14'lük sabit payda değiştirilmedi.

### Kaynak üstü görsel inceleme

Merkezi bölge desteğinde kaybedilen 29 hedefin tamamı için kaynak koordinatlı overlay üretildi ve incelendi: 28'i **görünür cilt, görünür örtücü yok**; 26ebdde4#2 dudak kırmızısı sınırında olduğu için **UNKNOWN**. Bu inceleme kör değildir, sonuçlardan sonra yapılmıştır, Claude mühendislik incelemesidir; dermatolog/insan doğrulaması, yeni etiket veya piksel maskesi değildir.

Bu bulgu “dışlama yanlış” etiketi değildir. Yan pozda tek yanak ve perioral alanın kapsam dışı olması ürün kapsamı kararlarıdır. Hücre boşlukları ise görünür bir yapıya karşılık gelmeyen bir destek geometrisi; düzeltilmesi ürün geometrisi değişikliği olacağı için bu görevde yapılmadı.

## Ölçüm uyumsuzluğu

- IoU≥0,50 bire bir eşleşme ve merkez eşleşmesi dondurulmuş sonuçlarla aynı: merkez A f2ed24a9 t1↔c1, 4a1762ee t1↔c0; B f2ed24a9 t0↔c13. Bir aday birden çok hedefi karşılayamaz.
- Gevşek IoU>0 eşleşmesi aynı hedefleri buluyor: A 2 (IoU 0,348 ve 0,110), B 1 (0,409). Bu yalnız tanısal göstergedir; başarı veya kabul ölçüsü değildir. Eşleşme kuralı değiştiği için artan bir sayı algoritma kazanımı sayılmaz.
- Alan oranı ve sınır: 4a1762ee#1'de A'nın 5×5 çekirdeği hedef alanının %11'i, bu yüzden en iyi yerleşimde bile IoU en fazla 0,11 olabilir. f2ed24a9#1'de A adayı hedefin 1,79 katı; alan sınırı 0,56, gerçek IoU 0,348 (yerleşim kaybı). f2ed24a9#0'da B adayı hedefin 2,15 katı; alan sınırı 0,46 olduğundan IoU 0,50'ye ulaşılamaz.
- Yöntem geometrisi sınırı: dondurulmuş boyut, en-boy ve doluluk aralıklarıyla 43 hedefin hepsinde IoU≥0,50 erişilebilir (en düşük sınır ≈0,90). Bu yüzden 0/14, kutu boyutunun yapısal olarak imkânsız olmasıyla açıklanamaz.
- YOLOX'un tam kutu çıktısı ile klasik çekirdek kutusu aynı anlamda “dedektör doğruluğu” diye kıyaslanmadı.

**Açıklanan / açıklanamayan:** Scope B'de ölçüm değişikliği en fazla 1/14 (A), 0/14 (B) hedefi açıklıyor. Açıklanamayan 13/14 (A) ve 14/14 (B) hedef yerelleştirmeden önce kayboluyor: 10'u bölge desteğinde, 2'si üretimde, 1–2'si filtrelerde. Kontrollerde açıklanan 1/29, açıklanamayan 28/29 (her iki yöntem).

## Üretim ve filtre ayrıntısı (yeniden hesaplama yalnız dondurulmuş alanlar)

Aşama 8/9 için yalnız dondurulmuş ön işleme ve yanıt alanı, dondurulmuş kodla yeniden hesaplandı. Kabul edilen bileşen listesi her fotoğrafta dondurulmuş adaylarla birebir eşleşmeden atıf kullanılmadı; 13/13 fotoğrafta iki yöntem için de eşleşti.

- Scope B üretim kaybı: 695ed248#0 (8,5×8) ve #4 (5,5×6,5, mikro); iki yöntemde de kutuda ham yanıt yok.
- Scope B filtre kaybı: A 55d380f7#5 `SUPPORT_EROSION`; B 55d380f7#5 ve 4a1762ee#1 `BOUNDARY_OR_EXCLUSION`.
- Kontrol filtreleri: A `SHAPE` 2, `SUPPORT_EROSION` 3, `SIZE` 1, `SHAPE+SIZE` 1, bir de sınır durumu (f2ed24a9#7). B 9 hedefin 7'sinde `BOUNDARY_OR_EXCLUSION`. B'nin sınır filtresi, uygun desteğin kenarına değen bileşenleri reddeder ve hücre boşlukları bu kenarları çoğaltır; bu etkileşim makul ama test edilmedi, neden diye yazılmaz.
- f2ed24a9#7 (A): kabul edilen bir bileşen kutunun piksel penceresine değiyor ama aday kutusu hedef kutusuyla kesişmiyor. Filtre olarak kaydedildi; daha doğru tanım “örtüşen kabul edilmiş aday yok”.

## Ürün kapısı (25 kontrol fotoğrafı, 126 hedef)

İlk kayıp: NO_FACE 21 hedef (2 fotoğraf), kalite 45 (10), poz 60 (13). Bağımsız bayraklar (örtüşür, toplanmaz): poz 23 fotoğraf / 121 hedef, kalite 12 / 66, snapshot çerçevesi 5 / 14, NO_FACE 2 / 21, gözlük UNCERTAIN 1 / 5; 7 fotoğrafta gözlük kapısı değerlendirilmedi (UNKNOWN). Bu 126 hedefin alt aşamaları **ölçülmedi**; algoritmik kaçırma veya sağlıklı sıfır sayılmadı. Scope B'nin reddedilen iki fotoğrafında (20031f35 gözlük, 0d891a03 kafa çerçevesi) kapsam içi hedef yok.

## Yöntem, kimlik ve kaynak

- Manifest çalıştırmadan önce commit edildi (`docs/acne-measurement-audit-manifest-20261015.json`). Hedef/fotoğraf listeleri, kod ve girdi SHA'ları, ölçümler, atıf sırası ve hesap bütçesi bu manifestte. Tolerans veya eşik seçilmedi.
- **Amendment 1** (`…-amendment1.json`) ilk koşu görüldükten sonra yazıldı: (1) analiz tuvali dışındaki bağımsız bayrakları reddedildi diye gösteren hata düzeltildi; (2) bölge kaybının geometrik ayrımı eklendi. Hedefler, metrikler ve sıra değişmedi; birincil sonuçlar iki koşuda aynı.
- Girdi kökü (CD checkout) salt okunur kullanıldı. 40/40 kaynak dosya SHA'sı ve 13 snapshot SHA'sı doğrulandı. Çıktılar yalnız bu worktree'nin git-ignored `audit-results/acne-measurement-audit-20261015[-r2]` klasöründe; fotoğraf, overlay, harita veya base64 Git'e eklenmedi. Kanıt: `docs/acne-measurement-audit-evidence-20261015.json`.
- Ortam: kullanıcının makinesindeki Linux VM; Python 3.12.15, NumPy 2.2.6, OpenCV 4.12.0 (headless), scikit-image 0.26.0. CD koşusu Windows'taydı; yukarıdaki bit düzeyindeki eşitlikler bu ortamda da aynı çıktıyı gösteriyor.
- HeavyJobLease (700 MiB / 1200 MiB, düşürülmedi): ortak kilit dosyaları alınıp bırakıldı. Tek süreç, akışlı işleme; tepe 328 MiB private, 27 sn. **Sınır:** süreç/RAM sayımı VM içinde yapıldı; Windows ana makinesindeki süreçleri göremez.
- 11 odaklı test geçti: dönüşümler, crop sınırı, çoklu neden/tekil atıf, merkez dışarıda ama kutu kısmen içeride, küçük çekirdek IoU sınırı, bire bir eşleşme, geçersiz/UNKNOWN girdi, dondurulmuş kimlikler, kimlik kayması ve kök çakışması, B replay neden eşliği.

## Kalan somut engeller

1. **Payda/kapsam kararı:** etiket kapsamı (`IN_SCOPE_VISIBLE_REGION`) ile ürünün poz başına dışa aktardığı bölgeler uyuşmuyor. Hangi paydanın kullanılacağı CD kararıdır.
2. **Destek geometrisi:** sunum meshinin üçgen birleşimi bölge zarfının yaklaşık yarısını boş bırakıyor. Klasik yöntemleri adil karşılaştırmak için bu desteğin açık bir kararla değiştirilmesi gerekir; bu, bu görevin dışında bir ürün değişikliği.
3. **Veri:** destek içinde merkezi kalan yalnız 4 Scope B ve 10 kontrol hedefi var; bunlar recall kararı için çok az. Ürün pozunda, desteklenen bölgelerin içinde kutu etiketli, hakları temizlenmiş, kişi ayrılmış kaynak gerekiyor. Kırmızı/soluk/beyaz alt tür etiketleri yok; FP incelemesi kör değil; bağımsız final test yok. Yayıncı lisans beyanı bireysel izin sayılmadı.

Ürüne hiçbir yöntem etkinleştirilmedi. Production build veya kısayol teslimi yapılmadı; PR #2'ye dokunulmadı.
