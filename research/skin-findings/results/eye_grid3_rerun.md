### A) 140 kişi (iç içe 5-kat, 10 tekrar)
| Bulgu | Yöntem | Kurgu | Confidence Threshold (ort.) | TP | FP | FN | Precision | Recall | F1 | AUC | Pozitif/Kişi |
| Göz altı morluğu | Renk kıyası (ışık düzeltmeli) | Ön | 0.82 | 24.9 | 3.0 | 29.1 | 0.89 | 0.46 | 0.61 | 0.86 | 54/140 |
| Göz altı morluğu | Renk kıyası (ışık düzeltmeli) | Ön + 20° | 0.81 | 24.0 | 2.4 | 30.0 | 0.91 | 0.44 | 0.60 | 0.86 | 54/140 |
| Göz altı morluğu | Renk kıyası + DINOv2 | Ön | 0.94 | 9.0 | 1.3 | 37.5 | 0.87 | 0.19 | 0.32 | 0.86 | 54/140 | (7/50 katta eşik bulunamadı)
| Göz altı morluğu | Renk kıyası + DINOv2 | Ön + 20° | 0.82 | 22.2 | 2.5 | 31.8 | 0.90 | 0.41 | 0.56 | 0.89 | 54/140 |
| Sarkma: kapak | Geometri | Ön | 0.91 | 3.9 | 1.5 | 13.4 | 0.72 | 0.23 | 0.34 | 0.92 | 31/140 | (22/50 katta eşik bulunamadı)
| Sarkma: kapak | Geometri | Ön + 20° | 0.92 | 0.2 | 0.6 | 3.4 | 0.25 | 0.06 | 0.09 | 0.88 | 31/140 | (44/50 katta eşik bulunamadı)
| Sarkma: kapak | Geometri + DINOv2 | Ön | 0.75 | 20.9 | 4.7 | 10.1 | 0.82 | 0.67 | 0.74 | 0.95 | 31/140 |
| Sarkma: kapak | Geometri + DINOv2 | Ön + 20° | 0.69 | 20.0 | 4.5 | 10.4 | 0.82 | 0.66 | 0.73 | 0.96 | 31/140 | (1/50 katta eşik bulunamadı)
| Sarkma: göz dış köşe | Geometri | Ön | 0.87 | 0.5 | 0.6 | 10.2 | 0.45 | 0.05 | 0.08 | 0.74 | 33/140 | (34/50 katta eşik bulunamadı)
| Sarkma: göz dış köşe | Geometri | Ön + 20° | 0.84 | 1.1 | 0.6 | 14.6 | 0.65 | 0.07 | 0.13 | 0.74 | 33/140 | (26/50 katta eşik bulunamadı)
| Sarkma: göz dış köşe | Geometri + DINOv2 | Ön | 0.84 | 6.3 | 2.3 | 20.8 | 0.73 | 0.23 | 0.35 | 0.83 | 33/140 | (9/50 katta eşik bulunamadı)
| Sarkma: göz dış köşe | Geometri + DINOv2 | Ön + 20° | 0.83 | 7.0 | 2.0 | 22.0 | 0.78 | 0.24 | 0.37 | 0.83 | 33/140 | (6/50 katta eşik bulunamadı)

