"""Locate a fixed on-screen caption from a SINGLE screenshot, not video-wide OCR.

FFmpeg extracts one frame around the configured second (normally 2s); the
optional image override allows supplying a screenshot when needed.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from io import BytesIO
from PIL import Image, ImageOps
from pathlib import Path
from functools import lru_cache


def duration_seconds(video: Path) -> float:
    cmd=["ffprobe","-v","error","-show_entries","format=duration", "-of","default=nokey=1:noprint_wrappers=1",str(video)]
    result=subprocess.run(cmd,check=True,capture_output=True,text=True)
    value=float(result.stdout.strip())
    if value <= 0: raise ValueError("Klip suresi bulunamadi")
    return value


def sample_frames(video: Path, w: int, h: int, max_duration: float,
                  samples: int = 1, frame_second: float = 2.0, start_seconds: float = 0.0):
    """Return a SINGLE FFmpeg screenshot at the requested second.

    The `samples` argument is retained to avoid breaking older integrations,
    but this workflow intentionally disallows per-video multi-frame OCR.
    """
    if samples != 1:
        raise ValueError("Piyaso sabit yazi modu tek ekran goruntusu kullanir")
    if frame_second < 0 or start_seconds < 0:
        raise ValueError("frame_second ve start_seconds sifirdan kucuk olamaz")
    usable = min(duration_seconds(video) - start_seconds, max_duration)
    if usable <= 0:
        raise ValueError("Klip suresi bulunamadi")
    at = min(float(frame_second), usable / 2 if usable < 2 * frame_second else usable - 0.05)
    at = max(0.0, at) + start_seconds
    with tempfile.TemporaryDirectory(prefix="piyaso-ocr-") as td:
        frame = Path(td) / "screenshot.png"
        vf=f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y", "-ss",str(at),"-i",str(video),
                        "-vf",vf,"-frames:v","1",str(frame)],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        return [(0,frame.read_bytes())]


def screenshot_bytes(image_path: Path, w: int, h: int) -> bytes:
    """Match a supplied screenshot to the final vertical video crop."""
    with Image.open(image_path) as source:
        rgb = ImageOps.fit(source.convert("RGB"), (w,h), method=Image.Resampling.LANCZOS)
        buff = BytesIO()
        rgb.save(buff, format="PNG")
        return buff.getvalue()


def group_boxes(frames: list[list[dict]], min_confidence: float = .45) -> dict:
    """Detect a static, possibly MULTI-LINE, caption from one screenshot.

    First union adjacent words into rows; then union nearby, horizontally
    aligned rows into a paragraph. Separated text blocks are deliberately
    flagged for review, rather than erasing an arbitrary portion of the video.
    """
    if len(frames) != 1:
        raise ValueError("Static-caption mode expects exactly one screenshot")
    boxes=[]
    for e in frames[0]:
        if float(e.get('confidence', 0)) < min_confidence: continue
        if not any(ch.isalnum() for ch in e.get('text', '')): continue
        try: x1,y1,x2,y2 = (float(v) for v in e['bbox'])
        except (KeyError, TypeError, ValueError): continue
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1): continue
        if x2-x1 < .018 or y2-y1 < .008 or y2-y1 > .13: continue
        if (y1+y2)/2 < .06 or (y1+y2)/2 > .84: continue
        boxes.append((x1,y1,x2,y2))
    boxes.sort(key=lambda b:(b[1]+b[3])/2)
    # Same-row tokens may be horizontally distant. Their vertical alignment
    # is sufficient to identify the line, but only after OCR filtering.
    rows=[]
    for x1,y1,x2,y2 in boxes:
        cy=(y1+y2)/2
        if rows and abs(cy - rows[-1]['cy']) <= max(.018, (y2-y1)*.65):
            r=rows[-1]
            r['x1']=min(r['x1'],x1);r['x2']=max(r['x2'],x2)
            r['y1']=min(r['y1'],y1);r['y2']=max(r['y2'],y2)
            r['cy']=(r['y1']+r['y2'])/2
            r['n']+=1
        else:
            rows.append(dict(x1=x1,y1=y1,x2=x2,y2=y2,cy=cy,n=1))
    groups=[]
    for row in rows:
        if groups:
            group=groups[-1]
            gap=row['y1']-group['y2']
            center1=(group['x1']+group['x2'])/2
            center2=(row['x1']+row['x2'])/2
            overlap=max(0,min(group['x2'],row['x2'])-max(group['x1'],row['x1']))
            narrower=min(group['x2']-group['x1'],row['x2']-row['x1'])
            align=abs(center1-center2)<.18 or overlap >= narrower*.5
            if -.03 <= gap <= .04 and align:
                group['x1']=min(group['x1'],row['x1']);group['x2']=max(group['x2'],row['x2'])
                group['y1']=min(group['y1'],row['y1']);group['y2']=max(group['y2'],row['y2'])
                group['lines']+=1
                continue
        groups.append(dict(x1=row['x1'],y1=row['y1'],x2=row['x2'],y2=row['y2'],lines=1))
    # Prefer a multi-line block, then the widest block.
    ranked=sorted(groups,key=lambda g:(-g['lines'],-(g['x2']-g['x1'])))
    main=ranked[0] if ranked else None
    regions=[]
    for g in ranked[:3]:
        center=(g['y1']+g['y2'])/2
        band_h=min(.42,max(.15,g['y2']-g['y1']+.06))
        y=max(.055,min(.86-band_h,center-band_h/2))
        regions.append({'x':.04,'y':round(y,4),'width':.92,'height':round(band_h,4)})
    text_region=None
    if main:
        left=max(0.,main['x1']-.014);right=min(1.,main['x2']+.014)
        top=max(0.,main['y1']-.016);bottom=min(1.,main['y2']+.016)
        text_region={'x':round(left,4),'y':round(top,4),
                     'width':round(right-left,4),'height':round(bottom-top,4)}
    # If the paragraph takes almost the entire image, a single mask risks
    # destroying faces/scenery. Require an explicit human review.
    too_large=bool(main and (main['y2']-main['y1'] > .38 or main['x2']-main['x1'] > .96))
    return {'headline_box':regions[0] if regions else None,
            'source_text_region':text_region,
            'cover_rectangles':regions[1:],
            'candidate_bands':len(groups),'stable_bands':len(regions),
            'detected_text_lines':main['lines'] if main else 0,
            'review_required':len(groups)!=1 or too_large}


@lru_cache(maxsize=1)
def _reader():
    try:
        import easyocr
    except ImportError as exc:
        raise RuntimeError("Auto OCR icin once: pip install -r requirements-ocr.txt") from exc
    # Cached across all clips for one daily job.
    return easyocr.Reader(["tr","en"],gpu=False,verbose=False)

def detect_clip(video: Path, w: int, h: int, max_duration: float = 12,
                frame_second: float = 2.0, start_seconds: float = 0.0, screenshot: Path | None = None,
                screenshot_output: Path | None = None) -> dict:
    """Run OCR once: video screenshot OR an owner-supplied still image."""
    if screenshot is not None:
        raw=screenshot_bytes(Path(screenshot),w,h)
        source="supplied_screenshot"
    else:
        raw=sample_frames(video,w,h,max_duration, samples=1,frame_second=frame_second,start_seconds=start_seconds)[0][1]
        source="video_frame"
    if screenshot_output is not None:
        screenshot_output.parent.mkdir(parents=True,exist_ok=True)
        screenshot_output.write_bytes(raw)

    items=_reader().readtext(raw,detail=1,paragraph=False)
    frame=[]
    for polygon,word,confidence in items:
        xs=[pt[0]/w for pt in polygon]; ys=[pt[1]/h for pt in polygon]
        frame.append({"bbox":[max(0,min(xs)),max(0,min(ys)),min(1,max(xs)),min(1,max(ys))],
                      "text":str(word),"confidence":float(confidence)})
    result=group_boxes([frame])
    result["sampled_frames"]=1
    result["screenshot_source"]=source
    result["frame_second"]=float(frame_second) if screenshot is None else None
    result["segment_start_second"]=float(start_seconds) if screenshot is None else None
    result["recognized_lines"]=len(frame)
    return result


def write_report(report:dict, path:Path):
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
