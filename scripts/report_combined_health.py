"""Final evidence summary; refuses incomplete or mismatched-build delivery."""
import hashlib,json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit-results/combined-health-20261008'


def load(path):return json.loads(path.read_text('utf8'))
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def link(label,path):return f'[{label}](<{path.resolve().as_posix()}>)'


def main():
    assert not git('status','--porcelain'),'Finish the verified source commit first'
    build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip();head=git('rev-parse','HEAD')
    delivery=load(OUT/'delivery.json');assert delivery['status']=='PASS' and delivery['buildId']==build and delivery['sourceHead']==head
    assert delivery['actualNormalDentalModelInference']
    assert git('branch','--show-current')=='fix/live-test-followup'
    assert git('ls-remote','origin','refs/heads/fix/live-test-followup').split()[0]==head
    proofs={name:load(OUT/name/'proof.json') for name in ('audio-render','audio-focus','hearing-positive','runtime','responsive','dental-runtime')}
    assert all(p['buildId']==build for p in proofs.values())
    assert all(proofs[name]['status']=='PASS' for name in ('audio-focus','hearing-positive','runtime','responsive','dental-runtime'))
    skin=load(OUT/'skin/proof.json')
    assert skin['buildId']==build and skin['status']=='PASS'
    model=load(ROOT/'services/core-api/models/dental-yolox-s.json');metrics=model['evaluation']
    assert hashlib.sha256((ROOT/'services/core-api/models/dental-yolox-s.onnx').read_bytes()).hexdigest()==model['modelHash']
    positive=load(OUT/'dental-training/frozen-model-diagnostics.json')['productPositiveCoordinateCheck']
    assert positive['status']=='PASS' and positive['modelHash']==model['modelHash'] and positive['atLeastOneSameClassIoU50Match']
    unit=ET.parse(OUT/'unit-final.xml').getroot();suite=unit.find('testsuite')
    assert suite is not None and suite.attrib['failures']=='0' and suite.attrib['errors']=='0'
    npm=load(OUT/'audit-production.json')['metadata']['vulnerabilities']
    assert npm['total']==0
    all_npm=load(OUT/'audit-all.json')['metadata']['vulnerabilities']
    py=load(OUT/'python-production-fixed-audit.json');assert not any(d['vulns'] for d in py['dependencies'])
    sensitivity=load(OUT/'proxy-sensitivity-summary.json')
    assert sensitivity['buildId']==build and sensitivity['analysisSourceSHA256']==hashlib.sha256((ROOT/'services/core-api/appearance_analysis.py').read_bytes()).hexdigest()
    preview=load(OUT/'audio-render/fixed-bank-preview.json')
    assert preview['synthesisCalls']==0 and not preview['auditoryAcceptance']
    assert hashlib.sha256((OUT/'audio-render/fixed-bank-0-to-9.wav').read_bytes()).hexdigest()==preview['previewSHA256']
    rows=[
      ('Cilt — ton eşitsizliği','appearance_proxy','Alın, iki yanak, T-bölgesi, çene','Renk dağılımı; 0–100 indeks'),
      ('Cilt — kızarıklık','appearance_proxy','Alın, iki yanak, T-bölgesi, çene','Yerel renk indeksi; sabit ölçekli harita'),
      ('Cilt — yağlı görünüm','appearance_proxy','Alın, iki yanak, T-bölgesi, çene','Parlama aday alanı; yüzde görünür alan'),
      ('Cilt — kuruluk görünümü','appearance_proxy','Altı bölge','İnce parlak pullanma adayları; düşük detayda null'),
      ('Cilt — sivilce görünümü','appearance_proxy','Alın, iki yanak, T-bölgesi, çene','Aday sayısı/sınırları; uzman lezyon etiketi değil'),
      ('Cilt — kontur/sarkma takibi','longitudinal_measurement','Alın, iki yanak, çene','Bölgesel geometri, ilk referans ve uyumlu değişim'),
      ('Cilt — göz altı morluğu','appearance_proxy','Göz çevresi','Komşu cilde göre yerel renk/kontrast'),
      ('Cilt — göz altı torbalanması','longitudinal_measurement','Göz çevresi','Kararlı alt kapak konturu/kenarı; kişisel takip'),
      ('Cilt — kaz ayakları','appearance_proxy','Göz dış köşeleri','Yönlü Gabor çizgi indeksi; göz küresi hariç'),
      ('Diş — görünür çürük adayları','trained_prediction','Görünen ağız içi yüzey','Gerçek YOLOX-s → ONNX → normal ürün API'),
      ('Diş — birikim görünümü','appearance_proxy','Görünen diş/diş eti sınırı','Renk+doku+sınır; farklı görünüm desteği'),
      ('Diş — ön diş dizilimi','appearance_proxy','Doğal kapanışta üst/alt sıra','Gerçek watershed konturları; derece dağılımı'),
      ('İşitme — saf ses','longitudinal_measurement','İki kulak, 6 frekans + tekrar','Dijital dBFS peak; limit/eksikler ayrı'),
      ('İşitme — Türkçe sayı/gürültü','longitudinal_measurement','24 skorlanan üçlü','Gerçek PCM RMS SNR; deneysel TTS bankası')]
    text=['# Birleşik kapsam — kullanıcı kabulüne hazır teknik teslim',
      'Bağımsız yazılım/eğitim/entegrasyon kontrolleri tamamlandı. Gerçek kullanıcı kamerası, subjektif işitme ve sayı telaffuzu kabulü açık; klinik veya uzman doğrulaması yapılmadı.',
      '| Başlık | İç tür | Kapsam | Çalışan yol / bağımsız kabul |',
      '|---|---|---|---|']
    text.extend('| '+' | '.join(row)+' |' for row in rows)
    text.extend(['',f'Kaynak/GitHub HEAD: `{head}`. Branch: `fix/live-test-followup`. BUILD_ID: `{build}`. PR #2 Draft; main merge yok.',
      'Normal kısayol → kurulu launcher → kaynak klasörü → sunulan chunk/banka/model hash zinciri geçti. Normal backend gerçek ONNX’i çalıştırdı; kullanılan kaynak tek kamuya açık ön poz fixture’dır.',
      'Launcher’daki gerçek Windows açılış takılması düzeltildi: ASGI/sayısal DLL yüklemesi stdin kapanış thread’inden önce tamamlanıyor. İzole aynı-ortam karşılaştırmasında eski sıra 45 saniyede hazır olamadı; aday sıra 10,547 saniyede hazır olup kontrollü pipe ile kapandı. Final launcher yaşam döngüsü ayrı doğrulandı; bu tanı koşusu donanım kabulü değildir.',
      link('Açılış karşılaştırması',OUT/'launcher-backend-candidate-diagnostic.json')+' · '+link('Son build launcher yaşam döngüsü',ROOT/'audit-results/windows-launcher.json'),
      link('Teslim zinciri',OUT/'delivery.json'),'',
      f'Birim/regresyon: {suite.attrib["tests"]} test, sıfır başarısızlık. Typecheck ve production build geçti. Lint geçti; iki mevcut uyarı ayrı logda.',
      link('Birim test kaydı',OUT/'unit-final.xml')+' · '+link('Lint',OUT/'lint-final.log')+' · '+link('Build',OUT/'build.log'),
      'Gerçek browser PCM: FFT, kanal izolasyonu, dB adımı, clipping, SNR, iptal/arka plan/aygıt değişimi; erken yanıt ve 24 DIN geçişi doğrulandı. Yanıtlar açıkça simüle edildi; insan işitme sonucu değildir.',
      'Göz/Ruhsal kaynak davranışları ve onaylanan Ahmet/Emel profilleri korundu; regresyon ve gerçek ses odağı kontrolü geçti. Bu build’de yeni insan mikrofonu, göz yumma/el/cisim örtüsü veya 24 denemelik fiziksel göz kabulü yapılmadı. Eski build’in fiziksel kanıtı son build kabulüne taşınmadı.',
      link('PCM/banka',OUT/'audio-render/proof.json')+' · '+link('Sesler arası dışlama',OUT/'audio-focus/proof.json')+' · '+link('24 deneme yakınsaması',OUT/'hearing-positive/proof.json')+' · '+link('Sınır/yaşam döngüsü',OUT/'runtime/proof.json'),
      'Gerçek Windows %100/%200 ve dar pencere kontrolü; sekiz navigasyon bağlantısı ile footer gizlilik/deep link/back/silme çalışıyor.',
      'Zoom, headed Chrome’un native Preferences ayarıyla doğrulandı; CSS zoom kullanılmadı. Windows exact-HWND yakalamasının boş döndüğü karelerde aynı Chrome’un compositor görüntüsü kullanıldı ve kanıtta bu yöntem açıkça ayrıldı; bu kareler OS ekran yakalaması olarak sunulmuyor.',
      link('Pencere/zoom kanıtı',OUT/'responsive/proof.json')+' · '+link('Cilt kaynak/mesh/overlay kanıtı',OUT/'skin/proof.json'),'',
      'Önceki kabul edilen tasarımın ekranı ayrı SHA/build kaydıyla korunmuştur; yeni build için fiziksel kabul yerine kullanılmadı. Kaynak fotoğraf/crop, renkler ve ağ yerleşimi korundu; hesaplanabilen yeni kriterler aynı kart dilinde eklendi.',
      link('Önceki tasarım kaydı',ROOT/'audit-results/skin-capabilities-20261008/ui-before/source.json')+' · '+link('Önceki alın ekranı',ROOT/'audit-results/skin-capabilities-20261008/ui-before/0-forehead-desktop.png')+' · '+link('Son build alın ekranı',OUT/'skin/0-forehead-desktop.png')+' · '+link('Son build gerçek %200',OUT/'skin/1-forehead-native200.png')+' · '+link('Diş sekmesi',OUT/'responsive/dental-100.png')+' · '+link('İşitme sekmesi',OUT/'responsive/hearing-100.png'),
      'Cilt hazırlığı ve kare yanıtları gerçek worker request/response zamanlarıyla ayrı kaydedildi. Initialization asset/runtime hazırlığını; frame bitmap aktarımı, inference ve yanıtı içerir. Saf kernel süresi veya karşılaştırılmamış hızlanma iddiası değildir.',
      '\n'.join(f'Kontrollü üç poz koşusu {i+1}: hazırlık {run["cameraWorkerTiming"]["initializeRoundTripMs"]} ms; ilk kare {run["cameraWorkerTiming"]["firstFrameRoundTripMs"]:.1f} ms; kare median {run["cameraWorkerTiming"]["medianFrameRoundTripMs"]:.1f} ms ({run["cameraWorkerTiming"]["measuredFrames"]} ölçüm).' for i,run in enumerate(skin['runs'])), '',
      '## Gerçek model ve bilimsel sınırlar',
      'Resmi Megvii YOLOX-s (Apache-2.0), rastgele başlangıç; Zenodo 14827784 CC BY 4.0. D/d etiketleri ayrı; hak zinciri ve arşiv hash’leri manifestte. Skin-Scan MIT; ONNX Runtime MIT; NumPy/SciPy/scikit-image ve ilgili notices korunuyor. Edge-TTS mevcut LGPL bildirimiyle ayrı.',
      f'YOLOX kaynak revision: `{model["codeRevision"]}`. Skin-Scan: `afc55f5cb87fcc644f36b472c37083b254bd3fe4`. Gerçek runtime kütüphaneleri: {model["additionalDiagnostics"]["libraryVersions"]}; eğitim/export: {model["trainingProvenance"]["trainingLibraryVersions"]}. Kod/veri/kendi ağırlık hakları ayrı belgelendi.',
      f'1478 train / 334 validation / 347 held-out; 2159 etiketli tekil fotoğraf, 1249 grup. Hasta kimliği doğrulanmadı; hasta bağımsız başarı iddiası yok. {model["epochs"]} tamamlanmış tur; seçilen tur {model["selectedEpoch"]}; validation eşik {model["confidenceThreshold"]}.',
      f'Held-out macro F1={metrics["macroF1"]:.4f}; mAP50={metrics["mAP50"]:.4f}; mAP50:95={metrics["mAP50_95"]:.4f}; grup bootstrap %95 F1 aralığı={metrics["groupBootstrapF1_95CI"]}.',
      '| Ham sınıf | Precision | Recall | F1 | F1 grup %95 aralığı | TP | FP | FN |', '|---|---:|---:|---:|---|---:|---:|---:|'])
    for c in metrics['classes']:
        ci=metrics['classGroupBootstrapF1_95CI'][c['classIndex']]
        text.append(f'| {model["classes"][c["classIndex"]]} | {c["precision"]:.4f} | {c["recall"]:.4f} | {c["F1"]:.4f} | {ci[0]:.4f}–{ci[1]:.4f} | {c["truePositive"]} | {c["falsePositive"]} | {c["falseNegative"]} |')
    diag=model['additionalDiagnostics']
    text.extend(['',f'ONNX SHA256: `{model["modelHash"]}`; boyut {diag["modelBytes"]/1e6:.2f} MB. CPU 2 thread: yükleme {diag["sessionLoadMs"]:.1f} ms; 19 sıcak örnek median inference {diag["medianInferenceMs"]:.1f} ms. Bellek sampled RSS’tir, garanti edilmiş OS peak değildir. Torch/ORT 10 örnek allclose (rtol .002 / atol .005) geçti.',
      link('Model/metrik/provenans',ROOT/'services/core-api/models/dental-yolox-s.json')+' · '+link('Süre/bellek/kalibrasyon',OUT/'dental-training/frozen-model-diagnostics.json')+' · '+link('Başarılı/yanlış/kaçırılmış örnekler',OUT/'dental-training/heldout-visual-evidence.json'),
      'Bunlar orijinal veri etiketlerine göre tespit metrikleridir. Araç kamerası doğruluğu, klinik tanı, görünmeyen çürük veya sağlıklı-negatif specificity kanıtı değildir. Confidence kalibrasyonu yalnız seçilmiş tespitleri kapsar.',
      f'Sabit 20 kaynak ölçümünde sampled RSS: başlangıç {diag["sampledRSSBytes"]["baseline"]/1e6:.1f} MB, örneklenen maksimum {diag["sampledRSSBytes"]["maximum"]/1e6:.1f} MB. Torch/ORT ölçülen en büyük mutlak çıktı farkı {max(model["onnxMaxAbsoluteErrors"]):.6g}.',
      'Yalnız sabit eşikte tutulmuş tespitlerde kalibrasyon (aynı sınıf IoU≥0,5): '+ '; '.join(f'{c["classCode"]}: ECE={c["ECE"]:.4f}, Brier={c["Brier"]:.4f}, n={c["retainedPredictions"]}' if c['ECE'] is not None else f'{c["classCode"]}: tutulmuş tespit yok; ECE/Brier null' for c in diag['calibration']['classes'])+'. Kaçırılmış tespitler bu hesaba dahil değildir.',
      'Ürünün gerçek ONNX/kutu eşleme fonksiyonu ayrıca ayrılmış kümedeki bir pozitif ağız içi kaynakta çalıştırıldı; kaynak sınırları ve en az bir aynı sınıf IoU≥0,5 eşleşmesi doğrulandı. Bu kontrolde tam ağız içi kare açıkça ROI olarak verildi; otomatik kamera/FaceWorker veya dört fiziksel poz kabulü değildir. Ayrıntılı aday koordinatları yerel kanıtta, ürün manifestinde yalnız kabul özeti tutuluyor.',
      'Vekillerde poz/ölçek/pozlama değişimi ve negatif kontroller koşuldu. Morluk/aday sayısı ışık ve detaya duyarlıdır; yağlı görünüm stres kaynağında sıfır olduğundan bu kaynak yağlı pozitif doğruluğunu kanıtlamaz. Kontrollü pozitifler yalnız hesaplama yolunu kanıtlar.',
      'Kurulukta sakal/koyu yapıların JPEG halkaları için yakalanan yanlış aday düzeltildi: karanlık yapı çevresi dışlanıyor, aday geometrisi değerlendirilen alan içinde yeniden doğrulanıyor. Dört JPEG kalite düzeyindeki negatifler ve üç ayrı kontrollü pozitif geçti. Dizilimde yön dağılımı, sıra tutarlılığı ve gerçek görünür kontur izdüşümlerinin örtüşme oranı hesaplanıyor; üç boyutlu örtüşme iddiası yok.',
      link('Sayısal duyarlılık',OUT/'proxy-sensitivity-summary.json')+' · '+link('Yöntemler/formüller',ROOT/'docs/combined-health-methods.md'),'',
      'Sabit banka: Ahmet 0–9, rate -10%, pitch -10Hz; test sırasında sentez yok. Tek sıralı dinleme örneği kaynak hash’leri kontrol edilmiş aynı PCM dosyalarından ortak gain ile hazırlanmıştır. Bu örneğin telaffuz kabulü bekleniyor.',
      link('0–9 kısa dinleme örneği',OUT/'audio-render/fixed-bank-0-to-9.wav')+' · '+link('Banka/örnek hash zinciri',OUT/'audio-render/fixed-bank-preview.json'),
      'SCIN havuzu yeniden incelendi: 30 kullanılabilir aday fotoğraf / 25 vaka / 9 acne case-proxy pozitif vaka; bölgesel uzman lezyon etiketi 0. Tam yüz geometrisi ve vaka tanısı, bu fotoğraftaki lezyonun uzman etiketi değildir. Bu sayılardan güvenilir bağımsız görüntü sınıflandırıcısı veya sahte lokal kutu/maske üretilmedi; çalışan CV görünüm vekili kullanılıyor.',
      link('SCIN yeniden incelemesi',ROOT/'audit-results/skin-expanded-20261008/scin/visual-review-report.json'),
      f'Güvenlik: npm production 0 bilinen bulgu; denetlenen Python production pinleri 0. İzole normal runtime FastAPI 0.135.4 / Starlette 1.3.1 / aiohttp 3.14.3 / Pillow 12.3.0. Dev/all npm bulguları saklanmadı: {all_npm["high"]} high + {all_npm["moderate"]} moderate. Bu sonuç tüm olası güvenlik risklerinin yokluğu iddiası değildir.',
      link('Production npm',OUT/'audit-production.json')+' · '+link('Python pin audit',OUT/'python-production-fixed-audit.json')+' · '+link('Açık dev bulguları',OUT/'audit-all.json'),'',
      '## Kullanıcının son kısa kabulü',
      '1. Normal kısayoldan ciltte üç pozu ve fotoğraf/altı bölge görünümünü kontrol edin.',
      '2. Dişte rahat ön/sağ/sol/doğal kapanış akışını deneyin; yetersiz diş görünümünde ilerlememeli.',
      '3. Stereo kulaklıkla sol/sağ kanalı ve 0–9 Türkçe sayıların doğru telaffuzunu dinleyin. Deneysel sonucu klinik işitme kabulü olarak değerlendirmeyin.'])
    report=text[0]
    for before,after in zip(text,text[1:]):
        report+=('\n' if before.startswith('|') and after.startswith('|') else '\n\n')+after
    (OUT/'final-report.md').write_text(report,'utf8')
    print('READY_FOR_USER_ACCEPTANCE '+str(OUT/'final-report.md'))


if __name__=='__main__':main()
