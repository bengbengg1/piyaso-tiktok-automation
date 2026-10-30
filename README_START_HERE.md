# Piyaso TikTok — v16 başlangıç

- **Depolama:** mevcut Cloudflare hesabındaki tek `piyaso-tiktok-assets` bucket'ı.
- **İki medya türü:** `backgrounds/` (ana video tek havuz), `app_recordings/` (uygulama ekran kaydı).
- **Metin:** her gün Piyaso jargonunda Groq üzerinden özgün başlık üretimi; ilk 6 onaylı örnek üslup referansı.
- **Edit:** 18 saniyelik kesit, tek kare OCR, VSR AI silme, doğal konturlu yazı, Piyaso ekran kaydı.
- **Yayın:** yalnızca ayrı yayımlanan R2 Worker ile sunulan video URL'si üzerinden Buffer'a planlama.
- **Canlı durum:** henüz gerçek API, VSR modeli, Buffer hesabı ve Worker bağlantıları doğrulanmadı; otomatik yayın kapalı.

**Önemli teknik düzeltmeler:** R2 üç bucket varsayımı kaldırıldı. Yazıların 2–5 satır olması artık algılamayı bölmüyor. Çok dosyalı arşivden sadece günün 2–3 ana videosu indiriliyor. Public GitHub repository için self-hosted runner varsayılanı kaldırıldı. Ayrıntılar `LIVE_DEPLOYMENT.md` ve `R2_SETUP.md`.
