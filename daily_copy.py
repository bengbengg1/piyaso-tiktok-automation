"""Generate original, Piyaso-specific ads for the actual clips scheduled today.

Daily GitHub Actions invokes this BEFORE rendering; its JSON is consumed by
render.py, so the model is a real production dependency rather than a draft
utility. Requires GROQ_API_KEY or a reachable private Ollama service.

Never claims a generation succeeded when the model or quality gate failed.
No API secrets are stored in artifacts, logs, or the repository.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import render

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / 'data/generated_history.json'
GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
DEFAULT_MODEL = 'openai/gpt-oss-20b'


def normalize(value: str) -> str:
    return ' '.join(re.findall(r'[a-z0-9çğıöşü]+', value.casefold()))


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def history_entries(path=HISTORY):
    if not Path(path).exists():
        return []
    data = json.loads(Path(path).read_text('utf-8'))
    entries = data.get('entries', [])
    if not isinstance(entries, list):
        raise ValueError('Reklam geçmişi bozuk')
    return entries


def planned_jobs(day):
    config = render.load_json('config.json')
    settings = render.load_json('clip_settings.json')
    approved = render.load_json('ad_copy.json')
    clips = [p for p in (ROOT / config['background_dir']).iterdir()
             if p.is_file() and p.suffix.casefold() in ('.mp4', '.mov', '.mkv')]
    jobs = render.pick_jobs(day, clips, config, settings, approved)
    return jobs, config


def make_prompt(jobs, style, approved, previous, attempt=0):
    """Reference examples, not memorized slogans; request a real joke-to-app link."""
    by_category = style['examples']
    refs = []
    # All main videos belong to one pool; copy style is not tied to genre.
    refs.extend(by_category.get('genel', [])[:8])
    refs.extend(style.get('explicitly_approved_reference_examples', []))
    refs = list(dict.fromkeys(refs))
    disallowed = [e.get('headline', '') for e in previous[-160:]]
    disallowed += [x.get('headline', '') for items in approved.values() for x in items]
    disallowed += style.get('explicitly_approved_reference_examples', [])
    jobs_spec = [{'slot': j['index'], 'video_name_hint': j['clip'].stem[:60]} for j in jobs]
    return (f'Piyaso adlı Antalya otomobil-sosyalleşme temalı uygulama için TAM {len(jobs)} '
            'özgün, Türkçe TikTok reklam fikri yaz. Yalnız geçerli JSON döndür: '
            '{"items":[{"slot":1,"headline":"...","caption":"..."}]}. '
            f'GÜNÜN GERÇEK VİDEO SIRASI: {json.dumps(jobs_spec, ensure_ascii=False)}. '
            'Her slot için tam BİR ayrı fikir üret. slot değerleri bu listedekilerle aynı olsun. '
            'Her headline 12-75 karakter, caption 10-105 karakter olsun. '
            'Her cümlede önce doğal bir OLAY / dedikodu / flört / arkadaş muhabbeti / yarı ciddi son dakika haberi olsun; '
            'sonra Piyaso uygulamasıyla organik ve komik bir bağlantı kurulsun. '
            'Sırf Konyaaltı + araba + tur kelimelerini yan yana getirip anlamsız slogan yazma. '
            'Uygulama ismi headline veya caption içinde mutlaka Piyaso olarak geçsin. '
            'Her video farklı açılış kalıbı kullansın; her seferinde KONYAALTI veya KIZLAR KOŞUN kullanma. '
            'Ana videoları türlere ayırma; gerektiğinde videonun atmosferine uygun sosyal durum düşün, videoda bulunmayan olayları gerçek haber gibi kesin iddia etme. '
            'İzin olmadan konum takibi, eski sevgiliyi gözetleme, profilden özel bilgi edinme, '
            'kesin tanışma/kişiyi bulma garantisi yazma. İşlevini bilmediğin özellikleri uydurma. '
            'Eğlenceli, hafif abartılı TikTok jargonu ve doğal noktalama/emoji uygundur. '
            'Başlığa hashtag koyma; caption kısa ve farklı olsun. '
            f'SOMUT MARKA BİLGİSİ: {json.dumps(style.get("allowed_facts", []), ensure_ascii=False)}. '
            f'KULLANICININ BEĞENDİĞİ ÜSLUP ÖRNEKLERİ (KOPYALAMA!): {json.dumps(refs, ensure_ascii=False)}. '
            f'ASLA TEKRARLAMA (ÖNCEDEN YAYINLANANLAR): {json.dumps(disallowed[-200:], ensure_ascii=False)}. '
            f'TEKRAR / DÜZELTME TURU: {attempt}. Sadece JSON yaz.')


def request_groq(prompt, *, opener=urlopen, model=None):
    token = os.environ.get('GROQ_API_KEY', '').strip()
    if not token:
        raise RuntimeError('GROQ_API_KEY eksik; otomatik reklam oluşturma çalıştırılamaz.')
    payload = json.dumps({
        'model': model or os.environ.get('GROQ_MODEL', DEFAULT_MODEL),
        'messages': [
            {'role': 'system', 'content': 'Türkiye TikTok kültürüne hakim yaratıcı reklam yazarı. Çıktın yalnızca doğru JSON.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.9,
        'reasoning_effort': 'low',
        'include_reasoning': False,
        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'piyaso_ads', 'strict': True, 'schema': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'items': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False,
                'properties': {'slot': {'type': 'integer'}, 'headline': {'type': 'string'}, 'caption': {'type': 'string'}},
                'required': ['slot', 'headline', 'caption']}}},
            'required': ['items']} }},
        'max_completion_tokens': 2200,
        'stream': False
    }, ensure_ascii=False).encode('utf-8')
    req = Request(GROQ_ENDPOINT, data=payload, method='POST',
                  headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    with opener(req, timeout=90) as response:
        reply = json.loads(response.read())
    try:
        return json.loads(reply['choices'][0]['message']['content'])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Groq geçerli JSON reklam listesi döndürmedi') from exc


def request_ollama(prompt, *, opener=urlopen):
    model = os.getenv('OLLAMA_MODEL', '').strip()
    if not model:
        raise RuntimeError('OLLAMA_MODEL eksik')
    base = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
    parsed = urlparse(base)
    if not (parsed.scheme == 'https' or
            (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1'))):
        raise ValueError('Ollama bağlantısı için yalnızca HTTPS veya yerel bağlantı kabul edilir')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('OLLAMA_URL yalnızca kök sunucu adresi olmalı')
    payload = json.dumps({'model': model, 'messages': [{'role': 'user', 'content': prompt}],
                          'format': 'json', 'stream': False}).encode('utf-8')
    req = Request(base + '/api/chat', data=payload, method='POST',
                  headers={'Content-Type': 'application/json'})
    with opener(req, timeout=240) as response:
        reply = json.loads(response.read())
    try:
        return json.loads(reply['message']['content'])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Ollama geçerli JSON üretmedi') from exc


# Detection deliberately errs on the side of not publishing a questionable claim.
HIGH_RISK = re.compile(
    r'\b(?:stalk\w*|gizlice\s+(?:takip|izle)|(?:ex|eski sevgili)\w*\s+(?:takip|izle)|'
    r'kimlerle\s+(?:olduğunu|gezdigini|gezdiğini)|canlı\s+konum\w*|'
    r'konumunu\s+(?:gör|bul|takip)|garanti\s+(?:tanış|buluş)|'
    r'herkesi\s+bul\w*|kesin\s+(?:bul|tanış))\b', re.IGNORECASE)
GENERIC = ['otomobil tutkunlarının buluşma noktası', 'araba tutkusu sadece sürmekle bitmez',
           'her arabanın bir hikâyesi var', 'konyaaltı biz konyaaltını ezberledik',
           'bir tur daha dedik antalya turu çıktı']


def validate_result(payload, jobs, config, style, approved, history):
    if not isinstance(payload, dict) or not isinstance(payload.get('items'), list):
        raise ValueError('Model çıktısı items listesi içermiyor')
    entries = payload['items']
    if len(entries) != len(jobs):
        raise ValueError(f'{len(jobs)} reklam bekleniyordu; {len(entries)} üretildi')
    expected = {j['index']: j for j in jobs}
    seen = set()
    prior = [entry.get('headline', '') for entry in history]
    prior += [x.get('headline', '') for v in approved.values() for x in v]
    # Ref examples aren't for literal recycling; strong duplicates should fail.
    prior += style.get('explicitly_approved_reference_examples', [])
    results = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError('Reklam öğesi nesne değil')
        slot, title, caption = item.get('slot'), item.get('headline'), item.get('caption')
        if type(slot) is not int or slot not in expected or slot in seen:
            raise ValueError('Slot eksik, tekrarlı veya tanımsız')
        if not isinstance(title, str) or not isinstance(caption, str):
            raise ValueError('Başlık veya açıklama metin değil')
        title, caption = ' '.join(title.split()).strip(), ' '.join(caption.split()).strip()
        if not (12 <= len(title) <= 75 and 10 <= len(caption) <= 105):
            raise ValueError(f'{slot}: başlık veya açıklama uzunluk sınırını aşıyor')
        if len(caption + ' ' + config['hashtags']) > 150:
            raise ValueError(f'{slot}: Buffer açıklaması çok uzun')
        if 'piyaso' not in (title + ' ' + caption).casefold():
            raise ValueError(f'{slot}: Piyaso marka adı bulunamadı')
        if HIGH_RISK.search(title + ' ' + caption):
            raise ValueError(f'{slot}: doğrulanmamış konum/kişisel takip vaadi')
        if any(normalize(s) in normalize(title) for s in GENERIC):
            raise ValueError(f'{slot}: beğenilmeyen jenerik slogan')
        if any(similarity(title, s) >= .80 for s in prior if s):
            raise ValueError(f'{slot}: önceki reklam veya referansla fazla benzer')
        prior.append(title)
        results.append({'slot': slot, 'category': expected[slot]['category'],
                        'source_clip': expected[slot]['clip'].name,
                        'headline': title, 'caption': caption})
        seen.add(slot)
    return sorted(results, key=lambda r: r['slot'])


def generate_for_day(day, *, provider=None, generate=None, history_path=HISTORY, output_root=None,
                     attempts=3):
    jobs, config = planned_jobs(day)
    style = render.load_json('style_examples.json')
    approved = render.load_json('ad_copy.json')
    old = history_entries(history_path)
    # Retries must reuse exactly the same copy to avoid accidental duplicate ideas.
    same_day = [x for x in old if x.get('date') == day.isoformat()]
    if same_day:
        lookup = {x.get('slot'): x for x in same_day}
        if len(same_day) != len(jobs) or set(lookup) != {x['index'] for x in jobs}:
            raise ValueError('Bu tarih için eksik/tutarsız geçmiş mevcut; otomatik yeniden üretim durduruldu')
        for job in jobs:
            item = lookup[job['index']]
            if item.get('source_clip') != job['clip'].name or item.get('category') != job['category']:
                raise ValueError('Bu tarihin video seçimi geçmişle uyuşmuyor; otomatik yeniden üretim durduruldu')
        result = [{k: x[k] for k in ('slot', 'category', 'source_clip', 'headline', 'caption')}
                  for x in sorted(same_day, key=lambda z: z['slot'])]
        output_dir = Path(output_root) if output_root else ROOT / config['output_dir']
        destination = output_dir / day.isoformat()
        destination.mkdir(parents=True, exist_ok=True)
        # No API call when retrying. Original provider is not known from history,
        # so do not pretend that this was a new inference.
        doc = {'date': day.isoformat(), 'provider': 'history_reuse', 'model': None,
               'generation_type': 'ai_generated', 'items': result}
        (destination / 'daily_copy.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', 'utf-8')
        print(f'Daha önce oluşturulmuş {len(result)} reklam yeniden kullanıldı: {day}')
        return doc
    provider = (provider or os.getenv('COPY_PROVIDER', 'groq')).lower()
    if provider not in ('groq', 'ollama'):
        raise ValueError('COPY_PROVIDER sadece groq veya ollama olabilir')
    generator = generate or (request_groq if provider == 'groq' else request_ollama)
    errors = []
    for attempt in range(attempts):
        prompt = make_prompt(jobs, style, approved, old, attempt=attempt)
        if errors:
            prompt += ' ÖNCEKİ YANITIN HATALARI: ' + '; '.join(errors[-2:])
        try:
            data = generator(prompt)
            result = validate_result(data, jobs, config, style, approved, old)
            break
        except ValueError as exc:
            errors.append(str(exc))
    else:
        raise RuntimeError('Günlük yapay zekâ reklamları kalite kontrolünü geçemedi: ' + '; '.join(errors))
    output_dir = Path(output_root) if output_root else ROOT / config['output_dir']
    destination = output_dir / day.isoformat()
    destination.mkdir(parents=True, exist_ok=True)
    daily_file = destination / 'daily_copy.json'
    document = {'date': day.isoformat(), 'provider': provider,
                'model': (os.environ.get('GROQ_MODEL', DEFAULT_MODEL) if provider == 'groq'
                          else os.environ.get('OLLAMA_MODEL', '')),
                'generation_type': 'ai_generated', 'items': result}
    daily_file.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    updated = {'entries': (old + [dict(item, date=day.isoformat()) for item in result])[-1000:]}
    history_path = Path(history_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    # Generated copy must persist between ephemeral daily GitHub Actions runners.
    history_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Yapay zekâdan {len(result)} farklı Piyaso reklamı üretildi: {daily_file}')
    return document


def main():
    parser = argparse.ArgumentParser(description='Günlük video klipleri için yeni Piyaso reklam metinleri üret')
    parser.add_argument('--date', default=dt.date.today().isoformat())
    parser.add_argument('--provider', choices=('groq', 'ollama'))
    args = parser.parse_args()
    generate_for_day(dt.date.fromisoformat(args.date), provider=args.provider)


if __name__ == '__main__':
    main()
