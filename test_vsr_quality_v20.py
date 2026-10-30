"""Tests new v20 quality gate using FFmpeg and decoded video. No fake AI claims."""
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from vsr_quality import check_ai_result, video_probe
from vsr_r2_review import validate_source_key

REGION={'x':0.25,'y':0.35,'width':0.50,'height':0.20}

class QualityGateV20(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.folder=Path(self.d.name)
        self.source=self.folder/'original.mp4'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                        '-f','lavfi','-i','color=c=blue:s=320x576:r=8:d=2',
                        '-f','lavfi','-i','sine=frequency=400:sample_rate=44100:duration=2',
                        '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',
                        '-shortest',str(self.source)],check=True,timeout=35)

    def test_original_unchanged_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'unchanged'):
            check_ai_result(self.source,self.source,REGION,self.folder,
                            t=2,target_width=320,target_height=576,fps=8)

    def test_real_changes_pass_but_still_require_human_review(self):
        after=self.folder/'edited.mp4'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                        '-i',str(self.source),'-vf','drawbox=x=90:y=225:w=110:h=30:color=green:t=fill',
                        '-c:v','libx264','-pix_fmt','yuv420p','-c:a','copy',str(after)],check=True,timeout=30)
        report=check_ai_result(self.source,after,REGION,self.folder,
                               t=2,target_width=320,target_height=576,fps=8)
        self.assertTrue(report['model_output_verified_as_non_noop'])
        self.assertTrue(report['original_audio_preserved'])
        self.assertFalse(report['quality_approved'])
        self.assertTrue((self.folder/'05_before_after_ai.png').exists())

    def test_losing_audio_fails_closed(self):
        silent=self.folder/'silent.mp4'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                        '-i',str(self.source),'-an','-c:v','copy',str(silent)],check=True,timeout=30)
        self.assertFalse(video_probe(silent)['has_audio'])
        with self.assertRaisesRegex(RuntimeError,'audio'):
            check_ai_result(self.source,silent,REGION,self.folder,
                            t=2,target_width=320,target_height=576,fps=8)

    def test_can_test_existing_published_r2_video_without_reupload(self):
        self.assertEqual(validate_source_key(
            'published/piyaso/2026-10-30/01_0001/video.mp4.mov'),
            'published/piyaso/2026-10-30/01_0001/video.mp4.mov')
        for key in ['published/piyaso/2026-10-30/01_0001/secret.json',
                    'published/piyaso/2026-10-30/01_0001/../video.mp4',
                    'published/davethemen/2026-10-30/01_0001/video.mp4']:
            with self.assertRaises(ValueError):validate_source_key(key)

if __name__=='__main__':unittest.main()
