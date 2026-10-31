"""Piyaso TikTok ONLY: user-written, single-use ad-copy stock in PRIVATE Cloudflare R2.

S3 keys:
  state/manual-copy/stock/<sha>.json  -- available or temporarily reserved text
  state/manual-copy/claims/<sha>.json -- immutable reservation by day/slot
  state/manual-copy/used/<sha>.json   -- immutable use audit; stock removed on success

Claim-first prevents another day using the same line even after a failed render.
The day's claim is reused on retry. No Groq, LLM, automatic writing or fallback.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREFIX = 'state/manual-copy/'
STOCK = PREFIX + 'stock/'
CLAIMS = PREFIX + 'claims/'
USED = PREFIX + 'used/'
BUCKET = 'piyaso-tiktok-assets'
DEFAULT_CAPTION = 'Uygulama adı: Piyaso'
MAX_BATCH = 200
MAX_BYTES = 24 * 1024


def encode(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def normalize(line):
    # Punctuation, case, excess whitespace, emojis must not let used lines return.
    line = unicodedata.normalize('NFKC', line).replace('İ', 'i').replace('I', 'ı').casefold()
    line = line.replace('i\u0307', 'i')
    return ' '.join(re.findall(r'[^\W_]+', line, re.UNICODE))


def identifier(headline):
    return hashlib.sha256(normalize(headline).encode('utf-8')).hexdigest()[:32]


def not_found(exc):
    code = str(getattr(exc, 'response', {}).get('Error', {}).get('Code', ''))
    return code in ('NoSuchKey', 'NotFound', '404')


def already_exists(exc):
    code = str(getattr(exc, 'response', {}).get('Error', {}).get('Code', ''))
    return code in ('PreconditionFailed', '412', 'ConditionalRequestConflict', '409')


def get(s3, key):
    try:
        response = s3.get_object(Bucket=BUCKET, Key=key)
    except Exception as exc:
        if not_found(exc):
            return None
        raise
    if response.get('ContentLength', 0) > MAX_BYTES:
        response['Body'].close()
        raise ValueError('Reklam kütüphanesinde çok büyük JSON nesnesi: ' + key)
    payload = response['Body'].read(MAX_BYTES + 1)
    response['Body'].close()
    if len(payload) > MAX_BYTES:
        raise ValueError('Reklam nesnesi fazla büyük: ' + key)
    return json.loads(payload)


def keys(s3, prefix):
    results = []
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket=BUCKET, Prefix=prefix):
        for item in page.get('Contents', []):
            key = item.get('Key', '')
            if key.startswith(prefix) and key.endswith('.json'):
                results.append((key, item.get('LastModified', dt.datetime.min.replace(tzinfo=dt.timezone.utc))))
    return sorted(results, key=lambda row: (row[1], row[0]))


def put_once(s3, key, record):
    try:
        s3.put_object(Bucket=BUCKET, Key=key, Body=encode(record),
                      ContentType='application/json', IfNoneMatch='*')
        return True
    except Exception as exc:
        if already_exists(exc):
            return False
        raise


def parse_batch(content):
    """One sentence per line, or `headline || caption`; or a JSON list."""
    content = content.strip().lstrip('\ufeff')
    if not content:
        raise ValueError('Liste boş. Her satıra bir reklam cümlesi yazın.')
    if content.startswith('['):
        items = json.loads(content)
        if not isinstance(items, list):
            raise ValueError('JSON içinde liste olmalı')
        rows = []
        for item in items:
            if isinstance(item, str):
                rows.append((item, DEFAULT_CAPTION))
            elif isinstance(item, dict):
                rows.append((item.get('headline'), item.get('caption') or DEFAULT_CAPTION))
            else:
                raise ValueError('Her öğe metin veya headline/caption nesnesi olmalı')
    else:
        rows = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            # Support numbered lists without altering ordinary text.
            line = re.sub(r'^\s*(?:\d{1,3}[.)]|[-*])\s+', '', line)
            if line.casefold().startswith(('uygulama adı:', 'uygulama adi:')):
                if not rows:
                    raise ValueError('Önce reklam cümlesi, sonra uygulama adı yazılmalı')
                title, caption = rows[-1]
                if caption != DEFAULT_CAPTION:
                    raise ValueError('Bir reklamın açıklaması iki kez verilmiş')
                rows[-1] = (title, line)
            elif ' || ' in line:
                title, caption = line.split(' || ', 1)
                rows.append((title, caption))
            else:
                rows.append((line, DEFAULT_CAPTION))
    if not 1 <= len(rows) <= MAX_BATCH:
        raise ValueError(f'Bir seferde 1-{MAX_BATCH} reklam girilebilir')
    results = []
    seen = set()
    for index, (title, caption) in enumerate(rows, 1):
        if not isinstance(title, str) or not isinstance(caption, str):
            raise ValueError(f'{index}. satırda metin bekleniyordu')
        # Preserve the user's spelling and emoji; don't rewrite creative copy.
        title, caption = title.strip(), caption.strip()
        # JSON girdisinde kullanıcıya ait çok satırlı TikTok metni korunur.
        # Render katmanı kelime sınırlarından otomatik satır kaydırır.
        if '\r' in title or '\r' in caption or '\n' in caption:
            raise ValueError(f'{index}. metinde desteklenmeyen satır sonu var')
        if not 10 <= len(title) <= 220:
            raise ValueError(f'{index}. reklam 10-220 karakter arasında olmalı')
        if not 1 <= len(caption) <= 105:
            raise ValueError(f'{index}. açıklama 1-105 karakter arasında olmalı')
        norm = normalize(title)
        if len(norm) < 8:
            raise ValueError(f'{index}. reklam çok kısa / anlamsız')
        fingerprint = identifier(title)
        if fingerprint in seen:
            raise ValueError(f'{index}. cümle aynı pakette tekrar edilmiş')
        seen.add(fingerprint)
        results.append({'id': fingerprint, 'headline': title, 'caption': caption})
    return results


def check_renderable(item):
    """Reject text that cannot fit actual 720p TikTok layout before stock addition."""
    import render
    from PIL import Image, ImageDraw
    cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    hbox = cfg['headline_box']
    w, h = 720, 1280
    margin = max(6, int(w * .015))
    width = int(w * hbox['width']) - 2 * margin
    height = int(h * hbox['height']) - 2 * margin
    try:
        render.fit_lines(ImageDraw.Draw(Image.new('RGB', (8, 8))), item['headline'],
                         width, height, max_lines=5, suggested=max(22, int(w * .07)))
    except ValueError as exc:
        raise ValueError('Bu yazı 720p videoya sığmıyor; kısaltın: ' + item['headline']) from exc
    if len(item['caption'] + ' ' + cfg['hashtags']) > 150:
        raise ValueError('Bu açıklama etiketlerle birlikte 150 karakteri aşıyor')


def import_batch(s3, content, *, verify_layout=True):
    parsed = parse_batch(content)
    if verify_layout:
        for item in parsed:
            check_renderable(item)
    # All input is validated before the first write.
    count = {'added': 0, 'already_available': 0, 'already_used_or_reserved': 0}
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for item in parsed:
        id_ = item['id']
        if get(s3, CLAIMS + id_ + '.json') is not None or get(s3, USED + id_ + '.json') is not None:
            count['already_used_or_reserved'] += 1
            continue
        entry = {'schema': 1, 'id': id_, 'headline': item['headline'],
                 'caption': item['caption'], 'added_at': now}
        if put_once(s3, STOCK + id_ + '.json', entry):
            count['added'] += 1
        else:
            count['already_available'] += 1
    return count


def _all_claims(s3):
    claims = {}
    for key, _ in keys(s3, CLAIMS):
        item = get(s3, key)
        if item is None:
            raise RuntimeError('Talep edilen reklam rezervasyonu kayboldu: ' + key)
        claims[item['id']] = item
    return claims


def status(s3):
    claims = _all_claims(s3)
    used_ids = {key[len(USED):-5] for key, _ in keys(s3, USED)}
    stock = keys(s3, STOCK)
    return {'available': sum(1 for key, _ in stock if key[len(STOCK):-5] not in claims),
            'reserved': sum(1 for id_ in claims if id_ not in used_ids),
            'used': len(used_ids)}


def list_available(s3):
    claims = _all_claims(s3)
    results = []
    for key, _ in keys(s3, STOCK):
        id_ = key[len(STOCK):-5]
        if id_ in claims or get(s3, USED + id_ + '.json') is not None:
            continue
        item = get(s3, key)
        if item is not None:
            results.append({'id': id_, 'headline': item['headline'], 'caption': item['caption']})
    return results


def reserve_for_day(s3, day, selected):
    """Atomic, retry-safe assignment. `selected` are preflight's ordered video dicts."""
    dt.date.fromisoformat(day)
    names = [p['name'] for p in selected]
    if not names or len(set(names)) != len(names):
        raise ValueError('Her slot için farklı kaynak video gerekli')
    claims = _all_claims(s3)
    assigned = {}
    for claim in claims.values():
        if claim.get('date') == day:
            slot = claim.get('slot')
            if not isinstance(slot, int) or not 1 <= slot <= len(names):
                raise RuntimeError('Önceki günlük metin rezervasyonu güncel planla uyuşmuyor')
            if slot in assigned or claim.get('source_clip') != names[slot - 1]:
                raise RuntimeError('Önceki günlük cümle ile video eşleşmesi değişmiş')
            assigned[slot] = claim
    free = []
    for key, _ in keys(s3, STOCK):
        id_ = key[len(STOCK):-5]
        if id_ in claims:
            continue
        record = get(s3, key)
        if record is not None:
            free.append(record)
    missing = len(names) - len(assigned)
    if len(free) < missing:
        raise RuntimeError(f'Reklam cümlesi yetersiz: gereken {missing}, kullanılabilir {len(free)}. '
                           'Yeni cümle eklenene kadar günlük video üretilmez.')
    used_this_round = set()
    for slot, name in enumerate(names, 1):
        if slot in assigned:
            continue
        for item in free:
            id_ = item['id']
            if id_ in used_this_round:
                continue
            claim = {'schema': 1, 'id': id_, 'date': day, 'slot': slot,
                     'source_clip': name, 'headline': item['headline'], 'caption': item['caption']}
            if put_once(s3, CLAIMS + id_ + '.json', claim):
                assigned[slot] = claim
                used_this_round.add(id_)
                break
            existing = get(s3, CLAIMS + id_ + '.json')
            if existing == claim:
                assigned[slot] = existing
                used_this_round.add(id_)
                break
        if slot not in assigned:
            raise RuntimeError('Eşzamanlı rezervasyon nedeniyle yeni reklam kalmadı; güvenli durduruldu')
    return {'date': day, 'provider': 'manual', 'model': None,
            'generation_type': 'manual_library',
            'items': [{'slot': slot, 'category': 'genel', 'source_clip': names[slot-1],
                       'library_id': assigned[slot]['id'], 'headline': assigned[slot]['headline'],
                       'caption': assigned[slot]['caption']} for slot in range(1, len(names)+1)]}


