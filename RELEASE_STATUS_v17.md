# Piyaso TikTok Otomasyon — v17, 2026-10-30

Üretim koduna servisler için kontrol ve dağıtım hazırlığı eklendi. **94 yerel Python testi ve Worker erişim testleri geçti.** **Gerçek R2/Buffer/Groq hesabına erişilmedi; Worker yayımlanmadı; VSR gerçek model testi çalıştırılmadı; TikTok yayını yapılmadı.**

- Groq strict JSON schema; hâlâ gerekli yerel Piyaso dil ve tekrarlama kalite kontrolü.
- `live_smoke.py`: Groq model, TikTok Buffer kanalı, R2 bucket ve Worker özel dosya erişim kapısı için salt-okunur doğrulama.
- `deploy-worker.yml`: manuel tetiklenen, Worker deploy öncesi test, ayrı Cloudflare Workers token; ham videoları yayımlamaz.
- `vsr-cpu-smoke.yml` ve `setup_vsr_cpu.sh`: gerçek VSR kurulumunu ve bir saniyelik gerçek model temizlemeyi denemek için ayrı yol; CPU/GitHub limiti bilinmiyor.
- VSR kaynak kodu tek başına hazır sayılmaz: gerçek checkpoint dosyası ayrıca aranır, yoksa üretim durur.
- `PUBLISH_ENABLED` güvenli varsayılan olarak kapalı; otomatik yayın ancak kullanıcı yetkilendirince.
