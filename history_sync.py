"""Persist ad-copy memory in PRIVATE R2 objects (public GitHub repo stays read-only).

Each daily copy uses immutable state/copy/YYYY-MM-DD.json, avoiding concurrent
writes and leaked drafts in a public Git history. No cloud access from imports.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import storage_client

ROOT=Path(__file__).resolve().parent
HISTORY=ROOT/'data'/'generated_history.json'


def key(day: str) -> str:
    dt.date.fromisoformat(day)
    return f'state/copy/{day}.json'


def pull():
    bucket=storage_client.bucket_name('state')
    records=storage_client.list_objects(bucket,'state/copy/')
    entries=[]
    for item in sorted(records,key=lambda e:e['name']):
        if not item['name'].endswith('.json'):continue
        day=item['name'][:-5]
        remote=storage_client.download(bucket,key(day),max_bytes=64*1024)
        if remote is None:raise RuntimeError('Copy archive disappeared during download')
        doc=json.loads(remote)
        if doc.get('date')!=day or doc.get('generation_type')!='ai_generated':
            raise RuntimeError(f'Untrusted copy history document: {day}')
        entries.extend(dict(x,date=day) for x in doc['items'])
    HISTORY.parent.mkdir(parents=True,exist_ok=True)
    HISTORY.write_text(json.dumps({'entries':entries[-1000:]},ensure_ascii=False,indent=2)+'\n','utf-8')
    print(f'Private R2: {len(records)} daily copy archives, {len(entries)} entries loaded')
    return entries


def push(day: str):
    path=ROOT/'output'/day/'daily_copy.json'
    doc=json.loads(path.read_text('utf-8'))
    if doc.get('date')!=day or doc.get('generation_type')!='ai_generated':
        raise ValueError('Copy day or provenance does not match')
    bucket=storage_client.bucket_name('state')
    payload=json.dumps(doc,ensure_ascii=False,sort_keys=True).encode('utf-8')
    prior=storage_client.download(bucket,key(day),max_bytes=64*1024)
    if prior is not None:
        # May originate from different JSON indentation; compare decoded docs.
        if json.loads(prior)!=doc:raise RuntimeError('Different ad copy already stored for this date; no overwrite')
        print('Copy archive already exists and matches')
        return
    storage_client.upload(bucket,key(day),payload,'application/json')
    print('Copy archive saved to private R2: '+day)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['pull','push'])
    p.add_argument('--date')
    a=p.parse_args()
    if a.action=='pull':pull()
    else:
        if not a.date:p.error('--date is required for push')
        push(a.date)
