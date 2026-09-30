"""Build data/orig_npcs.json: the original names of NPCs and mobs, from texts.xml.

The owner found the game's own string table, texts.xml (62 795 entries of
<item id="N">text</item>). Its ids do not go on the wire: a creature's name
travels under our own key, its type_id. What this file carries across is only
the text, so the output is a mapping "our type_id -> original text":

    {"_meta":   {"source", "source_md5", "source_size", "rule", "counts"},
     "npcs":    {"<type_id>": {"name", "string_id", "kind": "npc"|"mob",
                               "confidence": "high"}},
     "suggest": {"<type_id>": {"name", "string_id", "confidence": "medium"}}}

"npcs" is what the server imports. "suggest" holds the medium guesses; the
server does not read them, they are hints for the owner's NPC editor. Low
guesses are computed (they take part in the block logic) but not written.

The text is the original one with the XML entities decoded (&lt;Br&gt; ->
<Br>) and nothing else: level prefixes "[3] ...", "<Br>" in upper case and
any typo stay. All formatting happens in one place on the server.

How a creature type finds its string
------------------------------------
Nothing in the client links a creature to a string. The link is rebuilt from
four kinds of evidence, all read from data the project already has:

  name      the internal name in res/database/mobs.xml transliterates or
            translates into the string's name (Aziz_Trader -> "Азиз<Br>...")
  wiki-loc  the fan wiki (data/npc_wiki.json, data/wiki_world/locations.json)
            puts an NPC of that name in a location where the type spawns
            (res/locations/static/<id>.xml)
  sprite    the type's art folder fits the string (1f_Pilot -> "...Пилот",
            1f_Grindstone -> "Точильный камень", animal-* -> "Корова")
  test      "Тестовый ..." strings sit where member 000000 of a family is

and the strings of one family lie in the file as one block, in the same order
as the family's type ids. So:

  * families with a number in the name (Npc_Trader000032, Npc_Commoner000045):
    member k takes string "block start + k". The block start (an offset) is
    chosen by a Viterbi pass over the members, rewarded by wiki placement,
    role, sprite and the test string of member 000000, penalised for jumping
    between offsets. high = the member's own evidence, inside a run backed by
    at least two evidenced members, one of them wiki-loc or test. Only the 8
    heaviest offsets enter the pass; equal weights go to the offset voted
    for first (members in family order, strings by id), so no set or hash
    order ever decides anything.
  * families with speaking names (dn_, wh_, nz_ ...): anchors are strings the
    internal name transliterates into; anchors that keep the family's order
    form chains, and a chain of two or more proper-name anchors is high;
    strings strictly between two anchors fill the types between them 1:1
    (medium).
  * mobs: by name, a proper name found in only one "[N] Name" string, or in
    several with the level equal to ours, is high.
  * anything else that has one strong signal is medium.

Two guards sit on the output, not in the matcher:

  * no string starting with "Тест" is ever written. The "Тестовый ..."
    strings stay in the matcher as evidence (they pin where a block starts)
    but a type assigned one gets no name at all. Two such types do spawn:
    5320 KKND_Npc_Commoner000000 and 8289 VOV_Npc_Lessor000000.
  * strings 9182-9445 are a generated alphabetical list "[N] Name<Br>clan"
    whose level is ((id - 9182) mod 20) + 1 on all 264 of them; they are not
    creature names and are never assigned.

VERIFIED below lists anchors checked by hand. The matcher has to find each of
them on its own (the build stops otherwise); the check only raises a medium
pick of the same string to high.

Output is deterministic: sort_keys, indent=1, ensure_ascii=False; the digest
of the final string table is compared by every player's launcher.

    MSYS_NO_PATHCONV=1 wsl.exe -e bash -lc "cd /mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server && LAVA_RES=/mnt/c/Users/gmkrt/OneDrive/Desktop/lava/res python3 data/build_orig_npcs.py"

The source is LAVA_ORIG_TEXTS (default /mnt/c/Users/gmkrt/Downloads/texts.xml).
"""
import collections
import difflib
import glob
import hashlib
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world  # noqa: E402

DEFAULT_SOURCE = "/mnt/c/Users/gmkrt/Downloads/texts.xml"
OUT = os.path.join(HERE, "orig_npcs.json")
# Creatures the matcher cannot reach by name (mAntilope translates, it does
# not transliterate), given their rows by hand with the evidence beside each.
MANUAL = os.path.join(HERE, "orig_names_manual.json")

GENERATED = range(9182, 9446)   # "[N] Name<Br>clan", level = ((id-9182) % 20) + 1
FIRST_CREATURE_STRING = 8822    # ids below are the item table
TEMPLATE_PREFIX = "тестов"      # "Тестовый аукцион": evidence where member 000000 sits
TEST_PREFIX = "тест"            # output guard: nothing starting with this is written

# Checked by hand: type_id -> (string_id, a fragment of its text).
VERIFIED = {
    5212: (10437, "Борис<Br>Пистолеты и патроны"),
    5221: (10446, "Шульц<Br>Пистолеты и патроны"),
    5216: (10441, "Адам<Br>старший помощник"),
    5215: (10440, "Доктор Гофус<Br>Специальное снаряжение"),
    5140: (10389, "Ибн Сина<Br>Лекарь"),
    5198: (10386, "Фая<Br>Аренда транспорта"),
    5211: (10436, "Морис<Br>Еда и Медикаменты"),
    5122: (9637, "Кондрат<Br>Пилот"),
    5146: (9640, "Жрец Тефнут"),
    5189: (9645, "Сорванец"),
    5192: (9648, "Точильный камень"),
    5195: (9651, "Корова"),
    1682: (46953, "Кукуруза"),
}

RULE = (
    "type_id -> original string. Numbered families (Npc_Trader000039): member k takes string "
    "block start + k, the start picked by a Viterbi pass over wiki placement, role, sprite "
    "and the 'Тестовый' string of member 000000; high = own evidence in a run with >=2 "
    "evidenced members incl. a wiki-loc or test one. Speaking-name families (dn_, wh_, nz_): "
    "transliteration anchors chained in family order; >=2 proper-name anchors = high, 1:1 fill "
    "between anchors = medium. Mobs: proper name in one '[N] Name' string or level-equal = high. "
    "Single strong signal = medium. Output drops strings starting with 'Тест' and never uses "
    "the generated block 9182-9445. Text = html.unescape of the original, nothing else."
)


# --------------------------------------------------------------- original texts
def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def read_json(path):
    return json.loads(read_bytes(path).decode("utf-8"))


def load_texts(path):
    """id -> text with the XML entities decoded, plus md5 and size of the file."""
    raw = read_bytes(path)
    texts = {}
    for m in re.finditer(r'<item id="(\d+)">(.*?)</item>', raw.decode("utf-8"), re.S):
        texts[int(m.group(1))] = html.unescape(m.group(2))
    return texts, hashlib.md5(raw).hexdigest(), len(raw)


