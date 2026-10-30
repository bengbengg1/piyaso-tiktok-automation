"""Create synthetic clips for local visual tests; not actual Piyaso UI or stock footage.
No videos, music, images, or screenshots are downloaded from the internet.
"""
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def font(n):
    return ImageFont.truetype(FONT,n) if Path(FONT).exists() else ImageFont.load_default()


def centered(d,txt,y,sz,fill):
    f=font(sz)
    b=d.textbbox((0,0),txt,font=f)
    d.text(((360-(b[2]-b[0]))//2,y),txt,font=f,fill=fill)


def make_bg(kind,index,path):
    colors={'araba':(6,22,40),'karaoke':(40,13,55),'sarki':(47,24,25)}
    pic=Image.new('RGB',(360,640),colors[kind]); d=ImageDraw.Draw(pic)
    if kind=='araba':
        d.polygon([(178,205),(210,205),(352,640),(8,640)],fill=(35,41,52))
        for y in range(260,640,75):
            w=int((y-205)*.06)
            d.rounded_rectangle((179-w,y,181+w,y+33),radius=3,fill=(232,190,110))
        for x in (28,80,278,335):
            d.ellipse((x-9,288,x+9,306),fill=(255,197,93))
        centered(d,'ORIJINAL ARABA VIDEOSU',95,16,(255,255,255))
    elif kind=='karaoke':
        for x in (35,90,160,240,300):
            d.polygon([(x,140),(x+20,140),(x+100,630),(x-70,630)],fill=(58,32+index*9,92))
        d.ellipse((112,360,250,498),fill=(161,76,167))
        d.rounded_rectangle((155,380,205,525),radius=16,fill=(20,18,33),outline=(238,208,243),width=5)
        centered(d,'ESKI KARAOKE YAZISI',110,17,(255,255,255))
    else:
        d.ellipse((25,265,350,595),fill=(124,59,42))
        d.ellipse((78,335,293,548),fill=(222,117,57))
        d.arc((55,310,304,590),20,170,fill=(252,201,135),width=14)
        centered(d,'ESKI SARKI YAZISI',110,18,(255,255,255))
    path.parent.mkdir(parents=True,exist_ok=True)
    pic.save(path.with_suffix('.png'))
    subprocess.run(['ffmpeg','-y','-v','error','-loop','1','-framerate','25','-i',str(path.with_suffix('.png')),
                    '-t','5','-vf','format=yuv420p','-c:v','libx264','-preset','ultrafast',str(path)],check=True)
    path.with_suffix('.png').unlink()


def make_app(path):
    img=Image.new('RGB',(252,456),(236,242,239))
    d=ImageDraw.Draw(img)
    d.rectangle((0,0,252,66),fill=(15,75,60))
    d.text((22,17),'Piyaso',font=font(28),fill='white')
    d.rounded_rectangle((14,84,238,290),radius=13,fill=(195,222,213),outline=(46,120,92),width=3)
    d.text((24,107),'GARAJ',font=font(23),fill=(15,75,60))
    d.ellipse((76,152,182,240),fill=(42,120,105))
    d.rounded_rectangle((36,261,218,282),radius=10,fill=(15,75,60))
    d.text((22,320),'OTOMOBIL',font=font(19),fill=(11,72,54))
    d.text((22,351),'TOPLULUGU',font=font(19),fill=(11,72,54))
    d.rectangle((0,420,252,456),fill=(14,62,55))
    d.text((20,425),'TEMSILI EKRAN',font=font(16),fill='white')
    path.parent.mkdir(parents=True,exist_ok=True)
    img.save(path.with_suffix('.png'))
    subprocess.run(['ffmpeg','-y','-v','error','-loop','1','-framerate','25','-i',str(path.with_suffix('.png')),
                    '-t','5','-vf','format=yuv420p','-c:v','libx264','-preset','ultrafast',str(path)],check=True)
    path.with_suffix('.png').unlink()

if __name__=='__main__':
    for i,kind in enumerate(['araba','karaoke','sarki']):
        make_bg(kind,i,ROOT/'assets'/'backgrounds'/f'{kind}_ornek.mp4')
    make_app(ROOT/'assets'/'app_recording.mp4')
    print('3 sentetik kaynak video + temsili ekran kaydı oluşturuldu. Bunlar gerçek Piyaso içeriği değildir.')
