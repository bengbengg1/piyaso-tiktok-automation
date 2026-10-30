import sys, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import vsr_r2_review

class ReviewStorageTests(unittest.TestCase):
  def test_private_source_key_allowlist(self):
    for key in ['backgrounds/one.mov','backgrounds/clip.mp4.mov','backgrounds/one name.mp4']:
      self.assertEqual(vsr_r2_review.validate_source_key(key),key)
    for key in ['published/piyaso/video.mp4','../backgrounds/b.mp4','backgrounds/../x.mp4','backgrounds/sub/b.mp4','app_recordings/test.mp4']:
      with self.assertRaises(ValueError):vsr_r2_review.validate_source_key(key)
  def test_destinations_must_be_private(self):
    with patch.object(vsr_r2_review.storage_client,'client') as client:
      vsr_r2_review.private_review_upload('reviews/vsr/20261031/12/mask.png',b'abc','image/png')
      client.return_value.put_object.assert_called_once()
      self.assertEqual(client.return_value.put_object.call_args.kwargs['Key'],'reviews/vsr/20261031/12/mask.png')
      with self.assertRaises(ValueError):
        vsr_r2_review.private_review_upload('published/piyaso/2026-10-31/01_1300/video.mp4',b'xx','video/mp4')
