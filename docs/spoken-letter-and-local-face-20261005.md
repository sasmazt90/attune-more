# Sesli harf görevi ve yerel yüz sunumu

## Ürün sözleşmesi

`/vision` artık `SpokenLetterPage` kullanır. Döner seçici, kart ve alıştırma
canlı rotadan kaldırıldı. Eski yön sonuçlarının açılması ve eski matematik
regresyonları korunur; geçmiş sonuçlar yeni protokol gibi gösterilmez.
Yeni protokol `spoken-letter-v1`, her göz için 12 geçerli denemede durur.
Harf ve yön çözücüsü hedefi almaz. “Ters” netleştirilir; aynı sunum korunur.
SVG A'nın düz/aynalı ve E'nin baş-aşağı/aynalı görüntüleri eşdeğer kabul edilir.
İki ardışık doğru HARF boyutu 10^0,1 (1,258925…) kat küçültür; yanlış harf/göremiyorum büyütür. Yalnız yön hatası boyutu artırmaz. Başlangıç 120 CSS pikseldir.
18–180 CSS piksel sınırı ve 12 deneme mühendislik tercihleridir; klinik eşik
veya doğrulanmış test tekrarlanabilirliği iddia edilmez.

Uyarlanır görev mantığı [Levitt'in birincil çalışmasına](https://pubmed.ncbi.nlm.nih.gov/5541744/)
dayanır; bu uygulamanın sayılarını veya klinik geçerliliğini kanıtlamaz.
[Sayısal görme keskinliği çalışması](https://pubmed.ncbi.nlm.nih.gov/33139229/)
optotip ve sunum biçiminin ölçümü etkilediğini inceler. Döndürülmüş kendi
harflerimiz için Snellen/logMAR, göz numarası ve reçete üretilmez.

## Kamera geometrisi ve göz kanıtı

Windows WMI'dan iki etkin EDID boyutu (31×17 ve 60×34 cm), UGREEN Camera,
Integrated IR Camera ve hata durumundaki Integrated Camera alınabildi.
Bu bilgiler pencereyi fiziksel ekrana bağlayan doğrulanmış profil, kamera
intrinsikleri veya kamera-ekran ofseti sağlamıyor. Bu nedenle fiziksel ölçek
ve mutlak göz-ekran uzaklığı **doğrulanmamış**, güven düzeyi **belirlenemiyor**.
CSS mm, yüz genişliği veya varsayılan odak sabitiyle cm üretilmez.
Yeni kayıtlar fiziksel ölçek null ve profil unverified taşır; doğrulanmamış
cihazlar arasında önceki sonuçla karşılaştırma sunulmaz.

Başlangıç konumu bir saniyelik geçerli, tek-yüz görüntüsünden alınır. Mevcut
ışık/netlik/poz eşikleri korunur. Yüz ölçeğinin başlangıçtan %8 sapması,
750 ms eski görüntü, model/kamera kaybı ve göz koşulu yanıt işleyicisini de
durdurur. Anatomik sağ göz MediaPipe 33–133, sol 362–263; video aynalanmaz.
Lid geometrisine ek olarak aynı karedeki göz yaması kontrastı/koyu piksel
oranı gerekir. Açık, kapalı ve belirsiz ayrı tutulur; belirsiz puanlanmaz.
Bu mühendislik kontrolü elin arkasındaki görmeyi veya klinik örtülmeyi
garanti etmez. Kısa göz kırpması hemen puanlama engelidir; uyarı için 800 ms
kalıcılık gerekir. Tamam, kamera kanıtını değiştirmez.
Kişisel kapalı-göz/örtülme ve sesli yanıt kabulü kullanıcı testini bekler;
lisanslı sanal görüntüyle negatif kontroller kişisel kabul olarak sunulmaz.

## Ayrı doğruluk ve yeniden hesaplama

Her kayıt deneme/sunum kimliği, protokol, göz, hedef harf/yön, nominal boyut,
DOM'dan ölçülen SVG viewport/path sınırları ve stroke genişliği (CSS pikseli),
çözümlenmiş yanıt, ayrı harf/yön/birleşik doğruluk, geçerlilik/neden, yanıt
süresi ve güncel kare/konum/göz kanıtı taşır. Stroke ölçüsü ayrıca tutulur:
path sınırları stroke dahil boyalı alan diye sunulmaz. Fiziksel boyut yoktur.
Sonuç oranları hedef ve yanıt kayıtlarından yeniden hesaplanır; önceden
saklanan correct boolean'ına güvenilmez. Her göz ve render boyutu ayrı grup.
Doğru/deneme adetleri ve yüzde birlikte; sıfır örnekte yeterli yanıt yok.
Göremiyorum üç ilgili paydada yanlış; teknik/ASR geçersizlik değerlendirme dışı.
Geçersiz sunum aynı deneme/hedef/boyutu yeni sunum kimliğiyle yeniden alır.
STT instance/epoch ve tüketilmiş sunum kimliği geç/çift puanlamayı engeller.
En küçük doğru boyut veya tek şanslı yanıttan eşik üretilmez.

[Levitt 1971, DOI 10.1121/1.1912375](https://pubmed.ncbi.nlm.nih.gov/5541744/)
transformed up-down uyarlama ilkesini destekler; 12+12 UX sınırının klinik
yeterliliğini veya bu özel harf/yön testinin geçerliliğini desteklemez.
[Ferris ve ark. 1982](https://pubmed.ncbi.nlm.nih.gov/7091289/) eşit zorluk,
beş Sloan harfi ve geometrik boyut ilerlemesi tasarımını;
[National Research Council görme işlevleri raporu](https://www.ncbi.nlm.nih.gov/books/NBK207559/)
0,1 log birim = 1,2589 çarpanını açıklar. Biz yalnız log boyut adımını kullanırız;
fiziksel ölçek/göz mesafesi ve klinik eşik yöntemi olmadan logMAR/ETDRS sonucu yok.

## Microsoft Edge profilleri ve karşılaştırma

Merkezi `services/core-api/tts_profiles.py`:
- VISION_TTS_PROFILE: it-IT-GiuseppeMultilingualNeural, +20%, -10Hz.
- MENTAL_WELLBEING_TTS_PROFILE: en-US-AvaMultilingualNeural, +10%, +0Hz.

Güncel gerçek Edge kataloğunda iki exact ses bulundu (322 ses). İki profil
sabit; başka Edge sesi, tarayıcı sesi, OpenAI TTS veya Azure fallback'i yok.
Eski -5% aktif akıştan kaldırıldı. Mental demo da ses için çevrimiçi Edge kullanır.
Görme yalnız sabit yönerge kodu; hedef veya kullanıcı transcript'i göndermez.
Ruhsal yanıttan seslendirilecek metin, kullanıcının bu görevde açıkça onayladığı
Edge tüketici hizmetine, mevcut tek hizmet onayıyla gönderilir. Önceki Isabella
engeli yeni kullanıcı talimatıyla Ava seçimine dönüştü. OpenAI sohbet/izinli
özet modeli değişmedi; yeni ücretli kabul çağrısı yapılmadı.

Sınırlı karşılaştırma: aynı Giuseppe/sabit Türkçe cümle/+20% ile +0Hz,
-10Hz, -20Hz olmak üzere üç gerçek MP3; Ava +10%/+0Hz ile bir gerçek MP3.
Cümleler kişisel veri içermez. İlk parça gecikmeleri 1191/1122/963/787 ms;
boyutlar 21312/21312/21312/23184 bayt. Dosyalar
`audit-results/product-decisions-20261005/voices/` altında.
Giuseppe için denenmiş en küçük aşağı offset -10Hz yaklaşık aday olarak seçildi.
Gerçek Clipchamp Low referansı sağlanmadı: eşleşme veya keyfi Low→Hz eşlemesi
iddia edilmez. İnsan işitsel telaffuz/doğallık/Low tercihi manuel kabulü bekler.
MP3 veya native playing/ended bu işitsel kabulün yerine geçmez.

[edge-tts upstream](https://github.com/rany2/edge-tts) consumer Edge bağlantısı
ve desteklenen tek voice/prosody kullanımını açıklar. Türkçe metin gönderilir;
olmayan Language=Turkish/custom SSML parametresi eklenmedi. `edge-tts==7.2.8`.
Anahtar/kaynak/hesap taşınmadı veya oluşturulmadı. Edge için belgelenmiş uygulama
API kotası/SLA/ticari dağıtım yetkisi doğrulanmadı; sınırsız erişim sözü yok.
[Microsoft hizmet sözleşmesi](https://www.microsoft.com/en-us/servicesagreement)
consumer kullanım çerçevesidir; bu inceleme hukuki dağıtım onayı değildir.

## Cilt ve ruhsal kayıtlar

Başlangıç fotoğrafı yalnız belirtilen Scanned-Woman.png'nin kopyasıdır.
Sonuçta kabul edilmiş gerçek kare RAM'de tutulur, MediaPipe yüz konturuna
yerel kesilir; arka plan/gövde gösterilmez. Altı anatomik çizgi/nokta aynı
koordinat sistemindedir; asıl sayısal örnekleme ROI'si ve göz/dudak
istisnaları içinde kesilir. Analiz alanı veya sayısal metrikler değiştirilmedi.
Tüm altı verilen referans gerçekten açılıp incelendi. Fotoğraf geçmişe
veya yeni bir buluta yazılmaz. Kategori anlamları bilgi dialogundadır.

Ruhsal kayıt paneli asistan/tema panellerinin altında tam genişliktedir.
Gerçek startedAt ile sıralanır, eski eksik zaman/döküm uydurulmaz.
Tamamlama bildirimi Tamam dialogundadır; başarısızlık görünür kalır.
Tema/yuvarlama açıklaması yalnız bilgi dialogundadır. Özet/döküm tercihleri,
tekil kayıt, Evet/Hayır silme, yeniden açma ve kullanıcı izolasyonu korunur.

## Regresyon değişikliklerinin gerekçesi

Eski selector/card browser assertion'ları kullanıcı tarafından kaldırılan
UI'yi beklediğinden spoken entrypoint/removal/privacy/viewport assertion'larına
taşındı; eski angular/geometri unit testleri silinmedi. Yeni üretim TS testleri
hedef-bağımsız parsing, belirsizlik, simetri, gerçek doğru/yanlış/göremiyorum
adaptasyonu, aynı sunum, çift yanıt, yanlış göz/belirsiz göz/hareket/eski kare
puanlama engelini denetler. Eski Coral route testi sabit Microsoft yönerge
chunk/cleanup testine taşındı. Yeni modal testleri gerçek Tamam'ı tıklar;
kayıt sayısı tema paneli yerine yeni kayıt panelinden okunur. Skip veya
kalite eşiği düşürme yok. Browser üretim fixture yanıtları canlı OpenAI kabulü
değildir; yeni ücretli OpenAI koşusu ve kişisel fiziksel capture yapılmaz.

## Güncel yerel doğrulama

240 unit, skip yok; typecheck/fresh build/lint başarılı (iki önceden mevcut lint uyarısı).
16 korunan matris çalıştırması geçti; ayrı cilt ilk/tekrar ve üç açılı tarama,
ruhsaI kayıt yerleşimi, 10 UX ve 7 final akış kontrolü de geçti.
Native MPEG yardımcı + normal production API üzerinde iki yeni gerçek Edge
isteği: Giuseppe playing 1901 ms / body-end 3121 ms; Ava playing 814 ms /
body-end 1724 ms. İkisinde gerçek ended; ücretli OpenAI 0, fiziksel capture 0.
Bu yardımcı/endpoint kanıtı, kişisel göz/STT veya canlı sohbet kabulü değildir.
Algoritma ve gerçek DOM geometrisi test fixture'ı 120→95,3125 CSS pikseli
render değişimini, ayrı sonuç görünümünü ve kalıcı silmeyi doğruladı; kamera
ve native STT kabulü olarak sunulmaz.
Npm audit 7 high geliştirme / 0 production; beş bağımlılık güvenlik regresyonu geçti.
Edge tüketici hizmeti için dağıtım/SLA ve işitsel doğallık açık kalır.
Eski ücretli OpenAI TTS harness'leri güncel ürün kabulü değildir; gerçek
çalıştırma engellenir, tarihsel bütçe/transport korumaları yalnız keyless
fixture ile test edilir. Eski paired-20261004 arşivi değiştirilmedi.
