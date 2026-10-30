# Buffer → TikTok bağlama

1. Buffer'da hesabına giriş yapıp kendi TikTok hesabını bağla.
2. Buffer hesap ayarlarında API bölümünden API key oluştur.
3. GitHub Secrets: `BUFFER_API_KEY`.
4. `python buffer_setup.py` çalıştır veya Actions `buffer-check.yml` iş akışını manuel başlat. Salt-okunur sorguyla kanal kimliği listelenir.
5. TikTok için doğru channelId'yi GitHub Secret `BUFFER_CHANNEL_ID` olarak kaydet. Diğer sosyal ağ kimliği kullanılırsa yayın reddedilir.
6. Piyaso R2 Worker bağlantısını GitHub Variable `R2_PUBLIC_BASE_URL` olarak gir. Örneğin `https://piyaso-tiktok-media.<senin-worker-alt-adın>.workers.dev`. R2 S3 endpoint'ini buraya yazma.
7. Yayın testi yapılana kadar `PUBLISH_ENABLED=false` bırak. Gönderim güvenlik kontrolleri: AI yazı silme raporu, onaylı kaynak hakları, zaman aralığı, Buffer TikTok kanalı ve anonim HTTP HEAD.

Buffer API, dosyanın kendisini değil internette erişilebilir bir MP4 URL'sini kabul eder. Videonun URL'sini yayına kadar erişilebilir tutmak gerekir.

Başvuru: https://developers.buffer.com/examples/create-video-post.html ve https://developers.buffer.com/guides/hosting-media .
