#!/usr/bin/env bash
# Explicit install helper. No model downloads are performed until the operator
# follows VSR's own instructions in an isolated environment.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$ROOT/vendor/video-subtitle-remover}"
# Reviewed upstream main branch head on 2026-10-30.
COMMIT="e109b9ddc1d0e8f153199dfa05c1d767546906d8"
if [[ -e "$DEST" ]]; then echo "Directory exists: $DEST" >&2; exit 1; fi
git clone --filter=blob:none https://github.com/YaoFANGUK/video-subtitle-remover.git "$DEST"
git -C "$DEST" checkout --detach "$COMMIT"
ACTUAL="$(git -C "$DEST" rev-parse HEAD)"
[[ "$ACTUAL" == "$COMMIT" ]] || { echo "Unexpected VSR commit!" >&2; exit 2; }
WEIGHTS="$DEST/backend/models/sttn-auto/infer_model.pth"
[[ -s "$WEIGHTS" ]] || { echo "Missing STTN checkpoint: $WEIGHTS" >&2; exit 2; }
# Official tracked model must be the authentic binary, not a Git LFS pointer or placeholder.
EXPECTED_MODEL_BLOB_SHA="4d06d0c45383554c002040f7e73e69cc21d99620"
ACTUAL_MODEL_BLOB_SHA="$(git hash-object "$WEIGHTS")"
[[ "$ACTUAL_MODEL_BLOB_SHA" == "$EXPECTED_MODEL_BLOB_SHA" ]] || {
    echo "VSR STTN model checksum mismatch; refuse to run unverified weights" >&2; exit 2;
}
[[ "$(wc -c < "$WEIGHTS")" -ge 65000000 ]] || {
    echo "VSR STTN pretrained model is an incomplete or pointer file" >&2; exit 2;
}
cat <<MSG
VSR pinned source installed at: $DEST
Commit: $COMMIT
This is a verified source checkout with authentic STTN model weights; Python dependencies still need installation.
Follow upstream setup: https://github.com/YaoFANGUK/video-subtitle-remover/blob/$COMMIT/README_en.md
Set VSR_HOME=$DEST and VSR_PYTHON to its isolated Python interpreter.
Test removal on a licensed MP4 before enabling publishing.
MSG
