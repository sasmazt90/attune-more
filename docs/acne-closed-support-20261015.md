# Sivilce analiz desteği: kapalı hücre düzeltmesi ve etkisi — 2026-10-15

**Yalnız geometri değişikliği ve ölçümü.** Yeni model, eğitim, tespit algoritması, eşik veya filtre ayarı yok. Dondurulmuş A/B yöntemleri aynı parametrelerle ve aynı kaynaklarla çalıştı; değişen tek unsur sivilce analiz desteği. Üretim sivilcesi `accepted:false, file:null`; normal API/UI, `include_research_features`, ekrandaki ağ, diğer kriterler ve `appearance_analysis.py` değişmedi. Denetim referansı `fe7042ef26f1504f75658ac6218517e1bd61a32c`, dondurulmuş kod `5f11c11`.

## Düzeltilen gerçek hata

`skinMesh.ts` bir hücrenin çizim köşegenini yalnız `c%2===r%2` hücrelerinde ekliyor. `polygon_mask` ise yalnız üç kenarı da bulunan üçgenleri dolduruyor. Bu yüzden köşegeni çizilmemiş, dört güvenli kenarla kapanan dışbükey hücreler klasik sivilce desteğinde boş kalıyordu; ön yüzde üçgen birleşimi her bölge zarfının yalnız %25–52'sini dolduruyordu.

Kuruluk/sarkmanın kullandığı `closed_surface_mask` bu durum için tam olarak doğru kuralı içeriyor, değiştirilmeden yeniden kullanıldı. Kural: dört dışa aktarılmış (frontend güvenli filtresinden geçmiş) kenarla sınırlı, iki köşegeni de olmayan dışbükey dörtgen. Convex hull, açık kenar, konkav kısayol, desteksiz nokta veya görünmeyen tarafa uzanan bölge doldurulmaz. Yeni dar modül `services/core-api/acne_surface_support.py` bu fonksiyonu yalnız beş sivilce bölgesine uygular; periorbital ve diğer kriterlerin maskeleri kopyalanır, değişmez.

Ayrı tutulan üç durum: (1) çizim köşegeni olmayan kapalı hücre — **düzeltildi**; (2) yan pozda tek bölgenin dışa aktarılması — **değişmedi**; (3) perioral/üst dudak/glabella gibi beş bölge kapsamı dışı alanlar — **değişmedi**. YOLOX ürün yolu farklı bölge zarfı (`region_envelopes`) kullanmaya devam eder; bu bulgu geçmiş neural eğitim sonuçlarının nedeni olarak sunulmuyor.

**Koruma kontrolleri (13/13 fotoğraf):** eski desteğin hiçbir pikseli kaybolmadı; eklenen 344.067 kaynak pikselinin 0'ı otomatik dikdörtgen, çerçeve kenarı, göz/dudak/burun deliği/kaş deliği, oküler marj, kaş zarfı, kıl, parlama veya gray dışlamasına ya da yüz ovali dışına düşüyor; 0'ı bölge zarfları dışında. Bölge başına kapalı hücre: alın 6, yanak 4–7, burun 9–10, çene 9.

## Yöntem

- Karşılaştırma manifesti çalıştırmadan önce commit edildi (`docs/acne-closed-support-manifest-20261015.json`): kod/config/girdi kimlikleri, sabit 14 + 29 hedef, önceki denetim kimlikleri, ölçümler ve negatif kuralı.
- Her fotoğrafta önce **eski destek** çalıştırıldı ve dondurulmuş A/B aday listelerini birebir yeniden üretmeden yeni destek raporlanmadı (13/13 eşleşti). Sonra **yeni destek**. Her koşu: decode → üretim ön işleme/geometri → destek → dondurulmuş yöntem → bileşen haritası → JSON; her koşu iki kez.
- Yeni destek; ortak `overall`/`eligible` kapsamını, bölge sahipliğini ve A'nın `blemish_map` bölge maskelerini besler. Renk işlemleri, boyut/şekil/doluluk/sınır/koyuluk filtreleri, MAD eşiği, IoU≥0,50 açgözlü bire bir ve merkez eşleşmesi değişmedi.
- Hedef başına sonraki aşama atfı, dondurulmuş kod replay'iyle yapıldı; replay yeni aday listesini 6/6 hedefli fotoğrafta yeniden üretti.

## Sabit hedefler: önce / sonra

| | Scope B (14) önce | Scope B sonra | Uygun kontrol (29) önce | Kontrol sonra |
|---|---:|---:|---:|---:|
| Merkezi destek içinde | 4 | 5 | 10 | 15 |
| **IoU≥0,50 bire bir — A** | 0 | **1** | 0 | 0 |
| **IoU≥0,50 bire bir — B** | 0 | **1** | 0 | 0 |
| Merkez eşleşmesi (ikincil) — A | 1 | 2 | 1 | 3 |
| Merkez eşleşmesi (ikincil) — B | 0 | 1 | 1 | 4 |

