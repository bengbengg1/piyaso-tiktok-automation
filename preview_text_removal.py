"""Inspect a fixed subtitle region before invoking the *real* STTN VSR model.

Usage (before the expensive model install):
 python preview_text_removal.py --video source.mp4 --region 0.29,0.60,0.45,0.09 --output /tmp/text-review

Real AI (AFTER VSR is installed with pretrained weights):
 python preview_text_removal.py --video source.mp4 --region 0.29,0.60,0.45,0.09 --output /tmp/text-review --run --seconds 3

Coordinates are normalized x,y,width,height on the FINAL TikTok crop.
No secret is needed, no uploads and no publication. Outputs stay local.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

import ai_text_removal as ai
from render import px_rect


def parse_region(value: str) -> dict:
    try:
        x, y, w, h = [float(n.strip()) for n in value.split(",")]
    except (ValueError, TypeError) as e:
        raise argparse.ArgumentTypeError("--region needs x,y,width,height, each from 0 to 1") from e
    result = {"x": x, "y": y, "width": w, "height": h}
    try:
        px_rect(result, 1080, 1920)
    except (ValueError, TypeError, KeyError) as e:
        raise argparse.ArgumentTypeError(f"Invalid normalized region: {e}") from e
    return result


def review_mask(source: Path, dest: Path, region: dict, *,
                start: float = 0, frame_second: float = 1, width: int = 360,
                height: int = 640, padding: float = .012) -> dict:
    """Frame / green outlined region only. This is NOT an inpainted result."""
    if not source.is_file():
        raise FileNotFoundError(source)
    if start < 0 or frame_second < 0 or width < 64 or height < 64:
        raise ValueError("Invalid screenshot options")
    dest.mkdir(parents=True, exist_ok=True)
    frame = dest / "01_original_frame.png"
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start + frame_second),
            "-i", str(source), "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1",
            "-frames:v", "1", str(frame)]
    subprocess.run(args, check=True, timeout=90)
    raw_coords = px_rect(region, width, height)
    padded = ai.vsr_coords(region, width, height, padding)
    y1, y2, x1, x2 = list(map(int, padded))
    # Exact area that the model will fill is shown in blue/green.
    with Image.open(frame) as im:
        img = im.convert("RGB")
    marked = img.copy()
    d = ImageDraw.Draw(marked, "RGBA")
    d.rectangle((x1, y1, x2, y2), fill=(10, 210, 160, 45), outline=(25, 255, 110, 255), width=3)
    d.text((8, 8), "VSR MASK - NOT CLEANED", fill=(245, 235, 10, 255), stroke_width=1, stroke_fill=(0, 0, 0, 255))
    marked.save(dest / "02_mask_review.png")
    info = {"source": str(source), "mask_only": True, "start_seconds": start,
            "screenshot_seconds": start + frame_second, "normalized_region": region,
            "raw_rect_px": raw_coords, "padded_rect_ymin_ymax_xmin_xmax": list(map(int, padded)),
            "width": width, "height": height, "model_used": False,
            "publish_allowed": False}
    (dest / "review.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return info


def execute(source: Path, dest: Path, region: dict, *, start: float = 0, seconds: float = 3,
            width: int = 360, height: int = 640, fps: int = 15,
            padding: float = .012, mode: str = "sttn-auto", run: bool = False) -> dict:
    """Generate review screenshot, optionally run external pretrained AI and mux original audio."""
    preview = review_mask(source, dest, region, start=start, frame_second=min(1.0, seconds / 2),
                          width=width, height=height, padding=padding)
    if not run:
        return preview
    if seconds <= 0 or seconds > 90 or fps < 1 or fps > 60:
        raise ValueError("Seconds must be 0..90, FPS must be 1..60")
    cleaned = dest / "03_ai_cleaned_no_audio.mp4"
    # This call raises loudly if actual VSR source/weights are not installed.
    report = ai.remove_fixed_text(source, cleaned, region, start_seconds=start, duration_seconds=seconds,
                                  width=width, height=height, fps=fps, padding=padding, mode=mode)
    # VSR output itself has no audio; original source supplies the sound.
    final = dest / "04_ai_cleaned_with_original_audio.mp4"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(cleaned),
           "-ss", str(start), "-t", str(seconds), "-i", str(source), "-map", "0:v:0", "-map", "1:a?",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(final)]
    try:
        subprocess.run(cmd, check=True, timeout=240)
        if final.stat().st_size < 1024:
            raise RuntimeError("Output was empty")
    except Exception:
        final.unlink(missing_ok=True)
        raise
    # This is a real decoded-video comparison, not an AI-mock or mask preview.
    from vsr_quality import check_ai_result
    qa_input = dest / "06_qa_original_canvas.mp4"
    try:
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start),
            "-i", str(source), "-t", str(seconds),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps}",
            "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "19",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(qa_input)
        ], check=True, timeout=240)
        quality = check_ai_result(
            qa_input, final, region, dest,
        t=seconds, target_width=width, target_height=height,
            fps=fps, padding=padding,
        )
    finally:
        qa_input.unlink(missing_ok=True)
    preview.update({"model_used": True, "model": mode, "AI_processing_report": report,
                    "AI_quality_checks": quality,
                    "cleaned_video": str(final), "mask_only": False,
                    # The user still needs to inspect for flicker/face damage.
                    "publish_allowed": False, "human_quality_review_needed": True})
    (dest / "review.json").write_text(json.dumps(preview, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return preview


def main():
    p = argparse.ArgumentParser(description="Piyaso: review and run actual VSR AI on a single user video")
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--region", required=True, type=parse_region, help="Normalized x,y,width,height")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--seconds", type=float, default=3)
    p.add_argument("--width", type=int, default=360)
    p.add_argument("--height", type=int, default=640)
    p.add_argument("--fps", type=int, default=15)
    p.add_argument("--padding", type=float, default=.012)
    p.add_argument("--mode", choices=sorted(ai.SUPPORTED_MODES), default="sttn-auto")
    p.add_argument("--run", action="store_true", help="Actually run AI model (requires VSR installation)")
    args = p.parse_args()
    print(json.dumps(execute(args.video, args.output, args.region, start=args.start,
                             seconds=args.seconds, width=args.width, height=args.height, fps=args.fps,
                             padding=args.padding, mode=args.mode, run=args.run), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
