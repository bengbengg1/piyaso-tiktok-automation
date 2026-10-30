# Canlı servis bağlantıları — v17

**YAPILDI:** Kodda Groq JSON schema doğrulaması, salt-okunur canlı testler, ayrı Cloudflare Worker deploy iş akışı ve isteğe bağlı deneysel CPU VSR hazırlığı var. Yerel testler, gerçek hizmet bağlantısı değildir.

**HENÜZ YAPILMADI:** Cloudflare Worker yayımlama; Groq/Buffer/R2 servislerine canlı bağlanma; gerçek VSR model ağırlıklarıyla 18 sn çıkarma; Buffer/TikTok yayın testi. Proje henüz GitHub'a yüklenmedi. Hiçbir hesapta otomatik yayın açılmadı.

## Kullanıcının hesaplarında yapılacak zorunlu işlemler

1. **Buffer:** TikTok hesabını Buffer'a bağla; Buffer API key oluştur. GitHub Actions Secrets: `BUFFER_API_KEY`, `BUFFER_CHANNEL_ID`. TikTok channel ID öğrenmek için `python buffer_setup.py` çalıştır.
2. **Groq:** https://console.groq.com/keys sayfasından anahtar al, GitHub Secret: `GROQ_API_KEY`. Repo Variable: `GROQ_MODEL=openai/gpt-oss-20b`. `python live_smoke.py --groq` salt-okunur bağlantı testini yapar.
3. **R2:** Var olan `piyaso-tiktok-assets` bucket, `backgrounds/` ve `app_recordings/` klasörleri korunacak. Yetkilendirilmiş S3 anahtar çiftini GitHub Secrets: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`. Bunları buraya veya repo içine yazma. Public Access kapalı kalır. `python live_smoke.py --r2` doğrular. Davethemen bucket'ına dokunma.
4. **Cloudflare Worker:** Worker deployment için R2 S3 anahtarından **farklı** bir Cloudflare **Workers edit yetkili API Token** gerekir. GitHub Secrets: `CLOUDFLARE_WORKERS_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`. `.github/workflows/deploy-worker.yml` elle tetiklenir. Çıkan `https://...workers.dev` adresini repo variable `R2_PUBLIC_BASE_URL` olarak ayarla. `python live_smoke.py --worker` doğrular. Worker yalnız `published/piyaso/...mp4` yollarını sunar.
5. **VSR:** `.github/workflows/vsr-cpu-smoke.yml` yalnız kullanıcı isteyerek başlatacağı gerçek AI 1 saniyelik deneydir. CPU-only ağır olabilir, ücretsiz kota/tam 18s yükünü doğrulamadan `VSR_CPU_ENABLED=true` veya `LIVE_READY=true` yapma. AI modeli kurulmamışsa sistem yayımlamaz.
6. **İçerik:** İzinli ana videolar R2 `backgrounds/` altına; Piyaso ekran kaydı `app_recordings/app_recording.mp4` olarak yüklenir. `assets/catalog.json` dosyasında yalnız reklam kullanım hakkı doğrulanan ana videoları `commercial_use_authorized=true` yap.
7. **Son test:** GitHub dosyaları yüklenince `python live_smoke.py --all` bağlantıları okur (gönderi oluşturmaz). `python preflight.py --live` hazır olma kontrolüdür. `PUBLISH_ENABLED` varsayılan kapalı; tamamı doğrulanmadan açılmayacak.

**Not:** Public GitHub deposunda özel tokenlar/ham görüntüler bulundurulmaz. GitHub-hosted runner ücretsiz/GPU olmadan gerçek VSR ile 18 saniyelik 2–3 videoyu günlük çalıştırmaya yetmeyebilir. Performans testi sonucu ayrı GPU servisi gerekebilir.

> **v17 test sonucu:** 94 yerel Python testi + 1 Cloudflare Worker JS erişim testi geçti. `live_smoke.py --all` çalıştırıldığında gerçek hesap anahtarları ve çalışan Worker adresi henüz tanımlı olmadığından dört harici servis kontrolü de NOT READY verdi. Bu durum canlı hazır olduğu anlamına gelmez.
