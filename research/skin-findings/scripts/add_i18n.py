import json, hashlib, re, sys, unicodedata
sys.path.insert(0, '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad')
from tr_recs import T
P = 'repo/claude-skin/shared/localization/messages.json'
m = json.load(open(P))
norm = lambda s: re.sub(r'\s+', ' ', unicodedata.normalize('NFC', s)).strip()
have = {norm(v['tr']): k for k, v in m.items()}
UI = {
 'Önceki bulgu': ('Previous finding', 'Vorheriger Befund'),
 'Sonraki bulgu': ('Next finding', 'Nächster Befund'),
 'Belirginlik': ('Visibility', 'Ausprägung'),
 'Hafif': ('Mild', 'Leicht'), 'Orta': ('Moderate', 'Mittel'), 'Belirgin': ('Pronounced', 'Deutlich'),
 'Kapladığı alan': ('Area covered', 'Betroffene Fläche'),
 'Geçmiş': ('History', 'Verlauf'),
 'Geçmiş grafiği bir sonraki taramanızdan sonra burada görünür.': ('The history chart appears here after your next scan.', 'Der Verlauf erscheint hier nach Ihrem nächsten Scan.'),
 'Seçilen tarih aralığında yeterli tarama yok.': ('There are not enough scans in the selected date range.', 'Im gewählten Zeitraum gibt es nicht genug Scans.'),
 'Belirginlik geçmişi': ('Visibility history', 'Verlauf der Ausprägung'),
 'Tarih aralığı': ('Date range', 'Zeitraum'),
 'Son 30 gün': ('Last 30 days', 'Letzte 30 Tage'), 'Son 3 ay': ('Last 3 months', 'Letzte 3 Monate'), 'Son 6 ay': ('Last 6 months', 'Letzte 6 Monate'), 'Tümü': ('All', 'Alle'),
 'Önceki ay': ('Previous month', 'Vorheriger Monat'), 'Sonraki ay': ('Next month', 'Nächster Monat'),
 'Tarama yapılan günler': ('Days with a scan', 'Tage mit Scan'),
 'Uygula': ('Apply', 'Übernehmen'),
 'Tercih edebileceğiniz içerikler': ('Ingredients you can choose', 'Wirkstoffe, die Sie wählen können'),
 'Sabah': ('Morning', 'Morgens'), 'Akşam': ('Evening', 'Abends'), 'Kullanım': ('How to use', 'Anwendung'), 'Alışkanlık': ('Habit', 'Gewohnheit'),
 'Öneriler fotoğraftaki görünüme dayanır ve tanı değildir. Şikâyetiniz sürerse bir uzmana danışın.': ('Suggestions are based on how your skin looks in the photo and are not a diagnosis. If your concern persists, consult a specialist.', 'Die Empfehlungen beruhen auf dem Erscheinungsbild im Foto und sind keine Diagnose. Wenn Ihre Beschwerden anhalten, wenden Sie sich an eine Fachperson.'),
 'Tekrar taramadan önce': ('Before you scan again', 'Vor dem nächsten Scan'),
 'Yüzünüzün eşit şekilde aydınlatıldığından emin olun.': ('Make sure your face is evenly lit.', 'Achten Sie darauf, dass Ihr Gesicht gleichmäßig beleuchtet ist.'),
 'Yüzünüzün kameraya dönük olduğundan emin olun.': ('Make sure your face is turned towards the camera.', 'Achten Sie darauf, dass Ihr Gesicht der Kamera zugewandt ist.'),
 'Yüzünüzün eşit şekilde aydınlatıldığından ve kameraya dönük olduğundan emin olun.': ('Make sure your face is evenly lit and turned towards the camera.', 'Achten Sie darauf, dass Ihr Gesicht gleichmäßig beleuchtet und der Kamera zugewandt ist.'),
 'Tekrar tara': ('Scan again', 'Erneut scannen'),
 'Bu taramada bu bölgede öne çıkan bir bulgu yok.': ('No notable finding in this area in this scan.', 'In diesem Scan gibt es in diesem Bereich keinen auffälligen Befund.'),
 'Ayrıntılar': ('Details', 'Details'),
 'Bu taramada {0} bulgu görüldü': ('{0} findings seen in this scan', '{0} Befunde in diesem Scan'),
 'Bu taramada öne çıkan bir bulgu yok': ('No notable findings in this scan', 'Keine auffälligen Befunde in diesem Scan'),
 'Öne çıkan bulgu yok': ('No notable findings', 'Keine auffälligen Befunde'),
 'Cilt analizi': ('Skin analysis', 'Hautanalyse'),
 'Ön değerlendirme · Tanı değildir': ('Preliminary assessment · Not a diagnosis', 'Vorabeinschätzung · Keine Diagnose'),
 'Bölgeler': ('Areas', 'Bereiche'),
 'T-bölgesi': ('T-zone', 'T-Zone'), 'Göz çevresi': ('Eye area', 'Augenpartie'), 'Sağ profil': ('Right profile', 'Rechtes Profil'), 'Sol profil': ('Left profile', 'Linkes Profil'),
 'Dudak ve çevresi': ('Lips and surroundings', 'Lippen und Umgebung'),
 'Göz kapağı düşüklüğü': ('Droopy eyelids', 'Hängelider'), 'Göz kuyruğu düşüklüğü': ('Downturned eyes', 'Hängende Augenwinkel'),
 'leke': ('spots', 'Flecken'),
}
UI.update(T)
added = 0; existing = []
for tr, (en, de) in UI.items():
    if norm(tr) in have:
        existing.append((tr, m[have[norm(tr)]]['en'])); continue
    k = hashlib.sha256(norm(tr).encode()).hexdigest()[:16]
    m[k] = {'tr': tr, 'en': en, 'de': de}; added += 1
json.dump(m, open(P, 'w'), ensure_ascii=False, indent=2)
print('added', added); print('existing', existing)
