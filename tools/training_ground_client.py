"""Native AVM1 training terminal using the game's settings-window artwork."""
from avm_codegen import Compiler

SOURCE = '''
def __tgSend(op):
    m = new(lol.server.mess.CSMessage)
    m._name = "tg"
    m.addProp("op", "@" + op + "@")
    m.addProp("token", "@" + _global.__tgToken + "@")
    return m

def __tgTransmit(m):
    manager = lol.server.filters.FilterManager.getInstance()
    was = manager.currentFilter.getFlag("tg")
    manager.currentFilter.setFlag("tg", True)
    lol.server.XMLConnection.getInstance().Send(m)
    manager.currentFilter.setFlag("tg", was)

def __tgServiceActivate():
    m = _global.__tgSend(this.__op)
    m.addProp("npc", this.mob_id)
    _global.__tgTransmit(m)
    lol.core.SceneShifter.closeWindow("support")

def __tgNPCWrapper(obj):
    this.__tgNPCOrig(obj)
    if obj.param.tg_terminal:
        label = "Открыть: " + obj.param.tg_title
        desc = "Персонаж, противник и условия боя."
        if obj.param.tg_supply:
            label = "Получить снаряжение: " + obj.param.tg_title
            desc = "Категории и варианты снаряжения для полигона."
        op = "open"
        service = new(lol.core.player.Attendance, 100, this.id)
        service._name = label
        service._desc = desc
        service.__op = op
        service.activate = _global.__tgServiceActivate
        this.supportList.push(service)

def __tgText(p, name, value, x, y, w, h, input):
    p.createTextField(name, p.getNextHighestDepth(), x, y, w, h)
    f = p[name]
    f.embedFonts = False
    f.wordWrap = True
    f.multiline = True
    f.selectable = input
    fmt = new("TextFormat")
    fmt.font = "Tahoma"
    fmt.size = 12
    fmt.color = 13616814
    f.setNewTextFormat(fmt)
    f.text = value
    if input:
        f.type = "input"
        f.border = True
        f.borderColor = 5394505
        f.background = True
        f.backgroundColor = 3552308
        f.maxChars = 400
    return f

def __tgTile(p, name, bitmap, x, y, w, h):
    c = p.createEmptyMovieClip(name, p.getNextHighestDepth())
    c._x = x
    c._y = y
    c.beginBitmapFill(bitmap, new(flash.geom.Matrix), True, False)
    c.moveTo(0, 0)
    c.lineTo(w, 0)
    c.lineTo(w, h)
    c.lineTo(0, h)
    c.lineTo(0, 0)
    c.endFill()
    return c

def __tgPlate(p, name, x, y, w, h):
    art = _global.__onlineArt(p)
    b = p.createEmptyMovieClip(name, p.getNextHighestDepth())
    b._x = x
    b._y = y
    b.lineStyle(1, 2960680, 100)
    b.beginBitmapFill(art["in"], new(flash.geom.Matrix), True, False)
    b.moveTo(4, 0)
    b.lineTo(w - 4, 0)
    b.curveTo(w, 0, w, 4)
    b.lineTo(w, h - 4)
    b.curveTo(w, h, w - 4, h)
    b.lineTo(4, h)
    b.curveTo(0, h, 0, h - 4)
    b.lineTo(0, 4)
    b.curveTo(0, 0, 4, 0)
    b.endFill()
    b.lineStyle(1, 11053224, 60)
    b.moveTo(5, 1)
    b.lineTo(w - 5, 1)
    return b

def __tgButton(p, name, label, x, y, w, op, value):
    b = _global.__tgPlate(p, name, x, y, w, 25)
    _global.__tgText(b, "caption", label, 5, 3, w - 10, 20, False)
    b.__op = op
    b.__value = value
    b.onRelease = _global.__tgClick
    b.onRollOver = _global.__tgHover
    b.onRollOut = _global.__tgUnhover
    b.hintTitle_str = label
    return b

def __tgHUDResize():
    this._x = Math.max(8, Stage.width - 190)
    this._y = 8

def __tgHUD(phase):
    old = _global.__tgHUDPanel
    if old:
        Stage.removeListener(old)
        old.removeMovieClip()
    hud = _root.createEmptyMovieClip("__tgHUDPanel", _root.getNextHighestDepth())
    _global.__tgHUDPanel = hud
    _global.__tgButton(hud, "main", "К компьютеру", 0, 0, 175, "return", "")
    hud.onResize = _global.__tgHUDResize
    Stage.addListener(hud)
    hud.onResize()

def __tgHUDClose():
    hud = _global.__tgHUDPanel
    if hud:
        Stage.removeListener(hud)
        hud.removeMovieClip()
        _global.__tgHUDPanel = None

def __tgClose():
    p = _global.__tgPanel
    if p:
        p.stopDrag()
        Stage.removeListener(p)
        _global.__tgReleaseRows(p)
        _global.__tgSupplyClear(p)
        p.removeMovieClip()
        _global.__tgPanel = None
        lol.core.SceneShifter.hotKeyManager.removeFilter("tg")
        _global.__rfRepairKeys()
    else:
        lol.core.SceneShifter.hotKeyManager.removeFilter("tg")
    lol.gpui.HintManager.closeHint()

def __tgHover():
    lol.gpui.HintManager.showHint(this.hintTitle_str, 0, this._width)

def __tgUnhover():
    lol.gpui.HintManager.closeHint()

def __tgProfileKey(d):
    return d.skills + ";" + d.specs + ";" + d.gear

def __tgSelected(draft):
    pairs = draft.gear.split(",")
    result = ""
    i = 0
    while i < len(pairs):
        if len(pairs[i]) > 0:
            fields = pairs[i].split(":")
            label = _global.__tgNames[fields[0]]
            if not label:
                label = "Предмет " + fields[0]
            result = result + label + " × " + fields[1] + "\\n"
        i = i + 1
    return result

def __tgPut(draft, id, n):
    pairs = draft.gear.split(",")
    result = []
    found = False
    i = 0
    while i < len(pairs):
        fields = pairs[i].split(":")
        if len(fields) == 2:
            if fields[0] == String(id):
                result.push(String(id) + ":" + String(n))
                found = True
            else:
                if not _global.__tgSlots[id] or _global.__tgSlots[id] != _global.__tgSlots[fields[0]]:
                    result.push(pairs[i])
        i = i + 1
    if not found:
        result.push(String(id) + ":" + String(n))
    draft.gear = result.join(",")


def __tgDraft(who):
    if who == "result":
        p = _global.__tgPanel
        if p and p.mobHealth:
            _global.__tgMobHealth = Number(p.mobHealth.text)
            _global.__tgMobDamage = Number(p.mobDamage.text)
            _global.__tgHealBelow = Number(p.healBelow.text)
            _global.__tgHealCount = Number(p.healCount.text)
        return
    if who == "rules":
        _global.__tgRuleDraft()
        return
    p = _global.__tgPanel
    if not p:
        return
    out = _global.__tgPlayer
    if who == "enemy" or who == "enemygear":
        out = _global.__tgEnemy
    if p.skill0:
        values = []
        i = 0
        while i < 5:
            values.push(Number(p["skill" + String(i)].text))
            i = i + 1
        out.skills = values.join(",")
        values = []
        i = 0
        while i < 15:
            if p["spec" + String(i)]:
                values.push(Number(p["spec" + String(i)].text))
            else:
                values.push(0 - 1)
            i = i + 1
        out.specs = values.join(",")

def __tgRequestList():
    p = _global.__tgPanel
    if not p or not p.query:
        return
    if _global.__tgCategory == "skills" and _global.__tgTab != "mob":
        return
    m = _global.__tgSend("catalogue")
    cat = _global.__tgCategory
    if _global.__tgTab == "mob":
        cat = "mob"
    m.addProp("category", "@" + cat + "@")
    m.addProp("group", "@" + _global.__tgMobGroup + "@")
    _global.__tgCatalogueRequest = _global.__tgCatalogueRequest + 1
    m.addProp("request_id", _global.__tgCatalogueRequest)
    m.addProp("wclass", _global.__tgClass)
    line = _global.__tgLine
    if cat == "ammo" or cat == "medicine" or cat == "mob":
        line = "all"
    m.addProp("line", "@" + line + "@")
    m.addProp("page", _global.__tgPage)
    m.addProp("upgrade", "@" + _global.__tgUpgrade + "@")
    level = _global.__tgFilterLevel
    if cat == "ammo" or cat == "medicine":
        level = 0
    m.addProp("level", level)
    _global.__tgFilterQuery = p.query.text
    m.addProp("query", "@" + String(p.query.text.split("@").join("").split(";").join("").split("%").join("")) + "@")
    _global.__tgTransmit(m)

def __tgLayout(p, center):
    frame = lol.core.SceneShifter._ref
    dx = 0
    dy = 0
    if p.__nativeLayer:
        dx = Math.round(frame.minW / 2)
        dy = Math.round(frame.minH / 2)
    left = Math.round((frame.minW - Stage.width) / 2) + 8 - dx
    top = Math.round((frame.minH - Stage.height) / 2) + 8 - dy
    right = left + Math.max(0, Stage.width - p.__w - 16)
    bottom = top + Math.max(0, Stage.height - p.__h - 16)
    if center:
        p._x = Math.round((frame.minW - p.__w) / 2) - dx
        p._y = Math.round((frame.minH - p.__h) / 2) - dy
    p._x = Math.max(left, Math.min(right, p._x))
    p._y = Math.max(top, Math.min(bottom, p._y))

def __tgDragStart():
    p = this._parent
    frame = lol.core.SceneShifter._ref
    dx = 0
    dy = 0
    if p.__nativeLayer:
        dx = Math.round(frame.minW / 2)
        dy = Math.round(frame.minH / 2)
    left = Math.round((frame.minW - Stage.width) / 2) + 8 - dx
    top = Math.round((frame.minH - Stage.height) / 2) + 8 - dy
    p.startDrag(False, left, top, left + Math.max(0, Stage.width - p.__w - 16), top + Math.max(0, Stage.height - p.__h - 16))

def __tgDragStop():
    this._parent.stopDrag()
    _global.__tgLayout(this._parent, False)

def __tgResize():
    this.stopDrag()
    if this.__w != Math.min(Stage.width - 24, 980) or this.__h != Math.min(Stage.height - 70, 640):
        _global.__tgDraft(_global.__tgTab)
        _global.__tgBuild()
    else:
        _global.__tgLayout(this, False)

def __tgStatsWrapper(obj):
    if _global.__tgActive or _global.__tgSnapshotPending:
        this.__progressLoaded = False
    this.__tgStatsOrig(obj)
    _global.__tgSnapshotPending = False

def __tgBuild():
    old = _global.__tgPanel
    hadOld = Boolean(old)
    if old:
        oldX = old._x
        oldY = old._y
        old.stopDrag()
        Stage.removeListener(old)
        _global.__tgReleaseRows(old)
        _global.__tgSupplyClear(old)
        old.removeMovieClip()
    else:
        lol.core.SceneShifter.hotKeyManager.addFilter("tg")
    layer = lol.core.SceneShifter.linkWindow
    p = layer.createEmptyMovieClip("__tgPanel", layer.getNextHighestDepth())
    p.__nativeLayer = True
    _global.__tgPanel = p
    W = Math.min(Stage.width - 24, 980)
    H = Math.min(Stage.height - 70, 640)
    p.__w = W
    p.__h = H
    if hadOld:
        p._x = oldX
        p._y = oldY
    _global.__tgLayout(p, not hadOld)
    p.onResize = _global.__tgResize
    Stage.addListener(p)
    art = _global.__onlineArt(p)
    _global.__tgTile(p, "inside", art["in"], 0, 0, W, H)
    _global.__tgTile(p, "top", art.t, 22, 0, W - 44, 22)
    _global.__tgTile(p, "bottom", art.b, 22, H - 22, W - 44, 22)
    _global.__tgTile(p, "left", art.l, 0, 22, 22, H - 44)
    _global.__tgTile(p, "right", art.r, W - 22, 22, 22, H - 44)
    _global.__tgTile(p, "tl", art.tl, 0, 0, 22, 22)
    _global.__tgTile(p, "tr", art.tr, W - 22, 0, 22, 22)
    _global.__tgTile(p, "bl", art.bl, 0, H - 22, 22, 22)
    _global.__tgTile(p, "br", art.br, W - 22, H - 22, 22, 22)
    drag = _global.__tgTile(p, "drag", art["in"], 22, 16, W - 80, 28)
    _global.__tgText(drag, "title", _global.__tgPostTitle, 2, 2, W - 90, 24, False)
    drag.onPress = _global.__tgDragStart
    drag.onRelease = _global.__tgDragStop
    drag.onReleaseOutside = _global.__tgDragStop
    _global.__tgButton(p, "cross", "×", W - 51, 15, 27, "close", "")
    if _global.__tgSupply:
        _global.__tgSupplyBuild(p, W, H)
        return
    tabs = ["mob", "enemy", "enemygear", "result", "rules"]
    labels = ["Мобы и боссы", "Навыки бойца", "Снаряжение бойца", "Условия", "Правила"]
    if _global.__tgContext != "computer":
        tabs = ["gear"]
        labels = [_global.__tgPostTitle]
        if _global.__tgContext == "player":
            tabs = ["player"]
            labels = ["Навыки и специализации"]
    i = 0
    tabw = (W - 48) / len(tabs)
    while i < len(tabs):
        button = _global.__tgButton(p, "tab" + String(i), labels[i], 24 + i * tabw, 53, tabw - 5, "tab", tabs[i])
        if _global.__tgTab == tabs[i]:
            button.caption.textColor = 16777215
        i = i + 1
    _global.__tgTile(p, "sectionHead", art.t, 24, 84, W - 48, 3)
    _global.__tgTile(p, "sectionFoot", art.t, 24, H - 115, W - 48, 3)
    _global.__tgText(p, "status", _global.__tgStatus, 24, H - 105, W - 48, 40, False)
    if _global.__tgContext == "computer":
        _global.__tgButton(p, "start", "Вызвать противника", 24, H - 54, 205, "start", "")
        _global.__tgButton(p, "exit", "Покинуть полигон", W - 225, H - 54, 200, "exit", "")
        if _global.__tgTab == "enemy" or _global.__tgTab == "enemygear":
            _global.__tgButton(p, "applyEnemy", "Применить бойца", 250, H - 54, 190, "apply", "")
        modeLabel = "Будет вызван: моб / босс"
        if _global.__tgMode == "fighter":
            modeLabel = "Будет вызван: настроенный боец"
        _global.__tgText(p, "modeLabel", modeLabel, 24, H - 78, 420, 20, False)
    else:
        _global.__tgButton(p, "apply", "Выдать выбранное снаряжение", 24, H - 54, 245, "apply", "")
        _global.__tgButton(p, "close", "Закрыть", W - 150, H - 54, 125, "close", "")
        if _global.__tgContext == "player":
            p.apply.caption.text = "Применить навыки"
            _global.__tgButton(p, "recover", "Восстановить HP / ОД", 280, H - 54, 210, "recover", "")
    if _global.__tgTab == "rules":
        _global.__tgRulesControls(p, W, H)
        return
    if _global.__tgContext == "player" or _global.__tgTab == "enemy":
        _global.__tgSkillsControls(p, W, H)
        return
    if _global.__tgTab == "result":
        _global.__tgButton(p, "location", "Площадка: выбрать ▼", 28, 103, 340, "locations", "")
        _global.__tgText(p, "info", "Участников: " + String(_global.__tgParticipants) + ". Площадка общая; её смена переносит всех. Вещи и опыт в основную игру не переносятся.", 28, 140, W - 56, 42, False)
        _global.__tgText(p, "spawnTitle", "Точка противника", 28, 190, 200, 24, False)
        _global.__tgButton(p, "spawn", _global.__tgSpawnLabels[_global.__tgSpawnPoint] + " ▼", 28, 220, 350, "spawns", "")
        _global.__tgText(p, "distanceInfo", "Расстояние: около " + String(_global.__tgDistance) + " гексов", 28, 257, 350, 24, False)
        _global.__tgButton(p, "mode", "Цель: " + _global.__tgMode + " · изменить", 395, 103, 330, "mode", "")
        p.mode.caption.text = "Цель: моб / босс · изменить"
        if _global.__tgMode == "fighter":
            p.mode.caption.text = "Цель: настроенный боец · изменить"
        behaviour = "Активный противник · агро 100+"
        if _global.__tgStationary:
            behaviour = "Неподвижная мишень"
        _global.__tgButton(p, "stationary", behaviour, 395, 220, 330, "stationary", "")
        healing = "Боец: без лечения"
        if _global.__tgEnemyHealing:
            healing = "Боец: боевая медицина включена"
        _global.__tgButton(p, "healing", healing, 28, 260, 285, "enemyhealing", "")
        _global.__tgText(p, "belowLabel", "Порог HP / Ст, %", 325, 260, 145, 24, False)
        _global.__tgText(p, "healBelow", String(_global.__tgHealBelow), 475, 260, 45, 24, True)
        _global.__tgText(p, "countLabel", "Лечений за бой", 540, 260, 125, 24, False)
        _global.__tgText(p, "healCount", String(_global.__tgHealCount), 670, 260, 45, 24, True)
        _global.__tgText(p, "hpLabel", "HP / выносливость противника, %", 28, 300, 290, 24, False)
        _global.__tgText(p, "mobHealth", String(_global.__tgMobHealth), 325, 300, 70, 24, True)
        _global.__tgText(p, "damageLabel", "Урон противника, %", 430, 300, 210, 24, False)
        _global.__tgText(p, "mobDamage", String(_global.__tgMobDamage), 650, 300, 70, 24, True)
        _global.__tgText(p, "scaleHint", "От 25 до 300%. 100% — исходный моб. Только эта тренировка.", 28, 337, W - 56, 30, False)
        _global.__tgText(p, "report", _global.__tgReport, 28, 380, W - 56, Math.max(35, H - 510), False)
        return
    _global.__tgCatalogueControls(p, W, H)

def __tgRulesControls(p, W, H):
    _global.__tgButton(p, "baseline", "Текущая игра", 28, 100, 165, "rulespreset", "1,1,1,1,1,1,1,1,1,0,0,1,0")
    _global.__tgButton(p, "candidate", "Исправленная модель боя", 203, 100, 245, "rulespreset", "1,1,1,1,1,1,1,1,1,0,1,0,1")
    _global.__tgButton(p, "simulator", "Симулятор: после правок", 458, 100, W - 486, "rulespreset", "1,1,1,1,1,1,1,1,1,0,1,0,1,1")
    _global.__tgText(p, "ruleHint", "Только ваша сессия: персонаж и настраиваемый боец. ×1 — без изменения.", 28, 135, W - 56, 35, False)
    values = _global.__tgRuleDraftValues.split(",")
    labels = ["Сила ×", "Ловкость ×", "Телосложение ×", "Восприятие ×", "Интеллект ×", "Максимум HP ×", "Максимум выносливости ×", "Вся броня ×", "Разброс ×", "Добавка брони от эффекта"]
    i = 0
    cw = (W - 65) / 2
    rulePitch = Math.min(29, Math.max(18, (H - 380) / 5))
    ruleButtonsY = 160 + 5 * rulePitch + 10
    while i < 10:
        x = 28 + Math.floor(i / 5) * cw
        y = 160 + (i % 5) * rulePitch
        _global.__tgText(p, "ruleLabel" + String(i), labels[i], x, y, cw - 105, 24, False)
        field = _global.__tgText(p, "rule" + String(i), values[i], x + cw - 95, y, 75, 24, True)
        field.maxChars = 12
        field.multiline = False
        i = i + 1
    ammo = "Множители патронов: выкл."
    if values[10] == "1":
        ammo = "Множители патронов: вкл."
    broken = "Броня сломанных частей: не учитывать"
    if values[11] == "1":
        broken = "Броня сломанных частей: учитывать"
    _global.__tgButton(p, "ammoRules", ammo, 28, ruleButtonsY, 300, "ruletoggle", 10)
    _global.__tgButton(p, "brokenRules", broken, 340, ruleButtonsY, 320, "ruletoggle", 11)
    _global.__tgButton(p, "applyRules", "Применить правила", 28, ruleButtonsY + 35, 190, "rulesapply", "")
    _global.__tgText(p, "rules", "Действует: " + _global.__tgRules + "\\nБроня персонажа в расчёте: " + String(_global.__tgArmour) + ". Добавка эффекта — имитация, без выдачи настоящего бафа. Исправления боя действуют только на полигоне.", 28, ruleButtonsY + 75, W - 56, Math.max(20, H - ruleButtonsY - 195), False)
    return

def __tgSkillsControls(p, W, H):
    draft = _global.__tgPlayer
    if _global.__tgTab == "enemy" or _global.__tgTab == "enemygear":
        draft = _global.__tgEnemy
    values = draft.skills.split(",").concat(draft.specs.split(","))
    titles = ["Ближний бой", "Стрельба", "Медицина", "Промышленность", "Производство", "Рукопашный бой", "Режущее оружие", "Пистолеты", "Дробовики", "Автоматы", "Винтовки", "Ручные пулемёты", "Пистолет-пулемёты", "Хирургия", "Первая помощь", "Добыча", "Переработка", "Мастер свинца", "Мастер селитры", "Мастер меди"]
    i = 0
    cw = (W - 65) / 2
    pitch = Math.min(29, (H - 290) / 10)
    while i < 17:
        col = Math.floor(i / 10)
        row = i % 10
        x = 24 + col * cw
        y = 140 + row * pitch
        key = "spec" + String(i - 5)
        low = 0 - 1
        high = _global.__tgSpecMax
        if i < 5:
            key = "skill" + String(i)
            low = 0
            high = 20
        _global.__tgText(p, key + "label", titles[i], x, y, cw - 125, 23, False)
        _global.__tgText(p, key, values[i], x + cw - 120, y, 40, 23, True)
        _global.__tgButton(p, key + "minus", "−", x + cw - 75, y, 28, "adjust", {"field":key, "step":0 - 1, "low":low, "high":high})
        _global.__tgButton(p, key + "plus", "+", x + cw - 42, y, 28, "adjust", {"field":key, "step":1, "low":low, "high":high})
        i = i + 1
    if _global.__tgTab == "enemy":
        _global.__tgButton(p, "copy", "Скопировать моего персонажа", 24, 95, 280, "copy", "")
    _global.__tgText(p, "levelHint", "Базовый уровень:", 24, H - 141, 125, 23, False)
    levels = draft.skills.split(",")
    currentLevel = Math.max(Number(levels[0]), Number(levels[1]), Number(levels[2]), Number(levels[3]), Number(levels[4]))
    _global.__tgText(p, "presetLevel", String(currentLevel), 155, H - 141, 42, 23, True)
    _global.__tgButton(p, "setlevel", "Задать", 203, H - 141, 78, "setlevel", "")
    _global.__tgText(p, "levelExplanation", "Уровень персонажа определяется старшим навыком.", 292, H - 141, W - 320, 28, False)
    return
def __tgCatalogueControls(p, W, H):
    left = 24
    area = W - 340
    if _global.__tgTab == "mob":
        left = 205
        area = W - 230
        groups = ["all", "camps", "mines", "bosses", "dogs", "crocodiles", "vagrants", "animals", "other"]
        labels = ["Все противники", "Лагеря", "Шахты", "Боссы", "Собаки", "Крокодилы", "Бродяги", "Другие животные", "Другие"]
        i = 0
        while i < len(groups):
            button = _global.__tgButton(p, "group" + String(i), labels[i], 24, 105 + i * 33, 165, "mobgroup", groups[i])
            if _global.__tgMobGroup == groups[i]:
                button.caption.textColor = 16777215
            i = i + 1
        _global.__tgText(p, "picked", "Выбрано: " + _global.__tgMobName, left, H - 180, area, 34, False)
    else:
        _global.__tgText(p, "kitTitle", "ПОДГОТОВЛЕННЫЙ НАБОР", W - 292, 100, 265, 24, False)
        _global.__tgText(p, "qlabel", "Количество", W - 292, 145, 150, 22, False)
        _global.__tgText(p, "amount", "1", W - 292, 173, 70, 25, True)
        _global.__tgButton(p, "minus", "−", W - 210, 173, 32, "count", 0 - 1)
        _global.__tgButton(p, "plus", "+", W - 170, 173, 32, "count", 1)
        _global.__tgText(p, "gearhelp", "Комплект собирает готового бойца. Выбор оружия заменяет его оружие; нажмите «Применить бойца».", W - 292, 212, 265, 55, False)
        _global.__tgText(p, "selected", _global.__tgSelected(_global.__tgPlayer), W - 292, 280, 230, H - 445, False)
        _global.__tgButton(p, "selectedUp", "▲", W - 57, 280, 28, "selectedscroll", 0 - 1)
        _global.__tgButton(p, "selectedDown", "▼", W - 57, 314, 28, "selectedscroll", 1)
        _global.__tgButton(p, "removeLast", "Убрать последний", W - 292, H - 155, 200, "removeLast", "")
    if _global.__tgTab == "enemygear":
        _global.__tgButton(p, "category", "Категория ▼", 24, 96, 130, "filtermenu", "category")
        _global.__tgButton(p, "class", "Тип оружия ▼", 24, 129, 130, "filtermenu", "class")
        _global.__tgText(p, "catalogueHint", "Готовые комплекты, оружие и расходники бойца. Патроны к выбранному оружию добавятся при применении.", 24, H - 200, area, 50, False)
        left = 165
        area = W - 485
    p.__listX = left
    p.__listY = 175
    p.__listWidth = area
    levelLabel = "Любой уровень"
    if _global.__tgFilterLevel:
        levelLabel = "Ур. " + String(_global.__tgFilterLevel)
    _global.__tgButton(p, "levelfilter", levelLabel + " ▼", left, 103, 100, "filtermenu", "level")
    lineLabel = _global.__tgLine
    if lineLabel == "all":
        lineLabel = "Все версии"
    _global.__tgButton(p, "linefilter", lineLabel + " ▼", left + 106, 103, 85, "filtermenu", "line")
    upgradeLabel = "Все улучшения"
    if _global.__tgUpgrade == "base":
        upgradeLabel = "Без чертежа"
    if _global.__tgUpgrade == "modified":
        upgradeLabel = "С улучшением"
    _global.__tgButton(p, "upgradefilter", upgradeLabel + " ▼", left + 197, 103, 140, "filtermenu", "upgrade")
    p.upgradefilter._visible = _global.__tgCategory == "weapon"
    p.linefilter._visible = _global.__tgCategory != "mob" and _global.__tgCategory != "medicine" and _global.__tgCategory != "ammo"
    p.levelfilter._visible = _global.__tgCategory != "medicine" and _global.__tgCategory != "ammo"
    _global.__tgText(p, "query", _global.__tgFilterQuery, left, 138, area - 88, 25, True)
    _global.__tgButton(p, "search", "Найти", left + area - 80, 138, 80, "search", "")
    _global.__tgButton(p, "prev", "←", left, H - 140, 40, "page", 0 - 1)
    _global.__tgButton(p, "next", "→", left + 48, H - 140, 40, "page", 1)
    _global.__tgText(p, "page", "", left + 100, H - 140, 150, 24, False)
    _global.__tgRequestList()

def __tgThumbReady(event):
    icon = event.target
    width = icon.display_mc._width
    height = icon.display_mc._height
    if width > 0 and height > 0:
        maximum = 38
        if icon.__tgMaxHeight:
            maximum = icon.__tgMaxHeight
        scale = Math.min(48 / width, maximum / height) * 100
        icon._xscale = scale
        icon._yscale = scale
    icon.removeEventListener("completed", icon, _global.__tgThumbReady)

def __tgReleaseRows(p):
    if p.cards:
        i = 0
        while i < 10:
            icon = p.cards["row" + String(i)].icon
            if icon:
                icon.removeEventListener("completed", icon, _global.__tgThumbReady)
                if icon.src:
                    icon.src.removeEventListener("onLoadSource", icon)
                if icon.mcl_list:
                    icon.mcl_list.onLoadInit = None
            i = i + 1
        p.cards.removeMovieClip()
    if p.preview:
        if p.preview.src:
            p.preview.src.removeEventListener("onLoadSource", p.preview)
        if p.preview.mcl_list:
            p.preview.mcl_list.onLoadInit = None
        p.preview.removeMovieClip()

def __tgList(rows):
    p = _global.__tgPanel
    if not p or not p.page:
        return
    if rows.context and rows.context != _global.__tgContext:
        return
    if rows.request_id and rows.request_id != _global.__tgCatalogueRequest:
        return
    _global.__tgReleaseRows(p)
    p.page.text = String(Number(rows.page) + 1) + " / " + String(Math.max(1, Math.ceil(Number(rows.total) / 10)))
    p.cards = p.createEmptyMovieClip("cards", p.getNextHighestDepth())
    width = (p.__listWidth - 10) / 2
    pitch = Math.min(57, (p.__h - 370) / 5)
    i = 0
    while i < len(rows.ids):
        if _global.__tgCategory != "mob" and _global.__tgCategory != "set":
            _global.__tgNames[rows.ids[i]] = rows.labels[i]
            _global.__tgSlots[rows.ids[i]] = rows.slots[i]
        x = p.__listX + (i % 2) * (width + 10)
        y = p.__listY + Math.floor(i / 2) * pitch
        b = _global.__tgPlate(p.cards, "row" + String(i), x, y, width, pitch - 5)
        b.__op = "pick"
        b.__value = rows.ids[i]
        b.__icon = rows.icons[i]
        b.__group = rows.groups[i]
        b.__groupSlots = rows.group_slots[i]
        b.__label = rows.labels[i]
        b.onRelease = _global.__tgClick
        b.onRollOver = _global.__tgHover
        b.onRollOut = _global.__tgUnhover
        b.hintTitle_str = rows.labels[i]
        _global.__tgText(b, "caption", rows.labels[i], 58, 4, width - 64, pitch - 12, False)
        if _global.__tgCategory == "mob":
            _global.__tgText(b, "badge", "[" + String(rows.levels[i]) + "]", 6, 9, 46, 24, False)
        else:
            icon = lol.display.DisplaySprite.create(b, "icon", b.getNextHighestDepth())
            icon._x = 5
            icon._y = 5
            icon.__tgMaxHeight = Math.min(38, Math.max(12, pitch - 15))
            icon._xscale = 40
            icon._yscale = 40
            icon.addEventListener("completed", icon, _global.__tgThumbReady)
            icon.display(String(rows.icons[i]) + "_icon", lol.services.SSEmulator.getIcon(rows.icons[i]))
        i = i + 1
    if rows.total == 0:
        _global.__tgText(p.cards, "empty", "По этим фильтрам ничего не найдено.", p.__listX, p.__listY + 35, p.__listWidth, 50, False)


def __tgFilterMenu(key):
    p = _global.__tgPanel
    if p.filtermenu:
        p.filtermenu.removeMovieClip()
        return
    if p.choices:
        p.choices.removeMovieClip()
    labels = ["Все", "A", "P", "G", "Контрабанда"]
    values = ["all", "A", "P", "G", "C"]
    if key == "category":
        labels = ["Готовые комплекты", "Оружие", "Части брони", "Подсумки", "Патроны", "Медицина"]
        values = ["set", "weapon", "armour", "pouch", "ammo", "medicine"]
    if key == "class":
        labels = ["Пистолеты", "Дробовики", "Автоматы", "Винтовки", "Пулемёты", "Пистолет-пулемёты", "Ближний бой", "Все типы"]
        values = [0, 1, 2, 3, 4, 5, 6, 0 - 1]
    if key == "upgrade":
        labels = ["Без чертежа", "С улучшением", "Все варианты"]
        values = ["base", "modified", "all"]
    if key == "level":
        labels = ["Все"]
        values = [0]
        i = 1
        maximum = 20
        if _global.__tgCategory == "mob":
            maximum = 20
        while i <= maximum:
            labels.push(String(i) + " уровень")
            values.push(i)
            i = i + 1
    box = p.createEmptyMovieClip("filtermenu", p.getNextHighestDepth())
    i = 0
    while i < len(values):
        col = Math.floor(i / 9)
        row = i % 9
        width = 200
        if key == "level":
            width = 100
        _global.__tgButton(box, "choice" + String(i), labels[i], p.__listX + col * 105, 133 + row * 26, width, "filter", {"key":key, "value":values[i]})
        i = i + 1

def __tgClick():
    p = _global.__tgPanel
    op = this.__op
    value = this.__value
    if op == "filtermenu":
        _global.__tgFilterMenu(value)
        return
    if op == "filter":
        _global.__tgFilterQuery = p.query.text
        if value.key == "category":
            _global.__tgCategory = value.value
            _global.__tgClass = 0 - 1
        if value.key == "class":
            _global.__tgCategory = "weapon"
            _global.__tgClass = value.value
        if value.key == "line":
            _global.__tgLine = value.value
        if value.key == "level":
            _global.__tgFilterLevel = value.value
        if value.key == "upgrade":
            _global.__tgUpgrade = value.value
        _global.__tgPage = 0
        _global.__tgBuild()
        return
    if op == "rulespreset":
        _global.__tgRuleDraftValues = value
        _global.__tgBuild()
        return
    if op == "ruletoggle":
        _global.__tgRuleDraft()
        values = _global.__tgRuleDraftValues.split(",")
        values[Number(value)] = String(1 - Number(values[Number(value)]))
        _global.__tgRuleDraftValues = values.join(",")
        _global.__tgBuild()
        return
    if op == "rulesapply":
        _global.__tgRuleDraft()
        m = _global.__tgSend("rules")
        m.addProp("values", "@" + _global.__tgRuleDraftValues + "@")
        _global.__tgRulesApplying = True
        _global.__tgTransmit(m)
        return
    if op == "localslot":
        _global.__tgDraft(_global.__tgTab)
        _global.__tgLocalSlot = 1 + (_global.__tgLocalSlot % 3)
        _global.__tgBuild()
        return
    if op == "spawns":
        if p.spawns:
            p.spawns.removeMovieClip()
            return
        box = p.createEmptyMovieClip("spawns", p.getNextHighestDepth())
        i = 0
        while i < len(_global.__tgSpawnLabels):
            _global.__tgButton(box, "point" + String(i), _global.__tgSpawnLabels[i], 28, 253 + i * 28, 350, "spawn", i)
            i = i + 1
        return
    if op == "spawn":
        m = _global.__tgSend("spawn")
        m.addProp("spawn_point", Number(value))
        _global.__tgTransmit(m)
        return
    if op == "locations":
        if p.locations:
            p.locations.removeMovieClip()
            return
        box = p.createEmptyMovieClip("locations", p.getNextHighestDepth())
        i = 0
        while i < len(_global.__tgLocations):
            _global.__tgButton(box, "map" + String(i), _global.__tgLocationLabels[i], 28, 135 + i * 28, 320, "location", _global.__tgLocations[i])
            i = i + 1
        return
    if op == "location":
        m = _global.__tgSend("location")
        m.addProp("location", value)
        _global.__tgTransmit(m)
        _global.__tgClose()
        return
    if op == "terminal":
        _global.__tgTransmit(_global.__tgSend("open"))
        return
    if op == "adjust":
        f = p[value.field]
        f.text = String(Math.max(value.low, Math.min(value.high, Number(f.text) + value.step)))
        return
    if op == "copy":
        _global.__tgDraft(_global.__tgTab)
        d = _global.__tgPlayer
        _global.__tgEnemy = {"skills":d.skills, "specs":d.specs, "gear":d.gear}
        _global.__tgStatus = "Пресет скопирован противнику. Откройте вкладку Боец и примените."
        p.status.text = _global.__tgStatus
        return
    if op == "mobgroup":
        _global.__tgMobGroup = value
        _global.__tgFilterLevel = 0
        _global.__tgPage = 0
        _global.__tgBuild()
        return
    if op == "recover":
        _global.__tgTransmit(_global.__tgSend("recover"))
        return
    if op == "return":
        _global.__tgTransmit(_global.__tgSend("return"))
        _global.__tgClose()
        return
    if op == "close":
        _global.__tgClose()
        return
    if op == "exit" or op == "abort":
        _global.__tgTransmit(_global.__tgSend(op))
        _global.__tgClose()
        return
    if op == "count":
        p.amount.text = String(Math.max(1, Math.min(5000, Number(p.amount.text) + Number(value))))
        return
    if op == "tab":
        _global.__tgDraft(_global.__tgTab)
        _global.__tgTab = value
        if value == "player" or value == "enemy":
            _global.__tgCategory = "skills"
        if value == "gear" or value == "enemygear":
            _global.__tgCategory = "set"
            _global.__tgClass = 0 - 1
        if value == "mob":
            _global.__tgCategory = "mob"
            _global.__tgMode = "mob"
        if value == "enemy" or value == "enemygear":
            _global.__tgMode = "fighter"
        _global.__tgPage = 0
        _global.__tgBuild()
        return
    if op == "setlevel":
        n = Math.max(1, Math.min(20, Number(p.presetLevel.text)))
        i = 0
        while i < 5:
            f = p["skill" + String(i)]
            if i < 2:
                f.text = String(n)
            else:
                f.text = String(Math.min(n, Number(f.text)))
            i = i + 1
        return
    if op == "save":
        _global.__tgDraft(_global.__tgTab)
        _global.__tgSafeSave()
        return
    if op == "load":
        _global.__tgSafeLoad()
        return
    if op == "category":
        _global.__tgDraft(_global.__tgTab)
        _global.__tgCategory = value
        if value == "skills":
            if _global.__tgTab == "enemygear":
                _global.__tgTab = "enemy"
            else:
                _global.__tgTab = "player"
        else:
            if _global.__tgTab == "enemy":
                _global.__tgTab = "enemygear"
            if _global.__tgTab == "player":
                _global.__tgTab = "gear"
        _global.__tgPage = 0
        _global.__tgBuild()
        return
    if op == "page" or op == "search":
        _global.__tgPage = Math.max(0, _global.__tgPage + Number(value))
        if op == "search":
            _global.__tgPage = 0
        _global.__tgRequestList()
        return
    if op == "stationary":
        _global.__tgDraft(_global.__tgTab)
        _global.__tgStationary = 1 - _global.__tgStationary
        _global.__tgBuild()
        return
    if op == "enemyhealing":
        _global.__tgDraft(_global.__tgTab)
        _global.__tgEnemyHealing = 1 - _global.__tgEnemyHealing
        _global.__tgBuild()
        return
    if op == "mode":
        if _global.__tgMode == "mob":
            _global.__tgMode = "fighter"
        else:
            _global.__tgMode = "mob"
        _global.__tgBuild()
        return
    draft = _global.__tgPlayer
    if _global.__tgTab == "enemy" or _global.__tgTab == "enemygear":
        draft = _global.__tgEnemy
    if op == "selectedscroll":
        p.selected.scroll = Math.max(1, Math.min(p.selected.maxscroll, p.selected.scroll + Number(value)))
        return
    if op == "removeLast":
        pairs = draft.gear.split(",")
        pairs.pop()
        draft.gear = pairs.join(",")
        p.selected.text = _global.__tgSelected(draft)
        return
    if op == "clear":
        draft.gear = ""
        p.selected.text = ""
        return
    if op == "pick":
        if this.__group and _global.__tgTab == "enemygear":
            _global.__tgApplying = "enemy"
            m = _global.__tgSend("fighterpreset")
            m.addProp("set", value)
            _global.__tgTransmit(m)
            return
        if p.choice:
            p.choice.text = this.__label
        if p.choices:
            p.choices._visible = False
        if _global.__tgTab == "mob":
            _global.__tgMob = value
            _global.__tgMobName = this.__label
            p.picked.text = "Моб: " + this.__label
            _global.__tgMode = "mob"
        else:
            n = Number(p.amount.text)
            if _global.__tgSlots[value]:
                n = 1
            if this.__group:
                members = this.__group.split(",")
                j = 0
                while j < len(members):
                    t = Number(members[j])
                    name = lol.utils.StringCollector.getInstance().getString(2000000 + t)
                    _global.__tgNames[t] = "Часть комплекта " + String(j + 1)
                    if name and name.string:
                        _global.__tgNames[t] = name.string + ""
                    setSlots = this.__groupSlots.split(",")
                    _global.__tgSlots[t] = Number(setSlots[j])
                    _global.__tgPut(draft, t, 1)
                    j = j + 1
            else:
                _global.__tgPut(draft, value, n)
            p.selected.text = _global.__tgSelected(draft)
        return
    if op == "apply":
        _global.__tgDraft(_global.__tgTab)
        who = "player"
        if _global.__tgTab == "enemy" or _global.__tgTab == "enemygear":
            who = "enemy"
        _global.__tgApplying = who
        m = _global.__tgSend("apply")
        m.addProp("who", "@" + who + "@")
        m.addProp("skills", "@" + draft.skills + "@")
        m.addProp("specs", "@" + draft.specs + "@")
        m.addProp("gear", "@" + draft.gear + "@")
        _global.__tgTransmit(m)
    if op == "start":
        _global.__tgDraft(_global.__tgTab)
        if _global.__tgRuleDraftValues != _global.__tgRuleValues:
            p.status.text = "Сначала примените правила во вкладке Правила."
            return
        if _global.__tgProfileKey(_global.__tgPlayer) != _global.__tgPlayerKey or (_global.__tgMode == "fighter" and _global.__tgProfileKey(_global.__tgEnemy) != _global.__tgEnemyKey):
            p.status.text = "Сначала примените изменённые пресеты персонажа и противника."
            return
        m = _global.__tgSend("start")
        m.addProp("mob", _global.__tgMob)
        m.addProp("mode", "@" + _global.__tgMode + "@")
        m.addProp("stationary", _global.__tgStationary)
        m.addProp("spawn_point", _global.__tgSpawnPoint)
        m.addProp("mob_health", _global.__tgMobHealth)
        m.addProp("mob_damage", _global.__tgMobDamage)
        m.addProp("enemy_healing", _global.__tgEnemyHealing)
        m.addProp("heal_below", _global.__tgHealBelow)
        m.addProp("heal_count", _global.__tgHealCount)
        _global.__tgTransmit(m)

def __tgSpawnState(panel):
    if not panel.spawn:
        return
    panel.spawn.caption.text = _global.__tgSpawnLabels[_global.__tgSpawnPoint] + " ▼"
    panel.distanceInfo.text = "Расстояние: около " + String(_global.__tgDistance) + " гексов"
    if panel.spawns:
        panel.spawns.removeMovieClip()

def __tgNotifyWrapper(cmd):
    if cmd.messID != "tg":
        this.__tgNotifyOrig(cmd)
        return
    v = cmd.params
    if v.op == "supply_list" or v.op == "supply_variants" or v.op == "supply_bag" or v.op == "supply_done":
        _global.__tgSupplyReceive(v)
        return
    if v.op == "types":
        _global.__tgEpoch = _global.__tgEpoch + 1
        i = 0
        while i < len(v.copies):
            _global.__tgCopies[v.copies[i]] = v.sources[i]
            icon = v.sources[i]
            if v.icons and v.icons[i]:
                icon = v.icons[i]
            _global.__tgIcons[v.copies[i]] = icon
            _global.__tgIcons[v.sources[i]] = icon
            _global.__tgLines[v.copies[i]] = v.lines[i]
            _global.__tgLabels[v.copies[i]] = v.labels[i]
            _global.__tgPrices[v.copies[i]] = {"cost":v.costs[i], "gold":v.gold_costs[i], "pack":v.price_packs[i]}
            i = i + 1
    if v.op == "combat_stats":
        _global.__tgCombatStats = v
    if v.op == "inventory":
        _global.__tgLive = {}
        i = 0
        while i < len(v.live_oids):
            _global.__tgLive[v.live_oids[i]] = True
            i = i + 1
        _global.__tgEquipmentKey = v.live_oids.join(",")
        _global.__tgPlayer.gear = v.gear
        _global.__tgPlayerKey = _global.__tgProfileKey({"skills":v.skills.join(","), "specs":v.specs.join(","), "gear":v.gear})
        _global.__tgOutfitRevision = v.outfit_rev
    if v.op == "state":
        _global.__tgArenaWidth = v.arena_width
        _global.__tgArenaHeight = v.arena_height
        _global.__tgParticipants = v.participants
        _global.__tgLocations = v.locations
        _global.__tgLocationLabels = v.location_labels
        _global.__tgLocation = v.location
        _global.__tgDistance = v.distance
        _global.__tgSpawnPoint = v.spawn_point
        _global.__tgSpawnLabels = v.spawn_labels
        _global.__tgStationary = v.stationary
        _global.__tgMobHealth = v.mob_health
        _global.__tgMobDamage = v.mob_damage
        _global.__tgEnemyHealing = v.enemy_healing
        _global.__tgHealBelow = v.heal_below
        _global.__tgHealCount = v.heal_count
        _global.__tgMob = v.selected_mob
        if not _global.__tgPanel:
            _global.__tgMode = v.selected_mode
        if _global.__tgFilterLevel == None:
            _global.__tgFilterLevel = v.level
        _global.__tgRules = v.rules
        _global.__tgArmour = v.armour
        _global.__tgRuleValues = v.rule_values
        if not _global.__tgRuleDraftValues or _global.__tgRulesApplying:
            _global.__tgRuleDraftValues = v.rule_values
        rulesApplied = _global.__tgRulesApplying
        _global.__tgRulesApplying = False
        _global.__tgVirtualUID = v.virtual_uid
        _global.__tgLive = {}
        i = 0
        while i < len(v.live_oids):
            _global.__tgLive[v.live_oids[i]] = True
            i = i + 1
        refresh = _global.__tgApplying == "player"
        if v.loaded:
            _global.__tgHUD(v.phase)
        _global.__tgToken = v.token
        _global.__tgActive = True
        _global.__tgStatus = "Уровень " + v.level + " · HP " + v.hp + " · Выносливость " + v.sp + " · ОД " + v.ap + " " + v.message
        player = {"skills":v.skills.join(","), "specs":v.specs.join(","), "gear":v.gear}
        enemy = {"skills":v.enemy_skills.join(","), "specs":v.enemy_specs.join(","), "gear":v.enemy_gear}
        _global.__tgPlayerKey = _global.__tgProfileKey(player)
        _global.__tgEnemyKey = _global.__tgProfileKey(enemy)
        if not _global.__tgPlayer or _global.__tgApplying == "player" or _global.__tgOutfitRevision != v.outfit_rev:
            _global.__tgPlayer = player
        _global.__tgOutfitRevision = v.outfit_rev
        if not _global.__tgEnemy or _global.__tgApplying == "enemy":
            _global.__tgEnemy = enemy
        _global.__tgApplying = ""
        _global.__tgOwner = v.owner
        _global.__tgSpecMax = v.spec_max
        i = 0
        while i < len(v.gear_ids):
            _global.__tgNames[v.gear_ids[i]] = v.gear_labels[i]
            _global.__tgSlots[v.gear_ids[i]] = v.gear_slots[i]
            i = i + 1
        i = 0
        while i < len(v.enemy_ids):
            _global.__tgNames[v.enemy_ids[i]] = v.enemy_labels[i]
            _global.__tgSlots[v.enemy_ids[i]] = v.enemy_slots[i]
            i = i + 1
        loc = lol.core.Master.getInstance().currentLocation
        if loc and v.loaded:
            if _global.__tgOriginalLoc and _global.__tgOriginalLoc != loc.locInfo:
                _global.__tgOriginalLoc.pvpEnabled = _global.__tgOriginalPvp
                _global.__tgOriginalLoc = None
            if not _global.__tgOriginalLoc:
                _global.__tgOriginalLoc = loc.locInfo
                _global.__tgOriginalPvp = loc.locInfo.pvpEnabled
            loc.locInfo.pvpEnabled = True
        if v.phase == "fight" or v.phase == "loading":
            _global.__tgClose()
        _global.__tgRefreshEquipment(v, refresh)
        if _global.__tgPanel:
            _global.__tgPanel.status.text = _global.__tgStatus
            _global.__tgSpawnState(_global.__tgPanel)
            if rulesApplied and _global.__tgTab == "rules":
                _global.__tgBuild()
            if _global.__tgPanel.selected:
                draft = _global.__tgPlayer
                if _global.__tgTab == "enemy" or _global.__tgTab == "enemygear":
                    draft = _global.__tgEnemy
                _global.__tgPanel.selected.text = _global.__tgSelected(draft)
    if v.op == "open":
        _global.__tgSupply = Boolean(v.supply)
        _global.__tgMob = v.mob
        _global.__tgContext = v.context
        _global.__tgPostTitle = v.title
        _global.__tgCategory = v.category
        _global.__tgClass = v.wclass
        _global.__tgFilterLevel = 0
        _global.__tgPage = 0
        _global.__tgFilterQuery = ""
        _global.__tgTab = "gear"
        if v.context == "computer":
            _global.__tgTab = "mob"
            _global.__tgMode = "mob"
        if v.context == "player":
            _global.__tgTab = "player"
        _global.__tgBuild()
    if v.op == "catalogue":
        _global.__tgList(v)
    if v.op == "error":
        _global.__tgSupplyPending = 0
        _global.__tgRulesApplying = False
        _global.__tgApplying = ""
        _global.__tgStatus = v.message
        if _global.__tgPanel:
            _global.__tgPanel.status.text = v.message
        else:
            alert = lol.core.SceneShifter.openNewAlert("topSimple")
            alert.label = v.message
    if v.op == "result":
        _global.__tgReport = v.message
    if v.op == "exit_pending":
        _global.__tgExitPending()
    if v.op == "exit":
        _global.__tgExitPending()
        inspector = lol.core.quests.QuestInspector.getInstance()
        inspector.clear()
        inspector.quester = None
        inspector.lockUpdate = False
        _global.__tgEpoch = _global.__tgEpoch + 1
        _global.__tgReturnEquipment = True
        _global.__tgEquipmentKey = None
        _global.__tgSnapshotPending = True
        _global.__tgLive = {}
        _global.__tgForgetItems()
        _global.__tgHUDClose()
        if _global.__tgOriginalLoc:
            _global.__tgOriginalLoc.pvpEnabled = _global.__tgOriginalPvp
            _global.__tgOriginalLoc = None
        _global.__tgActive = False
        _global.__tgSupply = False
        _global.__tgSupplyPending = 0
        _global.__tgPlayer = None
        _global.__tgEnemy = None
        _global.__tgClose()

def __tgExitPending():
    # Detach the native quest UI before its completion callback redraws it.
    inspector = lol.core.quests.QuestInspector.getInstance()
    panel = lol.core.SceneShifter._ref.UIPanels.quests.instance.content
    if panel:
        inspector.removeEventListener("update", panel, panel.takeAck)
    lol.core.SceneShifter.closeWindow("quests")
    lol.core.SceneShifter.closeWindow("questInfo")
    lol.core.SceneShifter.closeWindow("annotation", "all")
    clearInterval(inspector.updateTimerID)
    inspector.updateNPCList = []
    inspector.lockUpdate = True
    _global.__tgClose()

def __tgRefreshEquipment(v, force):
    if not v.loaded:
        return
    key = v.live_oids.join(",")
    if force or _global.__tgEquipmentKey != key:
        _global.__tgEquipmentKey = key
        gamer = lol.core.Master.getInstance().gamer
        gamer.equipment.__tgReplaceNextBag = True
        gamer.equipment.getStuff(11, 0)
        gamer.apManager.setAP(v.regen, v.ap)

def __tgParse(doc):
    info = this.__tgParseOrig(doc)
    if _global.__tgActive:
        info.zones = []
        info.pvpEnabled = True
        info.width = _global.__tgArenaWidth
        info.height = _global.__tgArenaHeight
        info.sprites = []
        info.bgDecorations = []
        info.obstacles = []
        info.libraryID = "Desert"
        info.back = {"id":"bg_desert1.jpg", "resType":"lib"}
    return info

def __tgEnterWrapper(obj):
    this.__tgEnterOrig(obj)
    if _global.__tgActive or _global.__tgReturnEquipment:
        _global.__rfRepairKeys()
    if _global.__tgReturnEquipment:
        _global.__tgReturnEquipment = False
        this.gamer.equipment.__tgReplaceNextBag = True
        this.gamer.equipment.getStuff(11, 0)

def __tgMoveWrapper(cell, spliceNum):
    if not _global.__tgPanel:
        return this.__tgMoveOrig(cell, spliceNum)


def __tgTradeBuy(item, count):
    if not _global.__tgActive or not _global.__tgIsCopy(item):
        return this.__tgTradeBuyOrig(item, count)
    if item.rootID == lol.core.objects.Item.FIRE_ARM or item.rootID == lol.core.objects.Item.COLD_ARM or item.rootID == lol.core.objects.Item.WEAR:
        _global.__tgBuyFree(this, item, 1)
        return
    if item.rootID != lol.core.objects.Item.AMMO and count == None:
        this.__tgPurchaseItem = item
        box = lol.core.SceneShifter.openNewWindow("exchange").content
        this.__tgPurchaseBox = box
        box.label = "Сколько получить?"
        box.maxValue = 50
        box.cost_num = 0
        box.cost_mod = 1
        box.__tgFreeQuantity = True
        box.addEventListener("exchange", this, _global.__tgTradeQuantity)
        box.addEventListener("close", this, _global.__tgTradeCancel)
        return
    _global.__tgBuyFree(this, item, count)

def __tgBuyFree(trade, item, count):
    count = Math.max(1, Number(count))
    msg = new(lol.server.mess.CSM_SSUpdate, 1, new(lol.data.BigUINT, new(lol.data.BigUINTCluster, item.tradeID.toString(16))), count)
    if trade.XMC.Send(msg):
        lol.server.XMLCCallStack.addCall("cmdAck", trade, trade.transferAck)
    else:
        trade.applyTransfer(False)

def __tgQuantityCreate(item, title, mode, showGold, sell):
    box = this.__tgQuantityCreateOrig(item, title, mode, showGold, sell)
    if _global.__tgActive and _global.__tgIsCopy(item):
        box.__tgFreeQuantity = True
        box.__tgQuantityOwner = this
    return box

def __tgQuantityCancel(event):
    if not _global.__tgActive or not event.target.__tgFreeQuantity:
        return this.__tgQuantityCancelOrig(event)
    if event.target.__tgQuantityOwner != this:
        return
    event.target.__tgQuantityOwner = None
    event.target.removeEventListener("exchange", this, this.exchangeAck)
    event.target.removeEventListener("close", this, this.exchangeCancel)
    lol.core.SceneShifter.closeWindow("exchange")
    if this.currDDOperation:
        this.currDDOperation.failedOperation()
    this.currDDOperation = None
    this.separateItem = None
    this.dropEnabled = True

def __tgQuantityApply():
    if not _global.__tgActive or not this.__tgFreeQuantity:
        return this.__tgQuantityApplyOrig()
    count = Number(this.rightNum)
    if count > 0 and count <= this.maxValue:
        this.dispatchEvent({"type":"exchange", "left":Number(this.leftNum), "right":count})
    else:
        this.cancel()

def __tgTradeQuantity(event):
    if not this.__tgPurchaseBox or event.target != this.__tgPurchaseBox:
        return
    event.target.removeEventListener("exchange", this, _global.__tgTradeQuantity)
    event.target.removeEventListener("close", this, _global.__tgTradeCancel)
    item = this.__tgPurchaseItem
    this.__tgPurchaseItem = None
    this.__tgPurchaseBox = None
    lol.core.SceneShifter.closeWindow("exchange")
    if not item:
        return
    if item and _global.__tgActive:
        _global.__tgBuyFree(this, item, event.right)
    else:
        this.applyTransfer(False)

def __tgTradeCancel(event):
    if not this.__tgPurchaseBox or event.target != this.__tgPurchaseBox:
        return
    event.target.removeEventListener("exchange", this, _global.__tgTradeQuantity)
    event.target.removeEventListener("close", this, _global.__tgTradeCancel)
    item = this.__tgPurchaseItem
    this.__tgPurchaseItem = None
    this.__tgPurchaseBox = None
    lol.core.SceneShifter.closeWindow("exchange")
    if item:
        this.__tgCancelledFree = True
        this.applyTransfer(False)
        this.__tgCancelledFree = False

def __tgTradeError():
    if this.trade.__tgCancelledFree:
        operation = this.ddOperation_arr.shift()
        if operation:
            operation.failedOperation()
        return
    this.__tgTradeErrorOrig()

def __tgTradeKill():
    box = this.__tgPurchaseBox
    if box:
        box.removeEventListener("exchange", this, _global.__tgTradeQuantity)
        box.removeEventListener("close", this, _global.__tgTradeCancel)
        lol.core.SceneShifter.closeWindow("exchange")
    this.__tgPurchaseItem = None
    this.__tgPurchaseBox = None
    this.__tgTradeKillOrig()

def __tgCheckSell(item):
    if _global.__tgActive and _global.__tgIsCopy(item):
        return None
    return this.__tgCheckSellOrig(item)

def __tgReferencePrice(item):
    price = _global.__tgPrices[item.typeID]
    value = 0
    gold = False
    if price:
        pack = 1
        if price.pack and price.pack > 0:
            pack = Number(price.pack)
        value = Math.floor(Number(price.cost) * 1000 / pack + 1 / 2) / 1000
        if price.gold > 0:
            value = Math.floor(Number(price.gold) / pack + 1 / 2) / 100
            gold = True
    return {"value":value, "gold":gold}

def __tgShowCost(item, align):
    this.__tgShowCostOrig(item, align)
    if _global.__tgActive and _global.__tgCopies[item.typeID]:
        price = _global.__tgReferencePrice(item)
        value = price.value
        if this.showHeapCount and item.getProp("size"):
            value = value * Number(item.getProp("size"))
        this.mainCost = 0
        this.costType = "Афро · справочно"
        prefix = "a"
        frame = 1
        if price.gold:
            this.costType = "Золото · справочно"
            prefix = "g"
            frame = 2
        this.price_mc.gotoAndStop(frame)
        label = String(value)
        if not this.attachIconEnabled:
            label = prefix + label
        this.price_mc.fontContainer.showValue(label)

def __tgAnnotationPrice(rows):
    if not _global.__tgActive or not _global.__tgCopies[this.item.typeID]:
        return this.__tgAnnotationPriceOrig(rows)
    price = _global.__tgReferencePrice(this.item)
    unit = " Афро"
    if price.gold:
        unit = " G"
    if price.value > 0:
        rows.push(["Базовая цена за 1 шт.: ", String(price.value) + unit])
    else:
        rows.push(["Базовая цена: ", "не задана"])
    rows.push(["Использование: ", "только на полигоне"])

def __tgBack(root):
    line = _global.__tgLines[this.item.typeID]
    if not _global.__tgActive or not line:
        return this.__tgBackOrig(root)
    link = "fireArmBG"
    if root == lol.core.objects.Item.HEAL_ITEM:
        link = "medikKitBG"
    if root == lol.core.objects.Item.AMMO:
        link = "ammoBG"
    if root == lol.core.objects.Item.QUEST:
        link = "questBG"
    if root == lol.core.objects.Item.WEAR or root == "small":
        link = "wearBG"
    if line == "G":
        link = link + "_gold"
    if line == "P":
        link = link + "_premium"
    this.bg_mc.attachMovie(link, "bg", 0)
    if this.groupItem:
        second = this.bg_mc.attachMovie(link, "group2", 0 - 5)
        third = this.bg_mc.attachMovie(link, "group3", 0 - 10)
        second._x = 5
        second._y = 5
        third._x = 10
        third._y = 10

def __tgArmorCard():
    this.__tgArmorCardOrig()
    if _global.__tgActive and _global.__tgCombatStats:
        this.ArmorClassValue.value.text = String(_global.__tgCombatStats.armour)

def __tgCritCard():
    this.__tgCritCardOrig()
    if _global.__tgActive and _global.__tgCombatStats:
        this.crit_txt.text = String(_global.__tgCombatStats.critical) + " %"
        this.critDodge_txt.text = String(_global.__tgCombatStats.anticritical) + " %"

def __tgDodgeCard():
    this.__tgDodgeCardOrig()
    if _global.__tgActive and _global.__tgCombatStats:
        this.meleeEvade_value.value.text = String(_global.__tgCombatStats.dodge) + " %"

def __tgInfoButton():
    line = _global.__tgLines[this.item.typeID]
    if not _global.__tgActive or not line:
        return this.__tgInfoButtonOrig()
    link = "info_btn"
    if this.__itemInfoBase == "list_info_btn" or this.btnLinkID == "list_info_btn" or this.btnLinkID == "list_info_btn_gold" or this.btnLinkID == "list_info_btn_premium":
        link = "list_info_btn"
    if line == "G":
        link = link + "_gold"
    if line == "P":
        link = link + "_premium"
    if this.info_btn:
        this.info_btn.removeMovieClip()
    this.info_btn = this.attachMovie(link, "info_btn", this.getNextHighestDepth())
    this.info_btn._x = this.bg_mc._width
    this.info_btn.onRollOver = mx.utils.Delegate.create(this, this.rollOverBtn)
    this.info_btn.onRollOut = mx.utils.Delegate.create(this, this.rollOutBtn)
    this.info_btn.onRelease = mx.utils.Delegate.create(this, this.onPressBtn)
    this.info_btn.onReleaseOutside = mx.utils.Delegate.create(this, this.rollOutBtn)
    this.toggled_frame = this.toggled

def __tgIsCopy(item):
    if not item:
        return False
    if not item.id:
        return False
    return Boolean(_global.__tgCopies[item.typeID])

def __tgItemName(item):
    if _global.__tgIsCopy(item):
        proto = lol.core.objects.ItemFactory.getProtoItem(item.typeID)
        if proto.name:
            parts = proto.name.split("$")
            label = _global.__tgLabels[item.typeID]
            if not label:
                label = parts[0]
            i = 1
            while i < len(parts):
                label = label + "$" + parts[i]
                i = i + 1
            item._name = label

def __tgTradeParams():
    _global.__tgItemName(this.item)
    this.__tgTradeParamsOrig()

def __tgItemWrapper(param):
    _global.__tgItemName(this)
    this.__tgItemOrig(param)

def __tgCreate(oid, notRequestDI, target):
    result = this.__tgCreateOrig(oid, notRequestDI, target)
    _global.__tgItemName(result)
    if _global.__tgIsCopy(result):
        if not result.__tgTracked:
            result.__tgTracked = True
            _global.__tgObjects.push(result)
    return result

def __tgForgetItems(force):
    factory = lol.core.objects.ItemFactory
    if _global.__tgForgetting or len(_global.__tgObjects) == 0 or (not force and (factory.callCount > 0 or len(factory.callStack) > 0)):
        return
    _global.__tgForgetting = True
    batch = _global.__tgObjects
    _global.__tgObjects = []
    keep = []
    i = 0
    while i < len(batch):
        item = batch[i]
        if _global.__tgLive[item.id]:
            keep.push(item)
        else:
            item.removeEventListener("itemUpdate", lol.core.Master.getInstance().gamer.equipment)
            proto = factory.getProtoItem(item.typeID)
            proto.removeEventListener("itemUpdate", item)
            lol.utils.StringCollector.getInstance().removeEventListener("update", item, item.stringUpdate)
            _global.__tgDeleteItem(item.id)
        i = i + 1
    i = 0
    while i < len(_global.__tgObjects):
        keep.push(_global.__tgObjects[i])
        i = i + 1
    _global.__tgObjects = keep
    _global.__tgForgetting = False

def __tgUpdateCall():
    this.__tgUpdateOrig()
    _global.__tgForgetItems()

def __tgGetStuff(n, id):
    if not this.isGamer or (id and id != this.id) or (not this.__tgManaged and not _global.__tgActive):
        this.__tgGetStuffOrig(n, id)
        return
    this.__tgManaged = True
    m = new(lol.server.mess.CSM_SSGet, n, id)
    if this.XMC.Send(m):
        replace = Boolean(this.__tgReplaceNextBag)
        this.__tgReplaceNextBag = False
        lol.server.XMLCCallStack.addCall("ss_ack", this, _global.__tgSnapshotAck, {"mask":n, "epoch":_global.__tgEpoch, "replace":replace})

def __tgSnapshotAck(obj):
    if obj.data.epoch != _global.__tgEpoch:
        return
    this.__tgReplaceBag = Boolean(obj.data.replace)
    obj.data = obj.data.mask
    this.ss_ack(obj)
    this.__tgReplaceBag = False

def __tgClearBag(equipment):
    bag = equipment.bag
    if not bag:
        return
    old = bag.itemList
    bag.itemList = []
    i = 0
    while i < len(old):
        old[i].removeEventListener("itemUpdate", equipment)
        equipment.removeItem(bag, old[i])
        i = i + 1

def __tgBagItemUpdate(obj):
    item = obj.target
    if this.isGamer and this.__tgManaged:
        copy = _global.__tgIsCopy(item)
        if copy != Boolean(_global.__tgActive) or (copy and not _global.__tgLive[item.id]):
            item.removeEventListener("itemUpdate", this)
            return
    this.__tgBagUpdateOrig(obj)

def __tgClearSlots(equipment, slots):
    i = 0
    while i < len(slots):
        slot = slots[i]
        if slot.item:
            equipment.removeItem(slot, slot.item)
        i = i + 1

def __tgEquipWrapper(obj):
    if this.isGamer and this.__tgReplaceBag:
        mask = Number(obj.data)
        if Math.floor(mask) % 2 == 1:
            _global.__tgClearSlots(this, this.slots_arr)
        if Math.floor(mask / 2) % 2 == 1:
            _global.__tgClearSlots(this, this.action_arr)
        if Math.floor(mask / 8) % 2 == 1:
            _global.__tgClearBag(this)
    this.__tgEquipOrig(obj)
    if _global.__tgActive:
        _global.__tgForgetItems()


def __tgCleanup():
    _global.__tgEpoch = _global.__tgEpoch + 1
    _global.__tgEquipmentKey = None
    _global.__tgReturnEquipment = False
    _global.__tgLive = {}
    _global.__tgForgetItems(True)
    _global.__tgHUDClose()
    _global.__tgClose()
    if _global.__tgOriginalLoc:
        _global.__tgOriginalLoc.pvpEnabled = _global.__tgOriginalPvp
        _global.__tgOriginalLoc = None
    _global.__tgRuleDraftValues = None
    _global.__tgRuleValues = None
    _global.__tgRulesApplying = False
    _global.__tgPlayer = None
    _global.__tgEnemy = None
    _global.__tgActive = False
    _global.__tgSupply = False
    _global.__tgSupplyPending = 0

def __tgSocketWrapper():
    _global.__tgCleanup()
    this.__tgSocketOrig()

def __tgConnectionCloseWrapper():
    _global.__tgCleanup()
    this.__tgConnectionCloseOrig()

def __tgRuleDraft():
    p = _global.__tgPanel
    if not p or not p.rule0:
        return
    values = _global.__tgRuleDraftValues.split(",")
    i = 0
    while i < 10:
        values[i] = p["rule" + String(i)].text.split(",").join(".")
        i = i + 1
    _global.__tgRuleDraftValues = values.join(",")

def __tgPresetStore():
    suffix = ""
    if _global.__tgLocalSlot > 1:
        suffix = "_" + String(_global.__tgLocalSlot)
    return SharedObject.getLocal("lavaTrainingPresets_v1_" + _global.__hcEncode(_global.__hcEndpoint + "|" + _global.__tgOwner) + suffix)

def __tgSave():
    store = _global.__tgPresetStore()
    p = _global.__tgPlayer
    e = _global.__tgEnemy
    store.data.player = {"skills":p.skills, "specs":p.specs, "gear":p.gear}
    store.data.enemy = {"skills":e.skills, "specs":e.specs, "gear":e.gear}
    store.data.rules = _global.__tgRuleDraftValues
    result = store.flush()
    _global.__tgPanel.status.text = "Пресеты сохранены локально."
    if result == False:
        _global.__tgPanel.status.text = "Не удалось сохранить пресет в локальном хранилище."
    if result == "pending":
        _global.__tgPanel.status.text = "Для сохранения требуется разрешение локального хранилища Flash."

def __tgLoad():
    store = _global.__tgPresetStore()
    if not store.data.player or not store.data.enemy:
        _global.__tgPanel.status.text = "Сохранённого пресета нет."
        return
    p = store.data.player
    e = store.data.enemy
    if kind(p.skills) != "string" or kind(p.specs) != "string" or kind(p.gear) != "string" or kind(e.skills) != "string" or kind(e.specs) != "string" or kind(e.gear) != "string":
        _global.__tgPanel.status.text = "Сохранённый пресет повреждён."
        return
    if len(p.skills) > 128 or len(p.specs) > 128 or len(p.gear) > 4096 or len(e.skills) > 128 or len(e.specs) > 128 or len(e.gear) > 4096:
        _global.__tgPanel.status.text = "Сохранённый пресет слишком большой."
        return
    if store.data.rules != None:
        if kind(store.data.rules) != "string" or len(store.data.rules) > 256 or len(store.data.rules.split(",")) != 12:
            _global.__tgPanel.status.text = "Сохранённые правила повреждены."
            return
    if store.data.rules != None:
        _global.__tgRuleDraftValues = store.data.rules
    _global.__tgPlayer = {"skills":p.skills, "specs":p.specs, "gear":p.gear}
    _global.__tgEnemy = {"skills":e.skills, "specs":e.specs, "gear":e.gear}
    _global.__tgStatus = "Пресеты загружены. Примените их перед боем."
    _global.__tgBuild()

def __tgIcon(typeID):
    source = _global.__tgCopies[typeID]
    if _global.__tgActive or source:
        icon = _global.__tgIcons[typeID]
        if icon:
            typeID = icon
        elif source:
            typeID = source
    return this.__tgIconOrig(typeID)

def __tgInstall():
    _global.__tgEpoch = 0
    _global.__tgSupply = False
    _global.__tgSupplySequence = 0
    _global.__tgSupplyPending = 0
    _global.__tgCombatStats = None
    parser = lol.core.location.LDParser
    if not parser.__tgParseOrig:
        parser.__tgParseOrig = parser.parseLD
        parser.parseLD = _global.__tgParse
    f = lol.core.objects.ItemFactory
    if not f.__tgCreateOrig:
        f.__tgCreateOrig = f.create
        f.create = _global.__tgCreate
        f.__tgUpdateOrig = f.updateCall
        f.updateCall = _global.__tgUpdateCall
    art = lol.services.SSEmulator
    if not art.__tgIconOrig:
        art.__tgIconOrig = art.getIcon
        art.getIcon = _global.__tgIcon
    _global.__tgOutfitRevision = 0 - 1
    _global.__tgCopies = {}
    _global.__tgIcons = {}
    _global.__tgForgetting = False
    _global.__tgLines = {}
    _global.__tgLabels = {}
    _global.__tgPrices = {}
    _global.__tgObjects = []
    _global.__tgLive = {}
    _global.__tgNames = {}
    _global.__tgSlots = {}
    _global.__tgTab = "player"
    _global.__tgClass = 0
    _global.__tgFilterLevel = None
    _global.__tgFilterQuery = ""
    _global.__tgUpgrade = "base"
    _global.__tgLine = "all"
    _global.__tgCategory = "skills"
    _global.__tgPage = 0
    _global.__tgArenaWidth = 72
    _global.__tgArenaHeight = 144
    _global.__tgParticipants = 1
    _global.__tgDistance = 0
    _global.__tgSpawnPoint = 2
    _global.__tgSpawnLabels = ["Ближняя", "Средняя", "Дальняя — справа сверху"]
    _global.__tgContext = "computer"
    _global.__tgPostTitle = "Компьютер полигона"
    _global.__tgMobGroup = "all"
    _global.__tgCatalogueRequest = 0
    _global.__tgMobHealth = 100
    _global.__tgMobDamage = 100
    _global.__tgEnemyHealing = 0
    _global.__tgHealBelow = 50
    _global.__tgHealCount = 5
    _global.__tgStationary = 0
    _global.__tgMode = "mob"
    _global.__tgMob = 0
    _global.__tgMobName = "не выбран"
    _global.__tgReport = "Результаты появятся после боя."
    _global.__tgStatus = ""
    _global.__tgLocalSlot = 1
    _global.__tgRuleDraftValues = None
    _global.__tgRuleValues = None
    _global.__tgRulesApplying = False
'''


