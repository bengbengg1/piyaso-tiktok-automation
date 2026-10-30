"""Read-only external service connectivity. Requires user-supplied environment secrets.
NO publishing, uploading, model execution, or Cloudflare changes.
Never dump tokens to terminal or artifacts.
"""
from __future__ import annotations
import argparse
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def groq_check():
    key=os.environ.get('GROQ_API_KEY','').strip()
    if not key: raise RuntimeError('GROQ_API_KEY missing')
    req=Request('https://api.groq.com/openai/v1/models',headers={'Authorization':'Bearer '+key})
    with urlopen(req,timeout=25) as r: data=json.load(r)
    model=os.environ.get('GROQ_MODEL','openai/gpt-oss-20b')
    ids={m['id'] for m in data.get('data',[]) if m.get('id')}
    if model not in ids: raise RuntimeError('Groq key valid but model is not available: '+model)
    return 'API authenticated; configured model listed ('+model+')'


def buffer_check():
    from buffer_setup import list_channels,validate_tiktok_channel
    channels=list_channels()
    target=os.environ.get('BUFFER_CHANNEL_ID','').strip()
    selected=validate_tiktok_channel(target,channels)
    return 'TikTok channel verified: '+selected.get('name','(no display name)')


def r2_check():
    import storage_client
    bucket=storage_client.bucket_name('assets')
    storage_client.check_bucket(bucket,False)
    return 'Dedicated R2 bucket reachable: '+bucket


def worker_check():
    import storage_client
    base=storage_client.public_base()
    # Denied paths are a positive indication that raw assets are NOT exposed.
    for subpath in ('/backgrounds/should-not-leak.mp4','/app_recordings/app_recording.mp4'):
        req=Request(base+subpath,method='HEAD')
        try:
            with urlopen(req,timeout=20) as r: status=r.status
        except HTTPError as ex: status=ex.code
        if status!=404:
            raise RuntimeError('Worker access policy differs; private path returned HTTP '+str(status))
    return 'Worker origin reachable and raw footage paths denied (public video test requires an uploaded output)'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--all',action='store_true',help='Run all read-only external tests')
    for name in ('groq','buffer','r2','worker'):
        parser.add_argument('--'+name,action='store_true')
    args=parser.parse_args()
    funcs={'groq':groq_check,'buffer':buffer_check,'r2':r2_check,'worker':worker_check}
    names=[x for x in funcs if args.all or getattr(args,x)]
    if not names: parser.error('Select --all or at least one service')
    errors=0
    for name in names:
        try: print('OK',name,funcs[name]())
        except Exception as exc:
            errors+=1
            # Error strings deliberately exclude API credentials and request payloads.
            if isinstance(exc,HTTPError): msg='HTTP '+str(exc.code)
            else: msg=str(exc)[:220]
            print('NOT READY',name,msg)
    if errors: raise SystemExit(2)

if __name__=='__main__':main()
