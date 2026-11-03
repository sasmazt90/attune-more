# Codex Cloud → AWS erişimi

Bu sohbetin ortamında 2026-11-03 kontrolünde `outbound_identities=[]`,
`secrets=[]`, `runtime_variables=[]`. AWS hesap/quota/price/IAM gözlemi yok.
Kullanıcının G/VT 8 vCPU onayı beyanı kaydedildi; API doğrulaması BLOCKED.

## Tercih edilen bağlantı

1. Codex'te bu sohbete bağlı Cloud ortamının ayarlarını düzenleyin.
2. AWS/harici kimlik bağlantısı sunuluyorsa, kısa ömürlü STS kimliği üreten
   **IAM role/federation** bağlantısını seçin. Menü adı ürün sürümüne göre değişebilir;
   bu sohbette ayar ekranı görünmüyor ve ayar yazma aracı bulunmuyor.
3. Kurulumun sağladığı issuer/audience/subject veya external-ID güven ilişkisini
   kullanın. ARN, OIDC issuer veya external-ID tahmin etmeyin. Güveni yalnız kendi
   organizasyonunuzun bu ortamına sınırlayın; wildcard principal kullanmayın.
4. İlk aşamada `infra/aws/iam/preflight-read-only.json` politikasını role ekleyin.
   Politika kaynak oluşturmaz, start/stop yapamaz, `iam:PassRole` veya secret okuma
   vermez. Hesap genelinde envanter okuması, Standard/G kotasından mevcut kullanımı
   düşebilmek için gereklidir. AdministratorAccess/root anahtarı gerekmez.
5. Anlamlı bir bağlantı alias'ı seçip bu sohbete bağlı ortama uygulayın. SDK
   seçicileri `OIC_MANIFEST_PATH` içindeki ilgili AWS girdisinden alınır;
   `AWS_PROFILE` ve `AWS_CONFIG_FILE` yalnız o komutta seçilir. Credential dosyaları
   okunup çıktıya yazılmaz. `ready` ve güncel gözlem olmadan hazır sayılmaz.

Bu seçenek arayüzünüzde yoksa güvenli ikinci yol: zaten yetkili olduğunuz
federasyon/IAM Identity Center oturumundan alınan **geçici** STS bilgilerini
ortamın Secrets alanına `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_SESSION_TOKEN` olarak koymak. Üçü birlikte, süreli ve yukarıdaki dar rolle
sınırlı olmalı. `AWS_DEFAULT_REGION=eu-central-1` normal değişken olabilir.
Uzun ömürlü IAM kullanıcı anahtarı oluşturmak gerekli değildir. Secrets alanı yoksa
sohbete veya Git'e anahtar yazmayın; bağlantı kurulana kadar kontroller BLOCKED kalır.

## HTTPS outbound allowlist

İlk hesap kontrolü için yalnız:

- `sts.eu-central-1.amazonaws.com`
- `ec2.eu-central-1.amazonaws.com`
- `servicequotas.eu-central-1.amazonaws.com`
- `pricing.us-east-1.amazonaws.com` (Frankfurt fiyatları bu API bölgesinden sorgulanır)
- `cloudformation.eu-central-1.amazonaws.com`
- `ssm.eu-central-1.amazonaws.com`
- `budgets.amazonaws.com`

Federasyon kurulumunun gerçekten istediği ek kimlik adresleri varsa yalnız onları
ekleyin; örneğin Identity Center kullanılıyorsa ilgili SSO/OIDC endpoint'leri.
Sonraki onaylı SSM yönetimi `ssmmessages.eu-central-1.amazonaws.com` ve gerektiğinde
`ec2messages.eu-central-1.amazonaws.com` ister. Artifact staging için sonradan
seçilecek **tam bucket hostname** gerekir; wildcard S3 izni şimdiden açılmaz.
Model/API provider adresleri mevcut kullanım/izinler doğrulandıktan sonra eklenir.

Resmi belgeleri shell'den okumak için `docs.aws.amazon.com`,
`source.android.com`; Android Gradle için `dl.google.com`, `maven.google.com`,
`repo.maven.apache.org`, `services.gradle.org`, `downloads.gradle.org`.
Paket yöneticisi preset'i mevcut izinlerin çoğunu kapsar. Genel interneti açmak,
proxy/TLS kontrolünü kaldırmak veya ağ politikasını dosyadan değiştirmek gerekmez.

## Bağlantı hazır olduğunda

```bash
python scripts/aws/preflight.py --identity-alias GERCEK_ALIAS --output .aws-oem/account.json
# Geçici STS Secrets yöntemi kullanılıyorsa --identity-alias verilmez.
```

Bu yalnız okuma yapar. EC2 offerings sonucu gerçek anda kapasite rezervasyonu
sağlamaz. G/VT `L-DB2E81BA` ve Standard `L-1216C47A` ayrı sorgulanır;
mevcut running/pending kullanım da hesaba katılır. IAM kısıtları, SCP/permissions
boundary ve gerçek `RunInstances` dry-run kontrolü onaydan önce ayrıca değerlendirilir.

Ücretli izinler farklı, görev kaynaklarına bağlı deployment rolünde hazırlanmalı;
mevcut readonly role sessizce genişletilmez. İlk kaynak yaratma/başlatma ancak
kullanıcının tek, somut maliyet ve süre paketini onaylamasından sonra yapılabilir.
