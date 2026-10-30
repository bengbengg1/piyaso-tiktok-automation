"""Download licensed footage from a separate PRIVATE Storage bucket.

Expected bucket paths: backgrounds/*.mp4 and app_recordings/*.mp4.
Never put raw footage or user credentials in a public GitHub repository.
Every source background must be explicitly approved in catalog.json.
"""
from __future__ import annotations
import argparse
import json
import os
import datetime as dt
from pathlib import Path

import storage_client
ROOT=Path(__file__).resolve().parent


def sync_assets(*,catalog_path=None, day=None):
    bucket=storage_client.bucket_name('assets')
    storage_client.check_bucket(bucket,False)
    catalog_path=Path(catalog_path or ROOT/'assets'/'catalog.json')
    catalog=json.loads(catalog_path.read_text('utf-8'))
    approved=catalog.get('backgrounds',{})
    if not approved:
        raise RuntimeError('No footage approved in assets/catalog.json')
    backgrounds=storage_client.list_objects(bucket,'backgrounds/')
    eligible=[item for item in backgrounds
              if (item.get('name','').lower().endswith(('.mp4','.mov','.mkv'))
                  and approved.get(item.get('name',''),{}).get('commercial_use_authorized') is True)]
    if not eligible:
        raise RuntimeError('No authorized clip found; demo assets will not be used')
    # Full remote pool drives day-to-day rotation, but download ONLY today's
    # 2 or 3 videos. Large libraries should not be downloaded every morning.
    lock=None
    if day is not None:
        import render
        config=json.loads((ROOT/'config.json').read_text('utf-8'))
        settings=json.loads((ROOT/'clip_settings.json').read_text('utf-8'))
        copy=json.loads((ROOT/'ad_copy.json').read_text('utf-8'))
        pool_paths=[ROOT/'assets'/'backgrounds'/item['name'] for item in eligible]
        planned=render.pick_jobs(day,pool_paths,config,settings,copy,ignore_selection=True)
        choices=[j['clip'].name for j in planned]
        eligible=[item for item in eligible if item['name'] in set(choices)]
        lock={'date':day.isoformat(),'selected_names':choices,
              'remote_approved_pool_size':len(pool_paths)}
    # Discard bundled demo clips before production; keep only approved media.
    for old in (ROOT/'assets'/'backgrounds').glob('*'):
        if old.is_file() and old.suffix.lower() in ('.mp4','.mov','.mkv'):
            old.unlink()
    fetched=[]
    for item in eligible:
        name=item.get('name','')
        if not name.lower().endswith(('.mp4','.mov','.mkv')):continue
        meta=approved.get(name)
        if not meta or meta.get('commercial_use_authorized') is not True:
            continue
        content=storage_client.download(bucket,'backgrounds/'+name,max_bytes=80*1024*1024)
        if not content:raise RuntimeError('Empty media object '+name)
        dest=ROOT/'assets'/'backgrounds'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(content)
        fetched.append(name)
    if not fetched:raise RuntimeError('No approved footage found in private assets bucket')
    if lock is not None:
        (ROOT/'assets'/'selection.json').write_text(
            json.dumps(lock,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Strictly two media roles: MAIN backgrounds and APP recordings.
    # No subcategories, no filename-based pairing, no garage/karaoke mapping.
    config=json.loads((ROOT/'config.json').read_text('utf-8'))
    app_map=config.get('app_recordings',{})
    if app_map != {'default':'assets/app_recording.mp4','directory':'assets/app_recordings'}:
        raise ValueError('Piyaso screen recording paths must stay separate')
    app_folder=ROOT/'assets'/'app_recordings'
    app_folder.mkdir(parents=True,exist_ok=True)
    for old in app_folder.glob('*'):
        if old.is_file() and old.suffix.lower() in ('.mp4','.mov','.mkv'):
            old.unlink()
    # iOS may upload an actual QuickTime MOV or a file named *.mp4.mov.
    # Preserve the source extension; renaming is not transcoding.
    default_names=('app_recording.mp4','app_recording.mov','app_recording.mp4.mov')
    for name in default_names:
        (ROOT/'assets'/name).unlink(missing_ok=True)
    default_name=None
    default_content=None
    for name in default_names:
        content=storage_client.download(bucket,'app_recordings/'+name,max_bytes=80*1024*1024)
        if content:
            default_name,default_content=name,content
            break
    if default_content is None:
        raise RuntimeError('Missing default Piyaso screen recording; expected app_recordings/app_recording.mp4 or .mov or .mp4.mov')
    (ROOT/'assets'/default_name).write_bytes(default_content)

    screens=1
    app_objects=storage_client.list_objects(bucket,'app_recordings/')
    for item in sorted(app_objects,key=lambda o:o.get('name','')):
        name=item.get('name','')
        if name in default_names or Path(name).suffix.lower() not in ('.mp4','.mov','.mkv'):
            continue
        if not name or name in ('.','..') or '/' in name or '\\' in name:
            continue
        content=storage_client.download(bucket,'app_recordings/'+name,max_bytes=80*1024*1024)
        if not content:continue
        (app_folder/name).write_bytes(content)
        screens+=1

    print(f'Synced {len(fetched)} licensed main videos + {screens} Piyaso app screen recording(s) from isolated R2 folders')
    return fetched

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--catalog')
    p.add_argument('--date', help='YYYY-MM-DD: download only 2-3 videos selected for this day')
    a=p.parse_args()
    sync_assets(catalog_path=a.catalog,day=dt.date.fromisoformat(a.date) if a.date else None)
