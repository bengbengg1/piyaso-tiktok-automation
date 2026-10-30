"""Safety regressions: static multi-line subtitles, public-repo workflow, one R2 bucket."""
from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import auto_text
ROOT=Path(__file__).resolve().parents[1]

class FixedTextTests(unittest.TestCase):
    def test_four_line_caption_is_one_removal_region(self):
        boxes=[]
        for i,txt in enumerate(('Neee konyaaltında','arabayla sabaha kadar',
                                'müzik dinleyip','turlayacak mıyız?')):
            y=.12+i*.052
            boxes.append({'bbox':[.16,y,.85,y+.035], 'text':txt,'confidence':.93})
        report=auto_text.group_boxes([boxes])
        self.assertEqual(report['stable_bands'],1)
        self.assertEqual(report['detected_text_lines'],4)
        self.assertFalse(report['review_required'])
        self.assertGreater(report['source_text_region']['height'],.17)
    def test_two_far_text_blocks_require_review(self):
        boxes=[{'bbox':[.12,.11,.87,.15],'text':'Cümle','confidence':.95},
               {'bbox':[.17,.68,.81,.72],'text':'Başka metin','confidence':.96}]
        report=auto_text.group_boxes([boxes])
        self.assertTrue(report['review_required'])
        self.assertEqual(report['stable_bands'],2)
    def test_more_than_one_frame_is_explicitly_refused(self):
        with self.assertRaises(ValueError): auto_text.group_boxes([[],[]])
    def test_blank_and_low_confidence_are_not_published(self):
        r=auto_text.group_boxes([[{'bbox':[.1,.1,.8,.15], 'text':'old', 'confidence':.03}]])
        self.assertTrue(r['review_required'])
        self.assertIsNone(r['source_text_region'])

class DeploymentGuards(unittest.TestCase):
    def test_public_repo_workflow_never_uses_persistent_runner(self):
        workflow=(ROOT/'.github/workflows/daily.yml').read_text('utf-8')
        self.assertIn('runs-on: ubuntu-latest',workflow)
        self.assertNotIn('runs-on: self-hosted',workflow)
        self.assertNotIn('vars.VIDEO_RUNNER',workflow)
    def test_workflow_uses_one_bucket_only(self):
        workflow=(ROOT/'.github/workflows/daily.yml').read_text('utf-8')
        self.assertNotIn('$R2_PUBLIC_BUCKET',workflow)
        self.assertNotIn('$R2_STATE_BUCKET',workflow)
        self.assertIn("storage_client.bucket_name('public')",workflow)

if __name__ == '__main__': unittest.main()

class RotationEfficiency(unittest.TestCase):
    def test_selection_manifest_keeps_full_remote_pool_rotation(self):
        import datetime as dt, json, tempfile
        from unittest.mock import patch
        import render
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'assets').mkdir()
            clips=[root/'assets'/f'v{i}.mp4' for i in range(11)]
            day=dt.date(2026,11,2) # Monday: two slots
            config=render.load_json('config.json')
            approved=render.load_json('ad_copy.json')
            all_jobs=render.pick_jobs(day,clips,config,{},approved,ignore_selection=True)
            chosen=[j['clip'] for j in all_jobs]
            (root/'assets'/'selection.json').write_text(json.dumps({'date':str(day),'selected_names':[p.name for p in chosen]}))
            with patch.object(render,'ROOT',root):
                resumed=render.pick_jobs(day,list(reversed(chosen)),config,{},approved)
            self.assertEqual([x['clip'].name for x in resumed],[x['clip'].name for x in all_jobs])
    def test_incomplete_selected_files_fail_closed(self):
        import datetime as dt, json, tempfile
        from unittest.mock import patch
        import render
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'assets').mkdir()
            (root/'assets'/'selection.json').write_text(json.dumps({'date':'2026-11-02','selected_names':['a.mp4','missing.mp4']}))
            config=render.load_json('config.json')
            copies=render.load_json('ad_copy.json')
            with patch.object(render,'ROOT',root), self.assertRaisesRegex(ValueError,'Missing'):
                render.pick_jobs(dt.date(2026,11,2),[root/'a.mp4',root/'b.mp4'],config,{},copies)

class R2DailySelectiveSync(unittest.TestCase):
    def test_daily_sync_downloads_only_todays_sources(self):
        import datetime as dt, json, tempfile
        from unittest.mock import patch
        import asset_sync, render
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'assets'/'backgrounds').mkdir(parents=True)
            (root/'assets'/'app_recordings').mkdir()
            config=render.load_json('config.json')
            copies=render.load_json('ad_copy.json')
            (root/'config.json').write_text(json.dumps(config))
            (root/'ad_copy.json').write_text(json.dumps(copies))
            (root/'clip_settings.json').write_text('{}')
            names=[f'source_{i:03}.mp4' for i in range(30)]
            catalog={'backgrounds':{n:{'commercial_use_authorized':True,'source':'licensed'} for n in names}}
            (root/'assets'/'catalog.json').write_text(json.dumps(catalog))
            day=dt.date(2026,11,2)
            pool=[root/'assets'/'backgrounds'/x for x in names]
            with patch.object(render,'ROOT',root):
                jobs=render.pick_jobs(day,pool,config,{},copies,ignore_selection=True)
            expected={j['clip'].name for j in jobs}
            downloaded=[]
            def listing(bucket,prefix):
                if prefix=='backgrounds/':return [{'name':n} for n in names]
                if prefix=='app_recordings/':return [{'name':'app_recording.mp4'}]
                return []
            def download(bucket,key,**kwargs):
                downloaded.append(key)
                return b'dummy bytes'
            import storage_client
            with patch.object(asset_sync,'ROOT',root),patch.object(render,'ROOT',root),\
                 patch.object(storage_client,'check_bucket'),patch.object(storage_client,'list_objects',side_effect=listing),\
                 patch.object(storage_client,'download',side_effect=download):
                result=asset_sync.sync_assets(day=day)
            self.assertEqual(set(result),expected)
            self.assertEqual(len([x for x in downloaded if x.startswith('backgrounds/')]),2)
            self.assertEqual(set((root/'assets'/'backgrounds').glob('*.mp4')),{root/'assets'/'backgrounds'/n for n in expected})
            lock=json.loads((root/'assets'/'selection.json').read_text())
            self.assertEqual(lock['remote_approved_pool_size'],30)
            self.assertEqual(lock['selected_names'],[j['clip'].name for j in jobs])
