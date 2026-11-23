import numpy as np, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
FD="/home/claude/viral-factory/fonts/"
AN=FD+"Anton-Regular.ttf"; BL=FD+"Inter-Black.otf"
S=1080
def grad(c1,c2,radial=False):
    yy,xx=np.mgrid[0:S,0:S].astype(np.float32)/S
    t=np.sqrt((xx-.5)**2+(yy-.45)**2)*1.6 if radial else yy
    t=np.clip(t,0,1)[...,None]
    a=np.array(c1,np.float32)*(1-t)+np.array(c2,np.float32)*t
    return Image.fromarray(a.astype(np.uint8)).convert("RGBA")
def shadow(im,draw_fn,off=(0,14),blur=18,alpha=150):
    sh=Image.new("RGBA",im.size,(0,0,0,0)); draw_fn(ImageDraw.Draw(sh),(0,0,0,alpha))
    sh=sh.filter(ImageFilter.GaussianBlur(blur)); im.alpha_composite(sh,off)
def fit(d,text,font_path,maxw,start):
    s=start
    while d.textlength(text,font=ImageFont.truetype(font_path,s))>maxw: s-=4
    return ImageFont.truetype(font_path,s)

# A) Sarı zemin, siyah dev yazı (haber/bilgi kanalı tarzı)
im=grad((255,214,0),(255,170,0)); d=ImageDraw.Draw(im)
fa=fit(d,"İLGİNÇ",AN,700,330); fb=fit(d,"BİLGİLER",AN,700,330)
def tA(dd,c):
    dd.text((S/2,370),"İLGİNÇ",font=fa,fill=c,anchor="mm"); dd.text((S/2,700),"BİLGİLER",font=fb,fill=c,anchor="mm")
shadow(im,tA,(0,12),14,90); d=ImageDraw.Draw(im)
d.text((S/2,370),"İLGİNÇ",font=fa,fill=(15,15,15),anchor="mm")
d.rounded_rectangle((150,590,S-150,810),radius=30,fill=(214,30,40))
d.text((S/2,700),"BİLGİLER",font=fb,fill=(255,255,255),anchor="mm")
im.convert("RGB").save("profil_A_sari.png")

# B) Ampul + soru işareti, kırmızı-turuncu degrade
im=grad((235,60,45),(150,20,40),radial=True); d=ImageDraw.Draw(im)
cx,cy,r=S/2,450,250
g=Image.new("RGBA",(S,S),(0,0,0,0)); ImageDraw.Draw(g).ellipse((cx-r*1.5,cy-r*1.5,cx+r*1.5,cy+r*1.5),fill=(255,220,120,120))
im.alpha_composite(g.filter(ImageFilter.GaussianBlur(70))); d=ImageDraw.Draw(im)
def bulb(dd,c,dx=0,dy=0):
    dd.ellipse((cx-r+dx,cy-r+dy,cx+r+dx,cy+r+dy),fill=c)
    dd.polygon([(cx-140+dx,cy+180+dy),(cx+140+dx,cy+180+dy),(cx+105+dx,cy+330+dy),(cx-105+dx,cy+330+dy)],fill=c)
shadow(im,lambda dd,c: bulb(dd,c),(0,18),20,120); d=ImageDraw.Draw(im)
bulb(d,(255,214,60,255))
for i in range(3):
    y=cy+345+i*52; d.rounded_rectangle((cx-110,y,cx+110,y+38),radius=19,fill=(240,240,240) if i%2==0 else (200,200,205))
d.text((cx,cy+10),"?",font=ImageFont.truetype(AN,360),fill=(150,20,40),anchor="mm")
for k in range(8):   # ışık çizgileri
    a=math.radians(-90+(k-3.5)*26); r1,r2=r+40,r+95
    d.line((cx+r1*math.cos(a),cy+r1*math.sin(a),cx+r2*math.cos(a),cy+r2*math.sin(a)),fill=(255,230,150),width=22)
im.convert("RGB").save("profil_B_ampul.png")

# C) Lacivert zemin, beyaz büyük "!" ve "?" iç içe, turkuaz halka
im=grad((16,32,70),(6,12,30),radial=True); d=ImageDraw.Draw(im)
d.ellipse((90,90,S-90,S-90),outline=(40,210,200),width=26)
f=ImageFont.truetype(AN,620)
d.text((S/2-120,S/2+20),"?",font=f,fill=(255,255,255),anchor="mm")
d.text((S/2+150,S/2+20),"!",font=f,fill=(255,196,40),anchor="mm")
im.convert("RGB").save("profil_C_lacivert.png")

# D) Büyüteç + göz, krem zemin (keşif/arşiv)
im=grad((246,238,222),(226,212,186)); d=ImageDraw.Draw(im)
cx,cy,r=470,450,250
def lens(dd,c):
    dd.ellipse((cx-r,cy-r,cx+r,cy+r),outline=c,width=60)
    dd.line((cx+r*0.68,cy+r*0.68,cx+r*1.55,cy+r*1.55),fill=c,width=95)
shadow(im,lens,(10,16),16,110); d=ImageDraw.Draw(im)
lens(d,(28,28,34,255))
d.ellipse((cx-r+30,cy-r+30,cx+r-30,cy+r-30),fill=(214,38,38))
d.ellipse((cx-150,cy-85,cx+150,cy+85),fill=(255,255,255))
d.ellipse((cx-70,cy-70,cx+70,cy+70),fill=(28,28,34)); d.ellipse((cx-35,cy-55,cx-5,cy-25),fill=(255,255,255))
im.convert("RGB").save("profil_D_buyutec.png")

# karşılaştırma: daire maskeli, büyük ve küçük boy
names=["profil_A_sari.png","profil_B_ampul.png","profil_C_lacivert.png","profil_D_buyutec.png"]
sheet=Image.new("RGB",(4*320+50,470),(250,250,250)); sd=ImageDraw.Draw(sheet)
m=Image.new("L",(300,300),0); ImageDraw.Draw(m).ellipse((0,0,299,299),fill=255)
m2=Image.new("L",(64,64),0); ImageDraw.Draw(m2).ellipse((0,0,63,63),fill=255)
for i,n in enumerate(names):
    a=Image.open(n); x=10+i*320
    sheet.paste(a.resize((300,300)),(x,10),m); sheet.paste(a.resize((64,64)),(x+118,330),m2)
    sd.text((x+150,430),"ABCD"[i],fill=(0,0,0),font=ImageFont.truetype(BL,30),anchor="mm")
sheet.save("profil_secenekler.jpg")
