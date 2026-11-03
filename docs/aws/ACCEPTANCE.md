# Kabul matrisi — sahte PASS yok

> 3 Kasım final hazırlık güncellemesi: [doğrulanmış model/runtime paketleri ve onay sınırı](PREPARATION-20261103-FINAL.md). Önceki transfer engelleri giderildi; canlı kabul ve ücretli start onayı bekliyor. Aşağıdaki önceki runtime kayıtları tarihsel kanıttır.

> Güncel durum (2026-11-03 R2): önceki IAM okuma/Pricing engelleri kalktı.
> [R2 preflight](PREFLIGHT-20261103-R2.md) ve [sayısal başlangıç paketi](START-PLAN.md)
> önceki erişim/maliyet durumlarını günceller. Üç SG kuralı uygulandı/doğrulandı; model aktarımı ve canlı kabul bekliyor.


Mevcut AWS hedefleri: WEB `i-0b25450afc6633494`, AAOS `i-0f4cca4e92e94c351`.
2026-11-03 gerçek EC2 API çağrısı ikisini de `stopped` doğruladı. Bölge `eu-central-1`.
[Canlı preflight](PREFLIGHT-20261103.md) kısmen tamamlandı; runtime kabul hücreleri değişmedi.
WEB hedefi `https://attune.sasmaz.digital`, AAOS hedefi `https://aaos.sasmaz.digital`.
Bunlar **canlı demo URL'si değildir**. DNS/TLS/hesap doğrulaması yapılmadı.

| Kabul maddesi | WEB AWS | AAOS AWS | Gerekli kanıt |
|---|---|---|---|
| Beş modül ekranı açılır | BLOCKED | BLOCKED | HTTPS oturum + gerçek AWS kayıt |
| Skin FRONT/RIGHT/LEFT + regional fusion | BLOCKED | BLOCKED | Kaynak hash/poz/model hash/sonuç |
| Dental capture/analysis | BLOCKED | BLOCKED | Gerçek görüntü → mevcut model sonucu |
| Vision tam akış | BLOCKED | BLOCKED | Geometri, sonuç, geçmiş |
| Hearing tam akış | BLOCKED | BLOCKED | Gerçek ses aktarımı ve çıktı; noVNC ses taşımaz |
| Mental tam akış | BLOCKED | BLOCKED | Onaylı gerçek sağlayıcı, ses/mikrofon sınırları |
| Sonuç/geçmiş/yeniden açma/silme | BLOCKED | BLOCKED | Aynı oturum + yeniden başlatma; saklama onayı |
| İptal/DRIVE/geç sonuç düşürme | BLOCKED | BLOCKED | Gerçek uçtan uca yarış testi |
| TR/EN/DE | BLOCKED | BLOCKED | WEB ve native toolbar birlikte |
| Gerçek AAOS API35, APK, KVM | uygulanmaz | BLOCKED | Guest properties, APK hash, /dev/kvm |
| Uzaktan gerçek ekran/input | uygulanmaz | BLOCKED | Canlı emulator video + input kaydı |
| Native PARK/DRIVE | uygulanmaz | BLOCKED | Platform UX restriction + backend gate |
| UGREEN → cloud AAOS → analiz | uygulanmaz | BLOCKED | Gerçek fiziksel kamera ve kaynak kimliği |
| Windows backend/emulator bağımsızlığı | BLOCKED | BLOCKED | İki EC2 üzerinde çalışma kanıtı |
| AWS stop ve bakiye ücret makbuzu | BLOCKED | BLOCKED | API'den instance/volume/EIP durumları |

Yerel derleme, politika birim testleri ve sentetik kamera **taşıma** testi bu
matristeki hiçbir AWS/AI/AAOS hücresini PASS'e dönüştürmez. Ekran görüntüsü veya
önceden kayıtlı bir video gerçek AAOS runtime yerine kullanılmaz.

## Açık sınırlar

- AWS kimliği, izinler, actual quotas, AZ/capacity, güncel fiyat ve harcama: BLOCKED.
- Yeni kaynak oluşturmak yasak. Mevcut sunucuları başlatmadan önce maliyet/test kapsamı bildirimi ve onayı bekleniyor.
- IONOS kayıt okuması ve tam DNS değişiklik onayı yok.
- Canlı TLS/mTLS sertifika doğrulaması ve toplantı parola rotasyonu koşul.
- Model arşivleri Drive'da bulundu; mevcut kod manifestiyle tamamı eşleşmiş değil.
  Eski AG handoff farklı artifact isimlerini listeliyor. GPU çıktısı/eşdeğerliği yok;
  CPU yolu korunuyor, NVIDIA donanımı bulunması CUDA yürütme kanıtı değil.
- PNG demo köprüsünde gerçek UGREEN renk/kalite/poz/kayıt/cancellation doğrulaması yok.
- noVNC ekran/input hazırlığı ses sağlamıyor. Gerçek Hearing/Mental demosu için
  hazırlanan ayrı PCM ses/mikrofon transportunun guest üzerinde doğrulanması gerekiyor.
- Cloud APK debug-türevi demo varyantı; OEM üretim entegrasyonu değildir.
- Bir aktif toplantı desteklenir. Çok kullanıcıya ait ayrı hasta hesapları yok.

## Hesap erişimi sonrası sıralama

Mevcut kaynak inventory + readonly preflight → mevcut SG/subnet/volume/IAM eksiklerinin incelenmesi → gerçek maliyet/kapasite/izin değerlendirmesi → tek somut ücret
onayı → iki host/TLS/model kurulum → gerçek AAOS boot/input → gerçek kamera + model
çıktısı → ses/provider sınırları → beş modül tam kabul → DNS ayrı onayı → durdurma
ve kalan EBS/EIP ücretlerinin kaydı. Bir aşama geçilmeden sonraki aşama başarılı
olarak işaretlenmez.