# --------------------------------------------------------------- text helpers
BR = re.compile(r"</?[Bb][Rr]\s*/?>")
TAG = re.compile(r"<[^>]+>")
WORD = re.compile(r"[a-zа-яё]+", re.I)
CYR = re.compile("[а-яё]", re.I)


def parse(s):
    """'[3] Name<Br>Role<Br>Faction' -> (3, 'Name', ['Role', 'Faction'])."""
    m = re.match(r"^\[(\d+)\]\s*(.*)$", s, re.S)
    lvl = int(m.group(1)) if m else None
    body = m.group(2) if m else s
    parts = [TAG.sub("", p).replace("\\", "").strip() for p in BR.split(body)]
    return lvl, parts[0], [p for p in parts[1:] if p]


def words(s):
    return [w.lower() for w in WORD.findall(s)]


def norm(x):
    return re.sub(r"[^0-9a-zа-я]", "", x.lower().replace("ё", "е"))


# --------------------------------------------------------------- transliteration
RU = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
              ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r",
               "s", "t", "u", "f", "h", "c", "ch", "sh", "sh", "", "y", "", "e", "yu", "ya"]))
LATNORM = (("sch", "sh"), ("tch", "ch"), ("ph", "f"), ("kh", "h"), ("ck", "k"), ("tz", "c"), ("ts", "c"),
           ("x", "ks"), ("w", "v"), ("q", "k"), ("ee", "i"), ("oo", "u"), ("ou", "u"), ("iy", "i"),
           ("yi", "i"), ("ya", "ia"), ("yu", "iu"), ("j", "dzh"), ("dzhdzh", "dzh"), ("th", "t"), ("gh", "g"))


def ru2lat(w):
    return "".join(RU.get(ch, ch) for ch in w.lower())


def latnorm(w):
    """Fold the spelling variants of a Latin transliteration into one form."""
    w = w.lower()
    for a, b in LATNORM:
        w = w.replace(a, b)
    w = w.replace("y", "i")
    return re.sub(r"(.)\1+", r"\1", w)


def skel(w):
    return re.sub(r"[aeiou]", "", w)


def tsim(lat_token, ru_word):
    """How well a Latin token of an internal name spells a Russian word, 0..1."""
    a = latnorm(lat_token)
    b = latnorm(ru2lat(ru_word))
    if not a or not b:
        return 0.0
    r1 = difflib.SequenceMatcher(None, a, b).ratio()
    sa, sb = skel(a), skel(b)
    r2 = difflib.SequenceMatcher(None, sa, sb).ratio() if len(sa) >= 3 and len(sb) >= 3 else 0
    r3 = 0.85 if len(a) >= 4 and b.startswith(a) else 0.0     # Posl -> послушник
    return max(r1, r2 * 0.95, r3)


