import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import scene_select
import storage_client

class ExtraTests(unittest.TestCase):
    def test_scene_start_is_valid_and_deterministic(self):
        source=Path(__file__).resolve().parents[1]/'assets'/'backgrounds'/'araba_ornek.mp4'
        a=scene_select.choose_start(source,window=2.)
        b=scene_select.choose_start(source,window=2.)
        self.assertEqual(a,b)
        self.assertGreaterEqual(a,0.)
        self.assertLessEqual(a,3.)

    def test_small_footage_starts_at_zero(self):
        source=Path(__file__).resolve().parents[1]/'assets'/'backgrounds'/'araba_ornek.mp4'
        self.assertEqual(scene_select.choose_start(source,window=100.),0.)

    def test_reject_untrusted_storage_url(self):
        with patch.dict(os.environ, {'R2_ENDPOINT':'http://evil.example.com'}):
            with self.assertRaisesRegex(RuntimeError,'official HTTPS'):storage_client.endpoint()

    def test_storage_path_traversal_rejected(self):
        with self.assertRaises(ValueError):storage_client.valid_path('../secret')
        with self.assertRaises(ValueError):storage_client.valid_path('assets//secret')
        with self.assertRaises(ValueError):storage_client.public_url('private','foo.mp4')

    def test_public_url_does_not_embed_credentials(self):
        env={'R2_PUBLIC_BASE_URL':'https://piyaso-media.example.workers.dev',
             'R2_ASSETS_BUCKET':'piyaso-tiktok-assets'}
        with patch.dict(os.environ,env):
            self.assertEqual(storage_client.public_url('piyaso-tiktok-assets','published/piyaso/2026-10-30/01_1300/video.mp4'),
                'https://piyaso-media.example.workers.dev/piyaso/2026-10-30/01_1300/video.mp4')

    def test_public_base_cannot_be_private_s3_endpoint(self):
        with patch.dict(os.environ,{'R2_PUBLIC_BASE_URL':'https://abc.r2.cloudflarestorage.com'}):
            with self.assertRaisesRegex(RuntimeError,'NOT the S3 endpoint'):
                storage_client.public_base()

    def test_create_only_uses_atomic_r2_conditional_put(self):
        from unittest.mock import MagicMock
        mock=MagicMock()
        with patch.object(storage_client,'client',return_value=mock):
            self.assertIsNone(storage_client.upload('piyaso-tiktok-assets','state/piyaso/2026-11-01/01_1300/confirmed.json',b'{}','application/json'))
        self.assertEqual(mock.put_object.call_args.kwargs['IfNoneMatch'],'*')
        self.assertEqual(mock.put_object.call_args.kwargs['Bucket'],'piyaso-tiktok-assets')

    def test_pagination_and_paths_exclude_nested_and_traversal(self):
        from unittest.mock import MagicMock
        client=MagicMock()
        client.get_paginator.return_value.paginate.return_value=[
            {'Contents':[{'Key':'backgrounds/car01.mp4','Size':123},
                         {'Key':'backgrounds/nested/secret.mp4','Size':10}]}]
        with patch.object(storage_client,'client',return_value=client):
            self.assertEqual(storage_client.list_objects('piyaso-tiktok-assets','backgrounds/'),[
                {'name':'car01.mp4','key':'backgrounds/car01.mp4','size':123}])

    def test_private_bucket_requires_private_role(self):
        from unittest.mock import MagicMock
        with patch.object(storage_client,'client',return_value=MagicMock()):
            with self.assertRaisesRegex(ValueError,'Invalid bucket'):
                storage_client.check_bucket('piyaso-tiktok-public',False)

    def test_public_reachability_head_no_authorization(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.status=200;response.headers={'Content-Type':'video/mp4'}
        response.__enter__.return_value=response
        seen=[]
        def opener(request,timeout):
            seen.append(request)
            return response
        with patch.dict(os.environ,{'R2_PUBLIC_BASE_URL':'https://piyaso-media.example.workers.dev'}), \
             patch.object(storage_client,'urlopen',side_effect=opener):
            storage_client.verify_public_access('https://piyaso-media.example.workers.dev/piyaso/2026-11-01/01/video.mp4')
        self.assertEqual(seen[0].get_method(),'HEAD')
        self.assertNotIn('Authorization',seen[0].headers)

if __name__=='__main__':unittest.main()
