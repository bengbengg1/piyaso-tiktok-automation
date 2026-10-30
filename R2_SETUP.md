# Cloudflare R2 — mevcut hesaba dokunmadan Piyaso otomasyonu

**Tek bucket:** `piyaso-tiktok-assets`. Kullanıcı bu bucket'ı, `backgrounds/` ve `app_recordings/` klasörlerini Cloudflare panelinde oluşturdu. Sadece bu bucket'a `Object Read & Write` yetkisi olan S3 API anahtarını da oluşturdu. Bu paket hesapta ek değişiklik **yapmaz**.

R2 object key'leri:

- `backgrounds/*.mp4` — ana videolar; araba/karaoke türlerine göre ayrı sınıflandırma yapılmaz.
- `app_recordings/app_recording.mp4` — zorunlu Piyaso ekran kaydı. Başka kayıtlar da konulabilir; ana videolarla kategorik eşleştirme yoktur.
- `state/copy/YYYY-MM-DD.json` — yalnızca özel reklam metni geçmişi.
- `state/piyaso/YYYY-MM-DD/SLOT/{submission,confirmed}.json` — yalnızca özel Buffer tekrar-yayın koruması.
- `published/piyaso/YYYY-MM-DD/SLOT/video.mp4` — sadece *son* reklamlar. Worker üzerinden anonim URL ile servis edilir; bucket geneli **public değildir**.

**Davethemen:** `davethemen-media` bucket'ına koddan erişim açıkça engellenir. `piyaso-music` de kullanılmaz. Mevcut R2 token `piyaso-tiktok-assets` ile sınırlıdır; yeni bucket/token gerekmez.

## GitHub secrets (sohbete veya dosyaya koymayın)

- `R2_ENDPOINT` — Cloudflare'ın S3 endpoint'i `https://<account-id>.r2.cloudflarestorage.com` biçiminde
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

Cloudflare'da token oluşturma ekranındaki **Token value** ile S3 Access Key ID / Secret Access Key aynı şey değildir. Bu betiklerin kullandığı S3 çiftidir.

GitHub Actions variables:

- `R2_ASSETS_BUCKET=piyaso-tiktok-assets`
- `R2_PUBLIC_BASE_URL=https://<subdomain>.workers.dev`
- `LIVE_READY=false`
- `PUBLISH_ENABLED=false`

`R2_PUBLIC_BUCKET` ve `R2_STATE_BUCKET` **kullanılmıyor**. Üç rol tek bucket'ta yalıtılmış prefix'lerde.

## Yayın için salt-okunur Worker

`worker/` dizinindeki Worker'ı Cloudflare Workers & Pages'de yayımla; R2 binding `MEDIA` → sadece `piyaso-tiktok-assets`. Worker yalnızca `published/piyaso/.../video.mp4` dosyalarını `GET`/`HEAD` ile açar. Diğer dosya yollarına 404 döner. `workers.dev` URL'si `R2_PUBLIC_BASE_URL` olur. **R2 bucket'ın Public Access değerini değiştirme.**

Buffer video URL'sini göndermeden önce `HEAD` ile erişim denetlenir. Buffer dosyayı yayın saatine kadar internette okuyabilmelidir. Davethemen/müzik linkleri hiçbir koşulda bu Worker'a bağlanmaz.

## Kaynak dosyaları koyma

Dashboard'da `backgrounds/` içine kullanım izni bulunan videoları, `app_recordings/` içine Piyaso ekran kaydını yükle. `assets/catalog.json` dosyasında her reklamda kullanılabilecek ana video için onayı ve kaynağını kayıt altına al:

```json
{"backgrounds":{"ornek_001.mp4":{"commercial_use_authorized":true,"source":"lisans/izin belgesi referansı"}}}
```

**Önemli:** Ticari kullanım izni verilmemiş sosyal medya videoları yalnızca hesapta bulunuyor diye izinli sayılmaz. Gerçek kişiler ve müziklerin reklamda kullanımı da kontrol edilmeli.

Cloudflare R2 ücretsiz depolama payı *hesabın genelinde* uygulanır. Ekran görüntüsünde eski `davethemen-media` bucket'ında 54,42 GB vardı; Piyaso'nun oluşturduğu ek videolar ayrıca depolama maliyeti getirebilir. Güncel ücret: https://developers.cloudflare.com/r2/pricing/ .