# English words of internal names -> Russian stems they translate into.
DICT = {
    'box': ['ящик', 'короб', 'сундук', 'контейнер'], 'boxes': ['ящик'], 'chest': ['сундук', 'ящик'], 'crate': ['ящик'],
    'safe': ['сейф', 'хранилищ', 'тайник'], 'seif': ['сейф'], 'bank': ['банк', 'хранилищ', 'тайник'], 'bankir': ['банкир'],
    'grave': ['могил'], 'slave': ['раб'], 'police': ['полиц'], 'policeman': ['полиц'], 'chief': ['начальник', 'шеф'],
    'boy': ['мальчик', 'хулиган', 'сорванец', 'пацан', 'малыш'], 'kid': ['ребен', 'мальчик', 'девоч', 'малыш', 'внучок', 'хулиган'],
    'child': ['ребен', 'сын', 'доч'], 'son': ['сын'], 'wife': ['жена', 'жены'], 'woman': ['женщин'], 'girl': ['девушк', 'девоч'],
    'stove': ['печ'], 'avto': ['автомобил', 'машин'], 'auto': ['автомобил', 'машин'], 'car': ['автомобил', 'машин'],
    'dog': ['собак', 'пёс', 'пес'], 'rat': ['крыс'], 'antelope': ['антилоп'], 'antilope': ['антилоп'], 'cow': ['коров'],
    'camel': ['верблюд'], 'hyena': ['гиен'], 'croc': ['крокодил'], 'crocodile': ['крокодил'], 'jackal': ['шакал'],
    'cobra': ['кобр'], 'snake': ['змея', 'змей'], 'scorpion': ['скорпион'], 'wolf': ['волк'], 'vulture': ['гриф', 'стервятник'],
    'mach': ['пулемет', 'пистолет-пулемет'], 'gun': ['оруж', 'пулемет'], 'sub': ['пистолет-пулемет'], 'ekspert': ['эксперт'],
    'expert': ['эксперт'], 'locksmith': ['слесар'], 'sell': ['продаж', 'скупк', 'продав'], 'res': ['ресурс'], 'land': ['земл'],
    'alchemy': ['алхим'], 'battle': ['боев'], 'guard': ['охран', 'страж', 'часов', 'стража'], 'guardian': ['страж', 'хранител'],
    'sentry': ['часов'], 'watcher': ['дозор', 'смотрител', 'часов', 'сторож'],
    'soldier': ['солдат', 'рядов'], 'officer': ['офицер'], 'commander': ['командир', 'командер'], 'captain': ['капитан'],
    'sergeant': ['сержант'], 'corporal': ['капрал'], 'colonel': ['полковник'], 'major': ['майор'], 'general': ['генерал'],
    'private': ['рядов'], 'sniper': ['снайпер'], 'shooter': ['стрелок', 'стрелк'], 'rifler': ['стрелок', 'винтов'],
    'gunner': ['стрелок', 'пулемет', 'автоматчик'], 'assault': ['штурм', 'автомат'], 'raider': ['налетчик', 'налётчик'],
    'bandit': ['бандит'], 'leader': ['лидер', 'главар', 'вожак', 'предводител'], 'chieftain': ['главар', 'вожд', 'атаман'],
    'boss': ['босс', 'главар', 'хозяин'], 'courier': ['курьер', 'связн'], 'recruit': ['рекрут', 'новобран'],
    'miner': ['шахтер', 'шахтёр'], 'worker': ['рабоч'], 'driver': ['водител', 'шофер'], 'pilot': ['пилот', 'летчик', 'лётчик'],
    'mechanic': ['механик'], 'medic': ['медик', 'лекар', 'врач', 'доктор'], 'medik': ['медик', 'лекар', 'врач', 'доктор'],
    'med': ['медик', 'медицин', 'лекар', 'лекарств', 'медикамент'], 'healer': ['лекар', 'целител', 'медик'],
    'doctor': ['доктор', 'врач'], 'dr': ['доктор'], 'nurse': ['медсестр'], 'priest': ['жрец'],
    'monk': ['инок', 'монах', 'послушник'], 'master': ['мастер'], 'crafter': ['мастер', 'сборк', 'верстак', 'производ'],
    'craft': ['мастер', 'сборк', 'верстак'], 'trader': ['торгов'], 'trd': ['торгов'], 'seller': ['торгов', 'продав'],
    'lessor': ['аренд'], 'auctioneer': ['аукцион'], 'auction': ['аукцион'], 'lottery': ['лотер'], 'lotery': ['лотер'],
    'ammo': ['патрон', 'боеприпас'], 'pistol': ['пистолет'], 'pistols': ['пистолет'], 'shotgun': ['дробовик'],
    'shotguns': ['дробовик'], 'rifle': ['винтов'], 'rifles': ['винтов'], 'assrifle': ['автомат'],
    'assaultrifles': ['автомат'], 'submachgun': ['пистолет-пулемет', 'пп'], 'submachineguns': ['пистолет-пулемет'],
    'machinegun': ['пулемет'], 'machineguns': ['пулемет'], 'machgun': ['пулемет'], 'machingun': ['пулемет'],
    'knife': ['нож'], 'knifes': ['нож'], 'food': ['еда', 'еды', 'продукт', 'пищ'], 'wear': ['одежд', 'брон'],
    'armor': ['брон'], 'set': ['комплект', 'снаряжен'], 'exchange': ['обмен'], 'gold': ['золот'], 'stone': ['камен', 'камн'],
    'grindstone': ['точильн'], 'terminal': ['терминал'], 'door': ['двер'], 'container': ['контейнер'],
    'plant': ['растени', 'куст'], 'corn': ['кукуруз'], 'flower': ['цвет'], 'bush': ['куст'], 'tree': ['дерев', 'ёлк', 'елк'],
    'barrel': ['бочк'], 'tent': ['палатк'], 'nitre': ['селитр'], 'powder': ['порох'], 'factory': ['завод', 'фабрик', 'цех'],
    'bus': ['автобус'], 'enter': ['вход'], 'exit': ['выход'], 'lifter': ['лифт'], 'lift': ['лифт'],
    'trainer': ['обучени', 'инструктор', 'учител', 'тренер'], 'teacher': ['учител', 'обучени'], 'upgrader': ['улучшен'],
    'upg': ['улучшен'], 'modif': ['модиф', 'улучшен'], 'trmodif': ['улучшен', 'модиф'], 'butcher': ['мясник', 'живодер'],
    'fingers': ['пальц'], 'ears': ['уш'], 'hands': ['рук', 'кист'], 'scalps': ['скальп'], 'sculs': ['череп'],
    'skulls': ['череп'], 'horns': ['рог'], 'merc': ['наемник', 'наёмник'], 'mercenary': ['наемник'], 'farmer': ['фермер'],
    'hermit': ['отшельник'], 'bomb': ['бомб'], 'defender': ['защитник'], 'wounded': ['ранен'],
    'dead': ['мертв', 'мёртв', 'останк'], 'corpse': ['останк', 'труп', 'тел'], 'ghost': ['призрак'], 'zombie': ['зомби'],
    'robot': ['робот'], 'droid': ['дроид'], 'alien': ['пришел', 'инопланет'], 'ufo': ['нло', 'инопланет'],
    'archeolog': ['археолог'], 'archaeologist': ['археолог'], 'fash': ['фашист'], 'pirate': ['пират'],
    'terrorist': ['террорист'], 'smuggler': ['контрабанд'], 'custom': ['таможен'], 'customs': ['таможен'],
    'barmen': ['бармен'], 'bartender': ['бармен'], 'dancer': ['танцовщ'], 'client': ['посетител'],
    'bodyguard': ['телохранител'], 'bouncer': ['вышибал'], 'baker': ['пекар'], 'tailor': ['портн'], 'clerk': ['клерк'],
    'banker': ['банкир'], 'treasurer': ['казначей'], 'kaznachey': ['казначей'], 'accountant': ['бухгалтер'],
    'snowman': ['снегов'], 'santa': ['дед мороз'], 'ded': ['дед'], 'moroz': ['мороз'], 'hammer': ['хаммер'],
    'donkey': ['осел', 'осёл', 'ослик'], 'horse': ['лошад', 'конь'], 'motorcycle': ['мотоцикл'], 'uaz': ['уаз'],
    'airship': ['дирижабл'], 'helicopter': ['вертолет', 'вертолёт'], 'truck': ['грузовик'], 'camelcaravan': ['караван'],
    'caravan': ['караван'], 'nomad': ['кочевник'], 'refugee': ['беженец', 'беженк'], 'local': ['местн', 'житель'],
    'man': ['мужчин', 'человек', 'житель'], 'person': ['человек', 'житель'], 'homeless': ['бомж'], 'bich': ['бомж', 'бич'],
    'drunk': ['пьяниц', 'пьян'], 'old': ['стар'], 'owner': ['владел', 'хозя'], 'brigadir': ['прораб', 'бригадир'],
    'foreman': ['прораб', 'бригадир'], 'scout': ['скаут', 'разведчик'], 'spy': ['шпион', 'лазутчик'],
    'saboteur': ['диверсант'], 'hunter': ['охотник'], 'stalker': ['сталкер'], 'agent': ['агент'], 'tourist': ['турист'],
    'captive': ['пленн', 'заложник'], 'prisoner': ['заключ', 'пленн'], 'hostage': ['заложник'], 'pogonshik': ['погонщик'],
    'vodonos': ['водонос'], 'strannik': ['странник'], 'posl': ['послушник'], 'naemnik': ['наемник', 'наёмник'],
    'pereselenec': ['переселен'], 'sorting': ['сортир', 'сортировщ'], 'mine': ['шахт', 'мина'], 'cannonmeat': ['пушечн'],
    'evildog': ['злая собака', 'собак'], 'source': ['залеж', 'источник', 'руда', 'жила'], 'copper': ['мед'],
    'lead': ['свин'], 'plumbum': ['свин'], 'iron': ['желез'], 'coal': ['угол', 'угль'], 'weapon': ['оруж'],
    'part': ['детал', 'част'], 'parts': ['детал', 'част'], 'reward': ['наград'], 'present': ['подар'],
    'presents': ['подар'], 'gift': ['подар'], 'teleport': ['телепорт'], 'portal': ['портал'], 'generator': ['генератор'],
    'computer': ['компьютер'], 'radio': ['рац', 'радио'], 'table': ['стол'], 'workbench': ['верстак'],
    'bench': ['верстак', 'скамь'], 'map': ['карт'], 'cartographer': ['картограф'], 'librarian': ['библиотек'],
    'judge': ['судья'], 'executioner': ['палач'], 'cook': ['повар'], 'fisherman': ['рыбак'], 'hunter2': ['охот'],
    'spirit': ['дух'], 'god': ['бог'], 'goddess': ['богин'], 'tefnut': ['тефнут'], 'mummy': ['мумия', 'мумии'],
    'pharaoh': ['фараон'], 'sphinx': ['сфинкс'],
}

