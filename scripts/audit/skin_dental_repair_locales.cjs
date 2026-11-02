const fs=require('node:fs'),crypto=require('node:crypto');
const file='shared/localization/messages.json',catalog=JSON.parse(fs.readFileSync(file,'utf8'));
const rows=[
 ['Önceki bölge','Previous region','Vorherige Region'],
 ['Sonraki bölge','Next region','Nächste Region'],
 ['Bu bölgedeki bulgular kesinleştirilemedi.','Findings in this region are inconclusive.','Die Befunde in dieser Region sind nicht eindeutig.'],
 ['Ölçülmedi','Not measured','Nicht gemessen'],
 ['Bu bölgede desteklenen bulgu yok.','No supported finding in this region.','Kein belegter Befund in dieser Region.'],
 ['Bu taramada desteklenen bulgu yok.','No supported finding in this scan.','Kein belegter Befund in dieser Untersuchung.'],
 ['Geometri referans sırası (0–100)','Geometry reference rank (0–100)','Geometrischer Referenzrang (0–100)'],
 ['Belirginlik skoru (0–100)','Visibility score (0–100)','Sichtbarkeitswert (0–100)'],
 ['Göz köşesi eğiminin kayıtlı pozitif referanslar içindeki sırasıdır; hastalık olasılığı veya klinik şiddet değildir.','Ranks the eye-corner tilt among stored positive references; it is not disease probability or clinical severity.','Ordnet die Neigung der Augenwinkel unter gespeicherten positiven Referenzen ein; keine Krankheitswahrscheinlichkeit oder klinische Schwere.'],
 ['Sonuç kaydediliyor…','Saving result…','Ergebnis wird gespeichert…'],
 ['Geçerli sayısal sonuçlar otomatik olarak yerel geçmişe kaydedilir.','Valid numerical results are saved automatically to local history.','Gültige numerische Ergebnisse werden automatisch im lokalen Verlauf gespeichert.'],
 ['Fotoğraf görünümü','Photo view','Fotoansicht'],
 ['Detay görünümü','Detail view','Detailansicht'],
 ['Tam görünüm','Full view','Vollansicht'],
];
for(const [tr,en,de] of rows){const key=Object.keys(catalog).find(k=>catalog[k].tr===tr)||crypto.createHash('sha256').update(tr).digest('hex').slice(0,16);catalog[key]={tr,en,de};}
fs.writeFileSync(file,JSON.stringify(catalog,null,2)+'\n');
console.log('Added/verified '+rows.length+' TR/EN/DE messages');
