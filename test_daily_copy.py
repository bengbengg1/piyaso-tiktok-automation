import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import daily_copy
import render


class DailyCopyTests(unittest.TestCase):
    def setUp(self):
        self.date = dt.date(2026, 10, 30)  # Fri: 3 posts
        self.jobs, self.config = daily_copy.planned_jobs(self.date)
        self.style = render.load_json('style_examples.json')
        self.approved = render.load_json('ad_copy.json')

    def fake(self, prompt):
        # Produce independent, explicit Piyaso-linked ideas (not bland car slogans).
        texts = [
            ('Piyaso’ya girdim arkadaşlar yine plan yaptı 😭', 'Biri piyaso mu dedi? #arkadaş'),
            ('SON DAKİKA‼️ Piyaso yüzünden grup karıştı 💀', 'Antalya tayfası burada mı? Piyaso'),
            ('Piyaso’yu duydu bizim ekip yine hazırlandı 😭', 'Bu kez planı kim yapacak? Piyaso'),
        ]
        return {'items': [{'slot': j['index'], 'headline': texts[i][0], 'caption': texts[i][1]}
                          for i, j in enumerate(self.jobs)]}

    def test_monday_generates_two_ads(self):
        date = dt.date(2026, 11, 2)
        jobs, _ = daily_copy.planned_jobs(date)
        self.assertEqual(len(jobs), 2)
        with tempfile.TemporaryDirectory() as tmp:
            titles = [
                'Grup sessizdi, Piyaso adı geçince herkes yazmaya başladı 😭',
                'Annem nereye dediyse Piyaso toplantısı var deyip çıktım 🫣',
            ]
            fake = lambda _: {'items': [
                {'slot': job['index'], 'headline': titles[i],
                 'caption': f'Bugün piyaso dedik bütün ekip geldi #{i}'}
                for i, job in enumerate(jobs)
            ]}
            result = daily_copy.generate_for_day(date, generate=fake, provider='groq',
                                history_path=Path(tmp) / 'history.json', output_root=Path(tmp))
            self.assertEqual(len(result['items']), 2)

    def test_groq_parses_structured_json_response(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self):
                return json.dumps({'choices': [{'message': {'content': '{"items":[]}'}}]}).encode()
        seen = []
        def opener(request, timeout):
            seen.append(json.loads(request.data))
            self.assertTrue(request.full_url.startswith('https://api.groq.com/'))
            return FakeResponse()
        with patch.dict('os.environ', {'GROQ_API_KEY': 'not-a-real-key'}):
            response = daily_copy.request_groq('Yalnızca JSON', opener=opener)
        self.assertEqual(response, {'items': []})
        self.assertEqual(seen[0]['model'], 'openai/gpt-oss-20b')
        self.assertEqual(seen[0]['response_format']['type'], 'json_schema')
        self.assertTrue(seen[0]['response_format']['json_schema']['strict'])
        self.assertEqual(seen[0]['response_format']['json_schema']['schema']['required'], ['items'])

    def test_friday_has_three_ads(self):
        self.assertEqual(len(self.jobs), 3)

    def test_prompt_includes_user_approved_reference(self):
        prompt = daily_copy.make_prompt(self.jobs, self.style, self.approved, [])
        self.assertIn('SON DAKİKA‼️ ANTALYA', prompt)
        self.assertIn('gerçek', prompt.lower())
        self.assertIn('KOPYALAMA', prompt)

    def test_rejects_no_app_connection(self):
        bad = self.fake('')
        bad['items'][0]['headline'] = 'Bu gece yine deli gibi tur attık haha'
        bad['items'][0]['caption'] = 'Herkes bu kadar eğleniyordur'
        with self.assertRaisesRegex(ValueError, 'Piyaso marka adı'):
            daily_copy.validate_result(bad, self.jobs, self.config, self.style, self.approved, [])

    def test_rejects_unsafe_claim(self):
        bad = self.fake('')
        bad['items'][0]['headline'] = 'Piyaso ile exinin konumunu gör hayatını öğren'
        with self.assertRaisesRegex(ValueError, 'takip vaadi'):
            daily_copy.validate_result(bad, self.jobs, self.config, self.style, self.approved, [])

    def test_rejects_repeated_example(self):
        bad = self.fake('')
        bad['items'][0]['headline'] = self.style['explicitly_approved_reference_examples'][1]
        with self.assertRaises(ValueError):
            daily_copy.validate_result(bad, self.jobs, self.config, self.style, self.approved, [])

    def test_no_secret_is_explicit_error(self):
        with patch.dict('os.environ', {'GROQ_API_KEY': ''}):
            with self.assertRaisesRegex(RuntimeError, 'GROQ_API_KEY'):
                daily_copy.request_groq('Test')

    def test_generation_persists_history_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / 'history.json'
            generated = daily_copy.generate_for_day(
                self.date, generate=self.fake, provider='groq', history_path=history,
                output_root=Path(tmp) / 'outputs')
            self.assertEqual(len(generated['items']), 3)
            self.assertEqual(len(daily_copy.history_entries(history)), 3)
            second = daily_copy.generate_for_day(
                self.date, generate=lambda _: self.fail('must reuse history'),
                provider='groq', history_path=history, output_root=Path(tmp) / 'outputs')
            self.assertEqual(second['provider'], 'history_reuse')
            self.assertEqual(second['items'], generated['items'])

    def test_render_consumes_generated_copy(self):
        # Run the full editor through the FFmpeg path at a small render resolution.
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / 'history.json'
            daily_copy.generate_for_day(self.date, generate=self.fake,
                                        history_path=history, output_root=Path(tmp))
            path = Path(tmp) / self.date.isoformat() / 'daily_copy.json'
            # This is a generated-copy test, not an AI inference test. Use
            # explicit legacy mode for its unrelated editing smoke-check.
            original_load = render.load_json
            def test_config(name):
                value = original_load(name)
                if name == 'config.json':
                    value['text_removal'] = {'backend': 'delogo'}
                return value
            with patch.object(render, 'ROOT', Path(__file__).resolve().parents[1]), \
                 patch.object(render, 'load_json', side_effect=test_config):
                manifest = render.render_day(self.date, width=360, height=640, daily_copy_path=path)
            self.assertEqual(manifest['copy_source'], 'ai_generated')
            self.assertEqual([x['headline'] for x in manifest['items']],
                             [x['headline'] for x in json.loads(path.read_text('utf-8'))['items']])

    def test_render_rejects_wrong_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'day.json'
            path.write_text(json.dumps({'date': '2026-09-03', 'generation_type': 'ai_generated', 'items': []}), 'utf-8')
            with self.assertRaisesRegex(ValueError, 'tarihi'):
                render.render_day(self.date, daily_copy_path=path)


if __name__ == '__main__':
    unittest.main()
