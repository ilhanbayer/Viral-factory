import json
def P(search, label, fb=None, extra=2):
    return {"type":"photo","search":search,"label":label,"extra":extra,"fallback_show":fb or {"type":"icon","name":"camera","label":label}}
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