# Tokens of internal names that say nothing about the name: prefixes of
# families, clans, levels and single letters.
STOP = set("""nz wh dn ab ah abri ow mr mg oasis npc lvl mob old new the of in out inside outdoor up st pm ny g q l t b s
a n c e w v uf tef dom inst cl clan test quest admin vbg ves hws vov lemon lm rb lib kknd m m05 m510 m1520 mrare na me lc
vh dp ah n ow ol olm simple env x p r i k d f h o u y z j lvl1 lvl2 own ownloc trd2 hs inv add db blackwater zeon
liberty delta force raid battalion smersh evan noob ilg my zakon lexus vendetta gdi steel legion cl co clan clun one
two""".split())
SMALL = set("с и в на из у по за для к от до о об а the of".split())


def content_tokens(internal):
    """'Npc_AzizTrader02' -> ['aziz', 'trader']: the words that may name something."""
    raw = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", internal)
    return [t.lower() for t in raw if not t.isdigit() and t.lower() not in STOP and len(t) >= 2]


def _stem_in(stems, ws):
    return any(w.startswith(st) or (len(st) >= 4 and st in w) for st in stems for w in ws)


def token_match(tok, name_words, role_words):
    """Best evidence that one internal-name token names this string: (score, kind)."""
    best = (0.0, None)
    stems = DICT.get(tok)
    if stems:
        if _stem_in(stems, name_words):
            return (1.0, "dict")
        if _stem_in(stems, role_words):
            best = max(best, (0.8, "dict-role"))
    if len(tok) >= 3:
        for w in name_words:
            if len(w) >= 3:
                r = tsim(tok, w)
                if r >= 0.72 and r > best[0]:
                    best = (r, "translit")
        for w in role_words:
            if len(w) >= 3:
                r = tsim(tok, w) * 0.8
                if r >= 0.6 and r > best[0]:
                    best = (r, "translit-role")
    return best


def pair_sim(internal, name, roles):
    """Score of an internal name against a string: token coverage and name coverage."""
    ct = content_tokens(internal)
    if not ct:
        return 0.0, []
    nw = words(name)
    rw = [w for r in roles for w in words(r)]
    ms = [(t,) + token_match(t, nw, rw) for t in ct]
    cov = sum(m[1] for m in ms) / len(ct)
    content_nw = [w for w in nw if w not in SMALL and len(w) >= 3]
    ncov = 0.0
    if content_nw:
        expl = 0
        for w in content_nw:
            expl += any(_stem_in(DICT.get(t, []), [w]) or (len(t) >= 3 and tsim(t, w) >= 0.72) for t in ct)
        ncov = expl / len(content_nw)
    return 0.6 * cov + 0.4 * ncov, ms


# --------------------------------------------------------------- evidence rules
ITEMY = re.compile(r"\(\w{1,3}\)|\]\(|№|\bот\s+[A-Za-z]|за голд|\d+у\b|\bкл\.|Коллекц|^Чип |\bмод\b|\d+\s*шт"
                   r"|[A-Z]{1,3}\d{2,}|\d+[xх]\d+")

# What the roles of a string say, by root_type_id of mobs.xml (world.TRADER ...).
ROLE_RX = {
    1: r"торг|патрон|оруж|пистолет|винтов|автомат|пулем|дробов|еда|медикам|лекарств|одежд|брон|снаряж|обмен|скупк"
       r"|продукт|товар|нож|лотер|чертеж|барыг|антиквар|подар|цвет|боеприпас",
    2: r"обучени|специализ|инструктор|учител",
    3: r"улучшен|модерниз|подгон",
    5: r"лекар|медик|медсестр|целит|врач",
    6: r"аренд|транспорт|перел[её]т|пилот|водител",
    7: r"аукцион",
}
CLASS_WORDS = {1: r"торгов", 2: r"обучение специализац", 5: r"лекар|медик|целительн|медсестр",
               6: r"аренда транспорт", 7: r"аукционер", 3: r"улучшени"}

# (art folder regex, string regex, weight)
SPRITE_CUES = [
    (r"pilot", r"пилот|л[её]тчик", 0.7),
    (r"grindstone", r"точильн", 0.9),
    (r"animal|^dog|camel|^cow|antelope|f8_rat|hyena|croc|donkey|horse|verblud",
     r"корова|собак|п[её]с\b|верблюд|антилоп|крыс|гиен|крокодил|животн|осел|осёл|ослик|конь|лошад|скот", 0.8),
    (r"child|nigerboy|kid", r"хулиган|сорванец|сын\b|внук|мальчик|малыш|пацан|ребен|девочк|внучок", 0.7),
    (r"box|crate|safe|seif|chest|sunduk", r"ящик|сейф|хранилищ|сундук|тайник|контейнер|шкаф|шкатулк", 0.7),
    (r"inok|monk", r"жрец|послушник|святой|монах|инок|падре|отец", 0.7),
    (r"naemnik", r"на[её]мник", 0.7),
    (r"soldat|^a\d|mob-a\d", r"солдат|сержант|рядов|капрал|лейтенант|капитан|майор|полковник|прапорщик|офицер"
                            r"|генерал|часов|охран|старшина|интендант", 0.35),
    (r"plant|corn|bush|flower|elka|tree", r"кукуруз|растени|куст|цвет|дерев|ёлк|елк|пальм|кактус", 0.8),
    (r"rip\d|grave", r"могил", 0.8),
    (r"pechka|stove", r"печ", 0.8),
    (r"fiat|avto|uaz|truck|jeep|car\b", r"автомобил|машин|грузовик|уаз|джип", 0.8),
    (r"dead", r"мертв|мёртв|останк|труп|тел[оа]", 0.6),
    (r"bich", r"бомж|бич|попрошай|нищ|пьяниц", 0.5),
]
STRONG = {"wiki-loc", "test", "sprite"}
TEMPLATE_KEY = {"medic": "медик", "lessor": "транспорт", "spectrainer": "специализ", "auctioneer": "аукцион",
                "trader": "торг", "upgrader": "апгрейд", "bankir": "банкир"}
SAFE_ART = ("1f_Safe", "1f_BankSafe", "1f_Seif_Stary")
LEVEL_SOURCES = ("name", "name_index", "wiki", "name_band", "camp")
RANK = {"high": 3, "medium": 2, "low": 1}
GENERIC = re.compile(r"^(.*?Npc_[A-Za-z]+?)(\d+)$|^([A-Za-z]+_[A-Z])_?(\d+)$|^([A-Za-z_]+?)_?(\d{4,})$")


def is_template(name):
    """A 'Тестовый ...' string: what the developers named member 000000 of a family."""
    return name.lower().startswith(TEMPLATE_PREFIX)


def is_test(text):
    """Output guard: the text, or its name after a '[N] ' level, starts with 'Тест'."""
    low = text.lower()
    return low.startswith(TEST_PREFIX) or bool(re.match(r"\[\d+\]\s*" + TEST_PREFIX, low))


