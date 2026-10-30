# v16 — 2026-10-30

92 Python unit/integration-mock checks and Cloudflare Worker access-control smoke checks passed locally.

**Kod durumu:** yerel testleri geçen ama dış bağlantı/model gerektiren bir otomasyon taslağı. TikTok'a gönderi planlanmadı ve gerçek Buffer/R2/Groq anahtarlarıyla canlı uçtan uca test yapılmadı.

- GitHub Actions yayın öncesi kontrolünde kaldırılmış `R2_PUBLIC_BUCKET`/`R2_STATE_BUCKET` değişkenleri düzeltilerek tek bucket'a alındı.
- Sabit çok satırlı eski yazı için bir ekran görüntüsünden paragrafları birleştiren OCR bölge algılama eklendi. Ayrı uzak bloklar review_required olarak işaretlenir.
- Onaylı kaynak havuzundan yalnızca günün 2–3 ana videosunu indirme ve tüm kaynaklar üzerinden doğru deterministik seçim korunarak uygulanır.
- GitHub deposunun Public kalması isteği nedeniyle kalıcı self-hosted runner seçimi workflow'dan kaldırıldı. VSR GPU ortamı **hala gerekli ve sağlanmadı**.
- Daha eski üç bucket talimatları tek `piyaso-tiktok-assets` olacak şekilde güncellendi.
- VSR kaynak kodunu indiren yardımcı betik, doğrulanmış upstream commit SHA'sına sabitlendi (model ağırlıkları / GPU dahil değil).
- Otomatik dış yayın/hesap değişiklikleri gerçekleştirilmedi.