Ön kapı 25 kontrol fotoğrafındaki 126 hedef ölçülmedi, değişmedi.

**Kapsama geri kazanılan ile gerçek tespit ayrı:**
- Desteğe geri giren 6 hedef: Scope B 695ed248#1; kontrol f2ed24a9#11, #14, #15, #16, #17. Bunların **hiçbiri** IoU≥0,50 ile bulunmadı. 695ed248#1'de iki yöntemde de ham yanıt yok (aday üretimi). f2ed24a9 hedeflerinde A şekil/erozyon filtresinde kalıyor; B küçük adaylarla örtüşüyor (IoU 0,04–0,10; yalnız #16 merkez eşleşmesi).
- Tek tespit kazanımı **55d380f7#5** (A IoU 0,60, B 0,72). Bu hedef zaten destekteydi (kutunun %73'ü). Eski desteğin hücre kenarları bileşeni kesiyor, A'da `SUPPORT_EROSION`, B'de `BOUNDARY_OR_EXCLUSION` reddine yol açıyordu. Kazanım kapsam geri kazanımından değil, geometrinin mevcut filtreler üzerindeki etkisinden geliyor.
- Değişmeyen paydalar: 14 ve 29; kapsam veya piksel artışı başarı sayılmadı.

### Hedef başına ilk kayıp aşaması (merkez sırası)

| Aşama | Scope B A önce→sonra | Scope B B önce→sonra | Kontrol A önce→sonra | Kontrol B önce→sonra |
|---|---|---|---|---|
| Anatomik bölge | 10→9 | 10→9 | 19→14 | 19→14 |
| Aday üretimi | 2→3 | 2→3 | 1→1 | 0→0 |
| Bileşen filtreleri | 1→0 | 2→1 | 8→10 | 9→5 |
| Yerelleştirme IoU<0,50 | 1→1 | 0→0 | 1→4 | 1→10 |
| IoU≥0,50 | 0→1 | 0→1 | 0→0 | 0→0 |