# --------------------------------------------------------------- string pool
def string_record(i, s):
    """A string that can be a creature's name, parsed; None for everything else."""
    if s.startswith("<") or len(s) > 220 or "%" in s or "$" in s:
        return None
    lvl, name, roles = parse(s)
    if not name or len(name) > 60 or len(name.split()) > 7:
        return None
    if name[-1] in ".!?:,;" and not name.endswith("мл.") and not name.endswith("ст."):
        return None
    if re.search(r"\[[A-Za-zА-Яа-я]", name) or re.search(r"\(\d", name):   # item grades, counts
        return None
    kind = "L" if lvl is not None else ("B" if roles else "P")     # [N] level / Name<Br>Role / plain
    if kind == "P" and len(name) > 45:
        return None
    return dict(lvl=lvl, name=name, roles=roles, kind=kind, fake=i in GENERATED,
                latin=not CYR.search(name))


class Matcher:
    def __init__(self, texts, creatures, type_locs, wiki_locs):
        self.texts = texts
        self.creatures = creatures      # type_id -> dict(root, internal, res, level)
        self.type_locs = type_locs      # type_id -> static location ids it spawns in
        self.wiki_locs = wiki_locs      # norm(name) -> location ids the wiki puts it in
        self.pool = {}
        for i in sorted(texts):
            r = string_record(i, texts[i])
            if r:
                self.pool[i] = r
        strong = {i for i, r in self.pool.items() if r["kind"] in "LB" and not r["fake"]}
        for i, r in self.pool.items():
            r["near"] = sum(1 for k in range(i - 4, i + 5) if k != i and k in strong)
        self.by_name = collections.defaultdict(list)
        for i, r in self.pool.items():
            if not r["fake"]:
                self.by_name[norm(r["name"])].append(i)
        self.cand = self._candidates()
        self.result = {}

    # ---- candidates: strings an internal name may spell or translate into
    def _candidates(self):
        tri = collections.defaultdict(set)
        stem_ix = collections.defaultdict(set)
        for i, r in self.pool.items():
            if r["fake"]:
                continue
            for w in words(r["name"]) + [w for x in r["roles"] for w in words(x)]:
                if len(w) < 3:
                    continue
                lw = latnorm(ru2lat(w))
                for k in range(len(lw) - 2):
                    tri[lw[k:k + 3]].add(i)
                for n in range(2, min(len(w), 8) + 1):
                    stem_ix[w[:n]].add(i)
        cand = {}
        for t in sorted(self.creatures):
            internal = self.creatures[t]["internal"]
            ct = content_tokens(internal)
            if not ct:
                continue
            cs = set()
            for tok in ct:
                for st in DICT.get(tok, []):
                    cs |= stem_ix.get(st[:8], set())
                if len(tok) >= 3:
                    lt = latnorm(tok)
                    grams = [lt[k:k + 3] for k in range(len(lt) - 2)]
                    cnt = collections.Counter()
                    for g in grams:
                        for i in tri.get(g, ()):
                            cnt[i] += 1
                    need = 1 if len(grams) <= 2 else 2
                    cs |= {i for i, c in cnt.items() if c >= need}
            res = []
            for i in sorted(cs):
                r = self.pool[i]
                sc, ms = pair_sim(internal, r["name"], r["roles"])
                prop = max([m[1] for m in ms if m[2] == "translit" and len(m[0]) >= 4 and m[0] not in DICT] + [0])
                if sc >= 0.45 or prop >= 0.8:
                    res.append((round(sc, 3), round(prop, 3), i))
            res.sort(reverse=True)
            cand[t] = res[:25]
        return cand

    # ---- evidence
    def usable(self, i, root):
        """String i may name a creature of this root: mobs take '[N] Name', NPCs the rest."""
        r = self.pool.get(i)
        if r is None or r["fake"] or r["latin"] or i < FIRST_CREATURE_STRING or ITEMY.search(r["name"]):
            return False
        return r["kind"] == "L" if root == 0 else r["kind"] != "L"

    def text_of(self, i):
        r = self.pool[i]
        return (r["name"] + " " + " ".join(r["roles"])).lower()

    def sprite_cue(self, t, i):
        art = (self.creatures[t]["res"] or "").lower()
        if i not in self.pool:
            return 0.0, None
        txt = self.text_of(i)
        for srx, trx, w in SPRITE_CUES:
            if re.search(srx, art):
                if re.search(trx, txt):
                    return w, "sprite"
                return (-0.3 if w >= 0.7 else 0.0), None
        return 0.0, None

    def name_ev(self, t, i):
        for sc, prop, j in self.cand.get(t, []):
            if j == i:
                return max(sc, prop * 0.95), prop
        return 0.0, 0.0

    def wikiloc(self, t, i):
        r = self.pool.get(i)
        return bool(r and self.wiki_locs.get(norm(r["name"]), set()) & self.type_locs.get(t, set()))

    def roleok(self, t, i):
        rx = ROLE_RX.get(self.creatures[t]["root"])
        r = self.pool.get(i)
        return bool(r and rx and re.search(rx, (" ".join(r["roles"]) + " " + r["name"]).lower()))

    def role_clash(self, t, i):
        """The string says it is a different class of NPC than the type is."""
        root = self.creatures[t]["root"]
        txt = " ".join(self.pool[i]["roles"]).lower()
        for c, rx in CLASS_WORDS.items():
            if c != root and re.search(rx, txt) and not (root in (1, 4) and c in (1, 3)):
                return True
        return False

    def put(self, t, i, conf, how, ev=()):
        old = self.result.get(t)
        if old and RANK[old["conf"]] >= RANK[conf]:
            return
        self.result[t] = dict(sid=i, conf=conf, how=how, ev=list(ev))

    # ---- families
    def families(self):
        fams = collections.defaultdict(list)
        for t in sorted(self.creatures):
            v = self.creatures[t]
            m = GENERIC.match(v["internal"])
            if m:
                pre = m.group(1) or m.group(3) or m.group(5)
                num = int(m.group(2) or m.group(4) or m.group(6))
                fams[("gen", pre.lower(), v["root"])].append((num, t))
            else:
                first = re.split(r"[_\d]", v["internal"])[0]
                first = re.sub(r"^([a-z]+)[A-Z].*", r"\1", first).lower() or v["internal"].lower()
                fams[("sem", first, v["root"])].append((t, t))
        for k in fams:
            fams[k].sort()
        return fams

    @staticmethod
    def tight_chains(anch):
        """Chains of anchors in family order whose string gap <= type-position gap + 2."""
        anch = sorted(set(anch), key=lambda a: (a[0], a[1]))
        n = len(anch)
        best = [a[2] for a in anch]
        prev = [-1] * n
        for x in range(n):
            for y in range(x):
                dp_ = anch[x][0] - anch[y][0]
                ds = anch[x][1] - anch[y][1]
                if dp_ > 0 and 0 < ds <= dp_ + 2 and best[y] + anch[x][2] > best[x]:
                    best[x] = best[y] + anch[x][2]
                    prev[x] = y
        used, out = set(), []
        for x in sorted(range(n), key=lambda z: -best[z]):
            ch, y = [], x
            while y >= 0 and y not in used:
                ch.append(y)
                y = prev[y]
            if y >= 0:
                continue
            used.update(ch)
            out.append([anch[z] for z in ch[::-1]])
        return out

    def speaking_family(self, root, lst):
        pool = self.pool
        anch = []
        for pos, (_, t) in enumerate(lst):
            for sc, prop, i in self.cand.get(t, []):
                if not self.usable(i, root):
                    continue
                r = pool[i]
                proper = prop >= 0.85
                dictok = sc >= 0.85 and (r["kind"] in "LB" or r["near"] >= 1)
                if proper or dictok:
                    e = max(sc, prop * 0.95) + (0.15 if self.wikiloc(t, i) else 0)
                    anch.append((pos, i, round(e, 3), t, proper))
        taken = set()
        for ch in sorted(self.tight_chains(anch), key=lambda c: -len(c)):
            ch = [a for a in ch if a[3] not in taken]
            if not ch:
                continue
            nproper = sum(1 for a in ch if a[4])
            for pos, i, e, t, pr in ch:
                ev = ["name" if pr else "dict-name"] + (["wiki-loc"] if self.wikiloc(t, i) else [])
                shared = len(self.by_name.get(norm(pool[i]["name"]), [i]))
                if len(ch) >= 2 and nproper >= 2 and pr:
                    conf = "high"
                elif len(ch) >= 3 and nproper >= 1:
                    conf = "medium"
                elif pr and e >= 0.9 and (shared == 1 or self.wikiloc(t, i)):
                    conf = "medium"
                else:
                    conf = "low"
                self.put(t, i, conf, "name, chain of %d" % len(ch), ev)
                taken.add(t)
            for (p1, s1, _, _, pr1), (p2, s2, _, _, pr2) in zip(ch, ch[1:]):
                ts = [lst[p][1] for p in range(p1 + 1, p2)]
                ss = list(range(s1 + 1, s2))
                if not ss:
                    continue
                conf = "medium" if (pr1 and pr2) else "low"
                if len(ts) == len(ss) and all(self.usable(i, root) for i in ss):
                    for t, i in zip(ts, ss):
                        self.put(t, i, conf, "block order between %d and %d" % (s1, s2), ["order"])
                elif ts:
                    # more types than strings: pair by local evidence, keep the order
                    j0 = 0
                    for t in ts:
                        for j in range(j0, len(ss)):
                            e, _ = self.name_ev(t, ss[j])
                            sc, _ = self.sprite_cue(t, ss[j])
                            if (e >= 0.5 or sc > 0.5) and self.usable(ss[j], root):
                                self.put(t, ss[j], conf, "block order + weak name", ["order", "weak-name"])
                                j0 = j + 1
                                break

    def score_member(self, t, i, num):
        """Score of string i for member num of a numbered family, with the reasons."""
        root = self.creatures[t]["root"]
        if not self.usable(i, root):
            return None, []
        sc, why = 0.1, []
        if self.wikiloc(t, i) and (root in (1, 4) or self.roleok(t, i)):
            sc += 1.0
            why.append("wiki-loc")
        if self.roleok(t, i):
            sc += 0.25
            why.append("role")
        if self.role_clash(t, i):
            sc -= 0.6
            why.append("role-clash")
        if is_template(self.pool[i]["name"]):
            if num == 0 or not self.type_locs.get(t):
                sc += 0.8
                why.append("test")
            else:
                sc -= 0.8
        c, k = self.sprite_cue(t, i)
        if c:
            sc += c
            if k:
                why.append("sprite")
        return sc, why

    def member_strings(self, num, t):
        """Strings with strong evidence for member num: wiki names placed where it spawns,
        template strings, strings its sprite depicts."""
        pool = self.pool
        locs = self.type_locs.get(t, set())
        cs = set()
        for nmk in self.wiki_locs:
            if self.wiki_locs[nmk] & locs:
                cs.update(self.by_name.get(nmk, []))
        if num == 0 or not locs:
            cs.update(i for i, r in pool.items() if is_template(r["name"]))
        art = (self.creatures[t]["res"] or "").lower()
        for srx, trx, w in SPRITE_CUES:
            if w >= 0.7 and re.search(srx, art):
                cs.update(i for i, r in pool.items() if not r["fake"] and re.search(trx, self.text_of(i)))
                break
        return sorted(cs)

    def block_offsets(self, lst):
        """The 8 heaviest offsets (string - member number) voted for by two members or more.

        Equal weights are common (every unspawned member votes for every
        'Тестовый' string), so the tie order decides which offsets the Viterbi
        pass may use. Ties go to the offset that got its first vote earliest,
        walking the members in family order and each member's strings by id.
        """
        votes = collections.defaultdict(set)
        weight = {}                                     # insertion order = first vote
        for num, t in lst:
            for i in self.member_strings(num, t):
                s, why = self.score_member(t, i, num)
                if s is not None and set(why) & STRONG and s >= 0.7:
                    votes[i - num].add(t)
                    weight[i - num] = weight.get(i - num, 0.0) + s
        first = {off: k for k, off in enumerate(weight)}
        ranked = sorted(weight, key=lambda off: (-weight[off], first[off]))
        return [off for off in ranked if len(votes[off]) >= 2][:8]

    def numbered_family(self, key, lst):
        top = self.block_offsets(lst)
        if not top:
            return
        offs = sorted({o + dd for o in top for dd in (-2, -1, 0, 1, 2)})
        # Viterbi over "which block offset is member x in", last state = none
        n, S, NEG = len(lst), len(offs) + 1, -1e9
        dp = [[NEG] * S for _ in range(n)]
        bk = [[-1] * S for _ in range(n)]
        cache = {}
        for x, (num, t) in enumerate(lst):
            for s_ in range(S):
                if s_ == S - 1:
                    gain = 0.0
                else:
                    cache[(x, s_)] = self.score_member(t, num + offs[s_], num)
                    gain = cache[(x, s_)][0] or 0.0
                if x == 0:
                    dp[x][s_] = gain
                    continue
                for p in range(S):
                    sw = 0.0 if p == s_ else (-0.6 if S - 1 in (p, s_) else -1.0)
                    v = dp[x - 1][p] + sw + gain
                    if v > dp[x][s_]:
                        dp[x][s_] = v
                        bk[x][s_] = p
        s_ = max(range(S), key=lambda z: dp[n - 1][z])
        path = [0] * n
        for x in range(n - 1, -1, -1):
            path[x] = s_
            s_ = bk[x][s_]
        runs, x = [], 0
        while x < n:
            if path[x] == S - 1:
                x += 1
                continue
            y = x
            while y + 1 < n and path[y + 1] == path[x]:
                y += 1
            runs.append((x, y, path[x]))
            x = y + 1
        used = set()
        for x, y, s_ in runs:
            ev = [z for z in range(x, y + 1) if cache[(z, s_)][0] is not None and set(cache[(z, s_)][1]) & STRONG]
            hard = [z for z in ev if set(cache[(z, s_)][1]) & {"wiki-loc", "test"}]
            for z in range(x, y + 1):
                sc, why = cache[(z, s_)]
                if sc is None or sc < -0.2:
                    continue
                num, t = lst[z]
                i = num + offs[s_]
                if i in used:
                    continue
                used.add(i)
                own = z in ev
                if len(ev) >= 2 and own and hard:
                    conf = "high"
                elif len(ev) >= 2 and (own or ev[0] <= z <= ev[-1]):
                    conf = "medium"
                elif own:
                    conf = "medium"
                elif ev and min(abs(z - e_) for e_ in ev) <= 5:
                    conf = "low"
                else:
                    continue            # pure extrapolation of an offset: not reported
                self.put(t, i, conf, "%s block, member %d -> string %d (offset %d)" % (key, num, i, offs[s_]),
                         ["order"] + why)

    # ---- single types
    def singletons(self):
        for t in sorted(self.cand):
            lst = self.cand[t]
            if t in self.result or not lst:
                continue
            root = self.creatures[t]["root"]
            good = sorted(((max(a, b * 0.95), b, j) for a, b, j in lst if self.usable(j, root)), reverse=True)
            if not good:
                continue
            s, _, i = good[0]
            nm = norm(self.pool[i]["name"])
            second = max([g[0] for g in good[1:] if norm(self.pool[g[2]]["name"]) != nm] + [0])
            if s >= 0.9 and s - second >= 0.15:
                same = self.by_name.get(nm, [i])
                wl = self.wikiloc(t, i)
                self.put(t, i, "medium" if (len(same) == 1 or wl) else "low",
                         "name only; %d strings carry this name" % len(same), ["name"] + (["wiki-loc"] if wl else []))

    def npc_placement(self):
        """Template member 000000 -> its class's test string; else the one wiki name placed here."""
        tests = [i for i, r in self.pool.items() if is_template(r["name"])]
        for t in sorted(self.creatures):
            v = self.creatures[t]
            if v["root"] == 0:
                continue
            m = re.match(r"^(.*?)Npc_([A-Za-z]+?)(\d+)$", v["internal"])
            if m and int(m.group(3)) == 0 and (t not in self.result or self.result[t]["conf"] == "low"):
                key = TEMPLATE_KEY.get(m.group(2).lower())
                hits = [i for i in tests if key and key in self.texts[i].lower()]
                if len(hits) == 1:
                    self.put(t, hits[0], "medium", "template member 000000 -> the test string of its class", ["test"])
            cur = self.result.get(t)
            if cur and (cur["conf"] == "high" or set(cur["ev"]) & STRONG):
                continue
            locs = self.type_locs.get(t, set())
            if not locs or v["res"] in SAFE_ART:
                continue
            cs = {}
            for nmk in self.wiki_locs:              # insertion order of the wiki
                if not self.wiki_locs[nmk] & locs:
                    continue
                for i in self.by_name.get(nmk, []):
                    if (self.usable(i, v["root"]) and not self.role_clash(t, i)
                            and (v["root"] == 4 or self.roleok(t, i)) and self.sprite_cue(t, i)[0] >= 0):
                        cs.setdefault(nmk, []).append(i)
            pick = None
            if len(cs) == 1:
                pick = next(iter(cs.values()))
            elif len(cs) > 1:
                toks = [x for x in content_tokens(v["internal"]) if x not in ("trd", "trader", "npc", "commoner")]

                def rsim(i):
                    if not toks:
                        return 0.0
                    nw_ = words(self.pool[i]["name"])
                    rw_ = [w for r_ in self.pool[i]["roles"] for w in words(r_)]
                    return sum(token_match(x, nw_, rw_)[0] for x in toks) / len(toks)
                ranked = sorted(((rsim(max(ids, key=rsim)), nmk, ids) for nmk, ids in cs.items()), reverse=True)
                if ranked[0][0] >= 0.3 and ranked[0][0] - ranked[1][0] >= 0.15:
                    pick = ranked[0][2]
            if pick:
                ids = sorted(pick, key=lambda i: (-self.roleok(t, i), i))
                if cur and cur["sid"] != ids[0]:
                    self.result.pop(t)
                self.put(t, ids[0], "medium", "wiki places this name here, the role fits, the only such name",
                         ["wiki-loc", "role"])

    def mobs(self):
        """Mobs by name; the level in '[N] Name' and the faction of the location break ties."""
        pool = self.pool
        found = {}
        for t in sorted(self.creatures):
            v = self.creatures[t]
            if v["root"] != 0:
                continue
            groups = {}
            for sc, prop, i in self.cand.get(t, []):
                e = max(sc, prop * 0.95)
                if self.usable(i, 0) and e >= 0.8:
                    groups.setdefault(norm(pool[i]["name"]), []).append((e, prop, i))
            if not groups:
                continue
            ranked = sorted(groups.items(), key=lambda kv: -max(x[0] for x in kv[1]))
            members = ranked[0][1]
            e_best = max(x[0] for x in members)
            rival = len(ranked) > 1 and max(x[0] for x in ranked[1][1]) >= e_best - 0.1
            found[t] = (v["level"], e_best, max(x[1] for x in members), rival, sorted({x[2] for x in members}))

        def faction(i):
            return pool[i]["roles"][-1] if pool[i]["roles"] else ""
        loc_fac = collections.defaultdict(collections.Counter)
        for t, (_, _, prop, rival, ids) in found.items():
            if len(ids) == 1 and prop >= 0.85 and not rival:
                for loc in self.type_locs.get(t, set()):
                    loc_fac[loc][faction(ids[0])] += 1
        for t, (lvl, e, prop, rival, ids) in found.items():
            how, picks = [], ids
            if lvl is not None:
                same = [i for i in ids if pool[i]["lvl"] == lvl]
                if same:
                    picks = same
                    how.append("level equal")
                else:
                    dmin = min(abs(pool[i]["lvl"] - lvl) for i in ids)
                    picks = [i for i in ids if abs(pool[i]["lvl"] - lvl) == dmin]
                    how.append("nearest level")
            if len(picks) > 1:
                facs = collections.Counter()
                for loc in self.type_locs.get(t, set()):
                    facs.update(loc_fac[loc])
                picks = sorted(picks, key=lambda i: -facs.get(faction(i), 0))
                if facs.get(faction(picks[0]), 0) > facs.get(faction(picks[1]), 0):
                    how.append("faction of the spawn location")
                    picks = picks[:1]
            proper = prop >= 0.85
            if proper and not rival and len(picks) == 1:
                conf = "high" if (len(ids) == 1 or "level equal" in how) else "medium"
            elif not rival and len(picks) == 1 and e >= 0.85 and "level equal" in how:
                conf = "medium"
            else:
                conf = "low"
            old = self.result.get(t)
            if old is None or RANK[conf] >= RANK[old["conf"]]:
                self.result[t] = dict(sid=picks[0], conf=conf, ev=["name"] + (["level"] if "level equal" in how else []),
                                      how="mob name; %d strings carry it; %s" % (len(ids), ", ".join(how) or "-"))

    def run(self):
        fams = self.families()
        for key in sorted(fams):
            if key[0] == "sem":
                self.speaking_family(key[2], fams[key])
        for key in sorted(fams):
            if key[0] == "gen" and key[2] != 0:
                self.numbered_family(key[1], fams[key])
        self.singletons()
        self.npc_placement()
        self.mobs()
        return self.result


