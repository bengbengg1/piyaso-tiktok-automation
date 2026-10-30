"""MOV support must not require renaming QuickTime footage to MP4."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import asset_sync
import render
import storage_client

class MovSupportTests(unittest.TestCase):
    def test_app_for_falls_back_to_mov_without_pairing_with_main_video(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'assets/app_recording.mov').parent.mkdir(parents=True)
            (root/'assets/app_recording.mov').write_bytes(b'valid QuickTime movie placeholder')
            (root/'assets/app_recordings').mkdir()
            config={'app_recordings':{'default':'assets/app_recording.mp4','directory':'assets/app_recordings'}}
            with patch.object(render,'ROOT',root):
                self.assertEqual(render.app_for(1,config).name,'app_recording.mov')
    def test_r2_sync_can_select_true_mov_default(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'assets/backgrounds').mkdir(parents=True)
            (root/'assets/app_recordings').mkdir()
            (root/'assets/catalog.json').write_text(json.dumps({'backgrounds':{'source.mov':{'commercial_use_authorized':True}}}))
            (root/'config.json').write_text(json.dumps({'app_recordings':{'default':'assets/app_recording.mp4','directory':'assets/app_recordings'}}))
            def download(_bucket,key,*,max_bytes=0):
                return {'backgrounds/source.mov': b'approved main',
                        'app_recordings/app_recording.mov': b'valid app mov'}.get(key)
            def lister(_bucket,prefix):
                return [{'name':'source.mov','size':10}] if prefix=='backgrounds/' else []
            with patch.object(asset_sync,'ROOT',root), \
                 patch.object(storage_client,'bucket_name',return_value='piyaso-tiktok-assets'), \
                 patch.object(storage_client,'check_bucket'), \
                 patch.object(storage_client,'list_objects',side_effect=lister), \
                 patch.object(storage_client,'download',side_effect=download):
                self.assertEqual(asset_sync.sync_assets(),['source.mov'])
            self.assertEqual((root/'assets/app_recording.mov').read_bytes(),b'valid app mov')
            self.assertFalse((root/'assets/app_recording.mp4').exists())

if __name__ == '__main__':unittest.main()
