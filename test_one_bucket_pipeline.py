import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import storage_client
import history_sync

class OneBucketTests(unittest.TestCase):
    def test_write_only_published_mp4_or_private_receipts(self):
        c=MagicMock()
        with patch.object(storage_client,'client',return_value=c), patch.dict('os.environ',{'R2_PUBLIC_BASE_URL':'https://foo.workers.dev'}):
            url=storage_client.upload(storage_client.BUCKET,'published/piyaso/2026-11-01/01_1300/video.mp4',b'mp4','video/mp4')
            self.assertEqual(url,'https://foo.workers.dev/piyaso/2026-11-01/01_1300/video.mp4')
            self.assertIsNone(storage_client.upload(storage_client.BUCKET,'state/piyaso/2026-11-01/01_1300/submission.json',b'{}','application/json'))
        for path in ('davethemen-media/x','app_recordings/screen.mp4','backgrounds/new.mp4','published/piyaso/2026-11-01/x/screen.mp4','published/../../secret'):
            with self.subTest(path=path),self.assertRaises(ValueError):
                storage_client.upload(storage_client.BUCKET,path,b'data','video/mp4')
        self.assertEqual(c.put_object.call_count,2)
        self.assertEqual(c.put_object.call_args.kwargs['IfNoneMatch'],'*')

    def test_state_copy_is_private(self):
        with patch.object(storage_client,'client',return_value=MagicMock()):
            self.assertIsNone(storage_client.upload(storage_client.BUCKET,'state/copy/2026-11-01.json',b'{}','application/json'))
        with self.assertRaises(ValueError):
            storage_client.public_url(storage_client.BUCKET,'state/copy/2026-11-01.json')

    def test_history_pull_and_idempotent_push(self):
        day='2026-11-01'
        data={'date':day,'generation_type':'ai_generated','items':[{'slot':1,'headline':'Piyaso geldi'}]}
        archive=json.dumps(data).encode('utf-8')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'output'/day).mkdir(parents=True)
            (root/'output'/day/'daily_copy.json').write_text(json.dumps(data))
            with patch.object(history_sync,'ROOT',root),patch.object(history_sync,'HISTORY',root/'data'/'generated_history.json'),\
                 patch.object(storage_client,'list_objects',return_value=[{'name':day+'.json'}]),\
                 patch.object(storage_client,'download',return_value=archive),\
                 patch.object(storage_client,'upload') as upl:
                history_sync.pull()
                entries=json.loads((root/'data'/'generated_history.json').read_text())['entries']
                self.assertEqual(entries[0]['date'],day)
                history_sync.push(day)
                upl.assert_not_called()
            with patch.object(history_sync,'ROOT',root),patch.object(storage_client,'download',return_value=None),\
                 patch.object(storage_client,'upload',return_value=None) as upl:
                history_sync.push(day)
                self.assertEqual(upl.call_args.args[1],f'state/copy/{day}.json')

if __name__=='__main__':unittest.main()
