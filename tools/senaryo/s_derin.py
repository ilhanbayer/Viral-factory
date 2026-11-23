import sys; sys.path.insert(0,'.')
from series import *
TAGS=["#kapadokya","#derinkuyu","#ürgüp","#nevşehir","#ilginçbilgiler","#shorts"]
UG={"type":"scene","land":"underground","label":"","props":[{"k":"torch","x":0.18}]}
def U(label,people=None,props=None):
    d={"type":"scene","land":"underground","label":label,"props":props or [{"k":"torch","x":0.18}]}
    if people: d["people"]=people
    return d
parts=[
dict(title="Duvarı Yıktı, Arkasından Şehir Çıktı 😳 Bölüm 1 #shorts",desc="1963'te Derinkuyu'da bir ev sahibinin bodrumda bulduğu yeraltı şehri.",tags=TAGS,
 thumb={"lines":["DUVARIN","ARKASINDA ŞEHİR"],"red":1,"photo_search":"Derinkuyu Underground City"},
 broll=["Derinkuyu Underground City","Derinkuyu","Cappadocia"],
 beats=[
 ("1963, Nevşehir. Bir adam evini onarırken bodrum duvarını yıktı. Arkasında *bir şehir* vardı.",U("1963 · DERİNKUYU",{"n":1,"from":0.35,"to":0.5}),"hit"),
 ("Duvarın ardındaki oda, aşağı inen *dar tünellere* açılıyordu.",P("Derinkuyu tunnel","AŞAĞI İNEN TÜNELLER")),
 ("Tüneller indikçe yeni odalar, yeni katlar *çıktı*.",P("Derinkuyu Underground City","DERİNKUYU YERALTI ŞEHRİ")),
 ("Şehir, yerin yaklaşık *85 metre* altına iniyor.",NU("85","DERİNLİK"," M"),"riser"),
 ("Tahminlere göre burada *20 bine kadar* insan saklanabiliyordu.",NU("20.000","KİŞİYE KADAR")),
 ("Üstelik hayvanları ve *erzaklarıyla* birlikte.",L("İNSANLAR","HAYVANLAR","ERZAK")),
 ("Derinkuyu'nun adı da buradan: *derin kuyu*.",P("Derinkuyu well","DERİN KUYU")),
 ("Bugün bölgede, bazıları evlerin bodrumunda *600'den fazla* tünel girişi bulundu.",NU("600+","TÜNEL GİRİŞİ")),
 ("Bölüm 2'de: Binlerce insan yerin altında *nasıl yaşadı*?",T(["BÖLÜM 2","YERİN ALTINDA","HAYAT"])),
 ("Kaçırmamak için *takip et*.",FOL)]),
dict(title="Yerin 85 Metre Altında Nasıl Yaşadılar? 🕯️ Bölüm 2 #shorts",desc="Derinkuyu'da ahırlar, mutfaklar, kuyular, havalandırma bacaları ve kilise.",tags=TAGS,
 thumb={"lines":["YERİN","85 M ALTINDA"],"red":1,"photo_search":"Derinkuyu"},
 broll=["Derinkuyu","Kaymakli Underground City","Derinkuyu ventilation shaft"],
 beats=[
 ("Güneş görmeden, yerin 85 metre altında *aylarca* yaşamak mümkün mü?",U("YERİN 85 M ALTI",{"n":2,"from":0.5,"to":0.62}),"hit"),
 ("Derinkuyu'da her kat *bir işe* ayrılmıştı.",P("Derinkuyu","KAT KAT ŞEHİR")),
 ("Üst katlarda ahırlar, aşağıda mutfaklar, *depolar* ve odalar vardı.",L("AHIR","MUTFAK","DEPO","ODALAR")),
 ("En alt katta ise bir *kilise* bulunuyor.",P("Derinkuyu church","EN ALT KAT · KİLİSE")),
 ("Peki bu kadar insan *nasıl nefes alıyordu*?",IC("question"),"riser"),
 ("Cevap: Yüzeye uzanan dikey *havalandırma bacaları*.",P("Derinkuyu ventilation shaft","HAVALANDIRMA BACASI")),
 ("Ana bacalardan biri yaklaşık *55 metre* derinliğe iniyor ve kuyu olarak da kullanılıyordu.",NU("55","KUYU BACASI"," M")),
 ("Yeraltı şehri yaz kış *serin* kalıyor; erzak bozulmadan saklanabiliyordu.",P("Kaymakli Underground City","DOĞAL SERİNLİK")),
 ("Bölüm 3'te: Sadece *içeriden* açılan taş kapılar.",T(["BÖLÜM 3","TAŞ","KAPILAR"])),
 ("*Takip et* ki kaçırma.",FOL)]),
dict(title="Bu Taş Kapı Sadece İçeriden Kapanıyordu 🪨 Bölüm 3 #shorts",desc="Derinkuyu'nun yuvarlanan taş kapıları ve Kaymaklı'ya uzanan tünel.",tags=TAGS,
 thumb={"lines":["SADECE","İÇERİDEN"],"red":1,"photo_search":"Derinkuyu stone door"},
 broll=["Derinkuyu stone door","Kaymakli","Derinkuyu tunnel"],
 beats=[
 ("Bu dev taş kapılar sadece *içeriden* kapatılabiliyordu.",P("Derinkuyu stone door","TAŞ KAPI"),"hit"),
 ("Tehlike gelince köylüler, hayvanlarıyla birlikte *yerin altına* iniyordu.",U("SIĞINAK",{"n":6,"from":0.85,"to":0.4,"run":True})),
 ("Sonra koridorları, tekerlek gibi *yuvarlanan* taşlarla kapatıyorlardı.",U("YUVARLANAN KAPI",props=[{"k":"stonedoor","x":0.5},{"k":"torch","x":0.15}])),
 ("Dışarıdan gelen biri bu kapıları *açamıyordu*.",T(["DIŞARIDAN","AÇILAMIYORDU"])),
 ("Şehrin ilk kısımlarının *Frigler* döneminde oyulduğu düşünülüyor.",DO("FRİGLER","MÖ 8-7. YY",{"İDDİA":"İLK OYMALAR","DURUM":"TAHMİN"})),
 ("Bizans döneminde Arap akınlarına karşı *genişletildi*.",P("Cappadocia","BİZANS DÖNEMİ")),
 ("Ve en şaşırtıcısı: Derinkuyu'yu Kaymaklı'ya bağlayan *8-9 kilometrelik* tüneller.",NU("8-9","KM TÜNEL · KAYMAKLI"," KM"),"riser"),
 ("Kaymaklı da Kapadokya'nın en büyük *yeraltı şehirlerinden* biri.",P("Kaymakli Underground City","KAYMAKLI YERALTI ŞEHRİ")),
 ("Bölüm 4'te: Peribacaları *nasıl oluştu*?",T(["BÖLÜM 4","PERİBACALARININ","SIRRI"])),
 ("*Takip et* ki kaçırma.",FOL)]),
dict(title="Peribacaları Aslında Volkanlardan Doğdu 🌋 Bölüm 4 #shorts",desc="Peribacalarının oluşumu, Kapadokya adının anlamı ve Ürgüp'teki Üç Güzeller.",tags=TAGS,
 thumb={"lines":["PERİBACALARI","NASIL OLUŞTU?"],"red":1,"photo_search":"Fairy chimneys Urgup"},
 broll=["Fairy chimneys Cappadocia","Erciyes","Urgup"],
 beats=[
 ("Kapadokya'nın peribacalarını aslında *volkanlar* yaptı.",P("Fairy chimneys Cappadocia","PERİBACALARI"),"hit"),
 ("Milyonlarca yıl önce Erciyes, Hasandağı ve Göllüdağ *püskürdü*.",P("Erciyes","ERCİYES DAĞI")),
 ("Volkanik kül katman katman birikti ve yumuşak bir taşa, *tüfe* dönüştü.",L("KÜL","KATMAN","TÜF")),
 ("Sonra yağmur ve rüzgâr bu taşı binlerce yıl *aşındırdı*.",SC("AŞINMA","storm","desert",[{"k":"chimney","x":0.4},{"k":"chimney","x":0.75,"s":0.7}],weather="rain")),
 ("Tepede kalan sert kaya *şapka* gibi korudu; altındaki yumuşak taş sivrildi.",P("Fairy chimney","SERT ŞAPKA, YUMUŞAK GÖVDE"),"riser"),
 ("Ürgüp'teki en ünlüleri: *Üç Güzeller*.",P("Three Beauties Urgup","ÜÇ GÜZELLER · ÜRGÜP")),
 ("Halk arasında bu peribacalarına bir *aşk efsanesi* anlatılır.",IC("eye","EFSANE")),
 ("Kapadokya adının ise *güzel atlar ülkesi* anlamına geldiği söylenir.",Q("Katpatuka: güzel atlar ülkesi","Yaygın anlatım")),
 ("Bölüm 5'te: Bir dizi, Ürgüp'ün *kaderini* nasıl değiştirdi?",T(["BÖLÜM 5","BİR DİZİ","HER ŞEYİ DEĞİŞTİRDİ"])),
 ("*Takip et* ki kaçırma.",FOL)]),
dict(title="Bir Dizi Ürgüp'ün Kaderini Değiştirdi 🎈 Bölüm 5 #shorts",desc="Ürgüp: Temenni Tepesi, Asmalı Konak etkisi ve Kapadokya'nın balonları.",tags=TAGS,
 thumb={"lines":["ÜRGÜP'ÜN","SIRRI"],"red":1,"photo_search":"Urgup"},
 broll=["Urgup","Cappadocia balloons","Temenni hill Urgup"],
 beats=[
 ("Bir televizyon dizisi, koca bir bölgenin *kaderini* değiştirdi.",P("Urgup","ÜRGÜP"),"hit"),
 ("2002-2004 arasında *Asmalı Konak* Ürgüp'te çekildi.",NU("2002","ASMALI KONAK ÇEKİMLERİ")),
 ("Dizi, Kapadokya'ya yerli turist akınını *başlatan* etkenlerden biri sayılıyor.",P("Urgup houses","TAŞ EVLER")),
 ("Ürgüp'ün ortasında *Temenni Tepesi* yani dilek tepesi var.",P("Temenni hill Urgup","TEMENNİ TEPESİ")),
 ("Tepede, Selçuklu sultanı *IV. Kılıçarslan* için yapılmış sembolik bir türbe bulunuyor.",DO("IV. KILIÇARSLAN","SELÇUKLU",{"YER":"TEMENNİ TEPESİ","TÜRBE":"SEMBOLİK"})),
 ("Ve sabahları gökyüzü *yüzlerce balonla* doluyor.",P("Cappadocia balloons","KAPADOKYA BALONLARI"),"riser"),
 ("Kapadokya, dünyanın en ünlü *balon uçuşu* noktalarından biri.",SC("SABAH · KAPADOKYA","day","desert",[{"k":"chimney","x":0.3},{"k":"chimney","x":0.7,"s":0.8}])),
 ("Yerin 85 metre altından gökyüzüne: Kapadokya'nın *iki yüzü*.",T(["YERİN ALTI","VE","GÖKYÜZÜ"],2)),
 ("Dizinin sonu! Sen Kapadokya'ya gittin mi? *Yorumlara yaz*.",T(["SEN","KAPADOKYA'YA","GİTTİN Mİ?"],2)),
 ("Yeni dizi için *takip et*.",FOL)]),
]
build("S010_derinkuyu_urgup","Dizi: Derinkuyu ve Ürgüp","İLGİNÇ BİLGİLER","dosya",["Cappadocia","Derinkuyu","Urgup"],parts,"Derinkuyu ve Ürgüp")
