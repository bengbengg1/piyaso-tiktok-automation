# Piyaso — GitHub'daki hazır VSR ile gerçek yazı silme (v20)

## Durum

- **Tamam:** Video Subtitle Remover (VSR) `sttn-auto` hazır modelinin resmi depoya sabitlenmesi; commit ve 66 MB model dosyası Git blob SHA kontrolü; API adaptörü; MP4/MOV ve `.mp4.mov` desteği; orijinal sesin korunması; AI çıktısının görüntü üzerinde gerçekten değişiklik oluşturduğunu sınayan test; önce/sonra görseli; sadece özel R2 `reviews/vsr/` alanına kaydetme; otomatik yayın engeli.
- **Doğrulandı:** 105 yerel Python testi ve Worker testleri. FFmpeg video karelerini okuma, sesli video koruma ve yapay-zeka-modelinin **hiç değişiklik yapmadığı** durumları yakalama testleri geçti.
- **Doğrulanmadı:** Bu ortamda orijinal VSR/STTN modelini indirme/çalıştırma. Buradaki ağ GitHub alan adını çözmüyor; gerçek AI tarafından temizlenmiş video **üretilmedi**. Model çalıştırma işlemi GitHub Actions üzerinde uygulanmak üzere hazır.

## Kullanılan hazır GitHub modeli

YaoFANGUK/video-subtitle-remover, Apache-2.0 lisanslı kaynak kodu. Piyaso kendi sıfırdan eğitilmiş modelini kullanmaz. Pinned upstream commit: `e109b9ddc1d0e8f153199dfa05c1d767546906d8`.

STTN model ağırlığı: `backend/models/sttn-auto/infer_model.pth`, doğrulanan Git blob SHA `4d06d0c45383554c002040f7e73e69cc21d99620` (model ağırlıklarına ait ek lisans koşulları kontrol edilmelidir). Kurulum `scripts/setup_vsr_cpu.sh` ile yapılır; model kodu ve ağırlık GitHub Action koşan makineye indirilir, Piyaso ZIP dosyasına eklenmez.

## GitHub Actions / iPad üzerinden izlenecek tek seferlik sıra

1. v20 paketindeki **gerçek dosyaları**, `.github/workflows` dizinini de koruyarak `bengbengg1/piyaso-tiktok-automation` deposuna yükle. GitHub'da yalnız README bulunuyorsa Workflow'lar henüz yoktur. ZIP dosyasını depoya olduğu gibi koymak Workflow'ları çalıştırmaz.
2. GitHub → **Actions** → **Piyaso VSR real AI smoke test (manual / CPU)** → **Run workflow**. Bu iş akışı özel hesaptan dosya çekmez: sentetik 3 sn test videosunu oluşturur; gerçek kaynak ve modeli indirir, inference'ı çalıştırır, çıkan MP4 dosyasını **Actions → Artifacts → vsr-synthetic-smoke** altında verir. İlk deneme uzun sürebilir; CPU runner'ın yetersiz kalması da mümkündür.
3. Aynı Actions sayfasında **Piyaso AI text removal - private R2 preview (manual)** → **Run workflow**. `source_key` olarak `backgrounds/KENDI_VIDEO.mov` gir. Daha önce yüklenmiş bir test videosunu yeniden yüklemeden denemek için `published/piyaso/2026-10-30/01_0001/video.mp4.mov` de desteklenir, ancak o videoda gerçekten yazı varsa ve kullanım izni sana aitse kullan.
4. `region` = eski yazının bulunduğu alan (normalize `x,y,width,height`), örneğin daha önceki karaoke klibinde `0.305,0.601,0.415,0.083`. **Bunlar tüm videolara uygulanamaz.** Önce `run_ai=false` çalıştır. Sonuç `piyaso-tiktok-assets/reviews/vsr/YYYYMMDD/<workflow-run-id>/mask.png` içinde görünecektir.
5. Maske doğruysa `run_ai=true` çalıştır. Model başarılıysa aynı **özel** `reviews/vsr/` alanında `cleaned.mp4` ve `before_after.png` bulunur. Önce/sonra görüntüsü tek kareyi karşılaştırır; hareketli videoyu tamamıyla izlemek ve yüz, el, saç, yazı kenarı gibi görsel hataları kontrol etmek şarttır.
6. Test dosyaları otomatik olarak **Buffer'a veya TikTok'a gönderilmez**. İleride yayın açılması, bir insanın kalite onayı ve hak kontrolünden sonra ayrı bir karardır.

## Güvenlik

- **Asla** `BUFFER_API_KEY`, `R2_SECRET_ACCESS_KEY`, `GROQ_API_KEY` değerlerini koda/ZIP'e koyma; yalnız GitHub Secrets'ta bulunur.
- R2 bucket adı **yalnız** `piyaso-tiktok-assets`; `davethemen-media`'ya erişilmez.
- Temizlenmiş dosyalar `reviews/vsr/` özel alanına gider; Worker'ın public endpoint'i bunu servis etmez.
- Yazıyı kaldırmak klibin telif hakkını veya reklam amaçlı kullanım yetkisini değiştirmez.

## Otomatik üretimdeki sınır

`render.py` mevcut OCR ile sabit yazının alanını bulmayı dener. Yazı kayarsa, sahneler değişirse veya yüz üzerinden geçerse otomatik tespit kesin değildir. Bu durum yayın için **insan kontrolü gerektirir**. Yazıyı silen modelin işlevsel oluşu, her klibin kusursuzca temizlendiği anlamına gelmez.

## Yerel doğrulama komutları

```bash
python -m unittest discover -s tests -q
node worker/test.mjs
# İnternet ve yeterli CPU/GPU olan Linux ortamında:
bash scripts/setup_vsr_cpu.sh
export VSR_HOME="$PWD/vendor/video-subtitle-remover"
export VSR_PYTHON="$PWD/.vsr-venv/bin/python"
python preview_text_removal.py --video '/path/to/your-licensed-video.mp4' --region '0.305,0.601,0.415,0.083' --output output/local-ai-test --seconds 3 --run
```
