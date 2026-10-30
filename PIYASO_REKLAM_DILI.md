# Piyaso — Reklam dili ve jargon rehberi (30 Ekim 2026)

Bu rehber, kullanıcının **28 gerçek örnek metninden** türetilmiştir. Örneklerin tamamı `style_examples.json > user_supplied_examples` içinde, kullanıcının yazımı korunarak kayıtlıdır. `style_examples.json` örnekleri dil/model referansıdır; doğrudan otomatik paylaşılacak reklamlar değildir.

## Ton
- **Sokak ağzı / konuşma dili:** TikTok'un samimi arkadaş sohbeti, bir miktar abartma, argo olmayan şaşkınlık, gülerek dedikodu.
- **Piyaso yapmak bir eylem:** Araba ile tur atmak, müzik açmak, cadde-sahil gezmek, arkadaşlarla karşılaşmak, gece çıkmaları.
- **İronik 'son dakika' haberleri:** Tamamen sıradan bir piyaso turunu büyük olay gibi anlatmak.
- **İlişki/arkadaşlık mizahı:** Ex, next, ghost, kesişmek, kısmet, bacımla geldim gibi savunmalar.
- **Yerel Antalya dili:** Kültür, Konyaaltı, Lara, Işıklar, Bozkan. Kullanıcının yazımı aynen korundu; marka hedef kitlesi Antalya.
- **Format:** 18 saniyelik videoda 1 çarpıcı ekran yazısı, eşlik eden kısa TikTok açıklaması; marka adı metinde veya açıklamada geçsin. Sıralı kurguda araba/karaoke/şarkı/yerel/ilişki temalarına göre uyumlandır.
- **Özgünlük:** Örnekler 'ezberlemek' içindir, birebir kopyalanmaz; benzer şaka yerine gerçekten yeni gözlemler/girişler üretilir.

## Uygulama gerçekliği ve mahremiyet
Kullanıcının referans örneklerindeki "stalklamak", "exi takip etmek", başkasının nerede/kimle olduğuna bakmak gibi iddialar **yalnızca üslup örneğidir**. Piyaso hakkında doğrulanmamış bir gözetleme özelliği varmış gibi davranma. İnsanların konumuna, özel ilişkilerine veya profillerine rızaları dışında erişim vaadi verme. Piyaso'nun özellikleri doğrulanmadan uygulamanın kullanıcıları tanıştırma veya belirli kişileri buldurma garantisini yazma.

## Dosyalar
- `style_examples.json`: kullanıcıdan gelen bütün kaynak örnekler ve marka sesi profili
- `candidate_ads.json`: hazırlanan 50 **onay bekleyen** özgün reklam metni
- `ad_copy.json`: otomatik iş akışında kullanılmasına izin verilen onaylı reklamlar
- `creative_copy.py`: kategorilere göre daha fazla fikir üretmek için yerel LLM/Ollama prompt'u
- `approve_copies.py`: incelemeden sonra belirli taslakların yayın havuzuna aktarımı

## Güncelleme akışı
1. Kullanıcı yeni örnekler verdiğinde `style_examples.json > user_supplied_examples` içine ekle ve ilgili `examples` kategorisinde etiketle.
2. Benzer tonu koruyarak ayrı yeni özgün adaylar üret; varsayılan `review_status=pending`.
3. Kullanıcı metinleri seçtiğinde `python approve_copies.py --list` ve `python approve_copies.py --approve 1 5 12` komutlarıyla yalnızca onaylananları `ad_copy.json` içine geçir.
4. Önizleme ve telif kontrollerinden sonra ayrı yayın bağlantısını etkinleştir. Bu aşama henüz test edilmedi; `PUBLISH_ENABLED=false`.

## v7 Günlük üretim (kullanıcı geri bildirimi)
Önceki “Bi tur daha dedik Antalya turu çıktı” / “Konyaaltı biz Konyaaltını
 ezberledik” şakaları **kullanıcı tarafından reddedilmiştir**. Referans alınmaz.
Daha sonra kullanıcı bu kategorideki **6 yeni somut Piyaso bağlantılı örneğin
hepsini beğendiğini belirtmiştir**. Bu 6 örnek
`style_examples.json > explicitly_approved_reference_examples` içinde bulunur.
Günlük GPT-OSS üretimi `daily_copy.py` içinden çağrılır. Üretimde istenen şey
rastgele Antalya kelimeleri değil, gerçekten anlaşılır dedikodu/olay + Piyaso
uygulamasıyla anlamlı bağdır. Gizli takip ve gerçek dışı özellik vaatleri
reklama alınmaz.
