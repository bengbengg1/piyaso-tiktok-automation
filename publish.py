"""Opt-in uploader and exact-time Buffer scheduler. Disabled by default.

Safety: if a prior upload exists without a confirmed receipt, fail closed to avoid
posting a duplicate after a timeout. A human must reconcile the Buffer queue.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent
BUFFER_API="https://api.buffer.com"


def required(name):
    val=os.getenv(name,"").strip()
    if not val: raise RuntimeError(f"{name} eksik (GitHub Actions secrets / vars)")
    return val


def public_url(path):
    import storage_client
    return storage_client.public_url(storage_client.bucket_name('public'),path)


def write_object(path,content,ctype):
    import storage_client
    bucket=storage_client.bucket_name('public')
    url=storage_client.upload(bucket,path,content,ctype)
    storage_client.verify_public_access(url)
    return url


def read_public(path):
    from storage_client import download, bucket_name
    return download(bucket_name('public'),path)


def create_buffer_post(url,caption,due_at):
    """Official Buffer GraphQL video creation (not unofficial TikTok endpoints)."""
    if len(caption)>150:
        raise ValueError(f"TikTok Buffer açıklaması 150 karakteri aşıyor ({len(caption)})")
    query="""mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id text dueAt status } }
        ... on MutationError { message }
      }
    }"""
    values={"text":caption,"channelId":required("BUFFER_CHANNEL_ID"),
            "schedulingType":"automatic","mode":"customScheduled","dueAt":due_at,
            "aiAssisted":True,
            "assets":[{"video":{"url":url,"metadata":{"thumbnailOffset":2000}}}]}
    payload=json.dumps({"query":query,"variables":{"input":values}}).encode("utf-8")
    req=Request(BUFFER_API,data=payload,headers={"Authorization":"Bearer "+required("BUFFER_API_KEY"),"Content-Type":"application/json"},method="POST")
    with urlopen(req,timeout=45) as res:
        data=json.loads(res.read())
    if data.get("errors"):
        raise RuntimeError(f"Buffer API error: {str(data['errors'])[:600]}")
    result=data.get("data",{}).get("createPost") or {}
    if result.get("message"):
        raise RuntimeError("Buffer did not accept post: "+result["message"])
    post=result.get("post") or {}
    if not post.get("id"):
        raise RuntimeError("Buffer did not confirm post id: "+str(data)[:600])
    return post


def _state_bucket():
    from storage_client import bucket_name
    return bucket_name("state")


def read_state(key):
    from storage_client import download
    content=download(_state_bucket(),key,max_bytes=32768)
    return json.loads(content) if content is not None else None


def save_state(key,value):
    from storage_client import upload
    upload(_state_bucket(),key,json.dumps(value,ensure_ascii=False).encode("utf-8"),"application/json")


def validate_manifest_for_publish(manifest, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    if not manifest.get("items"):
        raise RuntimeError("Nothing to publish")
    for item in manifest["items"]:
        if item.get("demo"):
            raise RuntimeError("Demo footage cannot be published")
        if item.get("commercial_use_authorized") is not True:
            raise RuntimeError("Source footage lacks confirmed commercial-use rights in catalog")
        if item.get("review_required"):
            raise RuntimeError("Clip requires human review before publishing")
        if item.get("text_removal_backend") not in ("vsr",):
            raise RuntimeError("AI text removal not verified for this clip")
        if not item.get("ai_removal"):
            raise RuntimeError("No VSR output report for clip")
        due=dt.datetime.fromisoformat(item["dueAt"].replace("Z","+00:00"))
        if due<=now+dt.timedelta(minutes=15):
            raise RuntimeError(f"{item['slot']}: time passed or too close to publish")
        path=ROOT/item["file"]
        if not path.is_file():raise FileNotFoundError(path)
        if path.stat().st_size>45*1024*1024:raise ValueError("Video over 45 MiB")


def schedule_manifest(manifest):
    if os.getenv("PUBLISH_ENABLED","").lower()!="true":
        print("Publishing disabled. No external request sent.")
        return []
    validate_manifest_for_publish(manifest)
    # Fail closed even if publish.py is run manually outside the usual Actions preflight.
    from buffer_setup import list_channels, validate_tiktok_channel
    validate_tiktok_channel(required('BUFFER_CHANNEL_ID'), list_channels())
    from storage_client import check_bucket,exists,bucket_name
    check_bucket(bucket_name("assets"),True)
    confirmed=[]
    for item in manifest["items"]:
        date,slot=manifest["date"],item["slot"]
        base_key=f"piyaso/{date}/{slot}"
        receipt_base=f"state/{base_key}"
        state_key=f"{receipt_base}/submission.json"
        confirmed_receipt=read_state(f'{receipt_base}/confirmed.json')
        if confirmed_receipt is not None and confirmed_receipt.get('post',{}).get('id'):
            print(f"Already scheduled: {slot}; {confirmed_receipt['post']['id']}")
            confirmed.append(confirmed_receipt)
            continue
        state=read_state(state_key)
        if state is not None:
            raise RuntimeError(f'{slot}: prior incomplete Buffer submission. Reconcile manually before retrying to avoid duplicate publication.')
        video_key=f"published/{base_key}/video.mp4"
        if exists(bucket_name("public"),video_key):
            raise RuntimeError(f"{slot}: video already uploaded with no receipt; reconcile manually")
        filepath=ROOT/item["file"]
        media_url=write_object(video_key,filepath.read_bytes(),"video/mp4")
        # Persist intent BEFORE hitting Buffer. If Buffer replies but the process
        # crashes, the pending state blocks double scheduling on retry.
        save_state(state_key,{"status":"submitting","date":date,"slot":slot,"video_url":media_url})
        post=create_buffer_post(media_url,item["caption"],item["dueAt"])
        result={"status":"scheduled","date":date,"slot":slot,"video_url":media_url,"post":post}
        # New immutable receipt: write under separate key to avoid upsert races.
        # A pending state remains; retries fail closed unless manually reconciled.
        save_state(f'{receipt_base}/confirmed.json',result)
        confirmed.append(result)
        print(f"Buffer scheduled: {post['id']} / {item['dueAt']}")
    return confirmed

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",required=True)
    args=parser.parse_args()
    if os.getenv("PUBLISH_ENABLED","").lower()!="true":
        print("PUBLISH_ENABLED=false => no upload, no Buffer post")
        return
    manifest_path=ROOT/"output"/args.date/"manifest.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    schedule_manifest(manifest)

if __name__=="__main__":
    main()
