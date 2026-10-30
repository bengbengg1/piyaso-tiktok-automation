# Kullanılan açık kaynak projeler

| Proje | GitHub | Bu sistemdeki görevi | Lisans notu |
|---|---|---|---|
| FFmpeg | https://github.com/FFmpeg/FFmpeg | MP4 okuma, kırpma, resim içinde video, ses ve H.264 dışa aktarma | FFmpeg yapılandırmasına göre LGPL/GPL; FFmpeg bu ZIP'e eklenmedi, sistem paketi kuruluyor. |
| Pillow | https://github.com/python-pillow/Pillow | Eski metni opak kaplayan ve yeni metni üzerine yazan PNG katmanı | MIT-CMU. `requirements.txt` ile kurulur. |
| GitHub Actions | https://github.com/features/actions | Her sabah çalıştırma, test, ZIP/video çıktısını Actions artifact olarak saklama | GitHub hizmeti; açık kaynak kod kütüphanesi değil. |

Bu araçların bütün GitHub depolarını projeye kopyalamıyoruz. Paket yöneticilerinden kurulan bu bağımlılıkları **gerçekten kullanan** küçük bir entegrasyon geliştiriyoruz. Bu sayede gereksiz, ağır ve güncellenmesi zor kodu kopyalamıyoruz.

MoviePy ve Remotion gerekmiyor. v9 ile VSR yapay zekâlı yazı silme eklendi. Önceki opak kaplama ve klasik delogo işlevleri artık varsayılan değil. FFmpeg komutu tek başına ses ve video compositing yapıyor; Pillow ile metin kaplama sağlanıyor. Yalnızca ekran kaydı PIP ve opak yazı için yapay zekâ servisi veya ücretli API gerekmiyor.

## v3 dependencies
- EasyOCR, https://github.com/JaidedAI/EasyOCR (Apache-2.0). Used as an installed Python package for text bounding-box detection in a single representative screenshot, no vendored code. PyTorch/torchvision model and dependency licenses should be checked for distribution.
- Ollama, https://github.com/ollama/ollama (MIT). Optional, not required for the daily pipeline. Language models accessed via Ollama have separate licenses; verify each model license before promotional use.


## v9: AI video subtitle removal (external dependency)
- Project: https://github.com/YaoFANGUK/video-subtitle-remover (Apache-2.0).
- Integrates the project's documented `backend/main.py -i ... -o ... -c YMIN YMAX XMIN XMAX --inpaint-mode sttn-auto` command.
- Source and model weights are NOT bundled. The project is cloned separately to `vendor/video-subtitle-remover/` by `scripts/get_vsr.sh` and installed under its own Python environment.
- AI models (STTN/LAMA/ProPainter) and dependencies have their own license/resource requirements. Review upstream for any commercial use and redistributed model licenses.
- This project's adapter is `ai_text_removal.py`. An unavailable backend aborts the job without replacing the text via FFmpeg `delogo` and without submitting to Buffer.
