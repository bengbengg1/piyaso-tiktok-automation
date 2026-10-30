# Piyaso: Videodaki eski yazıları gerçek yapay zekâyla kaldırma (v19)

**Durum (31 Ekim 2026):** Video Subtitle Remover (VSR) `sttn-auto` modeli için projeye maskeyi önceden gösterme, manuel AI inference, orijinal sesle birleştirme, private Cloudflare R2 test çıkışı ve 101 yerel otomasyon testi eklendi. Fakat bu ortamda VSR modeli indirilemedi/çalıştırılamadı. Gerçek AI ile temizlenmiş bir MP4 **henüz üretilmedi**. Yeşil kutu gösterimi yalnız maskenin önizlemesidir, sahte AI temizliği değildir.

## Neyi siliyor?

TikTok tarzı sabit (görüntüye gömülü) eski metni ve yazı gölgesini, videonun **nihai 9:16 kırpımı** üzerinde verdiğin koordinatlarda. STTN video inpainting sahneyi çevre karelerden yeniden doldurmayı dener; hareketli sahnede yüz/kol/bina gibi yerlerde yanlış onarım olabilir, mutlaka videoyu izle. Yazının konumu hareket ediyorsa tek sabit kutu yeterli değildir; her sahne için ayrı maske veya zaman tabanlı işleme gerekir.

## Gerçek örnek: ön izleme

Örnek kaynakta 512x908 orijinal kırpım üzerinde eski yazı kutusunu işaretledik: `0.305,0.601,0.415,0.083`. Başkaca videolarda bölgeyi yeniden belirlemek gerekir.

```bash
python preview_text_removal.py \
  --video '/path/to/kendi-videon.mp4' \
  --region '0.305,0.601,0.415,0.083' \
  --output ./output/vsr-review \
  --seconds 3
```

İşlem *yalnızca* `01_original_frame.png`, `02_mask_review.png` ve `review.json` üretir. `--run` eklemeden yapay zekâ çalıştırılmaz.

## VSR gerçek modelini kur

Resmî upstream: https://github.com/YaoFANGUK/video-subtitle-remover (Apache-2.0 kaynak kodu; model ağırlıklarının koşullarını ayrıca incele). CPU kurulumu Linux + yeterli bellek ve zaman gerektirir; GPU daha uygundur.

```bash
bash scripts/setup_vsr_cpu.sh
export VSR_HOME="$PWD/vendor/video-subtitle-remover"
export VSR_PYTHON="$PWD/.vsr-venv/bin/python"
python -c "import ai_text_removal as v; print('model:',v.ensure_vsr_weights())"

# AI modelini gerçekten çalıştır, videonun ilk 3 saniyesi
python preview_text_removal.py \
  --video '/path/to/kendi-videon.mp4' \
  --region '0.305,0.601,0.415,0.083' \
  --output ./output/vsr-review \
  --seconds 3 --run
```

Model çıkışı `04_ai_cleaned_with_original_audio.mp4` olarak oluşur. Her durumda yayın kapalı kalır; çıkış sadece inceleme içindir. **İndirilemeyen veya yanlış checkpoint varsa işlem durur**, FFmpeg delogo ile taklit etmez. Upstream `STTN_AUTO_MODEL_PATH` konumu: `backend/models/sttn-auto/infer_model.pth` (eski sürümde yol hatalıydı, v19'da düzeltildi).

## iPad/telefon üzerinden GitHub Actions ile manuel deneme

ÖN KOŞUL: v19 ZIP **açılarak dosyaları** `bengbengg1/piyaso-tiktok-automation` deposuna yüklenmiş olmalı. Yalnız ZIP dosyası yüklemek yetmez. GitHub Secrets'a R2 anahtarları tanımlı olmalı (bunları kodlara yazma). R2 `piyaso-tiktok-assets` içinde kendine ait/ticari kullanıma izinli bir video `backgrounds/klip.mp4` gibi bulunmalı.

1. GitHub deposu → **Actions** → **Piyaso AI text removal - private R2 preview (manual)** → **Run workflow**.
2. `source_key`: `backgrounds/klip.mp4` (R2'de dosyanın gerçek adı MOV ise `.mov` yaz).
3. `region`: örnek `0.305,0.601,0.415,0.083`. **Önce** `run_ai` kutusunu kapalı bırakarak maskeyi doğrula.
4. Akış biterse Cloudflare → R2 → `piyaso-tiktok-assets` → `reviews/vsr/<YYYYMMDD>/<run-id>/mask.png` aç. Yeşil kutu tüm eski yazıyı kapsıyorsa ikinci kez `run_ai` **açık** çalıştır.
5. Gerçek inference başarılı olursa aynı özel klasörde `cleaned.mp4` bulunur. Bu dosya **herkese açık değildir** ve Worker tarafından servis edilmez. İndirip önce/sonra görüntü ve sesi kontrol et.

**Not:** GitHub-hosted ücretsiz CPU'da model kurulumu uzun sürebilir, disk/bellek sınırına takılabilir. Bu durumda GPU çalışma ortamına geçmek gerekir; bu bir doğrulanmış canlı özellik değil, hazırlanan gerçek-model entegrasyonudur.

## Güvenlik ve kalite kapısı

- `config.json → text_removal.require_human_review = true` varsayılanı yeni AI çıktıları yayın için engeller. Gerçek deneme görsel kontrolü ve hak onayı olmadan otomatik yayın açılmasın.
- R2 özel giriş `backgrounds/`, değerlendirme `reviews/vsr/`, kamuya açık final `published/` ayrı tutulur.
- Davethemen medyasına erişilmez; otomasyon hesabının anahtarları sadece `piyaso-tiktok-assets` bucket'ına kısıtlı olmalı.
- Kendi çekimin veya reklam amacıyla açıkça lisans aldığın videoları kullan; üçüncü taraf klipte eski yazıyı silmek kullanım izni oluşturmaz.

## Kontrol sonuçları

- Yerel `python -m unittest discover -s tests -q`: **101 / 101 başarılı**.
- `node worker/test.mjs`: başarılı.
- Gerçek klip üzerinde maske önizlemesi: başarılı.
- Gerçek VSR model çıkarımı: **bu ortamda indirilemediği için başarısız / tamamlanmadı**; mevcut model kurulumu gereklidir.
- GitHub'a yükleme, R2'den gerçek model denemesi, günlük yayına alma: henüz gerçekleşmedi.