### B) ~25° pozu olan 22 kişi (model ve eşik diğer 118 kişiden)
| Bulgu | Yöntem | Kurgu | Confidence Threshold | TP | FP | FN | Precision | Recall | F1 | AUC | Pozitif/Test |
| Göz altı morluğu | Renk kıyası (ışık düzeltmeli) | Ön | 0.83 | 1 | 0 | 3 | 1.00 | 0.25 | 0.40 | 0.90 | 4/22 |
| Göz altı morluğu | Renk kıyası (ışık düzeltmeli) | Ön + 20° | 0.84 | 1 | 0 | 3 | 1.00 | 0.25 | 0.40 | 0.92 | 4/22 |
| Göz altı morluğu | Renk kıyası (ışık düzeltmeli) | Ön + ~25° | 0.83 | 1 | 0 | 3 | 1.00 | 0.25 | 0.40 | 0.90 | 4/22 |
| Göz altı morluğu | Renk kıyası (ışık düzeltmeli) | Ön + 20° + ~25° | 0.84 | 1 | 0 | 3 | 1.00 | 0.25 | 0.40 | 0.92 | 4/22 |
| Göz altı morluğu | Renk kıyası + DINOv2 | Ön | eşik bulunamadı | | | | | | | 0.83 | 4/22 |
| Göz altı morluğu | Renk kıyası + DINOv2 | Ön + 20° | 0.95 | 0 | 0 | 4 | 0.00 | 0.00 | 0.00 | 0.85 | 4/22 |
| Göz altı morluğu | Renk kıyası + DINOv2 | Ön + ~25° | eşik bulunamadı | | | | | | | 0.82 | 4/22 |
| Göz altı morluğu | Renk kıyası + DINOv2 | Ön + 20° + ~25° | 0.95 | 0 | 0 | 4 | 0.00 | 0.00 | 0.00 | 0.82 | 4/22 |
| Sarkma: kapak | Geometri | Ön | 0.97 | 0 | 0 | 4 | 0.00 | 0.00 | 0.00 | 1.00 | 4/22 |
| Sarkma: kapak | Geometri | Ön + 20° | eşik bulunamadı | | | | | | | 1.00 | 4/22 |
| Sarkma: kapak | Geometri | Ön + ~25° | 0.97 | 0 | 0 | 4 | 0.00 | 0.00 | 0.00 | 1.00 | 4/22 |
| Sarkma: kapak | Geometri | Ön + 20° + ~25° | eşik bulunamadı | | | | | | | 1.00 | 4/22 |
| Sarkma: kapak | Geometri + DINOv2 | Ön | 0.73 | 3 | 1 | 1 | 0.75 | 0.75 | 0.75 | 0.88 | 4/22 |
| Sarkma: kapak | Geometri + DINOv2 | Ön + 20° | 0.60 | 3 | 2 | 1 | 0.60 | 0.75 | 0.67 | 0.94 | 4/22 |
| Sarkma: kapak | Geometri + DINOv2 | Ön + ~25° | 0.73 | 3 | 1 | 1 | 0.75 | 0.75 | 0.75 | 0.88 | 4/22 |
| Sarkma: kapak | Geometri + DINOv2 | Ön + 20° + ~25° | 0.60 | 3 | 1 | 1 | 0.75 | 0.75 | 0.75 | 0.90 | 4/22 |
| Sarkma: göz dış köşe | Geometri | Ön | eşik bulunamadı | | | | | | | 0.71 | 1/22 |
| Sarkma: göz dış köşe | Geometri | Ön + 20° | eşik bulunamadı | | | | | | | 0.48 | 1/22 |
| Sarkma: göz dış köşe | Geometri | Ön + ~25° | eşik bulunamadı | | | | | | | 0.52 | 1/22 |
| Sarkma: göz dış köşe | Geometri | Ön + 20° + ~25° | eşik bulunamadı | | | | | | | 0.38 | 1/22 |
| Sarkma: göz dış köşe | Geometri + DINOv2 | Ön | 0.92 | 0 | 0 | 1 | 0.00 | 0.00 | 0.00 | 1.00 | 1/22 |
| Sarkma: göz dış köşe | Geometri + DINOv2 | Ön + 20° | 0.81 | 0 | 0 | 1 | 0.00 | 0.00 | 0.00 | 0.90 | 1/22 |
| Sarkma: göz dış köşe | Geometri + DINOv2 | Ön + ~25° | 0.92 | 0 | 0 | 1 | 0.00 | 0.00 | 0.00 | 0.95 | 1/22 |
| Sarkma: göz dış köşe | Geometri + DINOv2 | Ön + 20° + ~25° | 0.81 | 0 | 0 | 1 | 0.00 | 0.00 | 0.00 | 0.95 | 1/22 |