# --------------------------------------------------------------- project data
def load_creatures():
    """type_id -> root, internal name, art folder (mobs.xml) and a trusted level."""
    levels = read_json(os.path.join(HERE, "mob_types.json"))["types"]
    out = {}
    for t, (root, internal, res) in world.mob_types().items():
        j = levels.get(str(t), {})
        lvl = j.get("level") if j.get("level_source") in LEVEL_SOURCES else None
        out[t] = dict(root=root, internal=internal, res=res, level=lvl)
    return out


def load_spawns():
    """type_id -> static location ids it spawns in; norm(title) -> static location ids."""
    base = os.path.join(world.RES, "locations")
    type_locs = collections.defaultdict(set)
    title_ids = collections.defaultdict(set)
    for p in sorted(glob.glob(os.path.join(base, "static", "*.xml"))):
        m = re.match(r"(\d+)\.xml$", os.path.basename(p))
        if not m:
            continue
        loc = int(m.group(1))
        txt = world._read(p)
        head = re.search(r"<location([^>]*)>", txt)
        if not head:
            continue
        title = dict(re.findall(r'(\w+)="([^"]*)"', head.group(1))).get("title", "")
        chunks = world._chunks(txt, "mobs", 8)
        for c in chunks:
            type_locs[int(c[4:8], 16)].add(loc)
        if chunks:
            title_ids[norm(title)].add(loc)
    if not type_locs:
        raise SystemExit("no spawns under %s: set LAVA_RES to the client's res folder" % base)
    return dict(type_locs), title_ids


