**HISTORICAL NOTE:** This is from an earlier feature release. For live storage/credentials use `R2_SETUP.md` and `LIVE_DEPLOYMENT.md`; no Supabase integration is present in v12.

# Piyaso — Her gün gerçekten yeni reklam cümleleri: v7

## Sistem bağlı mı?

**KODUN İÇİNDE EVET:** `.github/workflows/daily.yml` artık günlük çalışmada
`daily_copy.py` dosyasını, `render.py` işleminden ÖNCE çağırır. Model cevabı
`output/YYYY-MM-DD/daily_copy.json` dosyasına yazılır; `render.py --daily-copy ...`
**aynı** başlık ve açıklamaları o günün 2 veya 3 MP4 videosuna yerleştirir.

**DIŞ SERVİSLERDE HENÜZ HAYIR:** Bu ZIP henüz herhangi bir GitHub reposuna
kurulmadı; model API anahtarı ve Buffer/Cloudflare R2 (see R2_SETUP.md) hesap sırları yok. Bu nedenle
her sabah gerçekten yeni cümle üretip TikTok'a paylaşan canlı sistem başlatılmadı.

## Seçilen metin modeli: Groq (uzak) veya Ollama (özel sunucu)

- Varsayılan: **Groq** `openai/gpt-oss-20b` modeli; canlı GitHub Actions sunucusunda
  yerel büyük dil modeli indirmek yerine basit HTTPS API isteği gönderir.
- Alternatif: `COPY_PROVIDER=ollama`, `OLLAMA_URL` (yerel veya HTTPS) ve
  `OLLAMA_MODEL`. GitHub'ın sunucusunda `localhost:11434` genellikle çalışmaz;
  uzak erişilebilir Ollama gerektirir.
- **GitHub Models kullanılmaz** (Temmuz 2026'da emekliye ayrıldı).
- API kullanımı ve ücretsiz kota Groq hesabının güncel limitlerine bağlıdır.

### Canlı kurulum

1. Yeni **private** bir GitHub deposu oluştur. Kendi videolarını / ekran kaydını
   herkese açık Piyaso uygulaması reposuna yükleme.
2. ZIP içeriğini bu deponun **kök dizinine** koy. Workflow'un tam yolu
   `.github/workflows/daily.yml` olmalı.
3. [Groq Console](https://console.groq.com/keys) üzerinden API anahtarı oluştur;
   anahtarı **yalnızca GitHub repo Settings → Secrets and variables → Actions →
   New repository secret** alanına `GROQ_API_KEY` adıyla kaydet.
   Buraya veya kaynak koduna API anahtarını düz metin olarak yazma.
4. Gerçek ve **reklamda kullanma hakkın olan** 40–60 saniyelik videoları
   `assets/backgrounds/` içine koy. En az 3 farklı video gerekir.
   `clip_settings.json` ile klip başlangıcı, kategori ve üst yazı konumu
   belirlenebilir; tek kare OCR varsayılandır.
5. Gerçek uygulama ekran kayıtlarını `assets/app_recording.mp4` veya
   `assets/app_recordings/` içine ekle; kategori ayarları `config.json` içinde.
6. GitHub Actions → "Piyaso - AI copy + 2 / 3 TikTok promos" → Run workflow.
   İlk çalışmada **`PUBLISH_ENABLED` değişkenini `true` yapma**. Oluşan artifact'i
   kontrol et. Otomatik OCR'da emin olunmayan yazılar için sistem gönderimi durdurur.
7. Buffer TikTok hesabını bağlayıp Buffer API anahtarını, kanal kimliğini ve
   Cloudflare R2 (see R2_SETUP.md) Storage bağlantısını ayarladıktan sonra; depolama ve Buffer uçtan uca
   gerçek bir **taslak/test yayını** ile doğrulanmalı. Sonra repo variable
   `PUBLISH_ENABLED=true` yapılabilir. Bunlar bu ZIP içinde otomatik yapılandırılmaz.

## Günlük rutin

- GitHub Actions her sabah Türkiye saati 09:00 civarı tetiklenir.
- `weekly_plan`: Pazartesi–Perşembe 2, Cuma–Pazar 3 video.
- Gerçek video dosyalarına göre model o gün 2–3 **yeni** reklam başlığı ve
  TikTok açıklaması üretir; `style_examples.json` dosyasındaki **kullanıcının
  onayladığı 6 örneği** stil kılavuzu olarak alır ama aynen kopyalamaz.
- JSON kalite filtresi: marka adı, yayın açıklamasının boyu, önceki cümlelere
  benzerlik ve yüksek riskli gizli takip/konum iddiaları. Yeterli kalite çıkmazsa
  3 deneme sonrası **iş hata verir; otomatik olarak kötü sloganla paylaşmaz**.
- Cümleler `data/generated_history.json` içinde birikir; workflow başarılı
  render sonrasında otomatik commit atar; aynı gün yeniden tetiklendiğinde eski
  cümleleri kullanır ve tekrar yayın riskini düşürür.
- Gerçek videoların yazı OCR'sı **tek kare** üzerinden tespit edilir;
  model video görüntüsünü değil dosya adı/kategori + marka örneklerini görür.
  Video içeriğini tamamen anlaması sonraki özelliktir.
- Ön izleme `output/YYYY-MM-DD/` ve artifact içindedir.

## Yerel komutlar

```bash
pip install -r requirements-ocr.txt  # Python 3.12; FFmpeg sistemde kurulu olmalı
export GROQ_API_KEY="..."            # yalnızca kendi terminalinde
python daily_copy.py --date 2026-10-30
python render.py --date 2026-10-30 --daily-copy output/2026-10-30/daily_copy.json
python -m unittest discover -s tests -v
```

Yapay zekâ servisi olmadan `daily_copy.py` başarılı çalıştığını iddia etmez.
Varsayılan `render.py` (yalnız test/manuel) onaylı `ad_copy.json` havuzunu
kullanabilir; **günlük GitHub Actions işi bunu yapmaz**, yapay zekâ metin dosyası
oluşmasını zorunlu kılar.