def finalize_day(s3, day, document):
    """Only after the day's video drafts exist: archive use then physically delete stock."""
    if document.get('date') != day or document.get('generation_type') != 'manual_library':
        raise ValueError('Günlük kayıt manuel kütüphane değil veya tarihi yanlış')
    count = 0
    for item in document['items']:
        id_ = item['library_id']
        claim = get(s3, CLAIMS + id_ + '.json')
        if (claim is None or claim.get('date') != day or claim.get('slot') != item['slot']
                or claim.get('source_clip') != item['source_clip']
                or claim.get('headline') != item['headline']):
            raise RuntimeError('Reklam kullanım kaydı ile rezervasyon eşleşmiyor')
        used_record = {**claim, 'status': 'used_in_private_video'}
        if not put_once(s3, USED + id_ + '.json', used_record):
            if get(s3, USED + id_ + '.json') != used_record:
                raise RuntimeError('Reklam daha önce farklı biçimde kullanılmış')
        s3.delete_object(Bucket=BUCKET, Key=STOCK + id_ + '.json')
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description='Manuel Piyaso TikTok cümle kütüphanesi (R2)')
    sub = parser.add_subparsers(dest='action', required=True)
    add = sub.add_parser('import', help='Her satır bir cümle; isteğe bağlı cümle || açıklama')
    source = add.add_mutually_exclusive_group(required=True)
    source.add_argument('--file', type=Path)
    source.add_argument('--stdin', action='store_true')
    sub.add_parser('status', help='Kullanılabilir / ayrılmış / tüketilmiş sayıları')
    sub.add_parser('list', help='Kütüphanede kullanılabilir cümleleri göster')
    args = parser.parse_args()
    import storage_client
    s3 = storage_client.client()
    if args.action == 'status':
        print(json.dumps(status(s3), ensure_ascii=False, indent=2))
        return
    if args.action == 'list':
        print(json.dumps(list_available(s3), ensure_ascii=False, indent=2))
        return
    if args.stdin:
        import sys
        raw = sys.stdin.read()
    else:
        raw = args.file.read_text(encoding='utf-8')
    result = import_batch(s3, raw)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print('Güncel durum:', json.dumps(status(s3), ensure_ascii=False))


if __name__ == '__main__':
    main()