def load_wiki_places(title_ids):
    """norm(NPC name) -> static location ids the fan wiki places an NPC of that name in."""
    npcs = read_json(os.path.join(HERE, "npc_wiki.json"))["npcs"]
    pages = read_json(os.path.join(HERE, "wiki_world", "locations.json"))["pages"]
    title2ids = collections.defaultdict(set)
    for v in npcs.values():
        for p in v.get("places", []):
            if p.get("location") and p.get("loc_ids"):
                title2ids[p["location"]].update(p["loc_ids"])
    wiki_locs = collections.defaultdict(set)
    for name, v in npcs.items():
        for p in v.get("places", []):
            for loc in p.get("loc_ids") or []:
                wiki_locs[norm(name)].add(int(loc))
    for title, txt in pages.items():
        m = re.search(r"==\s*NPC\s*==(.*?)(\n==[^=]|\Z)", txt, re.S | re.I)
        if not m:
            continue
        ids = title2ids.get(title) or title_ids.get(norm(title))
        if not ids or len(ids) > 6:
            continue
        for n in re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", m.group(1)):
            if not n.startswith("Категория"):
                wiki_locs[norm(n)].update(ids)
    return dict(wiki_locs)


# --------------------------------------------------------------- output
def build(source=None):
    """Return (document, raw matcher result). Raises if a verified anchor is lost."""
    source = source or os.environ.get("LAVA_ORIG_TEXTS") or DEFAULT_SOURCE
    texts, md5, size = load_texts(source)
    creatures = load_creatures()
    type_locs, title_ids = load_spawns()
    result = Matcher(texts, creatures, type_locs, load_wiki_places(title_ids)).run()

    lost = {t: (sid, result.get(t, {}).get("sid")) for t, (sid, frag) in VERIFIED.items()
            if result.get(t, {}).get("sid") != sid or frag not in texts[sid]}
    if lost:
        raise SystemExit("verified anchors not reproduced (type: want, got): %r" % lost)
    promoted = 0
    for t in VERIFIED:
        if result[t]["conf"] != "high":
            result[t] = dict(result[t], conf="high", how=result[t]["how"] + "; verified by hand")
            promoted += 1

    manual = read_json(MANUAL)["types"] if os.path.exists(MANUAL) else {}
    for key, row in sorted(manual.items(), key=lambda kv: int(kv[0])):
        t, sid = int(key), row["string_id"]
        if t not in creatures:
            raise SystemExit("orig_names_manual: type %d is not a creature" % t)
        if sid in GENERATED or row["text"] not in texts.get(sid, ""):
            raise SystemExit("orig_names_manual: type %d wants row %d with %r, the file has %r"
                             % (t, sid, row["text"], texts.get(sid)))
        result[t] = dict(result.get(t, {}), sid=sid, conf="high", how="by hand: " + row["why"])

    npcs, suggest = {}, {}
    dropped = collections.Counter()
    for t in sorted(result):
        r = result[t]
        sid, text = r["sid"], texts[r["sid"]]
        if sid in GENERATED:
            raise SystemExit("type %d got generated string %d" % (t, sid))
        if r["conf"] == "low":
            continue
        if is_test(text):
            dropped[r["conf"]] += 1
            continue
        if r["conf"] == "high":
            npcs[str(t)] = dict(name=text, string_id=sid, kind="mob" if creatures[t]["root"] == 0 else "npc",
                                confidence="high")
        else:
            suggest[str(t)] = dict(name=text, string_id=sid, confidence="medium")
    kinds = collections.Counter(v["kind"] for v in npcs.values())
    doc = {
        "_meta": {
            "source": os.path.basename(source),
            "source_md5": md5,
            "source_size": size,
            "rule": RULE,
            "counts": {
                "npcs": len(npcs),
                "npcs_npc": kinds["npc"],
                "npcs_mob": kinds["mob"],
                "suggest": len(suggest),
                "dropped_test_high": dropped["high"],
                "dropped_test_medium": dropped["medium"],
                "verified_promoted_to_high": promoted,
                "manual": len(manual),
                "creature_types": len(creatures),
            },
        },
        "npcs": npcs,
        "suggest": suggest,
    }
    return doc, result


def dump(doc, path):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)


def main():
    doc, _ = build()
    dump(doc, OUT)
    raw = read_bytes(OUT)
    print("wrote %s: %d bytes, sha256 %s" % (OUT, len(raw), hashlib.sha256(raw).hexdigest()))
    print(json.dumps(doc["_meta"]["counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
