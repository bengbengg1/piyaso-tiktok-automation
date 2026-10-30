# Piyaso TikTok Otomasyonu — v18 uygulama paketi

Bu paket **önceki v17 kaynak kodunun devamıdır**, sıfırdan yazılmış yeni bir proje değildir. Kaynak kod, CI, R2 video ayrımı, Groq reklam metinleri, OCR + gerçek VSR yapay zekâ destekli sabit yazı silme, render, güvenlik kontrolleri ve Buffer API planlaması içerir.

## 30 Ekim 2026 itibarıyla gerçekten doğrulananlar

- Kullanıcı Cloudflare R2 `piyaso-tiktok-assets` bucket'ını oluşturdu; `backgrounds/` ve `app_recordings/` klasörleri açıldı. `davethemen-media` ayrı ve etkilenmiyor.
- `piyaso-tiktok-media.bengisucaglayan9.workers.dev` canlı Worker'ı MP4/MOV video dosyası sunabiliyor; gerçek video tarayıcıda oynadı.
- `kalbengift` TikTok hesabı Buffer'a bağlı, Buffer GraphQL API ile **video içeren taslak** oluşturulup Buffer önizlemesinde görüldü. Gerçek TikTok paylaşımı yapılmadı.
- GitHub depo Secrets ekranında şu **isimler** görünüyordu: `BUFFER_API_KEY`, `BUFFER_CHANNEL_ID`, `GROQ_API_KEY`, `R2_ACCESS_KEY_ID`, `R2_ENDPOINT`, `R2_SECRET_ACCESS_KEY`. Şifreli değerlerini inceleyemedik; uygulamadan canlı doğrulama yapılmadı.
- v18 yerel testleri: **96 Python testi geçti** ve Node Worker erişim testi geçti (MP4/MOV/`video.mp4.mov`, aralıklı indirme, private klasör reddi). Bunlar canlı GPU VSR ya da sosyal medya paylaşımı testi değildir.

## Henüz yapılmamış / engel olanlar

1. Kaynaklar `bengbengg1/piyaso-tiktok-automation` GitHub deposuna yüklenmedi. Bağlı GitHub entegrasyonu `beautycoconat-collab` hesabıyla bu depoda **yalnız okuma** iznine sahip. Web tarayıcısından repo sahibi `bengbengg1` ile dosyalar yüklenebilir; bu paket doğrudan GitHub'a gönderilemedi.
2. Gerçek ana videolar `backgrounds/` klasöründe ve gerçek Piyaso ekran kaydı `app_recordings/` klasöründe olmalı. İşletim için `app_recording.mp4`, `app_recording.mov` veya `app_recording.mp4.mov` isimlerinden biri varsayılan kayıt olarak kullanılmalı. Tüm ana videolar `assets/catalog.json` içinde **belgelenmiş ticari kullanım izniyle** listelenmeli. TikTok kaynaklı üçüncü taraf videoları izinsiz reklamda kullanmayın.
3. GitHub **Settings → Secrets and variables → Actions → Variables** bölümüne `R2_PUBLIC_BASE_URL` adıyla `https://piyaso-tiktok-media.bengisucaglayan9.workers.dev` eklenmeli. Bu adres özel R2 S3 endpoint'i değil, yalnız yayımlanan videoların servis adresidir.
4. `GROQ_API_KEY` ve R2 S3 anahtarlarının **gerçek sunucudan** erişimi `live-check.yml` ile doğrulanmalı; Groq metin kalitesi ayrıca gözle kontrol edilmeli.
5. Gerçek **VSR AI inpainting** kodu, model dosyası ve gerçek 18 saniyelik video performansı doğrulanmadı. `VSR_HOME`, `VSR_PYTHON` ve checkpoint yoksa sistem **sahte temizlik yapmaz, üretimi durdurur**. `vsr-cpu-smoke.yml` isteğe bağlı, maliyetli/uzun deneysel testtir. GitHub-hosted CPU 2–3 günlük videoyu işleyecek hızda olmayabilir; GPU altyapısı gerekebilir.
6. Buffer'ın gerçek TikTok otomatik yayını **test edilmedi**. TikTok'a otomatik paylaşımın hesabın yetkileri, profil ve video şartlarıyla kabul edildiği ayrıca doğrulanmalı.

