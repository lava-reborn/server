import os, re, io
RES = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"
manifests = ["xml/client.xml","xml/database.xml","xml/item_icons.xml","xml/loc_defs.xml",
             "xml/char_defs.xml","xml/mob_defs.xml" ,"xml/avatars.xml","xml/effects.xml",
             "xml/loc_libs.xml","xml/loc_sprites.xml","xml/loc_backs.xml","xml/item_anims.xml",
             "xml/char_anims.xml","xml/_mob_anims.xml","xml/_mob_defs.xml","xml/avatarlist.xml"]
total=missing=0
misslist=[]
for m in manifests:
    p=os.path.join(RES,m)
    if not os.path.isfile(p): continue
    txt=io.open(p,encoding="cp1251",errors="replace").read()
    for href in re.findall(r'href="([^"]+)"', txt):
        total+=1
        if not os.path.isfile(os.path.join(RES,href.replace("/",os.sep))):
            missing+=1
            misslist.append(href)
print("файлов в манифестах: %d, отсутствует локально: %d" % (total, missing))
for h in misslist[:40]:
    print("  нет:", h)
if len(misslist)>40: print("  ... ещё", len(misslist)-40)
