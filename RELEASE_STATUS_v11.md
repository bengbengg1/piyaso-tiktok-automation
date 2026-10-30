# Piyaso TikTok Studio — v11 technical state (2026-10-30)

## Implemented and tested locally
- Fixed daily 2/3-video schedule (Mon–Thu: 2; Fri–Sun: 3) and Istanbul time conversion.
- Clip trim at a configurable 18 s, plus optional automatic motion/sharpness-based start candidate via `scene_select.py` (not semantic scene understanding).
- Sparse single-frame OCR adapter for static source text.
- Original GitHub VSR AI inpainting integration with explicit error if models not present. No fake substitution on publish.
- Native-looking TikTok typography, app picture-in-picture, original source audio.
- Piyaso ad-language examples + Groq GPT-OSS/optional Ollama API + quality and repetition checks.
- Buffer official GraphQL post scheduling, TikTok channel verification, no auto post unless enabled.
- Private licensed media ingestion from a private Supabase Storage bucket, public final video object upload only, separate PRIVATE immutable submission and confirmation receipts. Failed request after intent does NOT retry automatically.
- Rights and uncertainty gate: no unapproved source clips, no demos, no uncertain OCR, no unverified AI removal in publisher.
- GitHub Actions manual workflow / gated scheduled workflow / CI tests.
- 69 local unittest cases PASS. 3 generated demo renders PASS. Preflight detects missing real credentials and model environment.

## Not live yet: requires outside authorization / hardware
- No Buffer login/TikTok channel connected; no BUFFER_API_KEY or channel ID.
- No GROQ_API_KEY to run real prompt generation.
- No dedicated Supabase media project/buckets/key configured; do NOT use Piyaso production secret key.
- No real licensed source clip catalog and app capture in a private object bucket.
- No VSR model weights and properly configured GPU/self-hosted runner.
- Dedicated private GitHub repository not provisioned and Actions variables/secrets not set. The existing `piyaso-app` repository is public and should not receive private source videos.
- **No videos have been scheduled or published to TikTok.**

Read `LIVE_DEPLOYMENT.md` for safe deployment steps. It is intentionally impossible to turn on posting until `PUBLISH_ENABLED=true` and all checks pass.
