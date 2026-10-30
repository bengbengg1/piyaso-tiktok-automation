import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import ai_text_removal
import live_smoke

class LiveChecksTests(unittest.TestCase):
    def test_no_api_keys_is_not_success(self):
        with patch.dict('os.environ', {'GROQ_API_KEY': ''}):
            with self.assertRaisesRegex(RuntimeError, 'GROQ_API_KEY'):
                live_smoke.groq_check()

    def test_model_checkpoint_is_distinct_from_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'backend').mkdir()
            (root/'backend/main.py').write_text('')
            with self.assertRaisesRegex(RuntimeError, 'checkpoint'):
                ai_text_removal.ensure_vsr_weights(root)
            ck=root/'backend/models/sttn-auto/infer_model.pth'
            ck.parent.mkdir(parents=True)
            ck.write_bytes(b'test' * 30000)
            self.assertEqual(ai_text_removal.ensure_vsr_weights(root),ck)
