"""Promote previously-reviewed Piyaso draft ad IDs into the publishing library.

Usage: python approve_copies.py --list
       python approve_copies.py --approve 1 3 12
This never publishes to Buffer or TikTok.
"""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def read(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8'))

def approve(ids, candidates, approved):
    ids=set(ids)
    available=set(range(1,len(candidates['items'])+1))
    if not ids or not ids.issubset(available):
        raise ValueError('Onay IDs 1 ile aday sayısı arasında olmalı')
    added=[]
    for n,item in enumerate(candidates['items'],1):
        if n not in ids:continue
        if item['review_status'] == 'approved':continue
        key=item['category']
        current=approved.setdefault(key,[])
        if not any(it['headline']==item['headline'] for it in current):
            current.append({'headline':item['headline'],'caption':item['caption']})
            added.append(n)
        item['review_status']='approved'
    return added

def main():
    p=argparse.ArgumentParser()
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--list',action='store_true')
    group.add_argument('--approve',type=int,nargs='+')
    args=p.parse_args()
    can=read('candidate_ads.json')
    if args.list:
        for i,item in enumerate(can['items'],1):
            print(f"{i:>2}. [{item['category']}] {item['headline']} [{item['review_status']}]")
        return
    ap=read('ad_copy.json')
    changed=approve(args.approve,can,ap)
    (ROOT/'candidate_ads.json').write_text(json.dumps(can,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'ad_copy.json').write_text(json.dumps(ap,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{len(changed)} yeni söz onaylanarak yayın kütüphanesine eklendi. Yayın yapılmadı.')

if __name__=='__main__':main()
