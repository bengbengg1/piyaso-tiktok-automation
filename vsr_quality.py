"""Post-inference evidence checks. Never mistake a rendered preview for AI output.

QA is a mechanical smoke test, not a guarantee of a convincing visual edit.
The user must still inspect every clip before publication.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


def video_probe(path: Path) -> dict:
    cp = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=index,codec_type,width,height,nb_frames",
         "-of", "json", str(path)], capture_output=True, text=True,
        check=True, timeout=45,
    )
    info = json.loads(cp.stdout)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("Video stream missing")
    return {"duration": float(info.get("format", {}).get("duration") or 0),
            "width": int(video["width"]), "height": int(video["height"]),
            "has_audio": any(s.get("codec_type") == "audio" for s in streams)}


def _frame(path: Path, time_s: float) -> np.ndarray:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Video cannot be decoded: {path}")
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, time_s * 1000)
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        if not ok:
            raise ValueError(f"No decodable video frames: {path}")
        return frame
    finally:
        cap.release()


def check_ai_result(source: Path, cleaned: Path, region: dict, output_dir: Path,
                    *, t: float, target_width: int, target_height: int,
                    fps: int, padding: float = .012) -> dict:
    """Compare two independent decoded video frames and create honest before/after proof.

    * Accept only real decodable files at expected resolution & approximate duration.
    * Fail obvious no-op models (a synthetic "VSR" merely copying source).
    * Record a before/after image and review.json; visual quality remains human-gated.
    """
    import ai_text_removal
    output_dir.mkdir(parents=True, exist_ok=True)
    before_info = video_probe(source)
    after_info = video_probe(cleaned)
    if (after_info["width"], after_info["height"]) != (target_width, target_height):
        raise RuntimeError("VSR output resolution is incorrect")
    if after_info["duration"] < max(.15, t - 1.0/fps - .1):
        raise RuntimeError("VSR video was truncated")
    if before_info["has_audio"] and not after_info["has_audio"]:
        raise RuntimeError("The original video's audio track was lost")
    # Read the same point in final uncropped canvas to avoid false difference due to scaling.
    sample_s = min(max(.05, t * .45), min(before_info['duration'], after_info['duration']) * .5)
    v0 = _frame(source, sample_s)
    v1 = _frame(cleaned, sample_s)
    if v0.shape != v1.shape:
        raise RuntimeError("Video frame dimensions changed")
    y1, y2, x1, x2 = map(int, ai_text_removal.vsr_coords(region, target_width, target_height, padding))
    mask = np.zeros(v0.shape[:2], dtype=bool)
    mask[y1:y2, x1:x2] = True
    diff = np.abs(v0.astype(np.int16) - v1.astype(np.int16)).mean(axis=2)
    inside_change = float(diff[mask].mean())
    # Lossy reencoding changes pixels everywhere; insist on a real change beyond codec noise.
    outside_change = float(diff[~mask].mean())
    if inside_change < 2.0 or inside_change < outside_change * 1.15:
        raise RuntimeError("VSR output appears unchanged within the selected text area; no upload allowed")
    # Evidence image for private review; not published.
    canvas = Image.new("RGB", (target_width * 2, target_height + 44), (22, 24, 28))
    canvas.paste(Image.fromarray(cv2.cvtColor(v0, cv2.COLOR_BGR2RGB)), (0, 44))
    canvas.paste(Image.fromarray(cv2.cvtColor(v1, cv2.COLOR_BGR2RGB)), (target_width, 44))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 12), "BEFORE (original)", fill="white")
    draw.text((target_width + 10, 12), "AFTER (real AI)", fill="white")
    canvas.save(output_dir / "05_before_after_ai.png")
    return {"model_output_verified_as_non_noop": True, "frame_sample_seconds": sample_s,
            "mean_pixel_change_in_mask": round(inside_change, 3),
            "mean_pixel_change_outside_mask": round(outside_change, 3),
            "original_audio_preserved": not before_info["has_audio"] or after_info["has_audio"],
            "source_duration_seconds": before_info["duration"],
            "cleaned_duration_seconds": after_info["duration"],
            "quality_approved": False, "human_review_required": True}
