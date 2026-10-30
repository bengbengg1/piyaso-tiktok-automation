# v12 R2 integration status — 2026-10-30

Changed from v11:
- Replaced Supabase REST Storage with Cloudflare R2 S3-compatible client (boto3, signed writes/reads, conditional create-only PutObject, streaming private downloads, paginated listings).
- Rewired the publication and asset-sync modules, private submission receipts, and GitHub daily workflow to use R2 credentials.
- Added an optional read-only Cloudflare Worker for final video delivery via workers.dev without a personal domain. Buffer receives a public URL that is checked with unauthenticated HEAD before scheduling.
- Kept assets and publication receipts private, separated from original Piyaso music assets and user data. No live account/bucket was changed.
- Expanded regression tests covering R2 endpoint validation, traversal, atomic writes, public URL access, private-role isolation, and listing.

Remaining gates: R2 user/account authorization and 3 new buckets; Worker deploy; Buffer TikTok authorization; Groq API key; VSR weights and capable GPU runner; licensed source video catalog; private GitHub Actions deployment and actual end-to-end test. PUBLISH_ENABLED is still off, no TikTok posts created.

### v13 addition (local implementation only)
- R2 bucket-name validation to prevent accidental use of existing Davethemen/music buckets.
- Two distinct source object-key prefixes and optional category-specific app screen recordings.
- Dedicated separation tests and setup guide (`MEDYA_AYIRMA.md`).
- Not yet deployed to Cloudflare or a production GitHub Actions workflow.
