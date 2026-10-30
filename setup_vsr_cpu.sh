#!/usr/bin/env bash
# Experimental CPU-only VSR installation. Slow/large: first run may download model weights.
# GitHub-hosted runners do NOT include a GPU; success is NOT guaranteed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$ROOT/scripts/get_vsr.sh" "$ROOT/vendor/video-subtitle-remover"
python -m venv "$ROOT/.vsr-venv"
"$ROOT/.vsr-venv/bin/python" -m pip install --upgrade pip
"$ROOT/.vsr-venv/bin/python" -m pip install torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cpu
"$ROOT/.vsr-venv/bin/python" -m pip install paddlepaddle==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
"$ROOT/.vsr-venv/bin/python" -m pip install -r "$ROOT/vendor/video-subtitle-remover/requirements.txt"
"$ROOT/.vsr-venv/bin/python" -c 'import torch,paddle,cv2; print("VSR dependencies import successfully; pretrained weights not yet validated")'
echo "VSR_HOME=$ROOT/vendor/video-subtitle-remover" >> "${GITHUB_ENV:-/dev/null}"
echo "VSR_PYTHON=$ROOT/.vsr-venv/bin/python" >> "${GITHUB_ENV:-/dev/null}"
# The model checkpoint and git commit were cryptographically checked during clone.
# This does NOT prove the model runs: the next step must actually run inference.
echo 'Pinned VSR source, authentic STTN weights and Python dependencies installed. Run the actual smoke inference now.' 
