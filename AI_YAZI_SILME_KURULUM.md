# VSR Yapay Zekâ ile Yazı Silme — Kurulum

- Resmi GitHub projesi: https://github.com/YaoFANGUK/video-subtitle-remover
- Kullanılan metot: STTN (`sttn-auto`); `lama`, `sttn-det`, `propainter` seçenekleri config üzerinden desteklenir.
- AI model ZIP içinde yoktur. Modeller ve ağır bağımlılıklar ayrı kurulmalıdır.

## 1. Kurulum

```sh
bash scripts/get_vsr.sh
# Ardından README_en.md'de sisteminize uygun GPU/CPU kurulumunu uygulayın.
export VSR_HOME="$PWD/vendor/video-subtitle-remover"
export VSR_PYTHON="/absolute/path/to/vsr-venv/bin/python"
```

## 2. Test

```sh
python -m unittest discover -s tests -q
python render.py --date 2026-11-02 --width 360 --height 640
```

`render.py` yukarıdan aşağı bu akışı yürütür:

1. 18 saniyelik klip ayırır.
2. Tek screenshot OCR üzerinden sabit yazı bbox'ını bulur.
3. Önce TikTok en-boy oranına göre kaydı kırpar; böylece yazı koordinatı şaşmaz.
4. `backend/main.py -c YMIN YMAX XMIN XMAX --inpaint-mode sttn-auto` çalıştırır.
5. Ekran görüntüsü, reklam metni ve orijinal kaynak sesiyle birleştirir.
6. `manifest.json` içinde uygulanan yöntemi kaydeder.

Yazı algılanmadığında veya VSR kurulmamışsa sistem doğrulanmamış işlerin otomatik yayınına izin vermez. AI işleme hatasını `delogo` olarak gizlice geçiştirmez.

## 3. GitHub Actions

- Videoları işlemek için tercihen güçlü GPU'lu self-hosted runner kullanın.
- Actions Variables: `VIDEO_RUNNER` (örn. `self-hosted`), `VSR_HOME` (yerel kurulum yolu), `VSR_PYTHON` (VSR ortamı Python yolu).
- Model ağırlıkları, kaynak videolar ve sırlar özel altyapıda tutulmalı.
- `PUBLISH_ENABLED=false` iken sadece video oluşturulur.
- Gerçek Buffer paylaşımı, OAuth/API ve video barındırma kurulup kontrol edilmeden etkinleştirilmemeli.

## 4. Kaynaklar ve lisanslar

VSR Apache-2.0 lisansı: https://github.com/YaoFANGUK/video-subtitle-remover/blob/main/LICENSE
VSR kurulum: https://github.com/YaoFANGUK/video-subtitle-remover/blob/main/README_en.md
Yapay zekâ ağırlıklarının lisanslarını ve ticari kullanım koşullarını ayrıca doğrulayın.
