"""Piyaso adapter for YaoFANGUK/video-subtitle-remover (VSR).

VSR remains an external Apache-2.0 project, installed separately on a runner
with sufficient CPU/GPU resources. This adapter does not fake AI inpainting or
fall back silently to FFmpeg delogo if VSR is unavailable.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SUPPORTED_MODES = frozenset({"sttn-auto", "sttn-det", "lama", "propainter"})


def padded_region(region: dict, padding: float = .012) -> dict:
    """Expand a normalized OCR bbox slightly to include text outlines."""
    from render import px_rect  # Local import avoids circular import at startup

    if not (0 <= padding <= .05):
        raise ValueError("AI mask padding must be between 0 and 0.05")
    px_rect(region, 10000, 10000)  # validate region without quantizing result
    x, y = float(region["x"]), float(region["y"])
    xx, yy = x + float(region["width"]), y + float(region["height"])
    x, y = max(0., x - padding), max(0., y - padding)
    xx, yy = min(1., xx + padding), min(1., yy + padding)
    return {"x": x, "y": y, "width": xx - x, "height": yy - y}


def vsr_coords(region: dict, width: int, height: int, padding: float = .012) -> list[str]:
    """VSR CLI coordinates order: YMIN YMAX XMIN XMAX (pixels)."""
    from render import px_rect

    x1, y1, x2, y2 = px_rect(padded_region(region, padding), width, height)
    if x2 - x1 < 8 or y2 - y1 < 8:
        raise ValueError("Text detection too small to remove safely")
    return [str(y1), str(y2), str(x1), str(x2)]


def find_vsr(vsr_home: str | Path | None = None, vsr_python: str | None = None) -> tuple[Path, str]:
    """Locate the user's local checkout without downloading code at render time."""
    home = Path(vsr_home or os.environ.get("VSR_HOME", "")).expanduser() if (vsr_home or os.environ.get("VSR_HOME")) else None
    if home is None:
        raise RuntimeError("AI subtitle remover is not installed. Set VSR_HOME to the video-subtitle-remover repository directory. Render stopped; no delogo fallback.")
    backend = home.resolve() / "backend" / "main.py"
    if not backend.is_file():
        raise FileNotFoundError(f"VSR backend/main.py not found: {backend}")
    python_exe = str(vsr_python or os.environ.get("VSR_PYTHON") or sys.executable)
    if not shutil.which(python_exe) and not Path(python_exe).is_file():
        raise FileNotFoundError(f"VSR Python executable not found: {python_exe}")
    return backend, python_exe


def remove_fixed_text(
    source: Path, output: Path, region: dict,
    *, start_seconds: float, duration_seconds: float,
    width: int, height: int, fps: int,
    mode: str = "sttn-auto", padding: float = .012,
    vsr_home: str | Path | None = None, vsr_python: str | None = None,
    timeout_seconds: int = 2700,
) -> dict:
    """Trim/crop to TikTok canvas, run AI VSR on the detected caption area.

    Sound is deliberately excluded from the intermediate file. The caller
    retrieves audio from the ORIGINAL source at the same start time, so VSR
    cannot accidentally change the user's audio.
    """
    source, output = Path(source), Path(output)
    if not source.is_file():
        raise FileNotFoundError(f"Source video not found: {source}")
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported VSR mode: {mode}")
    if duration_seconds <= 0 or start_seconds < 0 or width < 64 or height < 64 or fps <= 0:
        raise ValueError("Invalid video dimensions/duration for subtitle removal")
    # Validate the model BEFORE starting FFmpeg or writing any video.
    backend, py = find_vsr(vsr_home, vsr_python)
    ensure_vsr_weights(vsr_home, mode)
    coords = vsr_coords(region, width, height, padding)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Independent temporary workspace: concurrent videos cannot overwrite each other.
    tempdir = tempfile.TemporaryDirectory(prefix="piyaso-vsr-")
    trimmed = Path(tempdir.name) / "vsr_input_no_audio.mp4"
    command1 = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start_seconds),
                "-i", str(source), "-t", str(duration_seconds),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps}",
                "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "19", "-pix_fmt", "yuv420p", str(trimmed)]
    try:
        subprocess.run(command1, check=True, timeout=timeout_seconds)
        command2 = [py, str(backend), "-i", str(trimmed), "-o", str(output),
                    "-c", *coords, "--inpaint-mode", mode]
        subprocess.run(command2, cwd=str(backend.parent.parent), check=True, timeout=timeout_seconds)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("VSR returned without producing a readable output video. No upload attempted.")
        # ffprobe confirms this is a real decoded video stream, not only a file.
        result=subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                               "stream=width,height", "-of", "csv=p=0:s=x", str(output)],
                              capture_output=True, text=True, check=True, timeout=60)
        if result.stdout.strip() != f"{width}x{height}":
            raise RuntimeError(f"VSR unexpected output resolution: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError):
        output.unlink(missing_ok=True)
        raise
    finally:
        tempdir.cleanup()
    return {"backend": "vsr", "mode": mode, "pixel_coords_ymin_ymax_xmin_xmax": list(map(int, coords)),
            "output": str(output), "input_dimensions": [width, height], "audio_source": "original_video"}


def ensure_vsr_weights(vsr_home=None, mode='sttn-auto'):
    """Fail before processing if the selected VSR checkpoint is unavailable.

    A checked-out repository is NOT the same as a runnable AI model. The
    checkpoint is checked separately to avoid a false readiness signal.
    """
    backend, _ = find_vsr(vsr_home)
    paths = {
        # Official VSR stores its weights under backend/models/, not the repo root.
        'sttn-auto': backend.parent / 'models/sttn-auto/infer_model.pth',
        'sttn-det': backend.parent / 'models/sttn-det/sttn.pth',
        # VSR assembles split LaMa / ProPainter files at runtime.
        'lama': backend.parent / 'models/big-lama/bit-lama.pt',
        'propainter': backend.parent / 'models/propainter/ProPainter.pth',
    }
    if mode not in paths:
        raise ValueError('Unsupported VSR mode')
    checkpoint = paths[mode]
    if not checkpoint.is_file() or checkpoint.stat().st_size < 100_000:
        if mode in {'lama', 'propainter'}:
            raise RuntimeError('VSR checkpoint not assembled yet: ' + str(checkpoint) + '. Follow upstream split-model instructions.')
        raise RuntimeError('VSR pretrained model checkpoint missing or incomplete: ' + str(checkpoint))
    return checkpoint
