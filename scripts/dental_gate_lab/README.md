# Diş çekim kapısı laboratuvarı (görüntüler Git dışında)

Uygulamanın **gerçek istemci kapısını** (`apps/vehicle-app/src/utils/dentalCapture.ts`,
TypeScript'ten derlenip Chromium'da çalıştırılır) ve backend yeniden doğrulamasını
(`dental_analysis.dental_quality`) aynı karelerde karşılaştırır.

1. `landmarks.py` — uygulamanın kendi `face_landmarker.task` modeliyle (Python MediaPipe;
   uygulama WASM sürümünü kullanır) 478 nokta + dönüşüm matrisi. Ayrı bir venv'de çalıştırın
   (`mediapipe` OpenCV'yi değiştirdiği için çalışma ortamına kurulmamalı).
2. `compose.py`, `compose_lowres.py` — her portreyi yüz genişliği kare genişliğinin
   %16/22/30'u (1920×1080) ve %14/18/24'ü (1280×720) olacak şekilde yalnız ölçekleyip
   kaydırır (piksel üretimi yok); araç kamerası ölçeği varsayımıdır, ölçülmüş değildir.
3. `gate_eval.cjs <dentalCapture.ts> <lm.json> <out.json>` — dört poz için kapı kararları.
4. `gate_report.py` — önce/sonra kabul tablosu + backend uyumu.

Girdiler: `followup-closure-20261010/dental-sources/{0..9}-native.png` (Wikimedia Commons,
lisans sayfaları aynı klasörde) ve `7. TOGG/Assets/dental_*_full.jpg` (sentetik).
Bu kareler gerçek kişi fotoğraflarıdır ama **araç kamerasıyla çekilmemiştir**; fiziksel
kamera kanıtı değildir.
