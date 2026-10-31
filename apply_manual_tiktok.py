#!/usr/bin/env python3
"""Safely switch ONLY Piyaso TikTok to user-managed R2 copy stock.

Run from the root of the existing repository. Deliberately never touches
Groq model modules or secrets; they remain usable by a future Instagram flow.
This is a one-time, strict v24-main migration rather than blind regex rewriting.
"""
from __future__ import annotations

import shutil
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
ROOT = Path.cwd()


def once(value: str, old: str, new: str, label: str) -> str:
    hits = value.count(old)
    if hits != 1:
        raise RuntimeError(f'{label}: 1 expected anchor, found {hits}. Repository version may differ; no files changed.')
    return value.replace(old, new, 1)


def section(value: str, begin: str, end: str, new: str, label: str) -> str:
    if value.count(begin) != 1 or value.count(end) != 1:
        raise RuntimeError(f'{label}: expected unique markers missing. No files changed.')
    start = value.index(begin)
    stop = value.index(end, start + len(begin))
    return value[:start] + new + value[stop:]


def migrate_workflow(raw: str) -> str:
    value = raw
    value = once(value,
        '# v24: GET /models HTTP 403 yalanci engelini kaldir; gerçek Groq yazimi VSR oncesi doğrula.',
        '# v26: TikTok ONLY uses single-use manual copy from private R2; Groq preserved elsewhere.', 'header')
    value = once(value,
        "        description: 'Sadece hizli Groq erisim kontrolu (video isleme yok)'",
        "        description: 'Yalnizca manuel reklam kutuphanesi durumunu goster (video isleme yok)'", 'diagnose description')
    value = once(value,
        "      GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}\n      GROQ_MODEL: ${{ vars.GROQ_MODEL || 'openai/gpt-oss-20b' }}\n",
        '', 'remove TikTok Groq env ONLY')
    status_step = '''      - name: Manuel Piyaso reklam kutuphanesi durumunu goster
        if: ${{ github.event_name == 'workflow_dispatch' && inputs.diagnose_only == true }}
        shell: bash
        run: |
          set -euo pipefail
          python -m pip install 'boto3==1.43.18'
          python manual_copy.py status

'''
    value = section(value,
        '      - name: Groq hizli erisim dogrulamasi (istege bagli, video islenmez)\n',
        '      - name: FFmpeg ve R2 kutuphanelerini kur\n',
        status_step, 'replace model diagnosis with library status')
    value = once(value,
        '      - name: R2 baglantisini dogrula - Groq gerçek reklam adiminda kontrol edilir - YAYIN YOK',
        '      - name: R2 baglantisini ve Piyaso kaydini dogrula - YAYIN YOK', 'R2 precheck label')
    value = once(value,
        '          # live_smoke.py --groq GET /models kullanir. Bu endpoint bazen 403 döndürürken\n          # chat/completions HTTP 200 olabilir. Gerçek Groq reklam istegi VSR oncesi asagida dogrulanir.\n          python live_smoke.py --r2',
        '          # Sadece R2/medya erisimi; TikTok metinleri yalnizca manuel kütüphaneden gelir.\n          python live_smoke.py --r2',
        'remove old model comments')
    value = section(value,
        '      - name: Groq gercek istek HTTP istemcisini duzelt (yalniz runner)\n',
        '      - name: GERCEK Groq reklamlarini once olustur - VSR maliyetinden once\n',
        '', 'remove Groq HTTP mutation')
    value = once(value,
        '      - name: GERCEK Groq reklamlarini once olustur - VSR maliyetinden once',
        '      - name: Yayinlanmamis manuel cumleleri videolara rezerve et - VSR maliyetinden once',
        'reserve-step label')
    value = once(value,
        '          import daily_copy\n          import history_sync\n          import render\n          import storage_client',
        '          import manual_copy\n          import render\n          import storage_client',
        'preflight module imports')
    value = once(value,
        "          # Once kayitli ayni gun metinlerini kullan, yeni Groq istegi yapma.\n          existing=fetch(base+'copy.json')\n          if existing is not None:\n              items=existing.get('items',[])",
        "          # Ayni gunu tekrar calistirirken KESINLIKLE yeni cumle ayirma.\n          existing=fetch(base+'copy.json')\n          if existing is not None:\n              if existing.get('generation_type') != 'manual_library':\n                  raise SystemExit('Bu tarih icin eski Groq metni mevcut. Kaydi degistirmeden durduruldu.')\n              items=existing.get('items',[])",
        'legacy day guard')
    value = section(value,
        '              history_sync.pull()\n              try:\n                  doc=daily_copy.generate_for_day(d)\n',
        "              if [x['source_clip'] for x in sorted(doc['items'],key=lambda x:x['slot'])]",
        '              doc=manual_copy.reserve_for_day(s3, day, selected)\n',
        'reserve manual lines instead of generating AI text')
    value = once(value,
        "              print(f'GERCEK GROQ BASARILI: {count} reklam metni uretildi, ozel R2 kaydi olusturuldu.')",
        "              print(f'MANUEL KUTUPHANE: {count} cumle tekil rezerve edildi, ozel R2 kaydi olusturuldu.')",
        'preflight confirmation')
    value = once(value,
        "              print('Mevcut gunluk Groq metinleri kullaniliyor; tekrar API cagrisi yok.')",
        "              print('Mevcut gunluk manuel reklam metinleri yeniden kullaniliyor.')",
        'retry logging')
    value = once(value,
        "          # Retriede sadece metin kaydi varsa secim de olmali.",
        "          # Tekrarda yalnizca metin kaydi varsa secim de olmali.",
        'retry comment')
    value = once(value,
        "              raise SystemExit('Groq metni var ama gunluk kaynak secimi yok; elle uzlastirma gerekli.')",
        "              raise SystemExit('Manuel metin var ama gunluk kaynak secimi yok; elle uzlastirma gerekli.')",
        'retry error')
    value = once(value,
        '          import render\n          import daily_copy\n          import history_sync\n          import storage_client',
        '          import render\n          import manual_copy\n          import storage_client',
        'daily studio module imports')
    value = once(value,
        "              history_sync.pull()\n              generated=daily_copy.generate_for_day(dt.date.fromisoformat(day))\n              put_once(s3,saved_key,json_bytes(generated),'application/json')\n              return ROOT/'output'/day/'daily_copy.json'",
        "              raise RuntimeError('Manuel cumle rezervasyonu bulunamadi; VSR/render durduruldu. '" \
        "                                 'Once manuel kutuphaneyi doldurup preflight calistirin.')",
        'fail closed on missing manual copy')
    value = once(value,
        "raise RuntimeError('Wrong source mapping between Groq and render slot')",
        "raise RuntimeError('Wrong source mapping between manual copy and render slot')",
        'source mapping message')
    value = once(value,
        "'groq_copy':manifest['copy_source']=='ai_generated',",
        "'manual_copy':manifest['copy_source']=='manual_library',",
        'draft metadata')
    value = once(value,
        "                  # Preserve Groq history across daily ephemeral GitHub Action runners.\n                  history_sync.push(day)",
        "                  # Only completed private MP4 drafts consume the lines.\n                  # Claims survive retries and the used archive blocks all future reuse.\n                  manual_copy.finalize_day(s3, day, json.loads(daily_path.read_text('utf8')))",
        'finalize copy after draft writing')
    value = once(value,
        "'pipeline':'R2 -> scene selection -> VSR OCR -> Groq -> FFmpeg + Piyaso PiP -> private R2'",
        "'pipeline':'R2 -> manual single-use copy -> scene selection -> VSR OCR -> FFmpeg + Piyaso PiP -> private R2'",
        'pipeline metadata')
    value = once(value,
        "              if not os.getenv('GROQ_API_KEY'):\n                  parser.error('GROQ_API_KEY missing: real Groq copy is mandatory')\n",
        '', 'remove Groq mandatory check in TikTok only')
    if 'daily_copy.generate_for_day' in value or 'GROQ_API_KEY' in value or 'history_sync.push' in value or "groq_copy':" in value:
        raise RuntimeError('A Groq trigger remains in TikTok workflow. Aborting without writes.')
    return value


