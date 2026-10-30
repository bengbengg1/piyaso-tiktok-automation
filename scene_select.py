"""Fast, deterministic automatic start-time proposal for long user clips.

Samples at low resolution, favors visibly active/sharp footage and avoids
black/blurred moments. Does NOT claim semantic understanding of the footage.
Manual start_seconds always overrides this heuristic.
"""
from __future__ import annotations
import math
from pathlib import Path


def choose_start(path: str | Path, window: float = 18., sample_every: float = 1.25) -> float:
    import cv2
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Video could not be opened: {path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not (fps > 0 and frames >= 1):
            raise ValueError('No valid duration/fps for automatic clip choice')
        duration = frames / fps
        if duration <= window + 0.5:
            return 0.
        samples = []
        t = 0.
        prev = None
        while t < duration:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok: break
            frame = cv2.resize(frame, (144, 256))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = float(gray.mean())
            sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            motion = float(cv2.absdiff(prev, gray).mean()) if prev is not None else 0.
            prev = gray
            # Avoid empty/blurred shots; soft cap rewards active but not jumpy scenes.
            active = min(motion / 25., 1.0)
            clarity = min(sharp / 110., 1.0)
            exposure = min(brightness / 36., 1.0) if brightness < 36 else 1.0
            score = (0.6 * active + 0.4 * clarity) * exposure
            samples.append((t, score))
            t += sample_every
        if len(samples) < 2:
            return 0.
        best_start, best_score = 0., -math.inf
        limit = max(0., duration - window - .12)
        for s,_ in samples:
            if s > limit: break
            values = [v for t,v in samples if s <= t < s+window]
            if len(values) < 2: continue
            score = sum(values)/len(values)
            if score > best_score + 0.00001:
                best_start, best_score = s, score
        return round(min(best_start, limit), 2)
    finally:
        cap.release()
