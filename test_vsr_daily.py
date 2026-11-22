import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vsr_daily import clean_or_detect_empty


class DetectionOutcomes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'normal.mp4'
        self.output = Path(self.temp.name) / 'vsr.mp4'
        self.source.write_bytes(b'unchanged private source')

    def invoke(self, returncode, log='', output=None):
        def runner(command, **kwargs):
            kwargs['stdout'].write(log.encode())
            if output is not None:
                self.output.write_bytes(output)
            return subprocess.CompletedProcess(command, returncode)
        with patch('vsr_daily.subprocess.run', side_effect=runner):
            return clean_or_detect_empty('python', 'backend/main.py', self.source, self.output)

    def test_exact_empty_ocr_keeps_source_without_claiming_removal(self):
        log = ("raise Exception(tr['Main']['NoSubtitleDetected'].format(self.video_path))\n"
               'Exception: No subtitles detected. Check file: ' + str(self.source))
        result = self.invoke(1, log, output=b'partial broken output')
        self.assertFalse(result['text_removal_applied'])
        self.assertEqual(result['text_detection_status'], 'no_text_detected')
        self.assertTrue(result['human_quality_review_required'])
        self.assertEqual(self.output.read_bytes(), self.source.read_bytes())

    def test_unrelated_failure_never_copies_source(self):
        with self.assertRaisesRegex(RuntimeError, 'inference failed'):
            self.invoke(1, 'ImportError: missing model', output=b'partial')
        self.assertFalse(self.output.exists())

    def test_empty_text_mention_before_a_later_error_is_not_a_fallback(self):
        with self.assertRaises(RuntimeError):
            self.invoke(1, 'No subtitles detected\nRuntimeError: corrupted video')

    def test_empty_result_for_another_input_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.invoke(1, "raise Exception(tr['Main']['NoSubtitleDetected'].format(self.video_path))\n"
                        'Exception: No subtitles detected. Check file: /another.mp4')

    def test_success_requires_nonempty_output(self):
        for output in (None, b''):
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                self.invoke(0, output=output)

    def test_success_reports_inpainting(self):
        result = self.invoke(0, output=b'processed video')
        self.assertTrue(result['text_removal_applied'])

    def test_timeout_remains_an_error(self):
        with patch('vsr_daily.subprocess.run', side_effect=subprocess.TimeoutExpired('vsr', 1)):
            with self.assertRaises(subprocess.TimeoutExpired):
                clean_or_detect_empty('python', 'backend', self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_input_cannot_be_overwritten(self):
        with self.assertRaises(ValueError):
            clean_or_detect_empty('python', 'backend', self.source, self.source)
        self.assertEqual(self.source.read_bytes(), b'unchanged private source')


if __name__ == '__main__':
    unittest.main()
