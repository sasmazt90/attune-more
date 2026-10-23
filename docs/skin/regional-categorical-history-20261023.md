# Bölgesel kategorik geçmiş entegrasyonu

## Sonuç

Mevcut sonuç akışındaki geçmiş penceresi, bölgesel `oil`, `dry` ve `redness` özetlerini sayısal şiddet uydurmadan `mevcut / gözlenmedi` durumlarıyla gösterecek şekilde genişletildi. İlk karşılaştırılabilir kayıttan sonra her satır yalnız `durum değişti` veya `durum aynı` olarak işaretlenir.

Karşılaştırma serisi seçilen kayıtla sabitlenir. `methodVersion`, `normalizationVersion`, `modelHash` ve `validationEvidence` alanlarının tamamı eşleşmeyen kayıtlar seriye eklenmez; sayıları kullanıcıya ayrıca bildirilir. `unknown` durumlar negatif veya normal sayılmaz. Geçmiş kaydına ham görüntü eklenmez.

## Doğrulama

- Dört gerçek Python sunucu-özet fikstürü tarayıcı sözleşmesinden geçirildi.
- Toplam 65 çalıştırılabilir kontrol geçti.
- Pozitiften negatife geçiş, değişmeyen durum, yöntem değişimi, bozuk tarih, bilinmeyen gözlem ve desteklenmeyen bölge ayrı ayrı test edildi.
- UI bağlantısı ve yöntem/kanıt açıklaması statik sözleşmeyle korundu.
- Scratch ortamında `pytest` paketi bulunmadığı için aynı iki test fonksiyonu Python üzerinden doğrudan çağrıldı; ikisi de geçti.

Bu çalışma bir model veya bölgesel yöntemi kabul etmez. Tam uygulama tip kontrolü, saklanan fotoğrafla gerçek tarayıcı tekrar oynatımı, çoklu en-boy oranı hizalaması ve bağımsız kamera kabulü hâlâ gereklidir.

Makine-okunur kanıt: `docs/skin/evidence/regional-categorical-history-20261023-v1.json`.