**Bölge/poz kapsamı dışında kalmaya devam edenler (23):** yan poz tek bölge 11 (55d380f7 ×6, 2ed3716e ×5); beş bölge zarfı dışında 10 (695ed248#2, #3; f2ed24a9#4, #5, #6, #10, #12, #18, #20; 26ebdde4#2); zarf içinde ama dört kenarlı kapalı hücre olmayan kenar/bölgeler arası boşluk 2 (4a1762ee#0, f2ed24a9#2 glabella). Önceki denetimdeki 8 hücre-boşluğu hedefinden 6'sı geri kazanıldı; 2'si kural gereği kapatılmadı.

## Aynı incelenmiş negatifler (7 fotoğraf)

| | A önce | A sonra | B önce | B sonra |
|---|---:|---:|---:|---:|
| Toplam aday | 10 | 17 | 49 | 91 |
| İncelenmiş görünür cilt FP | 8 | **15** | 28 | **64** |
| FP / fotoğraf | 1,14 | **2,14** | 4,00 | **9,14** |
| UNKNOWN (saç/sakal/kaş/sınır) | 2 | 2 | 21 | 27 |

Eski adayların tamamı yeni listede aynen var ve önceki inceleme durumlarını koruyor. Yeni adayların hepsi mevcut açık negatif yüz etiket kapsamı içinde; kapsam dışında kalan yeni aday yok. Yeni 49 adayın (A 7, B 42) her biri kaynak overlay'inde incelendi: A'da 7'si görünür cilt; B'de 36'sı görünür cilt, 6'sı UNKNOWN (02413bf9 sakal ×3 ve kaş kenarı, 0597e811 gri doku, 36e4010b sarı perçem). Bu inceleme kör değil, sonuçlardan sonra yapıldı, Claude mühendislik incelemesidir; dermatolog/insan doğrulaması veya yeni etiket değildir.

**Sonuç:** dondurulmuş filtrelerle, yeni destekteki incelenmiş FP A'da ~1,9 kat, B'de ~2,3 kat arttı; tespit kazanımı 14 hedefte 1. Bu küçük, önceden görülmüş development grubundan genel doğruluk veya ürün kabulü çıkarılamaz. Mevcut ölçütlerle düzeltme kabul edilebilir bir yöntem iyileştirmesi değil, destek geometrisinin düzeltilmesidir.

## Filtre davranışı (ayar yapılmadı)

B ret toplamları 13 fotoğrafta eski → yeni: SIZE 138→178, BOUNDARY_OR_EXCLUSION 129→131, SHAPE 63→75, DARK 2→1. Sınır reddi bazı fotoğraflarda düşüyor (f2ed24a9 26→16, 55d380f7 7→4), bazılarında artıyor (4a1762ee 9→20); B'nin MAD eşiği yeni destek örneğiyle hesaplandığı için fotoğraf düzeyinde değişebilir. A'nın ortak kapsam reddi değişmedi (0560bfd8 3, 33da7a52 1). Bileşen ayrıntısı kanıt dosyasında.

Görsel gözlem: f2ed24a9 sol alın kenarında ve 36e4010b alnında yeni hücreler saç perçemiyle örtüşen cildi içeriyor; mevcut kıl maskesi (uzun koyu filament) açık/sarı perçemi kaldırmıyor. Bu, eski üçgenlerde de var olan bir kıl maskesi sınırı; yeni alan onu daha çok açığa çıkarıyor.

## Süre ve statik tekrar

Tam analiz (decode→ön işleme/geometri→tespit→harita→JSON), kullanıcının makinesindeki Linux VM'de, 13 fotoğraf medyan/maks saniye:

| | Eski destek | Yeni destek |
|---|---|---|
| A | 0,198 / 1,344 (ilk import dahil) | 0,187 / 0,344 |
| B | 0,275 / 0,755 | 0,268 / 0,543 |

Tekrar medyanları A 0,186→0,183, B 0,273→0,262. Anlamlı süre farkı yok. 52/52 statik tekrar çifti (aday listesi, harita ve destek) bit düzeyinde aynı. Tek süreç; HeavyJobLease 700/1200 MiB, tepe 346 MiB private, 38 sn (+ sonlandırma 228 MiB). VM içindeki süreç sayımı Windows ana makinedeki süreçleri göremez.

## Doğrulama

`tests/unit/test_acne_closed_support.py` 8 test + mevcut denetim testleri 11 = 19 geçti:
- köşegensiz kapalı hücre dolduruluyor;
- açık, konkav ve zaten üçgenlenmiş hücre yeni dolgu almıyor;
- origin/scale sözleşmesi;
- yalnız beş bölge değişiyor, girdiler mutasyona uğramıyor, eski pikseller korunuyor;
- dışlama/kıl/parlama/gray/cilt kapsamı korunuyor;
- aday listesi, sayı ve dolgu tek listeden;
- `analyze_skin`, `polygon_mask`, `closed_surface_mask`, `acne_candidates` AST kimlikleri dondurulmuş hâlleriyle aynı (diğer kriterler değişmedi);
- önceki denetim kanıtının yorumu ve kod kimliği değişmedi.

Gerçek veride: 13/13 eski destek dondurulmuş adayları ve eligible kayıtlarını yeniden üretti; 6/6 yeni destek replay'i yeni adaylarla eşleşti.

## CDC için en küçük paket ve entegrasyon noktaları

Seçilerek alınabilecek en küçük değişiklik: `services/core-api/acne_surface_support.py` (+ `tests/unit/test_acne_closed_support.py`). Üretim yoluna bağlanmadı. Entegrasyon noktaları (yalnız araştırma/klasik yol):

1. `scripts/skin-research/evaluate_acne_classical.py::run`:
   - `regions` ve `eligible`'ı `acne_support_masks(ctx['masks'], ctx['gray'].shape, payload['meshes'], ctx['scale'], ctx['origin'])` çıktısından yeniden kur (`compare_acne_closed_support.scoped` ile aynı formül).
   - A için `blemish_map` ve `acne_candidates` girdisini bu `overall` ile değiştir.
2. `appearance_analysis.analyze_skin` içindeki yalnız `include_research_features=True` sivilce dalı (`overall` ve bileşen sahipliği). Normal ürün yolu ve YOLOX `region_envelopes` dokunulmamalı.

Karşılaştırma aracı `compare_acne_closed_support.py` ve `finalize_acne_closed_support.py` ölçüm içindir; ürün paketi değildir.

## Kalan engeller

1. Kalan bölge kayıpları kapsam kararıdır (yan poz tek bölge, perioral/üst dudak/glabella); geometri hatası değildir.
2. Destek içindeki hedeflerde kayıp artık aday üretimi (Scope B 3), dondurulmuş filtreler ve yerelleştirmede (B'nin örtüşen adayları çoğunlukla IoU 0,03–0,12, en yüksek 0,39). FP artışıyla birlikte, bu filtrelerle yeni destek kabul edilebilir değil; filtreler bu görevde ayarlanmadı.
3. Kıl maskesi açık/sarı perçemi ve sakal sınırını kaldırmıyor; yeni alan bu riski büyütüyor.
4. Veri: destek içinde 5 Scope B / 15 kontrol hedefi; kişi ayrımı, bağımsız test, alt tür etiketleri ve haklar doğrulaması yok.

Sivilce `accepted:false, file:null` kaldı; hiçbir yöntem etkinleştirilmedi; CDC checkout'una, main'e veya kısayola dokunulmadı.
