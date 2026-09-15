import io, json
U = lambda *cp: "".join(chr(c) for c in cp)
# Real names from the wiki page for the black market, matched to the client's
# internal ids by the role each page describes.
NAMES = {
    "711":  ("wh_lotery_g",       "Золотая лотерея"),
    "2424": ("noobia_bank",       "Аарон"),
    "1200": ("wh_Pistols",        "Пистолеты и патроны"),
    "1201": ("wh_Shotguns",       "Дробовики и патроны"),
    "1202": ("wh_Rifles",         "Винтовки и патроны"),
    "1203": ("wh_SubMachineGuns", "Пистолет-пулеметы и патроны"),
    "653":  ("wh_Lessor",         "Шихаб"),
    "1205": ("wh_set_trd",        "Хамис"),
    "1204": ("wh_wear_trd",       "Ваккас"),
    "636":  ("presents_trader_g", "Савин"),
    "5":    ("Simple_Upgrader",   "Мастер Тиль"),
    "1152": ("wh_knife_trd",      "Однопальцый"),
    "1206": ("wh_med_battle",     "Люций"),
    "1207": ("wh_med_simple",     "Магдалена"),
    "2279": ("wh_modif_knifes",   "Точильный камень"),
    "652":  ("wh_technogeek",     "Техногик"),
}
doc = {
    "_note": ("Real names recovered from lava-online.fandom.com, matched to the "
              "client's type ids by the role each wiki page describes. The file "
              "that carried these in the live game, res/database/texts.xml, is "
              "one of the two missing from the shipped client. Wiki text is "
              "CC-BY-SA. Ids absent here fall back to the internal name."),
    "_source": "https://lava-online.fandom.com/ru/wiki/Черный_рынок_Вади-Хальфы",
    "names": {k: v[1] for k, v in NAMES.items()},
    "internal": {k: v[0] for k, v in NAMES.items()},
}
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/data/npc_names.json"
io.open(p, "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False, indent=2))
print("записано имён: %d" % len(NAMES))
