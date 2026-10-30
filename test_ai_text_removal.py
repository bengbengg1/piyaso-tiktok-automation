"""Unit and real FFmpeg integration tests; fake VSR is NOT AI validation."""
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ai_text_removal as ai


class VsrTests(unittest.TestCase):
    def test_correct_ymin_ymax_xmin_xmax_coordinate_order(self):
        r={"x": .2, "y": .3, "width": .4, "height": .2}
        self.assertEqual(ai.vsr_coords(r, 1000, 2000, padding=0), ["600", "1000", "200", "600"])

    def test_padded_rectangle_is_clamped(self):
        r={"x": .0, "y": .95, "width": .5, "height": .05}
        self.assertEqual(ai.vsr_coords(r, 100, 200, padding=.02), ["186", "200", "0", "52"])

    def test_malformed_coordinates_rejected(self):
        with self.assertRaises(ValueError):
            ai.vsr_coords({"x":.95,"y":.1,"width":.1,"height":.2},360,640)

    def test_missing_ai_backend_fails_no_delogo(self):
        with patch.dict('os.environ', {'VSR_HOME':''}):
            with self.assertRaisesRegex(RuntimeError, 'VSR_HOME'):
                ai.find_vsr()

    def test_unknown_mode_fails_before_running(self):
        with tempfile.TemporaryDirectory() as td:
            video=Path(td)/"input.mp4"; video.write_bytes(b'dummy')
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                ai.remove_fixed_text(video,Path(td)/'out.mp4',{"x":.3,"y":.4,"width":.3,"height":.05},
                                     start_seconds=0,duration_seconds=1,width=320,height=576,fps=25,mode='opencv')

    def test_real_ffmpeg_crop_plus_fake_vsr_adapter(self):
        # Fake VSR only verifies orchestration/coordinates. It does NOT remove text.
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); (p/'vsr/backend').mkdir(parents=True)
            fake=p/'vsr/backend/main.py'
            fake.write_text('''import sys, shutil, pathlib, json
args=sys.argv[1:]
assert args[args.index('--inpaint-mode')+1]=='sttn-auto'
coords=args[args.index('-c')+1:args.index('-c')+5]
assert list(map(int,coords))==[200,329,92,228], coords
shutil.copyfile(args[args.index('-i')+1],args[args.index('-o')+1])
''')
            ck=p/'vsr/backend/models/sttn-auto/infer_model.pth'
            ck.parent.mkdir(parents=True)
            ck.write_bytes(b'dummy checkpoint for mocked model; not real AI'*2500)
            source=p/'source.mp4'; output=p/'cleaned.mp4'
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
                            '-f','lavfi','-i','color=c=blue:s=320x576:d=1:r=12',
                            '-c:v','libx264',str(source)],check=True)
            reg={'x':.3,'y':.36,'width':.4,'height':.2}
            data=ai.remove_fixed_text(source,output,reg,start_seconds=0,duration_seconds=.7,
                                      width=320,height=576,fps=12,vsr_home=p/'vsr',vsr_python=sys.executable,padding=.012)
            self.assertEqual(data['backend'],'vsr')
            self.assertTrue(output.is_file())
            self.assertEqual(data['input_dimensions'],[320,576])


if __name__ == '__main__':
    unittest.main()
