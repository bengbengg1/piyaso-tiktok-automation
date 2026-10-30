> **v20 / hazır VSR-STTN entegrasyonu:** [AI_YAZI_SILME_v20.md](AI_YAZI_SILME_v20.md) içinde gerçek model GitHub Actions testi, özel R2 çıktısı ve bilinen sınırlar açıklanmıştır. v20, canlı model inference başarı iddiasında bulunmaz.

> **GÜNCEL / v19:** [AI_YAZI_SILME_v19.md](AI_YAZI_SILME_v19.md) — gerçek VSR için güvenli manuel deneme, özel R2 önizleme ve 101 test. Model henüz canlı çalıştırılmadı.

> **GÜNCEL / v18:** İlk olarak [BASLA_v18.md](BASLA_v18.md) dosyasını okuyun. Kod ve CI testleri hazırdır; canlı yayın henüz açılmadı.

> **v17:** Canlı hazırlık ve kalan servis izinleri için `CANLI_KURULUM_v17.md` dosyasına bakın. Gerçek hesaplara bağlantı hâlâ sağlanmadı.

# Piyaso TikTok Studio — v16

Daily 2–3 short TikTok videos for Piyaso, with automatically selected video snippets, Piyaso-specific ad copy, native-looking on-video typography, a small application screen-recording overlay, and an optional **Buffer** publication stage. Video storage is **Cloudflare R2**; Supabase is not used.

**Current status (2026-10-30): CODE READY FOR CONFIGURATION, NOT LIVE.** Cloudflare R2 `piyaso-tiktok-assets` exists (user-created) but the Worker, real model runner, Buffer/TikTok and Groq APIs have not been verified. No TikTok post has been scheduled. Do not enable publication before the owner approves a live end-to-end test.

## Components

| Component | Implementation |
|---|---|
| Select scenes from licensed footage | OpenCV-based heuristic `scene_select.py` (motion/sharpness, not semantic understanding) |
| Detect original static text | EasyOCR from one representative frame; unconfident cases require review |
| Remove original text | Video Subtitle Remover (VSR) STTN model; needs separately installed weights and a capable runner |
| New Piyaso copy | `daily_copy.py` with Groq API (optional Ollama provider for manual use); based on user's accepted examples |
| Native TikTok overlays and small app-screen picture | FFmpeg + Pillow |
| Daily plan | Monday–Thursday 2 videos, Friday–Sunday 3; default 18-second clips |
| Store raw media and private receipts | One R2 bucket, private isolated prefixes |
| Serve finished video URLs | Read-only Cloudflare Worker bound only to the dedicated Piyaso bucket, exposing published/ paths |
| Queue TikTok video posts | Buffer GraphQL via `publish.py`, explicitly opt-in |
| Repeat every day | GitHub Actions 09:00 Türkiye time, gated by `LIVE_READY` and `PUBLISH_ENABLED`; GitHub-hosted runner only in a public repo |

## Start here

1. **`R2_SETUP.md`** — existing Cloudflare account, one bucket, credentials, and read-only Worker.
2. **`LIVE_DEPLOYMENT.md`** — remaining Buffer, Groq, GPU, GitHub and compliance steps.
3. **`BUFFER_CONNECT.md`** — connect/verify Buffer and TikTok.
4. **`AI_YAZI_SILME_KURULUM.md`** — get the original VSR model weights and runner.
5. **`NATURAL_TIKTOK_STYLE.md`**, **`PIYASO_REKLAM_DILI.md`** — approved ad styling and copy language.

## Run local tests

```bash
python -m pip install -r requirements-ocr.txt
python -m unittest discover -s tests -q
node --check worker/src/index.js
python preflight.py --live
```

A `--live` preflight failure is expected until real secrets, footage and the VSR environment are installed. Demo clips under `assets/backgrounds/` are synthetic and **cannot be published**. To test local rendering, use `examples/make_demo_assets.py`, then `python render.py --date 2026-11-02 --width 360 --height 640`.

Keep all R2, Groq, and Buffer secrets in GitHub Actions Secrets — not in the repository or chat. Never add private source footage to a public GitHub repository or the public final-video bucket. The existing app/music storage must remain unchanged.

## Current limits

- Cloudflare R2 Standard free tier is account-wide: **10 GB-month, 1M Class A, 10M Class B monthly operations**, with no egress charge; existing music storage counts too. Overages cost money.
- AI inpainting with VSR has **not** been tested against a real installed model on the daily runner.
- Buffer media must remain reachable anonymously until posting time. The Worker is read-only and serves only final approved ad paths; a `workers.dev` endpoint can be used to start without purchasing a domain but has lower production guarantees than a custom domain.
- Video and music must have appropriate commercial use permissions; changing captions does not grant these rights.


## v14: İki medya türü, ana video kategorisi yok

Yeni kurallar için `MEDYA_AYIRMA.md` ve `RELEASE_STATUS_v14.md` dosyalarına bak. Ana videolar sınıflandırılmaz; ekran kayıtları bağımsız eşleştirilir.

## v16 technical fixes

- OCR groups a stable 2–5 line TikTok caption into a single removal region from **one screenshot**. Separate distant text remains flagged for review.
- Removed stale `R2_PUBLIC_BUCKET` and `R2_STATE_BUCKET` references from the publish precheck (all roles use the verified `piyaso-tiktok-assets` bucket).
- Public GitHub repository workflows use `ubuntu-latest`, not a persistent self-hosted runner. A GPU-powered VSR deployment remains a **separate unresolved operational dependency**, not a capability demonstrated by these unit tests. The scheduled job therefore remains disabled until an isolated safe model runner is configured.
- No outside account tokens, Buffer posting, or Cloudflare Worker deployment performed.

Daily R2 sync downloads only today's selected 2–3 authorized main clips; it never downloads the entire video archive.