def migrate_render(raw: str) -> str:
    value = raw
    value = once(value,
        '    jobs=pick_jobs(day,clips,config,settings,copy)\n    if daily_copy_path is not None:',
        "    jobs=pick_jobs(day,clips,config,settings,copy)\n    copy_kind = None\n    if daily_copy_path is not None:",
        'render select copy type')
    value = once(value,
        '        if generated.get("date")!=day.isoformat() or generated.get("generation_type")!="ai_generated":\n            raise ValueError("Günlük reklam dosyası tarihi veya türü yanlış")',
        '''        copy_kind = generated.get("generation_type")
        if generated.get("date")!=day.isoformat() or copy_kind not in ("ai_generated", "manual_library"):
            raise ValueError("Günlük reklam dosyası tarihi veya türü yanlış")''',
        'accept manual copy type and preserve old type')
    value = once(value,
        '"copy_source":"ai_generated" if daily_copy_path else "approved_library"',
        '"copy_source":copy_kind if daily_copy_path else "approved_library"',
        'render manifest source')
    return value


def main():
    workflow = ROOT / '.github/workflows/piyaso-daily-studio.yml'
    renderer = ROOT / 'render.py'
    if not workflow.exists() or not renderer.exists():
        raise SystemExit('Komut projedeki ana dizinde calistirilmali (render.py ve workflow olmali).')
    if not (SOURCE / 'manual_copy.py').exists() or not (SOURCE / 'piyaso-manual-library.yml').exists():
        raise SystemExit('Kurulum paketindeki dosyalar eksik: manual_copy.py / piyaso-manual-library.yml')
    destination = ROOT / '.github/workflows/piyaso-manual-library.yml'
    if destination.exists():
        raise SystemExit('Kutuphaneyi yoneten workflow zaten var. Uzerine yazmadan durduruldu.')
    w = migrate_workflow(workflow.read_text('utf-8'))
    r = migrate_render(renderer.read_text('utf-8'))
    import ast
    ast.parse(r, filename='render.py')
    ast.parse((SOURCE / 'manual_copy.py').read_text('utf-8'), filename='manual_copy.py')
    # Plan the whole patch in memory before touching repo.
    workflow.write_text(w, encoding='utf-8')
    renderer.write_text(r, encoding='utf-8')
    original = SOURCE / 'manual_copy.py'
    target = ROOT / 'manual_copy.py'
    if original.resolve() != target.resolve():
        if target.exists():
            raise SystemExit('Hedef manual_copy.py zaten var; degistirilmeyecek.')
        shutil.copyfile(original, target)
    workflow_source = SOURCE / 'piyaso-manual-library.yml'
    if workflow_source.resolve() != destination.resolve():
        shutil.copyfile(workflow_source, destination)
    print('Kurulum tamam: Sadece Piyaso TikTok metinleri MANUEL. Groq altyapisi korundu.')
    print('Degisen: render.py, .github/workflows/piyaso-daily-studio.yml')
    print('Eklenen: manual_copy.py, .github/workflows/piyaso-manual-library.yml')


if __name__ == '__main__':
    main()
