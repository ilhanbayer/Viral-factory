import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
FD="/home/claude/viral-factory/fonts/"
ANTON=FD+"Anton-Regular.ttf"; INTER=FD+"Inter-Bold.otf"; BLACK=FD+"Inter-Black.otf"
BG=(13,13,16); RED=(214,38,38); ORG=(240,160,58); TXT=(240,236,228)
def base(W,H,cx,cy,glow=(90,55,30),seed=1):
    yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
    d=np.sqrt(((xx-cx)/(W*0.6))**2+((yy-cy)/(H*0.6))**2)
    img=np.array(BG,np.float32)+np.array(glow,np.float32)*np.clip(1-d,0,1)[...,None]**1.5
    img*=np.clip(1.2-0.5*d,0.4,1)[...,None]
    img+=np.random.default_rng(seed).normal(0,5,(H,W))[...,None]
    return Image.fromarray(np.clip(img,0,255).astype(np.uint8)).convert("RGBA")
def glowdot(im,x,y,r,col):
    g=Image.new("RGBA",im.size,(0,0,0,0)); d=ImageDraw.Draw(g)
    d.ellipse((x-r*2.6,y-r*2.6,x+r*2.6,y+r*2.6),fill=col+(110,))
    g=g.filter(ImageFilter.GaussianBlur(r*1.2)); im.alpha_composite(g)
    ImageDraw.Draw(im).ellipse((x-r,y-r,x+r,y+r),fill=(255,214,120,255))
# ---------- profil 1080x1080
S=1080; im=base(S,S,S/2,S/2)
d=ImageDraw.Draw(im)
d.ellipse((60,60,S-60,S-60),outline=RED+(255,),width=34)
f=ImageFont.truetype(ANTON,560)
# "İB": I gövdesi + B; noktayı ışık olarak çiz
txt="IB"; w=d.textlength(txt,font=f); x0=S/2-w/2; y=S/2+40
d.text((S/2,y),txt,font=f,fill=TXT+(255,),anchor="mm")
iw=d.textlength("I",font=f); bb=d.textbbox((S/2,y),txt,font=f,anchor="mm")
glowdot(im,x0+iw/2,bb[1]-70,46,ORG)
d=ImageDraw.Draw(im)
im.convert("RGB").save("profil_foto.png")
# ---------- YouTube banner 2560x1440 (güvenli alan 1546x423 ortada)
W,H=2560,1440; im=base(W,H,W/2,H/2,glow=(80,45,28),seed=2); d=ImageDraw.Draw(im)
gf=ImageFont.truetype(ANTON,230)
words=["TARİH","BİLİM","ŞEHİRLER","YEMEK","DOĞA","KELİMELER","REKORLAR","GİZEMLER"]
ov=Image.new("RGBA",(W,H),(0,0,0,0)); od=ImageDraw.Draw(ov)
for row in range(7):
    s="   ·   ".join(words[(row*3+i)%len(words)] for i in range(8))
    od.text((-200+(row%2)*-380,row*215-40),s,font=gf,fill=(255,255,255,16))
im.alpha_composite(ov)
sh=Image.new("RGBA",(W,H),(0,0,0,0)); ImageDraw.Draw(sh).rectangle((0,H/2-252,W,H/2+250),fill=(10,9,12,200))
im.alpha_composite(sh); d=ImageDraw.Draw(im)
d.rectangle((0,H/2-260,W,H/2-252),fill=RED+(255,)); d.rectangle((0,H/2+250,W,H/2+258),fill=RED+(255,))
tf=ImageFont.truetype(ANTON,205)
t1,t2="İLGİNÇ ","BİLGİLER"
w1=d.textlength(t1,font=tf); w2=d.textlength(t2,font=tf); x=W/2-(w1+w2)/2
d.text((x,H/2-70),t1,font=tf,fill=TXT+(255,),anchor="lm"); d.text((x+w1,H/2-70),t2,font=tf,fill=RED+(255,),anchor="lm")
sf=ImageFont.truetype(INTER,58)
d.text((W/2,H/2+112),"Türkiye ve dünya hakkında bilmediğin gerçekler",font=sf,fill=TXT+(235,),anchor="mm")
bf=ImageFont.truetype(BLACK,38); tag="HER GÜN YENİ BÖLÜM"
tw=d.textlength(tag,font=bf); d.rounded_rectangle((W/2-tw/2-34,H/2+150,W/2+tw/2+30,H/2+205),radius=14,fill=ORG+(255,))
d.text((W/2,H/2+178),tag,font=bf,fill=(20,16,12),anchor="mm")
im.convert("RGB").save("youtube_kapak.png")
# önizleme: güvenli alan kontrolü
p=im.convert("RGB").copy(); dd=ImageDraw.Draw(p); dd.rectangle(((W-1546)/2,(H-423)/2,(W+1546)/2,(H+423)/2),outline=(0,255,0),width=6)
p.resize((1280,720)).save("_kontrol.jpg")
