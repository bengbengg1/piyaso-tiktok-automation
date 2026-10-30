"""Manual R2 -> pretrained VSR -> private R2 preview (never published).

Use with the dedicated GitHub Actions manual workflow. Requires the operator's
explicit commercial-use permission for the footage; original stays unchanged.
"""
from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path

import storage_client
import preview_text_removal

SOURCE_RE = re.compile(r'^backgrounds/([A-Za-z0-9][A-Za-z0-9_.() -]{0,159})\.(mp4|mov|mkv)$', re.I)
# Previously uploaded user test video: use it read-only; NEVER overwrite published objects.
PUBLISHED_RE = re.compile(
    r'^published/piyaso/[0-9]{4}-[0-9]{2}-[0-9]{2}/[0-9]{2}_[0-9]{4}/video\.(?:mp4|mov|mp4\.mov)$', re.I)

RUN_RE = re.compile(r'^[0-9]{1,16}$')


def validate_source_key(key: str) -> str:
    if not (SOURCE_RE.fullmatch(key) or PUBLISHED_RE.fullmatch(key)) or '..' in key or key.startswith('backgrounds/.'):
        raise ValueError('Only an approved video in backgrounds/ or an existing published/piyaso/.../video.* is allowed.')
    storage_client.valid_path(key)
    return key


def private_review_upload(key: str, data: bytes, ctype: str):
    # Deliberately does NOT reuse the public published/ pathway.
    if not re.fullmatch(r'reviews/vsr/[0-9]{8}/[0-9]{1,16}/(?:mask\.png|original\.png|cleaned\.mp4|before_after\.png|review\.json)', key):
        raise ValueError('Only private reviews/vsr destination is allowed')
    bucket = storage_client.bucket_name('assets')
    storage_client.client().put_object(
        Bucket=bucket, Key=key, Body=data, ContentType=ctype, IfNoneMatch='*')


def run_review(source_key: str, region: str, *, review_id: str, run_ai: bool = False, seconds: float = 3.0) -> list[str]:
    validate_source_key(source_key)
    if not RUN_RE.fullmatch(review_id):
        raise ValueError('Invalid workflow run ID')
    reg=preview_text_removal.parse_region(region)
    if seconds < 0.5 or seconds > 10:
        raise ValueError('Manual review is intentionally restricted to 0.5..10 seconds')
    bucket = storage_client.bucket_name('assets')
    with tempfile.TemporaryDirectory(prefix='piyaso-private-vsr-') as tmp:
        root=Path(tmp)
        original=root / ('source.' + source_key.rsplit('.',1)[1].lower())
        content = storage_client.download(bucket,source_key,max_bytes=200*1024*1024)
        if not content:
            raise FileNotFoundError('Requested video is not in private Piyaso backgrounds/ folder')
        original.write_bytes(content)
        out=root/'review'
        report=preview_text_removal.execute(original,out,reg,seconds=seconds,run=run_ai,
                                             width=360,height=640,fps=12)
        import datetime
        date=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')
        dest=f'reviews/vsr/{date}/{review_id}'
        paths=[]
        uploads=[('01_original_frame.png','original.png','image/png'),
                 ('02_mask_review.png','mask.png','image/png'),
                 ('review.json','review.json','application/json')]
        if run_ai:
            if not report['model_used'] or not (out/'04_ai_cleaned_with_original_audio.mp4').is_file():
                raise RuntimeError('VSR has not produced an authentic cleaned video')
            uploads.append(('04_ai_cleaned_with_original_audio.mp4','cleaned.mp4','video/mp4'))
            uploads.append(('05_before_after_ai.png','before_after.png','image/png'))
        for src,name,mime in uploads:
            key=f'{dest}/{name}'
            private_review_upload(key,(out/src).read_bytes(),mime)
            paths.append(key)
        return paths


def main():
    parser=argparse.ArgumentParser(description='Manually review pretrained VSR on private R2 footage')
    parser.add_argument('--source-key',required=True)
    parser.add_argument('--region',required=True,help='Normalized x,y,width,height')
    parser.add_argument('--review-id',default=os.getenv('GITHUB_RUN_ID','1'))
    parser.add_argument('--seconds',type=float,default=3.0)
    parser.add_argument('--run-ai',action='store_true')
    options=parser.parse_args()
    paths=run_review(options.source_key,options.region,review_id=options.review_id,
                     run_ai=options.run_ai,seconds=options.seconds)
    print('Only private R2 keys were written. NOT PUBLIC / NOT SCHEDULED / NOT POSTED:')
    for key in paths: print(key)

if __name__=='__main__':main()
