import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
FD="/home/claude/viral-factory/fonts/"; AN=FD+"Anton-Regular.ttf"; IB=FD+"Inter-Bold.otf"; BL=FD+"Inter-Black.otf"
S=1080
yy,xx=np.mgrid[0:S,0:S].astype(np.float32)/S
t=np.clip(yy,0,1)[...,None]
im=Image.fromarray((np.array((255,214,0),np.float32)*(1-t)+np.array((255,170,0),np.float32)*t).astype(np.uint8)).convert("RGBA")
d=ImageDraw.Draw(im)
f=ImageFont.truetype(AN,450)
sh=Image.new("RGBA",(S,S),(0,0,0,0)); ImageDraw.Draw(sh).text((S/2,S/2-110),"HT",font=f,fill=(0,0,0,90),anchor="mm")
im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)),(0,12)); d=ImageDraw.Draw(im)
d.text((S/2,S/2-110),"HT",font=f,fill=(15,15,15),anchor="mm")
d.rounded_rectangle((170,700,S-170,850),radius=26,fill=(214,30,40))
f2=ImageFont.truetype(AN,92); d.text((S/2,775),"HIDDEN TÜRKİYE",font=f2,fill=(255,255,255),anchor="mm")
im.convert("RGB").save("ht_profil.png")
# banner
W,H=2560,1440
im=Image.new("RGBA",(W,H),(13,13,16,255)); 
yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
dd=np.sqrt(((xx-W/2)/(W*0.6))**2+((yy-H/2)/(H*0.6))**2)
a=np.array((13,13,16),np.float32)+np.array((80,45,28),np.float32)*np.clip(1-dd,0,1)[...,None]**1.5
im=Image.fromarray(np.clip(a,0,255).astype(np.uint8)).convert("RGBA")
ov=Image.new("RGBA",(W,H),(0,0,0,0)); od=ImageDraw.Draw(ov); gf=ImageFont.truetype(AN,230)
words=["HISTORY","MYSTERIES","ANCIENT CITIES","LEGENDS","DISCOVERIES","NATURE"]
for row in range(7):
    s="   ·   ".join(words[(row*2+i)%len(words)] for i in range(8))
    od.text((-200+(row%2)*-380,row*215-40),s,font=gf,fill=(255,255,255,16))
im.alpha_composite(ov)
band=Image.new("RGBA",(W,H),(0,0,0,0)); ImageDraw.Draw(band).rectangle((0,H/2-252,W,H/2+250),fill=(10,9,12,200)); im.alpha_composite(band)
d=ImageDraw.Draw(im)
d.rectangle((0,H/2-260,W,H/2-252),fill=(214,38,38)); d.rectangle((0,H/2+250,W,H/2+258),fill=(214,38,38))
tf=ImageFont.truetype(AN,205); t1,t2="HIDDEN ","TÜRKİYE"
w1=d.textlength(t1,font=tf); w2=d.textlength(t2,font=tf); x=W/2-(w1+w2)/2
d.text((x,H/2-70),t1,font=tf,fill=(240,236,228),anchor="lm"); d.text((x+w1,H/2-70),t2,font=tf,fill=(214,38,38),anchor="lm")
d.text((W/2,H/2+112),"The untold history and mysteries of Türkiye",font=ImageFont.truetype(IB,58),fill=(240,236,228),anchor="mm")
bf=ImageFont.truetype(BL,38); tag="NEW EPISODES EVERY DAY"; tw=d.textlength(tag,font=bf)
d.rounded_rectangle((W/2-tw/2-30,H/2+150,W/2+tw/2+30,H/2+205),radius=14,fill=(255,196,40)); d.text((W/2,H/2+178),tag,font=bf,fill=(20,16,12),anchor="mm")
im.convert("RGB").save("ht_kapak.png")
Image.open("ht_kapak.png").crop((507,508,2053,931)).resize((773,211)).save("_ht_safe.jpg")
