import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
import render
import publish
import buffer_setup


class ScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = render.load_json('config.json')
        cls.settings = render.load_json('clip_settings.json')
        cls.copy = render.load_json('ad_copy.json')

    def test_friday_three(self):
        self.assertEqual(render.day_count(dt.date(2026,10,30), self.config)[0],3)

    def test_monday_two(self):
        self.assertEqual(render.day_count(dt.date(2026,11,2), self.config)[0],2)

    def test_utc_schedule(self):
        self.assertEqual(render.utc_due_at(dt.date(2026,11,2),'20:00'),'2026-11-02T17:00:00.000Z')

    def test_rotation_no_dup(self):
        clips=[Path(f'araba_{i:02}.mp4') for i in range(5)]
        for day in [dt.date(2026,10,30),dt.date(2026,11,2)]:
            jobs=render.pick_jobs(day,clips,self.config,self.settings,self.copy)
            self.assertEqual(len({j['clip'] for j in jobs}),len(jobs))

    def test_not_enough_clips(self):
        with self.assertRaisesRegex(ValueError,'3 farklı'):
            render.pick_jobs(dt.date(2026,10,30),[Path('araba_01.mp4')],self.config,self.settings,self.copy)

    def test_same_day_determinism(self):
        clips=[Path(f'araba_{i:02}.mp4') for i in range(4)]
        self.assertEqual(render.pick_jobs(dt.date(2026,10,31),clips,self.config,self.settings,self.copy),render.pick_jobs(dt.date(2026,10,31),list(reversed(clips)),self.config,self.settings,self.copy))

    def test_all_main_videos_one_pool(self):
        clips=[Path('araba_01.mp4'),Path('karaoke_01.mp4'),Path('gece_turu_01.mp4')]
        jobs=render.pick_jobs(dt.date(2026,10,30),clips,self.config,self.settings,self.copy)
        self.assertEqual({j['category'] for j in jobs},{'genel'})

    def test_app_recordings_independent_of_main_video_name(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'assets/app_recordings').mkdir(parents=True)
            (root/'assets/app_recording.mp4').write_bytes(b'default')
            (root/'assets/app_recordings/second.mp4').write_bytes(b'other')
            with patch.object(render,'ROOT',root):
                self.assertEqual(render.app_for(1,self.config).name,'app_recording.mp4')
                self.assertEqual(render.app_for(2,self.config).name,'second.mp4')
                self.assertEqual(render.app_for(3,self.config).name,'app_recording.mp4')

    def test_bad_schedule(self):
        bad={**self.config,'weekly_plan':{**self.config['weekly_plan'],'monday':4}}
        with self.assertRaises(ValueError): render.day_count(dt.date(2026,11,2),bad)

    def test_caption_limits(self):
        for collection in self.copy.values():
            for item in collection:
                self.assertLessEqual(len(item['caption']+' '+self.config['hashtags']),150)


class CompositingTests(unittest.TestCase):
    def test_rect(self):
        self.assertEqual(render.px_rect({'x':.1,'y':.2,'width':.4,'height':.5},100,200),(10,40,50,140))

    def test_mask_out_of_bounds(self):
        with self.assertRaises(ValueError):
            render.px_rect({'x':.8,'y':.2,'width':.4,'height':.4},100,200)

    def test_native_text_has_no_colored_cards(self):
        config=render.load_json('config.json')
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'overlay.png'
            render.make_overlay(path,360,640,'Yeni Piyaso yazısı',config,[{'x':.1,'y':.32,'width':.8,'height':.05}],config['headline_box'],(230,300,95,155))
            img=Image.open(path)
            # The old subtitle region and footer are transparent in the
            # static overlay; the original video is cleaned in the FFmpeg stage.
            self.assertEqual(img.getpixel((180,222))[3],0)
            self.assertEqual(img.getpixel((20,400))[3],0)
            self.assertGreater(sum(1 for p in img.crop((10,65,340,230)).getdata() if p[3]>0),100)

    def test_cannot_overspill_phone(self):
        with patch.object(render, 'probe_dimensions', return_value=(100,220)):
            with self.assertRaises(ValueError):
                render.phone_geometry(360,640,Path('a.mp4'),{'x':.9,'y':.9,'width':.4,'max_height':.4})