## Günlük kural

Pazartesi–Perşembe 2 video; Cuma–Pazar 3 video (haftada 17). Video süresi varsayılan 18 sn. İki kaynağımız var: bütün ana videolar **tek** `backgrounds/` havuzunda; Piyaso uygulaması ekran kayıtları ayrı `app_recordings/` havuzunda. Karaoke/araba/eğlence gibi alt kategoriye ayrılmaz. Video üstündeki eski sabit yazı OCR ile algılanıp VSR ile temizlenir; ana görüntüye doğal TikTok yazısı ve telefon ekranı bindirilir. Reklam metnini Groq her gün Piyaso jargonuyla yazar, tekrar/yanlış vaat kontrolü yapılır.

## GitHub Actions

- `Piyaso video CI` → kaynak kod yüklendikten sonra çalışır; önce **sentetik test** klipleri oluşturur, 96 Python + Worker JS testini çalıştırır; hiçbir videoyu yayınlamaz.
- `Piyaso live connections (read-only)` → `Run workflow` ile Groq, Buffer, R2, Worker bağlantılarını **sadece okur**. Paylaşım oluşturmaz.
- `Piyaso VSR real AI smoke test (manual / CPU)` → deneysel, gerçek model ağırlıkları gerekebilir; otomatik etkinleştirilmez.
- `Piyaso daily TikTok edits` → 06:00 UTC (09:00 Türkiye) zamanlanmıştır fakat `LIVE_READY=true` olmadan otomatik çalışmaz. Manuel deneme bile gerekli kaynaklar/modelsiz başarısız olur.
- `Piyaso Cloudflare Worker (manual deploy)` → mevcut elle kurulmuş Worker'ı değiştirmek zorunda değilsiniz. İleride GitHub'dan deploy için ayrıca **Workers edit yetkili** Cloudflare token gerekir; R2 S3 erişim anahtarları bu yetkiyi vermez.

## Güvenli açılış sırası

1. Paketi GitHub'a açılmış dosyaları ve `.github/workflows/` dahil olacak şekilde yükleyin; yalnız ZIP dosyasını repoya koymayın.
2. GitHub Actions `Piyaso video CI` yeşil olsun. `R2_PUBLIC_BASE_URL` değişkenini ekleyin.
3. Manuel `Piyaso live connections (read-only)` iş akışını başlatın. Sonuçta herhangi bir 404 / auth hatası varsa henüz yayın açmayın.
4. R2'deki videoları doğru iki klasöre yükleyin; `assets/catalog.json` hakları doğrulanmış dosyaları kapsasın.
5. VSR gerçek çıkarım testi + gerçek 18s render + görüntü inceleme tamamlanınca `LIVE_READY=true` düşünülebilir. `PUBLISH_ENABLED` **false** kalmalı, yayına çıkmak için ayrıca gerçek TikTok testini geçmeli.
6. Tüm testler tamamlanıp yayın istenirse `PUBLISH_ENABLED=true` kurulur. Free Buffer hesabında bir kanal için aynı anda bekleyen gönderi kotasına ayrıca dikkat edilmeli.

### Güvenlik

- Kodda API anahtarı yok. Repo public olabilir; anahtarları Github Actions Secrets haricinde paylaşmayın.
- `published/` altındaki dosyalar herkesin erişebileceği dosyalar; `backgrounds/`, `app_recordings/` ve `state/` internete açık olmamalı.
- Test için `published/.../video.mp4.mov` dosyası yüklenmişti; özel test videosunu sonradan yalnız o dosyayı silerek temizleyin.
- `PUBLISH_ENABLED` varsayılan olarak kapalı. Medyanın üretilmesi, otomatik olarak TikTok'a yayımlandığı anlamına gelmez.
