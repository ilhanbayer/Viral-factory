import sys; sys.path.insert(0,'.')
from series import *
TAGS=["#cappadocia","#derinkuyu","#turkey","#undergroundcity","#history","#shorts"]
def FO(n): return {"type":"icon","name":"eye","label":f"FOLLOW FOR PART {n}"}
def U(label,people=None,props=None):
    d={"type":"scene","land":"underground","label":label,"props":props or [{"k":"torch","x":0.18}]}
    if people: d["people"]=people
    return d
parts=[
dict(title="He Broke a Wall and Found a City 😳 Part 1 #shorts",desc="1963, Derinkuyu, Türkiye: a homeowner knocked down a basement wall and found a lost underground city.",tags=TAGS,
 thumb={"lines":["A CITY BEHIND","THE WALL"],"red":1,"photo_search":"Derinkuyu Underground City"},
 broll=["Derinkuyu Underground City","Derinkuyu tunnel","Cappadocia"],
 beats=[
 ("In 1963, a man in Türkiye knocked down a wall in his basement. Behind it was *a whole city*.",P("Derinkuyu Underground City","DERINKUYU · TÜRKİYE"),"hit"),
 ("The hidden room led to *narrow tunnels* going down.",P("Derinkuyu tunnel","TUNNELS GOING DOWN")),
 ("Every tunnel opened into new rooms and *new floors*.",P("Derinkuyu","FLOOR AFTER FLOOR")),
 ("The city goes about *85 meters* underground.",NU("85","METERS DEEP"," M"),"riser"),
 ("According to estimates, up to *20,000 people* could hide here.",NU("20,000","PEOPLE · ESTIMATED")),
 ("Along with their animals and *food supplies*.",L("PEOPLE","ANIMALS","FOOD")),
 ("Its name, Derinkuyu, means *deep well* in Turkish.",P("Derinkuyu well","DERİN KUYU = DEEP WELL")),
 ("Today, more than *600 entrances* have been found in the area, some inside homes.",NU("600+","TUNNEL ENTRANCES")),
 ("In part 2: how did thousands of people *live down here*?",T(["PART 2","LIFE","UNDERGROUND"])),
 ("*Follow* so you don't miss it.",FO(2))]),
dict(title="How Did They Live 85 Meters Underground? 🕯️ Part 2 #shorts",desc="Stables, kitchens, wells, ventilation shafts and a church inside Derinkuyu.",tags=TAGS,
 thumb={"lines":["85 METERS","UNDERGROUND"],"red":1,"photo_search":"Derinkuyu"},
 broll=["Derinkuyu","Kaymakli Underground City","Derinkuyu ventilation shaft"],
 beats=[
 ("Could you live *85 meters* underground for months without sunlight?",P("Derinkuyu Underground City","NO SUNLIGHT"),"hit"),
 ("In Derinkuyu, every level had *a purpose*.",P("Derinkuyu","LEVEL BY LEVEL")),
 ("Stables near the top, then kitchens, *storerooms* and living rooms.",L("STABLES","KITCHENS","STORAGE","ROOMS")),
 ("And on one of the deepest levels, *a church*.",P("Derinkuyu church","A CHURCH BELOW")),
 ("But how did so many people *breathe*?",IC("question","HOW DID THEY BREATHE?"),"riser"),
 ("The answer: vertical *ventilation shafts* reaching the surface.",P("Derinkuyu ventilation shaft","VENTILATION SHAFT")),
 ("One main shaft drops about *55 meters* and also worked as a well.",NU("55","METER SHAFT"," M")),
 ("Underground it stays *cool* all year, so food could be stored safely.",P("Kaymakli Underground City","NATURAL FRIDGE")),
 ("In part 3: stone doors that only *opened from inside*.",T(["PART 3","THE STONE","DOORS"])),
 ("*Follow* so you don't miss it.",FO(3))]),
dict(title="This Stone Door Only Closed From Inside 🪨 Part 3 #shorts",desc="Derinkuyu's rolling stone doors, who carved the city, and the tunnel to Kaymaklı.",tags=TAGS,
 thumb={"lines":["ONLY FROM","INSIDE"],"red":1,"photo_search":"Derinkuyu stone door"},
 broll=["Derinkuyu stone door","Kaymakli","Derinkuyu tunnel"],
 beats=[
 ("These giant stone doors could only be closed *from the inside*.",P("Derinkuyu stone door","ROLLING STONE DOOR"),"hit"),
 ("When danger came, villagers went *underground* with their animals.",P("Derinkuyu tunnel","INTO THE DARK")),
 ("Then they sealed the corridors with stones that *roll like wheels*.",U("ROLLING DOOR",props=[{"k":"stonedoor","x":0.5},{"k":"torch","x":0.15}])),
 ("From the outside, attackers *couldn't open* them.",T(["IMPOSSIBLE TO","OPEN FROM","OUTSIDE"],2)),
 ("The first rooms are believed to date back to the *Phrygians*, almost 3,000 years ago.",DO("PHRYGIANS","8TH-7TH C. BC",{"CLAIM":"FIRST CARVINGS","STATUS":"BELIEVED"})),
 ("In Byzantine times, the city was *expanded* to hide from raids.",P("Cappadocia","BYZANTINE ERA")),
 ("And reportedly, a tunnel of about *8 kilometers* links it to another city: Kaymaklı.",NU("8","KM TUNNEL · REPORTEDLY"," KM"),"riser"),
 ("Kaymaklı is one of the *largest* underground cities in Cappadocia.",P("Kaymakli Underground City","KAYMAKLI")),
 ("In part 4: how volcanoes made Cappadocia's *fairy chimneys*.",T(["PART 4","FAIRY","CHIMNEYS"])),
 ("*Follow* so you don't miss it.",FO(4))]),
dict(title="Volcanoes Built These Fairy Chimneys 🌋 Part 4 #shorts",desc="How Cappadocia's fairy chimneys formed from volcanic ash, and the Three Beauties of Ürgüp.",tags=TAGS,
 thumb={"lines":["MADE BY","VOLCANOES"],"red":1,"photo_search":"Fairy chimneys Urgup"},
 broll=["Fairy chimneys Cappadocia","Erciyes","Urgup"],
 beats=[
 ("Cappadocia's famous fairy chimneys were actually made by *volcanoes*.",P("Fairy chimneys Cappadocia","FAIRY CHIMNEYS"),"hit"),
 ("Millions of years ago, Mount Erciyes, Hasan Dağı and Göllüdağ *erupted*.",P("Erciyes","MOUNT ERCİYES")),
 ("Layers of ash piled up and hardened into a soft rock called *tuff*.",L("ASH","LAYERS","TUFF")),
 ("Then rain and wind *eroded* it for thousands of years.",P("Cappadocia valley","EROSION")),
 ("A hard rock cap on top protected the soft *stone below*, like a hat.",P("Fairy chimney","HARD CAP · SOFT BODY"),"riser"),
 ("The most famous are the *Three Beauties* in Ürgüp.",P("Three Beauties Urgup","THE THREE BEAUTIES · ÜRGÜP")),
 ("Locals tell a *love legend* about them.",P("Urgup","A LOCAL LEGEND")),
 ("And the name Cappadocia is often said to mean *land of beautiful horses*.",Q("Katpatuka: land of beautiful horses","Popular explanation")),
 ("In part 5: the sky above Cappadocia, full of *balloons*.",T(["PART 5","THE","BALLOON SKY"])),
 ("*Follow* so you don't miss it.",FO(5))]),
dict(title="The Sky Fills With Hundreds of Balloons 🎈 Part 5 #shorts",desc="Göreme's rock-cut churches, UNESCO 1985, and Cappadocia's hot air balloons.",tags=TAGS,
 thumb={"lines":["THE BALLOON","SKY"],"red":1,"photo_search":"Cappadocia balloons"},
 broll=["Cappadocia balloons","Goreme Open Air Museum","Uchisar"],
 beats=[
 ("Almost every calm morning, the sky over Cappadocia fills with *hot air balloons*.",P("Cappadocia balloons","CAPPADOCIA BALLOONS"),"hit"),
 ("It's one of the most famous *balloon flight* spots on Earth.",P("Goreme balloons","GÖREME")),
 ("Below them, monks carved *churches* straight into the rock.",P("Goreme Open Air Museum","GÖREME OPEN AIR MUSEUM")),
 ("Some still have *Byzantine frescoes* inside.",P("Goreme fresco","BYZANTINE FRESCOES")),
 ("In 1985, the region became a *UNESCO World Heritage* site.",NU("1985","UNESCO WORLD HERITAGE")),
 ("The highest point is *Uçhisar Castle*, a giant rock full of rooms.",P("Uchisar","UÇHİSAR CASTLE"),"riser"),
 ("Today, people sleep in *cave hotels* carved into the same stone.",P("Cappadocia cave hotel","CAVE HOTELS")),
 ("From 85 meters underground to the sky: Cappadocia's *two faces*.",T(["UNDERGROUND","AND","THE SKY"],2)),
 ("Series finale! Would you sleep in a cave hotel? *Comment below*.",T(["WOULD YOU","SLEEP IN","A CAVE?"],2)),
 ("*Follow* for the next series.",{"type":"icon","name":"eye","label":"FOLLOW FOR MORE"})]),
]
build("S010e_derinkuyu_cappadocia_en","Series: Derinkuyu & Cappadocia (EN)","HIDDEN TÜRKİYE","dosya",["Cappadocia","Derinkuyu","Goreme"],parts,"Derinkuyu & Cappadocia",
      lang="en",voice={"engine":"edge","speaker":"christopher","rate":"+0%","pitch":"-2Hz"},logo={"brand":"HIDDEN TÜRKİYE","mono":"HT"},
      tail=lambda k,n: f"\n\nSeries: Derinkuyu & Cappadocia — Part {k}/{n}. Watch all parts on the channel.")
