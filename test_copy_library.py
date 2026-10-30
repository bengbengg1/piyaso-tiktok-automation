import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import render
import creative_copy
import approve_copies

ROOT=Path(__file__).resolve().parents[1]

class BrandVoiceTests(unittest.TestCase):
    def test_28_original_samples_preserved(self):
        style=json.loads((ROOT/'style_examples.json').read_text('utf-8'))
        samples=style['user_supplied_examples']
        self.assertEqual(len(samples),28)
        self.assertTrue(any('exleri unutucaz' in x['text'] for x in samples))
        self.assertTrue(any('Bozkan' in place for place in style['voice_profile']['locations']))

    def test_all_50_candidates_unapproved(self):
        data=json.loads((ROOT/'candidate_ads.json').read_text('utf-8'))
        self.assertEqual(len(data['items']),50)
        self.assertTrue(all(x['review_status']=='pending' for x in data['items']))
        active=json.loads((ROOT/'ad_copy.json').read_text('utf-8'))
        active_headlines={item['headline'] for vals in active.values() for item in vals}
        self.assertFalse(any(x['headline'] in active_headlines for x in data['items']))

    def test_caption_and_headline_limits(self):
        cfg=render.load_json('config.json')
        data=json.loads((ROOT/'candidate_ads.json').read_text('utf-8'))
        for item in data['items']:
            with self.subTest(item=item['headline']):
                self.assertLessEqual(len(item['headline']),75)
                self.assertLessEqual(len(item['caption']+' '+cfg['hashtags']),150)

    def test_prompt_includes_specific_brand_voice(self):
        style=json.loads((ROOT/'style_examples.json').read_text('utf-8'))
        text=creative_copy.create_prompt('araba',5,style,render.load_json('ad_copy.json'))
        self.assertIn('Konyaaltı',text)
        self.assertIn('stalk',text)
        self.assertIn('Ne! Arabayla',text)

    def test_approval_only_moves_selected(self):
        can={'items':[{'category':'araba','headline':'A','caption':'B','review_status':'pending'},
                      {'category':'yerel','headline':'C','caption':'D','review_status':'pending'}]}
        existing={'araba':[]}
        self.assertEqual(approve_copies.approve([2],can,existing),[2])
        self.assertEqual(existing['yerel'],[{'headline':'C','caption':'D'}])
        self.assertEqual(can['items'][0]['review_status'],'pending')
        self.assertEqual(can['items'][1]['review_status'],'approved')

    def test_no_main_video_genre_classifier(self):
        self.assertFalse(hasattr(render,'category_for'))

if __name__=='__main__': unittest.main()
