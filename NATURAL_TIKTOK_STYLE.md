# Piyaso — doğal TikTok video biçimi (v8)

## Kullanıcının onayladığı görsel dil
- Video üzerindeki metin büyük, kalın, BEYAZ, siyah ince/orta konturlu; örneklerde olduğu gibi. Kart, siyah/pembe/mor reklam paneli, başlık çipi veya CTA bandı YOK.
- "ANTALYA / PİYASO", "Piyaso uygulaması", "PİYASO • ANTALYA" etiketleri YOK.
- Piyaso ekran kaydı küçük bir picture-in-picture olarak görünür; yalnızca ince nötr kenarlık kullanılır.
- Uygulama esprinin doğal bir parçasıdır, aşırı satış dili kullanılmaz.
- Yazılar video boyunca sabit olabilir; 18 saniye varsayılan, 15–22 saniye içerik için tercih edilen aralıktır.

## Kodda neler değişti?
- `config.json`: `text_style=tiktok_native`, üstte metin ve küçük sağ telefon yerleşimi.
- `render.py`: yeni `make_overlay` kolu metni doğrudan görüntünün üstüne yazar. Eski footer, renkli pano ve üst etiketler eklenmez.
- `auto_text.py`: tek SS üzerinden sadece genel yerleşim değil, orijinal yazının sınırlarını da döndürür (`source_text_region`).
- `render.py`: video boyunca sabit kalan eski yazı bölgesine FFmpeg `delogo` uygular. Birden fazla/uygunsuz tespitte `review_required` otomatik yayını engeller.

## Gerçek edit doğrulaması
Kullanıcının 23 saniyelik araba/karaoke videosundan 4.–22. saniye kesilerek 18 saniyelik örnek video, Piyaso ekran kaydı ve üstte doğal yazı ile oluşturuldu. Örnekte, kaynak videodaki küçük beyaz alt yazının üzerine gösterişli kart koymak yerine OpenCV'nin klasik piksel interpolasyonu kullanıldı; bu yapay zekâ modeli DEĞİLDİR. Statik bölge tek kare üzerinden belirlendi. Ekran kaydı ve video birleştirme FFmpeg ile yapıldı.

## Sınırlar
- FFmpeg `delogo` statik altyazı alanının çevresini yaklaşık doldurur; her video üzerinde kusursuz sonuç garantisi yoktur. Örnek videoda daha hedefli, beyaz pikselleri maskeleyen OpenCV yöntemi kullanıldı. Üretim pipeline'ındaki standart yaklaşım ile bu özel örnek arasındaki kalite farkını gidermek için ek doğrulama gerekir.
- Yapay zekâ API'si / Buffer hesap anahtarları bağlanmadıysa üretim ve yayın kendiliğinden çalışmaz. Otomatik paylaşım varsayılan olarak kapalıdır.
- Kullanıcı klip ve ekran kaydı medyası bu ZIP içinde yoktur.
