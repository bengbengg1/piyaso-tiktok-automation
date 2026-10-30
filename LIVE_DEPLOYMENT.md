# Piyaso TikTok — canlı yayına geçmeden gerekenler (v16)

## Kullanıcı tarafından tamamlananlar

- R2 `piyaso-tiktok-assets` bucket'ı ve iki kaynak klasörü açıldı.
- Yalnızca bu bucket'a izinli S3 R2 anahtarı oluşturuldu.
- Davethemen bucket'ına dokunulmadı.
- GitHub deposu oluşturuldu; kullanıcı kodları daha sonra yükleyecek ve Public kalacak.

## Eksikler (otomasyon HENÜZ CANLI DEĞİL)

1. Buffer hesabındaki TikTok kanalının yetkilendirilmesi, API key ve `channelId`.
2. Groq API key (`GROQ_API_KEY`) ve gerçek istek denemesi.
3. Cloudflare **Worker** yayımlanması ve `MEDIA` R2 binding kurulumu. Mevcut R2 anahtarı Worker'ı otomatik yayımlamaz.
4. `backgrounds/` içine en az 2 (3 video günleri için en az 3) ticari kullanım izni bulunan kaynak; `app_recordings/app_recording.mp4` kaydı; lisans kataloğu.
5. VSR altyazı silme modelinin gerçekten kurulması/denenmesi; GPU/CPU maliyeti ve süre testi. **GitHub public deposuna kalıcı self-hosted runner bağlamayın:** güvenlik riski. İş akışında yalnızca `ubuntu-latest` kullanılır ve VSR yüklü değilse fail-closed hata verir. İşlem için ayrı bir güvenli yürütme yolu henüz sağlanmadı.
6. Bir gerçek tanıtım videosu için edit kalitesi, mahremiyet ve telif onayı; kontrollü Buffer uçtan uca test.
7. Bundan sonra `LIVE_READY` ve `PUBLISH_ENABLED` güvenli şekilde etkinleştirilebilir.

## Kontrol komutları

```bash
python -m unittest discover -s tests -q
node worker/test.mjs
python preflight.py --live
python buffer_setup.py --check    # yalnızca gerçek API secrets mevcutken
```

Public GitHub depoya asla R2/Groq/Buffer anahtarları, özel videolar ya da müşteri içerikleri yüklenmez. Tokenlar sadece GitHub Secrets içinde; videolar R2'nin özel `backgrounds/` ve `app_recordings/` yollarında. Uygulama içi ekran kayıtları kişisel bilgileri göstermemeli.
