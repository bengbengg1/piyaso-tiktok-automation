"""Piyaso R2 storage: ONE dedicated bucket, three strictly isolated prefixes.

Existing user credential grants object read/write ONLY to piyaso-tiktok-assets.
No operations target Davethemen / Piyaso music buckets. Worker exposes ONLY
published/piyaso/... mp4 objects; all raw footage and receipts remain private.
"""
from __future__ import annotations
import os
import re
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

BUCKET = 'piyaso-tiktok-assets'
PUBLIC_KEY = re.compile(r'^published/piyaso/\d{4}-\d{2}-\d{2}/\d{2}_\d{4}/video\.mp4$')
STATE_KEY = re.compile(r'^state/piyaso/\d{4}-\d{2}-\d{2}/\d{2}_\d{4}/(?:submission|confirmed)\.json$')
COPY_KEY = re.compile(r'^state/copy/\d{4}-\d{2}-\d{2}\.json$')


def env(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value: raise RuntimeError(f'{name} eksik (secret/variable)')
    return value


def bucket_name(kind: str) -> str:
    if kind not in ('assets','state','public'):
        raise ValueError('Invalid R2 storage role')
    name = os.getenv('R2_ASSETS_BUCKET', BUCKET).strip()
    if name != BUCKET:
        raise ValueError('Only dedicated piyaso-tiktok-assets bucket is permitted; Davethemen must remain isolated')
    # All roles intentionally use the SAME dedicated bucket, different prefixes.
    return name


def check_isolation() -> dict[str,str]:
    name=bucket_name('assets')
    return {'assets':name,'state':name,'public':name}


def endpoint() -> str:
    value = os.getenv('R2_ENDPOINT','').strip()
    if not value:
        value = f'https://{env("R2_ACCOUNT_ID")}.r2.cloudflarestorage.com'
    parts=urlsplit(value)
    host=(parts.hostname or '').lower()
    if (parts.scheme!='https' or not host.endswith('.r2.cloudflarestorage.com')
            or parts.path not in ('','/') or parts.query or parts.fragment or parts.username or parts.password
            or parts.port not in (None,443)):
        raise RuntimeError('R2_ENDPOINT must be an official HTTPS R2 S3 endpoint')
    return value.rstrip('/')


def public_base() -> str:
    value=env('R2_PUBLIC_BASE_URL').rstrip('/')
    parts=urlsplit(value)
    host=(parts.hostname or '').lower()
    if (parts.scheme!='https' or not host or host in ('localhost',)
            or host.endswith('.r2.cloudflarestorage.com') or parts.username or parts.password
            or parts.port not in (None,443) or parts.query or parts.fragment):
        raise RuntimeError('R2_PUBLIC_BASE_URL must be a public HTTPS URL, NOT the S3 endpoint')
    return value


def valid_path(path: str) -> str:
    if (not isinstance(path,str) or not path or path.startswith('/')
            or any(part in ('','.','..') for part in path.split('/'))
            or any(ord(c)<32 for c in path) or '\\' in path):
        raise ValueError('Invalid object key')
    return path


def public_url(bucket: str, path: str) -> str:
    if bucket != BUCKET or not PUBLIC_KEY.fullmatch(valid_path(path)):
        raise ValueError('Only the approved final MP4 path may produce a public link')
    # Worker URL omits the private storage-level 'published/' prefix.
    return public_base()+'/'+quote(path[len('published/'):],safe='/')


def client():
    check_isolation()
    import boto3
    from botocore.config import Config
    return boto3.client('s3',endpoint_url=endpoint(),region_name='auto',
        aws_access_key_id=env('R2_ACCESS_KEY_ID'),aws_secret_access_key=env('R2_SECRET_ACCESS_KEY'),
        config=Config(signature_version='s3v4',s3={'addressing_style':'path'},
                      connect_timeout=15,read_timeout=120,retries={'max_attempts':2,'mode':'standard'}))


def _missing(error) -> bool:
    from botocore.exceptions import ClientError
    return isinstance(error,ClientError) and str(error.response.get('Error',{}).get('Code')) in (
        'NoSuchKey','NotFound','404','NoSuchBucketObject')


def upload(bucket: str, path: str, data: bytes, ctype: str) -> str | None:
    if bucket!=BUCKET:raise ValueError('R2 write outside Piyaso bucket is forbidden')
    valid_path(path)
    if PUBLIC_KEY.fullmatch(path):
        if ctype!='video/mp4':raise ValueError('Final ad must be MP4')
        is_public=True
    elif STATE_KEY.fullmatch(path) or COPY_KEY.fullmatch(path):
        if ctype!='application/json':raise ValueError('Receipt must be JSON')
        is_public=False
    else:
        raise ValueError('Writes permitted only under state/piyaso or published/piyaso exact paths')
    client().put_object(Bucket=bucket,Key=path,Body=data,ContentType=ctype,IfNoneMatch='*')
    return public_url(bucket,path) if is_public else None


def download(bucket: str, path: str, *, max_bytes: int=80*1024*1024) -> bytes | None:
    if bucket!=BUCKET:raise ValueError('R2 read outside Piyaso bucket is forbidden')
    valid_path(path)
    try: resp=client().get_object(Bucket=bucket,Key=path)
    except Exception as err:
        if _missing(err):return None
        raise
    if resp.get('ContentLength',0)>max_bytes:
        resp['Body'].close();raise ValueError('Object exceeds download size limit')
    stream=resp['Body']
    try:
        content=stream.read(max_bytes+1)
        if len(content)>max_bytes:raise ValueError('Object exceeds download size limit')
        return content
    finally:stream.close()


def exists(bucket: str, path: str) -> bool:
    if bucket!=BUCKET:raise ValueError('Invalid bucket')
    valid_path(path)
    try:client().head_object(Bucket=bucket,Key=path);return True
    except Exception as err:
        if _missing(err):return False
        raise


def list_objects(bucket: str, prefix: str='') -> list[dict]:
    if bucket!=BUCKET:raise ValueError('Invalid bucket')
    if prefix:
        valid_path(prefix.rstrip('/'))
        if prefix not in ('backgrounds/','app_recordings/','state/copy/'):
            raise ValueError('Only input media prefixes can be listed')
    result=[]
    for page in client().get_paginator('list_objects_v2').paginate(Bucket=bucket,Prefix=prefix):
        for item in page.get('Contents',[]):
            key=item['Key']
            if key.startswith(prefix):
                rel=key[len(prefix):]
                if rel and '/' not in rel and rel not in ('.','..'):
                    result.append({'name':rel,'key':key,'size':item.get('Size',0)})
    return result


def check_bucket(bucket: str, expected_public: bool):
    if bucket!=BUCKET:raise ValueError('Invalid bucket')
    client().head_bucket(Bucket=bucket)
    if expected_public:public_base()
    return {'bucket':bucket,'s3_access':True,'worker_public_reachability_not_yet_verified':True}


def verify_public_access(url: str) -> None:
    base=public_base()+'/'
    if not url.startswith(base) or not url.endswith('/video.mp4'):
        raise ValueError('Unexpected media URL outside Worker origin')
    try:
        with urlopen(Request(url,method='HEAD'),timeout=30) as res:
            if res.status not in (200,206):raise RuntimeError(f'Public file inaccessible: HTTP {res.status}')
            if res.headers.get('Content-Type','').split(';')[0].lower()!='video/mp4':
                raise RuntimeError('Unexpected public media content type')
    except HTTPError as err:
        raise RuntimeError(f'Buffer cannot fetch media: HTTP {err.code}') from err
