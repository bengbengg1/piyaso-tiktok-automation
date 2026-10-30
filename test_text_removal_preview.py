"""Test mask geometry and that the preview never claims to be an AI edit."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import preview_text_removal as mod

class PreviewTests(unittest.TestCase):
    def test_region_parsing(self):
        r = mod.parse_region("0.2, 0.3, 0.5, 0.1")
        self.assertEqual(r['width'],.5)
        for v in ("0.95,0.9,0.2,0.2", "hello", "0.1,0.2,0,0.1"):
            with self.assertRaises(Exception):
                mod.parse_region(v)

    def test_real_ffmpeg_screenshot_marks_without_running_ai(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            video = p / 'source.mp4'
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi',
                            '-i','color=c=black:s=320x576:d=2:r=5','-c:v','libx264',str(video)],
                            check=True, timeout=30)
            with patch.object(mod.ai, 'remove_fixed_text', side_effect=AssertionError('AI should NOT be called')):
                result=mod.execute(video, p/'review',mod.parse_region('.2,.3,.5,.1'),width=320,height=576)
            self.assertFalse(result['model_used'])
            self.assertFalse(result['publish_allowed'])
            self.assertTrue((p/'review'/'02_mask_review.png').is_file())
            self.assertTrue(json.loads((p/'review'/'review.json').read_text())['mask_only'])

    def test_explicit_ai_run_raises_without_installed_model(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            video=p/'source.mp4'
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
                            'color=c=black:s=320x576:d=2:r=5','-c:v','libx264',str(video)], check=True, timeout=30)
            with patch.dict('os.environ',{'VSR_HOME':''}):
                with self.assertRaisesRegex(RuntimeError,'VSR_HOME'):
                    mod.execute(video,p/'review',mod.parse_region('.2,.3,.5,.1'),width=320,height=576,run=True)
            self.assertFalse((p/'review'/'04_ai_cleaned_with_original_audio.mp4').exists())
