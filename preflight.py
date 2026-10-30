"""Check readiness without posting, uploading or revealing API keys."""
from __future__ import annotations
import argparse
import json
import datetime as dt
from zoneinfo import ZoneInfo
import os
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent


def checks(*,live=False):
    result=[]
    def record(name,passed,detail):result.append({'item':name,'ready':bool(passed),'detail':detail})
    record('FFmpeg',bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),'Required to render videos')
    try:
        import cv2
        record('OpenCV',True,'Scene selection is available')
    except ImportError:
        record('OpenCV',False,'pip install -r requirements.txt')
    try:
        from PIL import Image
        record('Pillow',True,'Text overlays available')
    except ImportError:
        record('Pillow',False,'pip install -r requirements.txt')
    backgrounds=list((ROOT/'assets'/'backgrounds').glob('*.mp4'))
    real=[x for x in backgrounds if not x.stem.endswith('_ornek')]
    record('Footage',bool(real),'At least one real, authorized clip is required; demo clips do not count')
    cat=json.loads((ROOT/'assets'/'catalog.json').read_text('utf-8'))
    good=[x for x in real if cat.get('backgrounds',{}).get(x.name,{}).get('commercial_use_authorized') is True]
    # An R2 daily job downloads only 2-3 clips. A remote-pool selection
    # manifest proves it had enough other approved clips to rotate through.
    from render import day_count
    config=json.loads((ROOT/'config.json').read_text('utf-8'))
    today=dt.datetime.now(ZoneInfo('Europe/Istanbul')).date()
    day_slots=day_count(today,config)[0]
    lock_path=ROOT/'assets'/'selection.json'
    try:
        lock=json.loads(lock_path.read_text('utf-8')) if lock_path.exists() else None
    except json.JSONDecodeError:
        lock=None
    if lock is not None and lock.get('date')==today.isoformat():
        valid_count=(len(good)==day_slots and lock.get('remote_approved_pool_size',0)>=day_slots
                     and set(lock.get('selected_names',[]))=={x.name for x in good})
    else:
        valid_count=len(good)>=3
    record('Commercial rights',valid_count,'Authorized main clips and full remote rotation; 3 sources required for 3-video days')
    record('Screen recording', any((ROOT/'assets'/name).is_file() for name in ('app_recording.mp4','app_recording.mov','app_recording.mp4.mov')), 'Application demo capture (MP4/MOV)')
    if live:
        from storage_client import bucket_name,endpoint,public_base
        names=[bucket_name(k) for k in ('assets','state','public')]
        record('R2 isolated prefixes',len(set(names)) == 1 and names[0] == 'piyaso-tiktok-assets','One bucket; backgrounds/, app_recordings/, state/, published/ paths')
        try:
            endpoint()
            public_base()
            record('R2 URL config',True,'Valid S3 endpoint and anonymous HTTPS video origin')
        except RuntimeError as exc:
            record('R2 URL config',False,str(exc))
        for key in ['GROQ_API_KEY','BUFFER_API_KEY','BUFFER_CHANNEL_ID','R2_ENDPOINT','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_PUBLIC_BASE_URL']:
            record(key,bool(os.getenv(key)),'Add to GitHub Actions Secrets, never to repository')
        from ai_text_removal import ensure_vsr_weights
        try:ensure_vsr_weights();record('VSR AI environment',True,'Backend and selected model checkpoint located (inference still unverified)')
        except (RuntimeError,FileNotFoundError):record('VSR AI environment',False,'Dedicated VSR installation and model checkpoint required; run real inference smoke separately')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');a=p.parse_args()
    r=checks(live=a.live)
    for x in r:print(('OK' if x['ready'] else 'MISSING')+' '+x['item']+': '+x['detail'])
    if any(not x['ready'] for x in r):raise SystemExit(2)
