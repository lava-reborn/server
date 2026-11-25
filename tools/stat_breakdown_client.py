"""Display trained values separately from effective gear/effect bonuses.

Numeric .level getters stay effective for combat and equipment checks.
Only the character's overall level uses trained skills, as on the server.
Updates follow existing stat/card events; there are no timers or requests.
"""
from avm_codegen import Compiler

SOURCE = '''
def __sbValue(base, total):
    if base == None or total == None:
        return ""
    delta = Math.round((total - base) * 1000) / 1000
    if delta > 0:
        return String(base) + " (+" + String(delta) + ")"
    if delta < 0:
        return String(base) + " (" + String(delta) + ")"
    return String(base)

def __sbSkillString(num):
    base = this.value
    if base == None:
        return this.__sbSkillStringOrig(num)
    native = this.__sbSkillStringOrig(base)
    return _global.__sbValue(base, this.level) + native.substring(len(String(base)))

def __sbLevel():
    level = 0
    i = 0
    while i < len(this.skillArray):
        if this.skillArray[i].value > level:
            level = this.skillArray[i].value
        i = i + 1
    return level

def __sbIgnoreLevel(obj):
    # Effective-value setters announce gear changes as level-ups natively.
    # The stat snapshot below announces only actual trained-level gains.
    return

def __sbInfo(obj):
    this.__sbInfoOrig(obj)
    i = 0
    while i < len(this.skillArray):
        skill = this.skillArray[i]
        if skill.__sbTrained != None and skill.value > skill.__sbTrained:
            this.__sbSkillGainOrig({"target":skill, "value":skill.value})
        skill.__sbTrained = skill.value
        i = i + 1
    i = 0
    while i < len(this.specArray):
        spec = this.specArray[i]
        if spec.__sbTrained != None and spec.__sbTrained >= 0 and spec.value > spec.__sbTrained:
            this.__sbSpecGainOrig({"target":spec, "value":spec.value})
        spec.__sbTrained = spec.value
        i = i + 1

def __sbCard(obj):
    this.__sbCardOrig(obj)
    attrs = lol.core.Master.getInstance().gamer.attributes
    i = 0
    while i < len(attrs.attribArray):
        field = this["attribute" + String(i)].value
        stat = attrs.attribArray[i]
        field.text = _global.__sbValue(stat.value, stat.level)
        field.autoSize = "right"
        i = i + 1
    if this.showArmorLevel:
        this.showArmorLevel()
    if this.showOD:
        this.showOD()
    if this.showMeleeEvade:
        this.showMeleeEvade()
    if this.showKrit:
        this.showKrit()

def __sbSpecs():
    this.specItemArr = []
    this.__sbSpecsOrig()
    i = 0
    while i < len(this.specItemArr):
        row = this.specItemArr[i]
        stat = row.data
        # The fighter/reputation rows share SlideItem but have no value pair.
        if stat.value != None and stat.value >= 0 and stat.value_bonus != None:
            row.label = stat.title + ", " + _global.__sbValue(stat.value, stat.level)
        i = i + 1

def __sbArmor():
    this.__sbArmorOrig()
    attrs = lol.core.Master.getInstance().gamer.attributes
    base = (3 * attrs.attrib1.value + attrs.attrib3.value) / 4
    field = this.ArmorClassValue.value
    field.text = _global.__sbValue(base, Number(field.text))
    field.autoSize = "right"

def __sbOD():
    this.__sbODOrig()
    attrs = lol.core.Master.getInstance().gamer.attributes
    field = this.od_value.value
    field.text = _global.__sbValue(attrs.ap_max, Number(field.text))
    field.autoSize = "right"

def __sbEvade():
    this.__sbEvadeOrig()
    attrs = lol.core.Master.getInstance().gamer.attributes
    base = attrs.attrib1.value + attrs.attrib3.value + attrs.skill0.value + attrs.spec1.value
    field = this.meleeEvade_value.value
    field.text = _global.__sbValue(base, parseFloat(field.text)) + "%"
    field.autoSize = "right"

def __sbCrit():
    this.__sbCritOrig()
    gamer = lol.core.Master.getInstance().gamer
    weapon = gamer.equipment.primaryItem
    if not weapon:
        return
    kind = weapon.getProp("weapon_type")
    if kind == None or kind < 0 or kind > 5:
        return
    if isNaN(parseFloat(this.crit_txt.text)) or isNaN(parseFloat(this.critDodge_txt.text)):
        return
    # Native firearm constants: pistol, shotgun, assault, rifle, MG, SMG.
    weights = [[1,8,4,2],[0,6,6,3],[1,6,6,4],[1,6,6,5],[0,8,4,6],[1,6,4,7]]
    row = weights[kind]
    attrs = gamer.attributes
    spec = attrs.specArray[row[3]].value
    base = (attrs.attribArray[row[0]].value * row[1] + attrs.attrib3.value * row[2]) / 4 + attrs.skill1.value / 4 + spec
    anti = (attrs.attrib1.value + attrs.attrib3.value) / 2 + attrs.skill1.value / 2 + spec
    this.crit_txt.text = _global.__sbValue(base, parseFloat(this.crit_txt.text)) + "%"
    this.critDodge_txt.text = _global.__sbValue(anti, parseFloat(this.critDodge_txt.text)) + "%"
    this.crit_txt.autoSize = "right"
    this.critDodge_txt.autoSize = "right"
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (args, body) for name, args, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('core', 'player', 'SkillObject'), 'skillString', '__sbSkillStringOrig', '__sbSkillString'),
        (('core', 'player', 'PersAttributes'), 'getLevel', '__sbLevelOrig', '__sbLevel'),
        (('core', 'player', 'PersAttributes'), 'increase_level_func', '__sbSkillGainOrig', '__sbIgnoreLevel'),
        (('core', 'player', 'PersAttributes'), 'increase_spec_level_func', '__sbSpecGainOrig', '__sbIgnoreLevel'),
        (('core', 'player', 'PersAttributes'), 'rp_info', '__sbInfoOrig', '__sbInfo'),
        (('gpui', 'CharInterface'), 'rpUpdate', '__sbCardOrig', '__sbCard'),
        (('gpui', 'CharInterface'), 'attachSpec', '__sbSpecsOrig', '__sbSpecs'),
        (('gpui', 'CharInterface'), 'showArmorLevel', '__sbArmorOrig', '__sbArmor'),
        (('gpui', 'CharInterface'), 'showOD', '__sbODOrig', '__sbOD'),
        (('gpui', 'CharInterface'), 'showMeleeEvade', '__sbEvadeOrig', '__sbEvade'),
        (('gpui', 'CharInterface'), 'showKrit', '__sbCritOrig', '__sbCrit'),
    ):
        wraps.append((path, method, keep, *bodies[helper]))
    return dict(globals=[entry for entry in functions if entry[0] == '__sbValue'], wraps=tuple(wraps))
