**HISTORICAL NOTE:** This is from an earlier feature release. For live storage/credentials use `R2_SETUP.md` and `LIVE_DEPLOYMENT.md`; no Supabase integration is present in v12.

> **v4 güncellemesi:** Aşağıdaki 4-kare açıklaması artık geçerli değil. Sabit yazılı videolarda artık tek ekran görüntüsü (varsayılan 2. saniye) kullanılır; ayrıntılar README.md sonunda.

# Piyaso v3 — otomatik yazı bulma + yaratıcı reklam kütüphanesi

## Önceki sürümden farkı

v2 her kaynak video için `clip_settings.json` içine eski yazının koordinatını elle istiyordu. v3 yeni/gerçek videolarda `text_detection.mode=auto` ile **EasyOCR** kullanarak önceden gömülü metinlerin **konumlarını tahmin eder**. Yazıları silmez, sadece üzerinde yüzde 100 opak bir alan çizer. Bu alanın üstüne bizim yeni Piyaso başlığımızı yerleştirir.

### Algoritmanın adımları
1. FFmpeg videodan yalnızca 4 farklı anı (örnek kareyi) 9:16 ekrana kırpılmış biçimde çıkarır.
2. EasyOCR Türkçe/İngilizce metinler için köşe noktalarını, güven puanını ve bulunan yazıyı üretir.
3. `auto_text.py` küçük/şüpheli yazıları ayıklar, **birden fazla karede benzer yükseklikte bulunan yazıları** yatay şerit olarak birleştirir. Değişen kelimelerde bile yazının tipik bölgesini bulmaya çalışır.
4. Yatay şeridi **tam genişlikte** opak kutuyla kapatıp Piyaso reklam cümlesini o kutunun üzerine yazar. Tek ve tutarlı şerit algılanmadıysa `review_required=true` yazar ve dışarıya otomatik yayın ENGELLENİR.
5. `output/<tarih>/<slot>/ocr_report.json` içine koordinatlar ve güven/kontrol durumu kaydedilir.

> OCR %100 güvenilir değildir. Örneklenen kareler arasındaki animasyon/yazı geçişleri gözden kaçabilir. Görsel önizleme ile ilk gerçek içeriklerde doğrulama gerekir. `auto` için CPU üzerinde yoğun OCR kullanılabilir, GitHub Actions ücretsiz dakika kotasını ölçmek gerekir. `easyocr` kurulumunda PyTorch bağımlılıkları vardır. Her videoda OCR için yalnızca 4 kare seçilir (tüm kareler işlenmez).

### Elle düzeltme seçeneği
Zor bir videoda `clip_settings.json` içine
```
"araba_123.mp4": {
  "text_mode": "manual",
  "headline_box": {"x": 0.05, "y": 0.15, "width": 0.9, "height": 0.16},
  "cover_rectangles": []
}
```
ekleyebilirsiniz. Bu, OCR yerine kesin verilen koordinatların kullanılmasını sağlar.

### Çalıştırma
```
python -m pip install -r requirements-ocr.txt
python -m unittest discover -s tests -v
python render.py --date 2026-11-02
```
İlk OCR modeli gerektiğinde indirilebilir. Demo klipleri manuel maske ile işlenir; gerçek yeni kliplerde OCR devreye girer. Otomatik OCR **gerçek video ile henüz denenmedi**; testler koordinat mantığı ve render motorunu doğrular.

## Reklam cümlesi kütüphanesi ve örneklerden yaratıcı üretim

- **`style_examples.json`** içine kullanıcının gönderdiği cümleler kategori olarak kaydedilecek. Örneklerin tonundan, hitap biçiminden ve mizahından ilham alınacak; birebir tekrar edilmeyecek.
- **`ad_copy.json`** yayın için onaylanmış başlıkları, açıklamaları ve rotasyonu tutar. Kullanıcı örnekleri geldikçe tarafımızdan özgün cümleler eklenir. Bu yöntem **ücretsiz ve GitHub Actions'ta ek dil modeli çalıştırmadan** her gün 2–3 video hazırlamaya yeter.
- **`creative_copy.py`** güncel kullanımda iki şekilde çalışır: `--mode prompt` bir dil modeli için örnek odaklı bir yönerge üretir. `--mode ollama` kendi makinenizde Ollama servisiniz varsa yerel modelden **özgün taslaklar** ister. Bu taslaklar `creative_drafts.json` dosyasına yazılır ama **otomatik yayın kütüphanesine eklenmez**; doğruluk/telif/üslup için gözden geçirilir.
- Ollama kendi makinenizde ücretsiz kurulabilir, ancak model çalıştıracak CPU/RAM kaynağı ve açık çalışan servis gerekir. GitHub'ın standart ücretsiz Actions koşucusu sürekli bir Ollama sunucusu değildir. Bu sürümde üretken yapay zekâyla **her gün yeni metin üretilmesi otomatik devreye alınmadı**.

Örnek:
```
python creative_copy.py --category araba --count 8 --mode prompt
# Yerel Ollama hazırsa ve bir model yüklenmişse:
OLLAMA_MODEL="yuklu_model_adiniz" python creative_copy.py --category araba --count 8 --mode ollama
```

GitHub kaynakları:
- https://github.com/JaidedAI/EasyOCR (Apache-2.0)
- https://github.com/ollama/ollama (MIT)
- https://github.com/FFmpeg/FFmpeg
- https://github.com/python-pillow/Pillow

## Yayın güvenliği

`PUBLISH_ENABLED` yine `false`. OCR'un güvenle belirleyemediği videolara otomatik yayın yapılmaz; `review_required` işareti yayıncının çağrısından önce kontrol edilir. Gerçek TikTok/Buffer/Cloudflare R2 (see R2_SETUP.md) bağlanmadı.
