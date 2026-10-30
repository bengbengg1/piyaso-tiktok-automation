# Piyaso'da iki medya türü

1. **Ana video:** Her şey tek havuzda: `piyaso-tiktok-assets/backgrounds/`. Araba sürme, karaoke, müzik, arkadaş ortamı vb. içerikler kategorilere ayrılmaz.
2. **Uygulama ekran kaydı:** `piyaso-tiktok-assets/app_recordings/` altındaki MP4'ler. `app_recording.mp4` varsayılan ve zorunlu kayıttır. Diğerleri isteğe bağlı olarak sırayla kullanılır.

Her günün 2 veya 3 ana videosu R2'deki tüm *izinli* ana video listesinden döngüsel seçilir; sadece o gün kullanılacak dosyalar indirilir. Uygulama ekran kayıtları bağımsız döndürülür, ana videonun adından ya da kategorisinden eşleştirme yapılmaz.

İşlem sırası: ana videonun 18 saniyelik kesiti → tek görüntüden sabit eski yazıyı algılama → VSR ile gerçekten kaldırma → doğal beyaz/siyah konturlu TikTok reklam cümlesi → küçük Piyaso ekran kaydı → Buffer.

**Yapay zekâ tespiti belirsizse veya AI yazı silme başarısızsa otomatik paylaşım kapalı kalır.**