class PublishTests(unittest.TestCase):
    def test_publishing_disabled(self):
        with patch.dict(os.environ, {'PUBLISH_ENABLED':'false'}):
            with patch.object(publish,'read_public',side_effect=AssertionError('Should not touch network')):
                self.assertEqual(publish.schedule_manifest({'items':[{'slot':'01'}]}),[])

    def test_buffer_graphql_payload(self):
        class Dummy:
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def read(self): return b'{"data":{"createPost":{"post":{"id":"1234","dueAt":"2026-11-02T17:00:00.000Z"}}}}'
        with patch.dict(os.environ,{'BUFFER_API_KEY':'fake','BUFFER_CHANNEL_ID':'fake-channel'}):
            with patch.object(publish,'urlopen',return_value=Dummy()) as mock:
                result=publish.create_buffer_post('https://example.org/video.mp4','Piyaso #otomobil','2026-11-02T17:00:00.000Z')
                body=json.loads(mock.call_args.args[0].data.decode())
        self.assertEqual(result['id'],'1234')
        self.assertEqual(body['variables']['input']['mode'],'customScheduled')
        self.assertEqual(body['variables']['input']['assets'][0]['video']['url'],'https://example.org/video.mp4')

    def test_buffer_read_only_channels(self):
        with patch.object(buffer_setup,'query_buffer',side_effect=[
            {'account':{'organizations':[{'id':'org1','name':'Piyaso'}]}},
            {'channels':[{'id':'chan1','name':'Piyaso TikTok','service':'tiktok'}]}
        ]):
            out=buffer_setup.list_channels()
        self.assertEqual(out[0]['id'],'chan1')
        self.assertEqual(out[0]['service'],'tiktok')

    def test_buffer_caption_too_long(self):
        with self.assertRaises(ValueError):
            publish.create_buffer_post('https://example.org/video.mp4','x'*151,'2026-11-02T17:00:00Z')

if __name__=='__main__':
    unittest.main()

class AutomaticTextTests(unittest.TestCase):
    def test_fixed_caption_becomes_full_width_opaque_headline(self):
        import auto_text
        f = lambda y, t: [{"bbox":[.16,y,.78,y+.028],"confidence":.95,"text":t}]
        report = auto_text.group_boxes([f(.15,'OLD TEXT')])
        self.assertEqual(report['stable_bands'],1)
        self.assertFalse(report['review_required'])
        self.assertAlmostEqual(report['headline_box']['width'],.92)
        self.assertLess(report['source_text_region']['width'],.75)
        self.assertTrue(report['headline_box']['y'] <= .15)

    def test_scattered_text_is_review_required(self):
        import auto_text
        frames=[[{"bbox":[.12,.16,.80,.2],"confidence":.96,"text":"upper"},
                 {"bbox":[.12,.69,.8,.73],"confidence":.96,"text":"bottom"}]]
        report=auto_text.group_boxes(frames)
        self.assertEqual(report['stable_bands'],2)
        self.assertTrue(report['review_required'])
        self.assertEqual(len(report['cover_rectangles']),1)

    def test_no_detected_text_is_review_required(self):
        import auto_text
        report=auto_text.group_boxes([[]])
        self.assertIsNone(report['headline_box'])
        self.assertTrue(report['review_required'])

    def test_publish_blocks_uncertain_ocr(self):
        with patch.dict(os.environ, {'PUBLISH_ENABLED':'true'}):
            with self.assertRaisesRegex(RuntimeError,'human review'):
                publish.schedule_manifest({'items':[{'review_required':True,'commercial_use_authorized':True, 'demo':False}]})

class CreativeCopyTests(unittest.TestCase):
    def test_style_based_prompt(self):
        import creative_copy
        style={'allowed_facts':['otomobil toplulugu'],'style_rules':['samimi'],
               'examples':{'araba':['Gaza değil muhabbete bas'], 'genel':[]}}
        prompt=creative_copy.create_prompt('araba',4,style,{'araba':[{'headline':'Eski reklam'}]})
        self.assertIn('Gaza değil muhabbete bas',prompt)
        self.assertIn('Eski reklam',prompt)
        self.assertIn('4 farklı',prompt)

    def test_rejects_near_duplicates_and_long_copy(self):
        import creative_copy
        old={'araba':[{'headline':'Yolda muhabbet güzel olur'}]}
        data={'items':[{'headline':'Yolda muhabbet güzel olur!', 'caption':'Bir açıklama yazısı'},
                       {'headline':'Direksiyon başında güzel sohbetler', 'caption':'Bir açıklama yazısı'}]}
        drafts=creative_copy.validate_drafts(data,'araba',old)
        self.assertEqual(len(drafts),1)
        self.assertEqual(drafts[0]['review_status'],'pending')

