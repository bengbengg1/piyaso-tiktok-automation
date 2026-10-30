"""Safety regression tests: no access to Davethemen and no mixing media types."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import asset_sync
import storage_client

class SeparateMediaTests(unittest.TestCase):
    def test_davethemen_never_accepted_as_assets_bucket(self):
        for unsafe in ('davethemen','piyaso-music','piyaso-tiktok-public','piyaso-tiktok-assets/other'):
            with self.subTest(unsafe=unsafe),patch.dict(os.environ,{'R2_ASSETS_BUCKET':unsafe}):
                with self.assertRaises(ValueError): storage_client.bucket_name('assets')

    def test_single_bucket_roles_use_separate_prefixes(self):
        with patch.dict(os.environ,{'R2_ASSETS_BUCKET':'piyaso-tiktok-assets',
                    'R2_PUBLIC_BUCKET':'piyaso-tiktok-public',
                    'R2_STATE_BUCKET':'piyaso-tiktok-state'}):
            self.assertEqual(storage_client.check_isolation(), {
                'assets':'piyaso-tiktok-assets',
                'public':'piyaso-tiktok-assets',
                'state':'piyaso-tiktok-assets'})

    def test_main_and_app_media_never_enter_same_folder(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'assets'/'backgrounds').mkdir(parents=True)
            (root/'assets'/'app_recordings').mkdir(parents=True)
            (root/'assets'/'catalog.json').write_text(json.dumps({
                'backgrounds': {'karaoke-01.mp4': {'commercial_use_authorized':True},
                                'unlicensed.mp4': {'commercial_use_authorized':False}}}),encoding='utf8')
            (root/'config.json').write_text(json.dumps({'app_recordings':{
                'default':'assets/app_recording.mp4',
                'directory':'assets/app_recordings'}}),encoding='utf8')
            objects=[{'name':'karaoke-01.mp4','size':10}, {'name':'unlicensed.mp4','size':10}]
            def download(bucket,key,*,max_bytes):
                return {
                    'backgrounds/karaoke-01.mp4': b'main video bytes',
                    'app_recordings/app_recording.mp4': b'default screen',
                    'app_recordings/garage.mp4': b'garage screen',
                }.get(key)
            with patch.object(asset_sync,'ROOT',root), \
                 patch.object(storage_client,'bucket_name',return_value='piyaso-tiktok-assets'), \
                 patch.object(storage_client,'check_bucket'), \
                 patch.object(storage_client,'list_objects',side_effect=[objects,[{'name':'garage.mp4'}]]) as lister, \
                 patch.object(storage_client,'download',side_effect=download) as getter:
                self.assertEqual(asset_sync.sync_assets(),['karaoke-01.mp4'])
            self.assertEqual([c.args[1] for c in lister.call_args_list],['backgrounds/','app_recordings/'])
            keys=[x.args[1] for x in getter.call_args_list]
            self.assertNotIn('backgrounds/unlicensed.mp4', keys)
            self.assertNotIn('app_recordings/karaoke-01.mp4',keys)
            self.assertEqual((root/'assets'/'backgrounds'/'karaoke-01.mp4').read_bytes(),b'main video bytes')
            self.assertEqual((root/'assets'/'app_recording.mp4').read_bytes(),b'default screen')
            self.assertEqual((root/'assets'/'app_recordings'/'garage.mp4').read_bytes(),b'garage screen')
            self.assertFalse((root/'assets'/'app_recordings'/'community.mp4').exists())

    def test_invalid_app_path_fails_before_download(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'assets'/'backgrounds').mkdir(parents=True)
            (root/'assets'/'catalog.json').write_text(json.dumps({
                'backgrounds': {'karaoke-01.mp4':{'commercial_use_authorized':True}}}))
            (root/'config.json').write_text(json.dumps({'app_recordings':{
                'default':'assets/app_recording.mp4','directory':'assets/backgrounds'}}))
            with patch.object(asset_sync,'ROOT',root), \
                 patch.object(storage_client,'bucket_name',return_value='piyaso-tiktok-assets'), \
                 patch.object(storage_client,'check_bucket'), \
                 patch.object(storage_client,'list_objects',return_value=[{'name':'karaoke-01.mp4'}]), \
                 patch.object(storage_client,'download',return_value=b'main'):
                with self.assertRaisesRegex(ValueError,'screen recording paths'):
                    asset_sync.sync_assets()

if __name__=='__main__':unittest.main()
