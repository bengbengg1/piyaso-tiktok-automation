"""Example-driven original copy drafts. No hosted API or key required.

Use `--mode prompt` to print the prompt for any LLM, or `--mode ollama`
with an independently hosted Ollama instance to generate unapproved drafts.
Approved copy goes into ad_copy.json via review, never silently to publishing.
"""
from __future__ import annotations
import argparse
import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent

def normalize(s):
    return re.sub(r"\s+"," ",re.sub(r"[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ]+"," ",s.casefold())).strip()

def similar(a,b):
    return SequenceMatcher(None,normalize(a),normalize(b)).ratio()

def create_prompt(category,count,style,existing):
    examples=style["examples"].get(category,[])+style["examples"].get("genel",[])
    previous=[v["headline"] for v in existing.get(category,[])]
    voice=style.get("voice_profile",{})
    return ("Türkçe sosyal medya reklam metni yazarı olarak Piyaso için yeni, kendine özgü cümleler üret. "
            "Yalnızca geçerli JSON döndür: {\"items\":[{\"headline\":\"...\",\"caption\":\"...\"}]}. "
            f"Kategori: {category}. Tam {count} farklı cümle üret. "
            "Örneklerin tonunu ve jargonunu sez, ancak hiçbir örneği kopyalama. "
            "Her başlık en fazla 75 karakter, açıklama en fazla 105 karakter olsun. "
            "Ürünün gerçekten sunduğunu bilmediğin özellik veya sonuç vaadinde bulunma. "
            f"Marka jargonu, yerel bağlam ve kaçınılacak iddialar: {json.dumps(voice,ensure_ascii=False)}. "
            f"Uygulama gerçekleri: {json.dumps(style['allowed_facts'],ensure_ascii=False)}. "
            f"Stil kuralları: {json.dumps(style['style_rules'],ensure_ascii=False)}. "
            f"Kullanıcı örnekleri: {json.dumps(examples,ensure_ascii=False)}. "
            f"Tekrarlanmaması gereken önceki başlıklar: {json.dumps(previous[-60:],ensure_ascii=False)}.")

def validate_drafts(data,category,old):
    if not isinstance(data,dict) or not isinstance(data.get('items'),list):
        raise ValueError('Model JSON items listesi dondurmedi')
    used=[x['headline'] for x in old.get(category,[])]
    result=[]
    for x in data['items']:
        if not isinstance(x,dict): continue
        title=x.get('headline'); caption=x.get('caption')
        if not isinstance(title,str) or not isinstance(caption,str): continue
        if not (10<=len(title)<=75 and 10<=len(caption)<=105): continue
        if any(similar(title,y)>.83 for y in used): continue
        result.append({'headline':title.strip(),'caption':caption.strip(),'review_status':'pending'})
        used.append(title)
    return result

def ollama_generate(prompt,model,base):
    payload=json.dumps({'model':model,'messages':[{'role':'user','content':prompt}],
                        'format':'json','stream':False}).encode()
    url=base.rstrip('/')+'/api/chat'
    if not url.startswith(('http://localhost:','http://127.0.0.1:','https://')):
        raise ValueError('OLLAMA_URL localhost veya guvenilir HTTPS adresi olmali')
    req=Request(url,data=payload,headers={'Content-Type':'application/json'},method='POST')
    with urlopen(req,timeout=240) as resp:
        data=json.loads(resp.read())
    return json.loads(data['message']['content'])

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--category',choices=['araba','karaoke','sarki','genel','yerel','iliski'],required=True)
    p.add_argument('--count',type=int,default=10)
    p.add_argument('--mode',choices=['prompt','ollama'],default='prompt')
    args=p.parse_args()
    if not (1<=args.count<=30): raise ValueError('count 1-30 olmali')
    style=json.loads((ROOT/'style_examples.json').read_text(encoding='utf-8'))
    existing=json.loads((ROOT/'ad_copy.json').read_text(encoding='utf-8'))
    prompt=create_prompt(args.category,args.count,style,existing)
    if args.mode=='prompt':
        print(prompt)
        return
    model=os.getenv('OLLAMA_MODEL','').strip()
    if not model: raise RuntimeError('OLLAMA_MODEL eksik. Yerel Ollama model adini belirtin.')
    data=ollama_generate(prompt,model,os.getenv('OLLAMA_URL','http://localhost:11434'))
    drafts=validate_drafts(data,args.category,existing)
    dest=ROOT/'creative_drafts.json'
    dest.write_text(json.dumps({'category':args.category,'items':drafts},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{len(drafts)} reklam fikri {dest} dosyasina inceleme icin yazildi. Otomatik paylasima eklenmedi.')

if __name__=='__main__': main()