from training_supply_client import SOURCE as SUPPLY_SOURCE
SOURCE += SUPPLY_SOURCE

def patches(Asm, undef):
    compiler = Compiler(Asm, undef)
    functions = compiler.functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('gpui', 'Annotation'), 'addCost', '__tgAnnotationPriceOrig', '__tgAnnotationPrice'),
        (('gpui', 'ExchangePan'), 'sendObj', '__tgQuantityApplyOrig', '__tgQuantityApply'),
        (('gpui', 'TradeInterface'), 'createExchangePan', '__tgQuantityCreateOrig', '__tgQuantityCreate'),
        (('gpui', 'TradeInterface'), 'exchangeCancel', '__tgQuantityCancelOrig', '__tgQuantityCancel'),
        (('gpui', 'CharInterface'), 'showArmorLevel', '__tgArmorCardOrig', '__tgArmorCard'),
        (('gpui', 'CharInterface'), 'showKrit', '__tgCritCardOrig', '__tgCritCard'),
        (('gpui', 'CharInterface'), 'showMeleeEvade', '__tgDodgeCardOrig', '__tgDodgeCard'),
        (('gpui', 'ItemContainer'), 'attachBack', '__tgBackOrig', '__tgBack'),
        (('gpui', 'ExtItemContainer'), 'attachBtn', '__tgInfoButtonOrig', '__tgInfoButton'),
        (('core', 'player', 'Trade'), 'buy', '__tgTradeBuyOrig', '__tgTradeBuy'),
        (('core', 'player', 'Trade'), 'kill', '__tgTradeKillOrig', '__tgTradeKill'),
        (('gpui', 'TradeInterface'), 'checkSellItem', '__tgCheckSellOrig', '__tgCheckSell'),
        (('gpui', 'TradeInterface'), 'moveItemError', '__tgTradeErrorOrig', '__tgTradeError'),
        (('gpui', 'ItemContainer'), 'showCost', '__tgShowCostOrig', '__tgShowCost'),
        (('core', 'player', 'PersEquip'), 'itemUpdate', '__tgBagUpdateOrig', '__tgBagItemUpdate'),
        (('core', 'player', 'StuffManager'), 'getStuff', '__tgGetStuffOrig', '__tgGetStuff'),
        (('core', 'Master'), 'lenter', '__tgEnterOrig', '__tgEnterWrapper'),
        (('core', 'player', 'PersAttributes'), 'rp_info', '__tgStatsOrig', '__tgStatsWrapper'),
        (('core', 'player', 'NPC'), 'userInfo', '__tgNPCOrig', '__tgNPCWrapper'),
        (('server', 'XMLConnection'), 'sendNotification', '__tgNotifyOrig', '__tgNotifyWrapper'),
        (('core', 'location', 'Location'), 'movePlayer', '__tgMoveOrig', '__tgMoveWrapper'),
        (('server', 'XMLConnection'), 'close', '__tgConnectionCloseOrig', '__tgConnectionCloseWrapper'),
        (('server', 'XMLConnection'), 'onClose', '__tgSocketOrig', '__tgSocketWrapper'),
        (('core', 'player', 'PersEquip'), 'ss_ack', '__tgEquipOrig', '__tgEquipWrapper'),
        (('core', 'objects', 'Item'), 'itemUpdate', '__tgItemOrig', '__tgItemWrapper'),
        (('core', 'objects', 'TradeItem'), 'initParams', '__tgTradeParamsOrig', '__tgTradeParams'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    from avm_codegen import protected_call
    functions += [('__tgSafeSave', (), protected_call(Asm, '__tgSave', (), undef)),
                  ('__tgSafeLoad', (), protected_call(Asm, '__tgLoad', (), undef))]
    delete = Asm()
    delete.var('lol').member('core', 'objects', 'ItemFactory', 'itemStore').var('oid')
    delete.op('delete')  # Remove only a tracked instance from ItemFactory.itemStore.
    delete.op('pop')
    functions.append(('__tgDeleteItem', ('oid',), delete))
    return dict(globals=functions, wraps=tuple(wraps))