class TextDetectorIntegrationMockTests(unittest.TestCase):
    def test_detect_clip_samples_fake_ocr_without_model(self):
        import auto_text
        class Reader:
            def readtext(self, raw, detail=1, paragraph=False):
                return [([[90,95],[300,95],[300,130],[90,130]],'Eski baslik',.98)]
        with patch.object(auto_text, '_reader', return_value=Reader()):
            with patch.object(auto_text, 'sample_frames', return_value=[(0,b'fake')]) as frames:
                result=auto_text.detect_clip(Path('clip.mp4'),360,640)
        frames.assert_called_once()
        self.assertEqual(result['sampled_frames'],1)
        self.assertEqual(result['screenshot_source'],'video_frame')
        self.assertEqual(result['stable_bands'],1)
        self.assertFalse(result['review_required'])


class SingleScreenshotModeTests(unittest.TestCase):
    def test_video_uses_one_screenshot_and_the_selected_second(self):
        import auto_text
        class Reader:
            def readtext(self, raw, detail=1, paragraph=False):
                return [([[30,120],[300,120],[300,155],[30,155]],"Yazi",.95)]
        with tempfile.TemporaryDirectory() as td:
            outfile=Path(td)/"detected_frame.png"
            with patch.object(auto_text,'_reader',return_value=Reader()):
                with patch.object(auto_text,'sample_frames',return_value=[(0,b"fake")]) as sample:
                    result=auto_text.detect_clip(Path('araba.mp4'),360,640,
                                                 frame_second=3.5,screenshot_output=outfile)
            self.assertEqual(outfile.read_bytes(),b"fake")
            self.assertEqual(result['sampled_frames'],1)
            self.assertEqual(result['frame_second'],3.5)
            self.assertFalse(result['review_required'])
            self.assertEqual(sample.call_args.kwargs['samples'],1)

    def test_supplied_screenshot_has_priority_over_video(self):
        import auto_text
        with tempfile.TemporaryDirectory() as td:
            img=Path(td)/"clip.png"
            Image.new('RGB',(360,640),'black').save(img)
            class Reader:
                def readtext(self, raw, detail=1, paragraph=False):
                    return [([[40,150],[300,150],[300,180],[40,180]],"Eski metin",.93)]
            with patch.object(auto_text,'_reader',return_value=Reader()):
                with patch.object(auto_text,'sample_frames',side_effect=AssertionError('No video frame')):
                    result=auto_text.detect_clip(Path('unused.mp4'),360,640,screenshot=img)
            self.assertEqual(result['screenshot_source'],'supplied_screenshot')
            self.assertFalse(result['review_required'])

class SelectedSegmentTests(unittest.TestCase):
    def test_default_is_eighteen_seconds(self):
        cfg=render.load_json('config.json')
        self.assertEqual(cfg['duration_seconds'],18)

    def test_long_video_selects_exact_eighteen_seconds_at_requested_start(self):
        cfg=render.load_json('config.json')
        with patch.object(render.auto_text,'duration_seconds',return_value=60.):
            start,duration,short=render.segment_window(Path('araba_01.mp4'),cfg,{'start_seconds':15})
        self.assertEqual((start,duration,short),(15,18,False))

    def test_no_loop_and_no_beyond_end(self):
        cfg=render.load_json('config.json')
        with patch.object(render.auto_text,'duration_seconds',return_value=23.):
            start,duration,short=render.segment_window(Path('araba_01.mp4'),cfg,{'start_seconds':15})
        self.assertEqual((start,duration,short),(15,8,True))

    def test_screenshot_is_from_selected_portion(self):
        import auto_text
        from unittest.mock import MagicMock
        with patch.object(auto_text,'duration_seconds',return_value=60.):
            def ffmpeg_stub(cmd,**kwargs):
                Path(cmd[-1]).write_bytes(b'fake')
                return MagicMock()
            with patch.object(auto_text.subprocess,'run',side_effect=ffmpeg_stub) as called:
                frames=auto_text.sample_frames(Path('video.mp4'),360,640,18,frame_second=2.,start_seconds=15.)
        self.assertEqual(len(frames),1)
        cmd=called.call_args.args[0]
        self.assertEqual(float(cmd[cmd.index('-ss')+1]),17.)

    def test_invalid_start_is_rejected(self):
        cfg=render.load_json('config.json')
        with patch.object(render.auto_text,'duration_seconds',return_value=40.):
            with self.assertRaisesRegex(ValueError,'negatif'):
                render.segment_window(Path('source.mp4'),cfg,{'start_seconds':-3})
