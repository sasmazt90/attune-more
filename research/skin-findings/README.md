# Cilt bulguları — araştırma kodu (teslim kopyası)

Bu klasör, Claude'un 2026-10-25/26 oturumunda cilt bulguları, eşikler ve belirginlik skorları için kullandığı
analiz betiklerinin **olduğu gibi** kopyasıdır. Üretim kodu değildir; sunucuya henüz bağlanmamıştır.

## Önemli sınırlar

- Betikler sabit bir çalışma kökü varsayar: `S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'`.
  Bu yol yalnızca Claude Cloud oturum konteynerinde vardır. Başka bir ortamda çalıştırmak için `S` değerini değiştirip
  aşağıdaki veri düzenini yeniden kurmak gerekir.
- Veri seti (sentetik karakter görüntüleri), gömme/özellik önbellekleri ve RF-DETR ağırlıkları **bu klasörde yoktur**
  (Git'e eklenmedi). Konumları ve SHA-256 değerleri `MODEL_MANIFEST.json` içindedir.
- Bulgu sınıflandırıcıları (lojistik regresyon) ve belirginlik regresörleri (Ridge) **dosya olarak dışa aktarılmadı**;
  betikler her çalıştırmada yeniden eğitir.
- `scripts/` içinde keşif amaçlı, artık kullanılmayan betikler de vardır (tam geçmiş). Seçilen yöntemlerin betikleri
  `CODEX_HANDOFF.md` içindeki eşleme tablosunda listelenmiştir.
- `results/*.md`: betiklerin kaydedilmiş çıktı tabloları. Dosya adı, üreten betiği gösterir; `det3.md`, `det4.md` ve
  `fa3.md` kaydedilmemiş satır içi betiklerle üretildi (bkz. CODEX_HANDOFF.md "Kanıt durumu").

## Beklenen veri düzeni (S altında)

| Yol | İçerik |
|---|---|
| `gen/state.json` | Karakter planları ve etiketler (`extras`, `sens`, `sensRegions`, `regions`, `acne`, `intensity`, `ageIndependent`) |
| `gen/approved/K-xxx/K-xxx-{front,side_1,side_2}.png` | 340 onaylı sentetik karakter, 3 poz |
| `gen/side32/`, `gen/side28/` | Test kişilerinin (pilot32 ∪ val28) ~25° ek pozları |
| `gen/pilot32.txt`, `gen/val28.txt` | 80 test kişisi listesi |
| `weights/<model>/weights.pt` | RF-DETR ağırlıkları (Roboflow'dan, `scripts/dl_weights.py`) |
| `rf/finding_angle4_emb.npz` | DINOv2-small bölge kırpıntısı gömmeleri (9620 × 768) |
| `rf/feats2*.json`, `rf/items*.json` | Dedektör + doku özellikleri (`kx_pipeline.sh`) |
| `rate/ratings.json`, `rate/key.json` | Kör belirginlik derecelendirmeleri (burada `ratings/`) |

## Değerlendirme protokolü

- **Kişi düzeyinde ayrım:** Aynı kişinin pozları eğitim ve test arasında bölünmez.
- **Eşik:** Yalnızca eğitim kişilerinde seçilir (`scripts/thr_rule.py`, `thr_prev`): her t' ≥ t eşiğinde (≥3 pozitif çağrı)
  beklenen kesinlik ≥ 0,80 olacak en küçük t; varsayılan yaygınlık p0 = min(0,25, eğitim yaygınlığı).
  Test kişilerine değiştirilmeden uygulanır. Test skorları katlama-topluluğu (fold-ensemble) ile aynı ölçekte hesaplanır.
- **Test kümeleri:** (a) 80 sabit test kişisi (pilot32 ∪ val28); (b) 140/190/340 kişide iç içe tekrarlı StratifiedKFold;
  (c) ~25° pozu olan 22 kişi.
- **Seçim yanlılığı:** Yöntem ve çekim kurgusu seçimi aynı test sonuçlarına bakılarak yapıldı; bağımsız, hiç
  görülmemiş bir doğrulama kümesi yoktur.
- **Veri türleri:** Tüm eşikler ve skorlar **sentetik** (OpenAI görüntü API ile üretilmiş) araç içi selfie
  karakterlerine dayanır. Gerçek fotoğraf kontrolü yalnızca eski dedektör sınıfları için SCIN alt kümesinde yapıldı
  (`scripts/scin_eval.py`, `results/scin_results.json`). Belirginlik "doğru cevabı" Claude'un kör 1–3
  derecelendirmesidir; **dermatolog etiketi yoktur**.
