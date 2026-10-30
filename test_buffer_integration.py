"""Buffer integration contract tests: all network calls are mocked and read-only."""
from __future__ import annotations
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import buffer_setup
import publish


class MockResponse:
    status=200
    def __init__(self,data): self.data=data
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self): return json.dumps(self.data).encode()


class BufferIntegrationTests(unittest.TestCase):
    def test_channel_read_only_query_and_tiktok_validation(self):
        queries=[]
        def fake_query(query):
            queries.append(query)
            if 'account' in query:
                return {'account':{'organizations':[{'id':'org123','name':'Piyaso'}]}}
            return {'channels':[{'id':'c1','name':'Piyaso TikTok','service':'tiktok','isQueuePaused':False}]}
        channels=buffer_setup.list_channels(query_fn=fake_query)
        self.assertEqual(buffer_setup.validate_tiktok_channel('c1',channels)['name'],'Piyaso TikTok')
        self.assertTrue(all('mutation' not in q for q in queries))

    def test_wrong_platform_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,'TikTok'):
            buffer_setup.validate_tiktok_channel('c1',[{'id':'c1','service':'instagram'}])

    def test_paused_queue_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,'duraklatılmış'):
            buffer_setup.validate_tiktok_channel('c1',[{'id':'c1','service':'tiktok','isQueuePaused':True}])

    def test_missing_channel_id_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,'BUFFER_CHANNEL_ID'):
            buffer_setup.validate_tiktok_channel('',[])

    def test_graphql_query_contract_and_bearer_token(self):
        seen=[]
        def opener(request, timeout):
            seen.append(request)
            return MockResponse({'data':{'account':{'organizations':[]}}})
        with patch.dict(os.environ,{'BUFFER_API_KEY':'fake-123'}):
            answer=buffer_setup.query_buffer('query { account { organizations { id } } }',opener=opener)
        self.assertEqual(answer['account']['organizations'],[])
        self.assertEqual(seen[0].full_url,'https://api.buffer.com')
        self.assertEqual(seen[0].headers['Authorization'],'Bearer fake-123')

    def test_create_post_sends_video_url_exact_due_at(self):
        seen=[]
        def opener(request,timeout):
            seen.append(json.loads(request.data))
            return MockResponse({'data':{'createPost':{'post':{'id':'p123','dueAt':'2026-12-02T10:00:00.000Z'}}}})
        with patch.dict(os.environ,{'BUFFER_API_KEY':'fake-123','BUFFER_CHANNEL_ID':'c1'}),patch.object(publish,'urlopen',opener):
            result=publish.create_buffer_post('https://example.org/video.mp4','Piyaso 🫣 #Piyaso','2026-12-02T10:00:00.000Z')
        self.assertEqual(result['id'],'p123')
        body=seen[0]['variables']['input']
        self.assertEqual(body['mode'],'customScheduled')
        self.assertEqual(body['channelId'],'c1')
        self.assertEqual(body['dueAt'],'2026-12-02T10:00:00.000Z')
        self.assertTrue(body['aiAssisted'])
        self.assertEqual(body['assets'][0]['video']['url'],'https://example.org/video.mp4')

    def test_buffer_union_error_rejected(self):
        def opener(request,timeout):
            return MockResponse({'data':{'createPost':{'message':'Queue full'}}})
        with patch.dict(os.environ,{'BUFFER_API_KEY':'fake-123','BUFFER_CHANNEL_ID':'c1'}),patch.object(publish,'urlopen',opener):
            with self.assertRaisesRegex(RuntimeError,'Queue full'):
                publish.create_buffer_post('https://example.org/video.mp4','Piyaso','2026-12-02T10:00:00.000Z')

    def test_disabled_never_calls_network(self):
        with patch.dict(os.environ,{'PUBLISH_ENABLED':'false'}),patch.object(publish,'read_public',side_effect=AssertionError('network!')):
            self.assertEqual(publish.schedule_manifest({'date':'2026-12-01','items':[]}),[])

    def test_mock_publish_creates_private_receipt_and_no_duplicate(self):
        day='2099-01-01'
        with tempfile.TemporaryDirectory() as folder:
            video=Path(folder)/'video.mp4';video.write_bytes(b'fake media for mock')
            manifest={'date':day,'items':[{'slot':'01_1300','file':'video.mp4','caption':'Piyaso',
                'dueAt':'2099-01-01T10:00:00.000Z','demo':False,'review_required':False,
                'text_removal_backend':'vsr','ai_removal':{'backend':'vsr'},'commercial_use_authorized':True}]}
            receipts={}
            def fake_read(path): return receipts.get(path)
            def fake_save(path,data):receipts[path]=data
            with patch.dict(os.environ,{'PUBLISH_ENABLED':'true','BUFFER_CHANNEL_ID':'c1'}), \
                 patch.object(publish,'ROOT',Path(folder)), \
                 patch('buffer_setup.list_channels',return_value=[{'id':'c1','name':'Piyaso','service':'tiktok'}]), \
                 patch('storage_client.check_bucket',return_value={}), \
                 patch('storage_client.exists',return_value=False), \
                 patch.object(publish,'read_state',side_effect=fake_read), \
                 patch.object(publish,'save_state',side_effect=fake_save), \
                 patch.object(publish,'write_object',return_value='https://piyaso-tiktok-media.workers.dev/video.mp4'), \
                 patch.object(publish,'create_buffer_post',return_value={'id':'post123'}) as create:
                a=publish.schedule_manifest(manifest)
                b=publish.schedule_manifest(manifest)
            self.assertEqual(a[0]['post']['id'],'post123')
            self.assertEqual(b[0]['post']['id'],'post123')
            self.assertEqual(create.call_count,1)
            self.assertIn('state/piyaso/2099-01-01/01_1300/confirmed.json',receipts)
            self.assertIn('state/piyaso/2099-01-01/01_1300/submission.json',receipts)

    def test_prior_submission_blocks_reschedule(self):
        day='2099-01-01'
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'video.mp4').write_bytes(b'dummy')
            manifest={'date':day,'items':[{'slot':'01_1300','file':'video.mp4','caption':'Piyaso',
                'dueAt':'2099-01-01T10:00:00.000Z','review_required':False,'demo':False,
                'text_removal_backend':'vsr','ai_removal':{'backend':'vsr'},'commercial_use_authorized':True}]}
            def fake_read(path):
                return {'status':'submitting'} if path.endswith('submission.json') else None
            with patch.dict(os.environ,{'PUBLISH_ENABLED':'true','BUFFER_CHANNEL_ID':'c1'}), \
                 patch.object(publish,'ROOT',Path(folder)), \
                 patch('buffer_setup.list_channels',return_value=[{'id':'c1','name':'Piyaso','service':'tiktok'}]), \
                 patch('storage_client.check_bucket',return_value={}), \
                 patch.object(publish,'read_state',side_effect=fake_read), \
                 patch.object(publish,'create_buffer_post',side_effect=AssertionError('Duplicate post!')):
                with self.assertRaisesRegex(RuntimeError,'incomplete Buffer submission'):
                    publish.schedule_manifest(manifest)

    def test_unverified_ai_removal_never_publishes(self):
        manifest={'date':'2099-01-01','items':[{'slot':'x','file':'whatever.mp4',
            'dueAt':'2099-01-01T10:00:00.000Z','demo':False,'review_required':False,'commercial_use_authorized':True}]}
        with patch.dict(os.environ,{'PUBLISH_ENABLED':'true'}):
            with self.assertRaisesRegex(RuntimeError,'AI text removal'):
                publish.schedule_manifest(manifest)

if __name__=='__main__': unittest.main()
