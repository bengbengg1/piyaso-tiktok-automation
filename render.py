"""Produce 2 or 3 daily TikTok video edits from owner-supplied footage.

Depends on GitHub projects FFmpeg/FFmpeg and python-pillow/Pillow.
No third-party video/source contents are bundled in this repository.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

import auto_text
import ai_text_removal

ROOT = Path(__file__).resolve().parent
DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
EPOCH = dt.date(2026, 1, 1)
FONTS = [
    "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def load_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def font(size):
    for candidate in FONTS:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def day_count(day, config):
    count = int(config["weekly_plan"][DAY_NAMES[day.weekday()]])
    times = config["posting_times"].get(str(count))
    if count not in (2, 3) or not isinstance(times, list) or len(times) != count:
        raise ValueError("Her gün 2 veya 3 video ve aynı sayıda saat tanımlanmalı")
    for time in times:
        dt.time.fromisoformat(time)
    if times != sorted(set(times)):
        raise ValueError("Yayın saatleri artan sırada ve tekrarsız olmalı")
    return count, times


def videos_before(day, config):
    if day < EPOCH:
        raise ValueError("Desteklenen ilk tarih 2026-01-01")
    offset = 0
    for i in range((day - EPOCH).days):
        offset += day_count(EPOCH + dt.timedelta(days=i), config)[0]
    return offset


def pick_jobs(day, clips, config, settings, copy, *, ignore_selection=False):
    """Return deterministic rotation without same-day duplicate source clips."""
    count, times = day_count(day, config)
    if len(clips) < count:
        raise ValueError(f"{day} için {count} farklı video gerekiyor; klasörde {len(clips)} tane var.")
    clips = sorted(clips)
    start = videos_before(day, config)
    selected = None
    # During daily R2 sync, only the 2-3 selected main videos are downloaded.
    # Preserve the rotation calculated against the ENTIRE remote video pool.
    if not ignore_selection:
        lock_path = ROOT / 'assets' / 'selection.json'
        if lock_path.exists():
            lock = json.loads(lock_path.read_text(encoding='utf-8'))
            if lock.get('date') == day.isoformat():
                names = lock.get('selected_names')
                if not isinstance(names, list) or len(names) != count or len(set(names)) != count:
                    raise ValueError('Remote selection manifest has incorrect slots')
                lookup = {p.name:p for p in clips}
                if any(name not in lookup for name in names):
                    raise ValueError('Missing a selected main video from private R2 sync')
                selected = [lookup[name] for name in names]
    result = []
    for i, time in enumerate(times):
        clip = selected[i] if selected is not None else clips[(start + i) % len(clips)]
        # ONE main-video pool. Filenames and genres never cause classification.
        variants = copy["genel"]
        ad = variants[((start + i) // len(clips)) % len(variants)]
        result.append({"index": i+1, "time": time, "clip": clip, "category": "genel", "ad": ad})
    return result


def fit_lines(draw, text, available_width, available_height, max_lines=3, suggested=52):
    """Constrain overlay text to its opaque backing; never show partially hidden old writing."""
    for size in range(suggested, 13, -2):
        f = font(size)
        words = text.split()
        lines = []
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if draw.textbbox((0, 0), test, font=f, stroke_width=0)[2] <= available_width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        lineheight = int(size * 1.38)
        if (len(lines) <= max_lines and len(lines)*lineheight <= available_height
                and all(draw.textbbox((0, 0), line, font=f)[2] <= available_width for line in lines)):
            return lines, f, lineheight
    raise ValueError(f"Reklam yazısı kutuya sığmıyor: {text}")


def px_rect(rect, w, h):
    fields = [rect[k] for k in ("x", "y", "width", "height")]
    x, y, width, height = map(float, fields)
    if min(fields) < 0 or x + width > 1.00001 or y + height > 1.00001 or width <= 0 or height <= 0:
        raise ValueError(f"Maske koordinatları kadraj içinde 0-1 olmalı: {rect}")
    x1, y1 = round(x*w), round(y*h)
    return (x1, y1, round((x+width)*w), round((y+height)*h))


def probe_dimensions(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise ValueError(f"Video görüntü akışı yok: {path}")
    return int(streams[0]["width"]), int(streams[0]["height"])


def segment_window(clip, config, clip_settings):
    """Take the requested ~18s segment; never loop the source to reach the target.

    start_seconds is configurable per clip because selecting the genuinely best
    moment needs editorial/contextual judgment, not a random timestamp.
    """
    duration=float(clip_settings.get("duration_seconds", config["duration_seconds"]))
    start_spec = clip_settings.get("start_seconds", "auto")
    if start_spec == "auto":
        from scene_select import choose_start
        start = choose_start(clip, duration)
    else:
        start=float(start_spec)
    if not 12 <= duration <= 30:
        raise ValueError("Klip hedef suresi 12 ile 30 saniye arasinda olmali")
    if start < 0:
        raise ValueError("Klip baslangici negatif olamaz")
    source_duration=auto_text.duration_seconds(clip)
    available=source_duration - start
    if available < 0.5:
        raise ValueError(f"Klipte belirtilen baslangic icin goruntu yok: {clip.name}")
    actual=min(duration, available)
    short=actual < float(config.get("minimum_source_seconds", 12))
    return start, round(actual,3), short


def app_for(slot_index, config):
    """Choose only from Piyaso screen recordings; never inspect main-video genre.

    One mandatory default recording and zero or more optional files in a
    dedicated directory, rotated independently of the main-video pool.
    """
    recordings = config["app_recordings"]
    default = ROOT / recordings["default"]
    folder = ROOT / recordings["directory"]
    if recordings["default"] != "assets/app_recording.mp4" or recordings["directory"] != "assets/app_recordings":
        raise ValueError("Piyaso ekran kayıtlarının yolları değiştirilmemeli")
    if not default.is_file():
        fallback=[ROOT/'assets/app_recording.mov', ROOT/'assets/app_recording.mp4.mov']
        default=next((candidate for candidate in fallback if candidate.is_file()), default)
    if not default.is_file():
        raise FileNotFoundError('Piyaso ekran kaydı eksik: app_recording.mp4 / .mov / .mp4.mov')
    extras = sorted(p for p in folder.glob('*') if p.is_file() and p.suffix.lower() in ('.mp4','.mov','.mkv')) if folder.exists() else []
    choices = [default] + extras
    return choices[(slot_index-1) % len(choices)]


def phone_geometry(w, h, path, spec):
    appw, apph = probe_dimensions(path)
    ow = max(2, (int(spec["width"]*w)//2)*2)
    oh = max(2, (int(ow*apph/appw)//2)*2)
    max_h = max(2, (int(spec["max_height"]*h)//2)*2)
    if oh > max_h:
        oh = max_h
        ow = max(2, (int(oh*appw/apph)//2)*2)
    x, y = round(spec["x"]*w), round(spec["y"]*h)
    if x < 6 or y < 6 or x+ow > w-6 or y+oh > h-6:
        raise ValueError("Telefon penceresi kadraj dışında; clip_settings.json içindeki phone konumunu düzeltin")
    return x, y, ow, oh


def make_overlay(path, w, h, headline, config, masks, title_area, phone):
    pic = Image.new("RGBA", (w,h), (0,0,0,0))
    d = ImageDraw.Draw(pic)
    if config.get("text_style")=="tiktok_native":
        # TikTok-native overlay: large white lettering with a dark stroke.
        # No colored headline card, no footer, no title badge or phone label.
        x1,y1,x2,y2=px_rect(title_area,w,h)
        margin=max(6,int(w*.015))
        lines,f,lineh=fit_lines(d,headline,x2-x1-2*margin,y2-y1-2*margin,
                                  max_lines=5,suggested=max(22,int(w*.07)))
        yy=y1+(y2-y1-len(lines)*lineh)//2
        for line in lines:
            bb=d.textbbox((0,0),line,font=f)
            xx=x1+(x2-x1-(bb[2]-bb[0]))//2
            d.text((xx,yy),line,font=f,fill="white",
                   stroke_width=max(2,int(w*.006)),stroke_fill="black")
            yy+=lineh
        px,py,pw,ph=phone
        d.rounded_rectangle((px-5,py-5,px+pw+5,py+ph+5),
                            radius=max(6,w//60),outline=(248,248,248,255),width=max(2,w//190))
        pic.save(path)
        return
    for r in masks:
        x1,y1,x2,y2 = px_rect(r,w,h)
        d.rounded_rectangle((x1,y1,x2,y2), radius=max(4,w//80), fill=(10,16,22,255))
    # Headline's *opaque* backing replaces any underlying original text.
    x1,y1,x2,y2 = px_rect(title_area,w,h)
    radius = max(4,int(w*.025))
    d.rounded_rectangle((x1,y1,x2,y2), radius=radius, fill=(14,19,29,255), outline=(84,206,148,230), width=max(1,w//400))
    margin = max(8,int(w*.045))
    lines, f, lineh = fit_lines(d,headline,x2-x1-2*margin,y2-y1-2*margin,max_lines=3,suggested=max(18,int(w*.054)))
    yy = y1+(y2-y1-len(lines)*lineh)//2
    for line in lines:
        bb=d.textbbox((0,0),line,font=f)
        xx=x1+(x2-x1-(bb[2]-bb[0]))//2
        d.text((xx,yy),line,font=f,fill="white")
        yy+=lineh
    # Thin frame for PiP app recording added by FFmpeg (transparent middle).
    px,py,pw,ph=phone
    d.rounded_rectangle((px-5,py-5,px+pw+5,py+ph+5),radius=max(6,w//60),outline=(240,244,247,250),width=max(2,w//160))
    x1,y1,x2,y2=px_rect(config["footer_box"],w,h)
    d.rounded_rectangle((x1,y1,x2,y2),radius=max(4,w//50),fill=(14,19,29,255))
    footer=config["bottom_label"]
    margin=max(6,int(w*.027))
    lines,f,lineh=fit_lines(d,footer,x2-x1-2*margin,y2-y1-2*margin,max_lines=2,suggested=max(16,int(w*.036)))
    yy=y1+(y2-y1-len(lines)*lineh)//2
    for line in lines:
        bb=d.textbbox((0,0),line,font=f)
        d.text((x1+(x2-x1-(bb[2]-bb[0]))//2,yy),line,font=f,fill=(240,247,241))
        yy+=lineh
    pic.save(path)


def utc_due_at(day, time):
    hour,minute = [int(x) for x in time.split(":")]
    local=dt.datetime.combine(day,dt.time(hour,minute),tzinfo=ZoneInfo("Europe/Istanbul"))
    return local.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")


def render_day(day, width=None, height=None, daily_copy_path=None):
    config, settings, copy = (load_json(x) for x in ("config.json","clip_settings.json","ad_copy.json"))
    if width is not None: config["width"] = width
    if height is not None: config["height"] = height
    w,h=config["width"],config["height"]
    if min(w,h) < 240 or w%2 or h%2:
        raise ValueError("Video ölçüleri çift sayı ve en az 240 piksel olmalı")
    base=ROOT/config["background_dir"]
    clips=[p for p in base.iterdir() if p.is_file() and p.suffix.lower() in (".mp4",".mov",".mkv")]
    jobs=pick_jobs(day,clips,config,settings,copy)
    if daily_copy_path is not None:
        generated=json.loads(Path(daily_copy_path).read_text(encoding="utf-8"))
        if generated.get("date")!=day.isoformat() or generated.get("generation_type")!="ai_generated":
            raise ValueError("Günlük reklam dosyası tarihi veya türü yanlış")
        supplied=generated.get("items",[])
        if len(supplied)!=len(jobs) or {x.get("slot") for x in supplied}!={j["index"] for j in jobs}:
            raise ValueError("Günlük reklam dosyası eksik veya slotlar hatalı")
        by_index={x["slot"]:x for x in supplied}
        for job in jobs:
            fresh=by_index[job["index"]]
            if fresh.get("category")!=job["category"] or fresh.get("source_clip")!=job["clip"].name:
                raise ValueError("Günlük reklam dosyası seçilen videoya ait değil")
            if not isinstance(fresh.get("headline"),str) or not isinstance(fresh.get("caption"),str):
                raise ValueError("Günlük reklam başlık/açıklama metni eksik")
            job["ad"]={"headline":fresh["headline"],"caption":fresh["caption"]}
    directory=ROOT/config["output_dir"]/day.isoformat()
    directory.mkdir(parents=True,exist_ok=True)
    catalog_file=ROOT/"assets"/"catalog.json"
    catalog=load_json("assets/catalog.json") if catalog_file.exists() else {"backgrounds":{}}
    rights=catalog.get("backgrounds",{})
    manifest={"date":day.isoformat(),"timezone":"Europe/Istanbul","copy_source":"ai_generated" if daily_copy_path else "approved_library","count":len(jobs),"items":[]}
    for job in jobs:
        clip,ad=job["clip"],job["ad"]
        cfg=settings.get("videos",{}).get(clip.name,{})
        app=app_for(videos_before(day,config)+job["index"],config)
        clip_start,clip_duration,source_too_short=segment_window(clip,config,cfg)
        spec={**config["phone"],**settings.get("defaults",{}).get("phone",{}),**cfg.get("phone",{})}
        pgeom=phone_geometry(w,h,app,spec)
        slot=f"{job['index']:02d}_{job['time'].replace(':','')}"
        dest=directory/slot
        dest.mkdir(parents=True,exist_ok=True)
        overlay=dest/"overlay.png"
        title_area={**config["headline_box"],**settings.get("defaults",{}).get("headline_box",{}),**cfg.get("headline_box",{})}
        masks=cfg.get("cover_rectangles",settings.get("defaults",{}).get("cover_rectangles",[]))
        # A manually annotated clip stays manually controlled. All other clips
        # use sparse OCR and mark uncertain layouts as REVIEW REQUIRED.
        text_mode=cfg.get("text_mode",config.get("text_detection",{}).get("mode","manual"))
        review_required=source_too_short
        ocr_report=None
        source_text_region=None
        if text_mode=="auto":
            frame_second=float(cfg.get("frame_second",config.get("text_detection",{}).get("frame_second",2)))
            screenshot_path=cfg.get("screenshot")
            screenshot=ROOT/screenshot_path if screenshot_path else None
            if screenshot is not None and not screenshot.is_file():
                raise FileNotFoundError(f"Klip ekran goruntusu bulunamadi: {screenshot}")
            ocr_report=auto_text.detect_clip(clip,w,h,clip_duration,
                                              frame_second=frame_second,start_seconds=clip_start,screenshot=screenshot,
                                              screenshot_output=dest/"detected_frame.png")
            review_required=ocr_report["review_required"] or source_too_short
            if ocr_report["headline_box"] is not None:
                if config.get("text_style")!="tiktok_native":
                    title_area=ocr_report["headline_box"]
                masks=ocr_report["cover_rectangles"]
                source_text_region=ocr_report.get("source_text_region")
            else:
                # No confident detection: use the legacy header but refuse
                # automatic publishing unless manually reviewed.
                masks=[]
            auto_text.write_report(ocr_report,dest/"ocr_report.json")
        elif text_mode=="manual" and masks:
            source_text_region=masks[0]
        elif text_mode!="manual":
            raise ValueError(f"Bilinmeyen text_mode: {text_mode}")
        make_overlay(overlay,w,h,ad["headline"],config,masks,title_area,pgeom)
        x,y,pw,ph=pgeom
        # The background is reconstructed by the GitHub VSR project before
        # composing native-looking TikTok typography / the app screen capture.
        # Absence or failure of the AI model must NEVER revert to fake erasing.
        removal_cfg = {**config.get("text_removal", {}), **cfg.get("text_removal", {})}
        backend = removal_cfg.get("backend", "vsr" if config.get("text_style")=="tiktok_native" else "cover")
        ai_report = None
        bg_input = clip
        bg_seek = clip_start
        if config.get("text_style") == "tiktok_native":
            if source_text_region:
                if backend == "vsr":
                    # Input is cropped FIRST so the OCR coordinates are in the
                    # exact pixel space VSR sees (important for 9:16 crops).
                    cleaned = dest/"cleaned_background.mp4"
                    ai_report = ai_text_removal.remove_fixed_text(
                        clip, cleaned, source_text_region, start_seconds=clip_start,
                        duration_seconds=clip_duration, width=w, height=h, fps=config["fps"],
                        mode=removal_cfg.get("mode", "sttn-auto"),
                        padding=float(removal_cfg.get("padding", .012)),
                        timeout_seconds=int(removal_cfg.get("timeout_seconds", 2700)))
                    bg_input, bg_seek = cleaned, 0
                    # New AI results need visual inspection for ghosting, flicker or face damage.
                    if removal_cfg.get("require_human_review", True):
                        review_required = True
                elif backend == "delogo":
                    # Explicit legacy mode only. Never imply this is AI.
                    review_required=True
                else:
                    raise ValueError(f"Unknown text removal backend: {backend}")
            else:
                review_required=True
        # In an AI render the first input is the already trimmed and cropped
        # clean video, while the original source supplies the ORIGINAL audio.
        if ai_report:
            filtergraph=(f"[0:v]fps={config['fps']},setsar=1[bg];"
                         f"[1:v]scale={pw}:{ph},setsar=1,fps={config['fps']}[phone];"
                         f"[bg][phone]overlay={x}:{y}:shortest=0[merged];"
                         f"[merged][2:v]overlay=0:0:shortest=0[v]")
            audio_source=["-ss", str(clip_start), "-i", str(clip)]
            audio_map="3:a?"
        else:
            removal=""
            if backend=="delogo" and source_text_region:
                # Delogo coordinates operate on the *source* pixel space, not
                # the cropped 9:16 canvas. Force human review for legacy mode.
                sw,sh=probe_dimensions(clip)
                rx,ry,rxe,rye=px_rect(source_text_region,sw,sh)
                if 8<(rxe-rx)<sw*.8 and (rye-ry)>8:
                    removal=f"delogo=x={rx}:y={ry}:w={rxe-rx}:h={rye-ry},"
            filtergraph=(f"[0:v]{removal}scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={config['fps']}[bg];"
                         f"[1:v]scale={pw}:{ph},setsar=1,fps={config['fps']}[phone];"
                         f"[bg][phone]overlay={x}:{y}:shortest=0[merged];"
                         f"[merged][2:v]overlay=0:0:shortest=0[v]")
            audio_source=[]
            audio_map="0:a?"
        video=dest/"video.mp4"
        command=["ffmpeg","-hide_banner","-loglevel","error","-y",
                 "-ss",str(bg_seek),"-i",str(bg_input),
                 "-stream_loop","-1","-i",str(app),"-loop","1","-i",str(overlay),
                 *audio_source,
                 "-filter_complex",filtergraph,"-map","[v]","-map",audio_map,
                 "-t",str(clip_duration),"-c:v","libx264","-preset","veryfast","-crf","24","-pix_fmt","yuv420p",
                 "-c:a","aac","-b:a","128k","-movflags","+faststart",str(video)]
        subprocess.run(command,check=True)
        caption=" ".join([ad["caption"].strip(),config["hashtags"].strip()]).strip()
        if len(caption)>150:
            raise ValueError(f"TikTok açıklaması Buffer 150 karakter limitini aşıyor: {len(caption)}")
        (dest/"caption.txt").write_text(caption+"\n",encoding="utf-8")
        item={"slot":slot,"time":job["time"],"dueAt":utc_due_at(day,job["time"]),"background":clip.name,"segment_start_seconds":clip_start,"duration_seconds":clip_duration,
              "source_too_short":source_too_short,"demo":clip.stem.endswith("_ornek"),
              "commercial_use_authorized": rights.get(clip.name,{}).get("commercial_use_authorized") is True,"review_required":review_required,"text_mode":text_mode,"app_recording":app.name,"headline":ad["headline"],"caption":caption,
              "file":str(video.relative_to(ROOT)),
              "text_removal_backend":backend if source_text_region else "none", "ai_removal":ai_report}
        manifest["items"].append(item)
        print(f"Hazır: {slot} / {clip.name} / {video}")
    (directory/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest


def main():
    parser=argparse.ArgumentParser(description="Piyaso: her gün 2 ya da 3 TikTok videosu üret")
    parser.add_argument("--date",default=dt.datetime.now(ZoneInfo("Europe/Istanbul")).date().isoformat())
    parser.add_argument("--width",type=int)
    parser.add_argument("--height",type=int)
    parser.add_argument("--daily-copy",type=Path,help="Yapay zekâ günlük reklam metinleri JSON dosyası")
    args=parser.parse_args()
    result=render_day(dt.date.fromisoformat(args.date),args.width,args.height,args.daily_copy)
    print(json.dumps({"day":result["date"],"videos":result["count"],"times":[x["time"] for x in result["items"]]},ensure_ascii=False))

if __name__=="__main__":
    main()
