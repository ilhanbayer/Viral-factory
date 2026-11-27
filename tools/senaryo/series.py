"""SENARYO YARDIMCILARI — GÖRSEL DİL (kullanıcı isteği, 27 Kasım 2026; referans: "Spesifik Kayseri" tarzı infografik Shorts)
Kalite hedefi: her bölüm en az 9/10 (görsel-konu uyumu, kanca, hareket/ritim, içerik zenginliği, ses/yazı; her biri 0-2).
Her bölümde yaklaşık yarı yarıya: 5-6 gerçek fotoğraf P(...) + 4-6 hareketli infografik (factory/mograph.py):
  yer adı geçince  -> MAP(pins=[{"at":"İl","label":..}], x=[il], dots=N, route={...}, fill=[il], focus=il, zoom=2.5, title, sub) ya da SIGN(metin, stil)
  sayı geçince     -> DOC(kurum, satır, değer, birim, yıl, alt) / RATIO(n,k,başlık) / RANK(sıra, ad, başlık) / POD(kazanan)
  tartışma/efsane  -> TAPE(kelime) ya da SPLIT(üst, alt, rozet)
  soru anı         -> QM(kelime);  yapı/mimari -> BLD("mosque|castle|house|columns|tower|bridge", etiket, rozet)
Eski düz yazı kartlarını (T/NU/L/IC/DO) yeni senaryolarda kullanma (yalnız "BÖLÜM k" kapanış kartı T kalabilir).
AI görseli (P(..., ai="...", ai_first=True)) yalnızca gerçekten gerekli 1-2 sahnede; Pollinations sık başarısız oluyor.
10-14 kısa beat, ~550-750 karakter, sayı/yıl string, bilgiler web aramasıyla doğrulanmış; açıklamaya kaynak satırı.
Örnek: s_yerebatan.py, s_pamukkale.py (TR) ve *_en.py (EN).
"""
import json
def P(search, label, fb=None, extra=2, ai=None, ai_first=False):
    """Commons fotoğrafı; ai=İngilizce sahne tarifi verilirse fotoğraf bulunamazsa (ai_first=True ise doğrudan)
    yapay zekâ ile belgesel tarzı temsili canlandırma üretilir (etikete 'AI · TEMSİLİ' eklenir)."""
    d={"type":"photo","search":search,"label":label,"extra":extra,**({"fallback_show":fb} if fb else {})}
    if ai:
        d["ai"]=ai
        if ai_first: d["ai_first"]=True
    return d
def T(l,r=1): return {"type":"title","lines":l,"red":r}
def L(*it): return {"type":"list","items":list(it)}
def PL(n,s): return {"type":"place","name":n,"sub":s}
def DO(n,no,f): return {"type":"dossier","name":n,"no":no,"fields":f}
def NU(v,l,suf=""):
    d={"type":"number","value":str(v),"label":l}
    if suf: d["suffix"]=suf
    return d
def IC(n,l=None):
    d={"type":"icon","name":n}
    if l: d["label"]=l
    return d
def Q(t,w): return {"type":"quote","text":t,"who":w}
def SC(label,sky="dusk",land="hills",props=None,people=None,weather="none"):
    d={"type":"scene","sky":sky,"land":land,"weather":weather,"moon":sky=="night","label":label,"props":props or []}
    if people: d["people"]=people
    return d
FOL=IC("eye","TAKİP ET · BİLDİRİMİ AÇ")
def build(sid, title, brand, theme, broll, parts, series_name, lang="tr", voice=None, logo=None, part_word="Bölüm", tail=None):
    out=[]
    n=len(parts)
    for k,p in enumerate(parts):
        beats=[]
        for row in p["beats"]:
            b={"say":row[0],"show":row[1]}
            if len(row)>2 and row[2]: b["sfx"]=row[2]
            beats.append(b)
        c=sum(len(b["say"]) for b in beats)
        print(sid,k+1,len(beats),c,len(p["title"]),p["title"])
        assert len(p["title"])<=60
        out.append({"beats":beats,"thumb":p["thumb"],"broll":p.get("broll"),
          "publish":{"title":p["title"],"description":p["desc"]+(tail(k+1,n) if tail else f"\n\nDizi: {series_name} — Bölüm {k+1}/{n}. Tüm bölümler kanalda."),
                     "hashtags":p["tags"]}})
    d={"id":sid,"format":"story","title":title,"brand":brand,"theme":theme,"lang":lang,
       "voice":voice or {"engine":"edge","speaker":"ahmet","rate":"+0%","pitch":"-2Hz"},"broll":broll,"parts":out}
    if logo: d["logo"]=logo
    json.dump(d,open(f"/home/claude/viral-factory/topics/queue/{sid}.json","w"),ensure_ascii=False,indent=1)

# ---- hareketli infografik sahneleri (factory/mograph.py) ----
def MAP(**k): return {"type":"map",**k}
def SIGN(text, style="blue", **k): return {"type":"sign","text":text,"style":style,**k}
def DOC(org, row, value=None, unit=None, year=None, sub=None):
    d={"type":"doc","org":org,"row":row}
    for kk,v in (("value",value),("unit",unit),("year",year),("sub",sub)):
        if v: d[kk]=str(v)
    return d
def POD(win, **k): return {"type":"podium","win":win,**k}
def RANK(pos, name, title=None): return {"type":"rank","pos":pos,"name":name,**({"title":title} if title else {})}
def RATIO(n, k, title=None): return {"type":"ratio","n":n,"k":k,**({"title":title} if title else {})}
def SPLIT(top, bottom, badge=None): return {"type":"split","top":top,"bottom":bottom,**({"badge":badge} if badge else {})}
def TAPE(text): return {"type":"tape","text":text}
def BLD(kind, label=None, tag=None, title=None):
    d={"type":"building","kind":kind}
    for kk,v in (("label",label),("tag",tag),("title",title)):
        if v: d[kk]=v
    return d
def QM(word): return {"type":"qmark","word":word}
