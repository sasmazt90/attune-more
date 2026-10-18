# Son build kabul kaydı — 8 Ekim 2026

Durum: **fiziksel kabul tamamlanmadı**. Önceki rapor ve eski build'in 2/12
fiziksel ilerlemesi bu kayda kabul kanıtı olarak taşınmaz.

Production BUILD_ID: `HKnW2pgTWCpYbT6ArP0oc`.

## Bağımsız tamamlananlar

- Production high `GHSA-68fv-2mgg-jv7q`: source-map-js 1.2.1 → exact 1.2.2.
  Root override bütün PostCSS yollarını kapsar; Next/PostCSS sürümleri korunur.
  Büyük/sonsuz ofsetin eski consumer tarafından kabulü sınırlı çağrıyla
  doğrulandı; aynı çağrı artık reddedilir. Kötü tipler ve nested toplam ofset
  reddi, normal map/SourceNode/PostCSS davranışı regresyonda geçti.
  Production build, bağımsız read-only aday incelemesi ve production audit
  geçti. Production audit: 0 bulgu; full audit: 7 high dev + 2 moderate açık.
- 62 ilgili regresyon ilk toplu çalışmada geçti. Eski bir ses testi, kullanıcının
  harf alanına bakması yönergesine aykırı beklenti taşıyordu; beklenti düzeltildi.
  Ses profili/transport ve V3 fotoğraf kontrollerinin tamamı yeniden geçti (6).
  Güvenlik boundary testi ayrıca geçti (1).
- Son production build'de `postmeeting_skin_contract.py` iki gerçek-model
  kontrollü üç poz taramasını tamamladı. V3 kaynak fotoğraf alpha'sı tamamen
  opak; SVG clip/mask yok; altı seçili bölge, legacy referans ayrımı ve
  kalıcı kayıtta fotoğraf tutulmaması doğrulandı. Bu insan kabulü değildir.
- `skin_cabin_preview.py`: lisanslı tam video karesinde kaynak analizini
  değiştirmeyen yüz zoom'u, gerçek SVG/video hizası, native Chrome %100/%200
  DPR 1.5/3, yatay taşma olmaması ve iptalde kamera kapanması geçti.
- `vision_camera_followup.py`: gerçek üretim modeli ile stale-frame, privacy,
  sürüş/route kapanması ve ses hatasında ilerlememe negatif kontrolleri geçti.
  Sahte STT olayı ve ücretli çağrı yok. Pozitif göz/konuşma kabulü sayılmaz.
- Aktif Cilt yolu `snapshotRawSkinFrame`; kaynak fotoğraf/arka plan, seçili
  bölge ağları, kayıt sözleşmesi ve `tts_profiles.py` 6ec0d5c ile aynı.

## Yalnız son build için açık fiziksel maddeler

| Madde | Durum |
| --- | --- |
| Sağ 12 + sol 12 geçerli native mikrofon denemesi | BEKLİYOR |
| Her gözde göz yumma, el, opak cisim pozitif kabulü | BEKLİYOR |
| TTS sürerken tam ve iki parçalı yanıt; her iki söyleme sırası | BEKLİYOR |
| Sessiz kullanıcıda sistem sesinin puan/yanıt üretmemesi | BEKLİYOR |
| Gerçek belirgin yaklaşma/uzaklaşma ve toparlanma | BEKLİYOR |
| Harf görünürken fiziksel oturumda native %200 | BEKLİYOR |

`tests/e2e/vision_acceptance_session.py` tek bounded oturum açar: önce gerçek
başlangıç/near/far, sonra her gözde dört yumma + dört el + dört opak cisim
denemesi. Kısa mavi şerit test protokolüdür; hedef yanıtı vermez, uygulama
koşullarını değiştirmez. Kaynak video/model/ASR veya yanıt yerine fixture
konmaz. Gerçek native ASR/audio olayları, parsed alanlar ve geometri ölçülür;
kamera fotoğrafı, ham konuşma ve ses saklanmaz. Ayrı geçici browser profili
normal kullanıcı kayıtlarını değiştirmez.

Fiziksel başarısız adım, yalnız kendi exact build/sunum/zaman kanıtıyla
düzeltilip tekrar doğrulanır. Bu hazırlık belgesi final kabul değildir.
