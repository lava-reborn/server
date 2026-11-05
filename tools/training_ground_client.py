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
    panel = lol.core.SceneShifter._ref.UIPanels.default
    if panel and panel.instance:
        lol.core.SceneShifter.closeWindow()

def __tgNPCWrapper(obj):
    this.__tgNPCOrig(obj)
    if obj.param.tg_terminal:
        label = "Настроить тренировку"
        desc = "Персонаж, противник и условия боя."
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

def __tgButton(p, name, label, x, y, w, op, value):
    art = _global.__onlineArt(p)
    b = _global.__tgTile(p, name, art.b, x, y, w, 25)
    _global.__tgText(b, "caption", label, 5, 3, w - 10, 20, False)
    b.__op = op
    b.__value = value
    b.onRelease = _global.__tgClick
    b.onRollOver = _global.__tgHover
    b.onRollOut = _global.__tgUnhover
    b.hintTitle_str = label
    return b

def __tgHUDResize():
    this._x = Math.max(8, Stage.width - 350)
    this._y = 8

def __tgHUD(phase):
    old = _global.__tgHUDPanel
    if old:
        Stage.removeListener(old)
        old.removeMovieClip()
    hud = _root.createEmptyMovieClip("__tgHUDPanel", _root.getNextHighestDepth())
    _global.__tgHUDPanel = hud
    op = "terminal"
    label = "Компьютер"
    if phase == "fight" or phase == "loading":
        op = "abort"
        label = "Прервать бой"
    _global.__tgButton(hud, "main", label, 0, 0, 155, op, "")
    _global.__tgButton(hud, "exit", "Выйти из центра", 165, 0, 176, "exit", "")
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
                if _global.__tgSlots[id] == 512 or _global.__tgSlots[id] == 513 or not _global.__tgSlots[id] or _global.__tgSlots[id] != _global.__tgSlots[fields[0]]:
                    result.push(pairs[i])
        i = i + 1
    if not found:
        result.push(String(id) + ":" + String(n))
    draft.gear = result.join(",")


def __tgDraft(who):
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
            values.push(Number(p["spec" + String(i)].text))
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
    left = Math.round((frame.minW - Stage.width) / 2) + 8
    top = Math.round((frame.minH - Stage.height) / 2) + 8
    right = left + Math.max(0, Stage.width - p.__w - 16)
    bottom = top + Math.max(0, Stage.height - p.__h - 16)
    if center:
        p._x = Math.round((frame.minW - p.__w) / 2)
        p._y = Math.round((frame.minH - p.__h) / 2)
    p._x = Math.max(left, Math.min(right, p._x))
    p._y = Math.max(top, Math.min(bottom, p._y))

def __tgDragStart():
    p = this._parent
    frame = lol.core.SceneShifter._ref
    left = Math.round((frame.minW - Stage.width) / 2) + 8
    top = Math.round((frame.minH - Stage.height) / 2) + 8
    p.startDrag(False, left, top, left + Math.max(0, Stage.width - p.__w - 16), top + Math.max(0, Stage.height - p.__h - 16))

def __tgDragStop():
    this._parent.stopDrag()
    _global.__tgLayout(this._parent, False)

def __tgResize():
    this.stopDrag()
    if this.__w != Math.min(Stage.width - 24, 1040) or this.__h != Math.min(Stage.height - 70, 640):
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
        old.removeMovieClip()
    else:
        lol.core.SceneShifter.hotKeyManager.addFilter("tg")
    p = _root.createEmptyMovieClip("__tgPanel", _root.getNextHighestDepth())
    _global.__tgPanel = p
    W = Math.min(Stage.width - 24, 1040)
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
    _global.__tgText(drag, "title", "Учебный центр · испытательный полигон", 2, 2, W - 90, 24, False)
    drag.onPress = _global.__tgDragStart
    drag.onRelease = _global.__tgDragStop
    drag.onReleaseOutside = _global.__tgDragStop
    _global.__tgButton(p, "cross", "×", W - 51, 15, 27, "close", "")
    tabs = ["player", "gear", "mob", "enemy", "enemygear", "result", "rules"]
    labels = ["Персонаж", "Предметы", "Противник", "Боец", "Вещи бойца", "Условия / итог", "Правила"]
    i = 0
    tabw = (W - 48) / 7
    while i < 7:
        button = _global.__tgButton(p, "tab" + String(i), labels[i], 24 + i * tabw, 50, tabw - 5, "tab", tabs[i])
        if _global.__tgTab == tabs[i]:
            button.caption.textColor = 16777215
            _global.__tgTile(p, "activeTab", art.t, 24 + i * tabw, 75, tabw - 5, 3)
        i = i + 1
    _global.__tgTile(p, "sectionHead", art.b, 24, 80, W - 48, 3)
    _global.__tgTile(p, "sectionFoot", art.t, 24, H - 115, W - 48, 3)
    _global.__tgText(p, "status", _global.__tgStatus, 24, H - 100, W - 48, 36, False)
    _global.__tgButton(p, "apply", "Применить пресет", 24, H - 57, 170, "apply", "")
    _global.__tgButton(p, "start", "Начать бой", 203, H - 57, 130, "start", "")
    _global.__tgButton(p, "abort", "Прервать бой", 342, H - 57, 140, "abort", "")
    _global.__tgText(p, "returnHint", "Выход — задание у компьютера", W - 300, H - 55, 276, 28, False)
    p.apply._visible = _global.__tgTab != "mob" and _global.__tgTab != "result" and _global.__tgTab != "rules"
    if _global.__tgTab == "result":
        _global.__tgButton(p, "location", "Локация: выбрать ▼", 28, 100, 320, "locations", "")
        _global.__tgText(p, "info", "Бой проходит без потерь и наград. Обычные вещи и навыки не меняются.\\nНастройте персонажа, затем выберите моба или бойца.\\nДистанция в гексах (1–30):", 28, 135, W - 56, 100, False)
        _global.__tgText(p, "distance", String(_global.__tgDistance), 28, 205, 80, 24, True)
        behaviour = "Активный противник"
        if _global.__tgStationary:
            behaviour = "Неподвижная мишень"
        _global.__tgButton(p, "stationary", behaviour, 125, 205, 200, "stationary", "")
        _global.__tgText(p, "report", _global.__tgReport, 28, 250, W - 56, H - 370, False)
        return
    if _global.__tgTab == "rules":
        _global.__tgText(p, "rules", _global.__tgRules, 28, 100, W - 56, H - 230, False)
        return
    if _global.__tgTab != "mob" and _global.__tgCategory == "skills":
        _global.__tgButton(p, "gearcat", "Выбрать снаряжение", 24, 95, 160, "category", "weapon")
        draft = _global.__tgPlayer
        if _global.__tgTab == "enemy" or _global.__tgTab == "enemygear":
            draft = _global.__tgEnemy
        values = draft.skills.split(",").concat(draft.specs.split(","))
        titles = ["Ближний бой", "Стрельба", "Медицина", "Промышленность", "Производство", "Рукопашный бой", "Режущее оружие", "Пистолеты", "Дробовики", "Автоматы", "Винтовки", "Ручные пулемёты", "Пистолет-пулемёты", "Хирургия", "Первая помощь", "Добыча", "Переработка", "Мастер свинца", "Мастер селитры", "Мастер меди"]
        i = 0
        cw = (W - 65) / 2
        pitch = Math.min(29, (H - 290) / 10)
        while i < 20:
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
                high = 17
            _global.__tgText(p, key + "label", titles[i], x, y, cw - 125, 23, False)
            _global.__tgText(p, key, values[i], x + cw - 120, y, 40, 23, True)
            _global.__tgButton(p, key + "minus", "−", x + cw - 75, y, 28, "adjust", {"field":key, "step":0 - 1, "low":low, "high":high})
            _global.__tgButton(p, key + "plus", "+", x + cw - 42, y, 28, "adjust", {"field":key, "step":1, "low":low, "high":high})
            i = i + 1
        _global.__tgButton(p, "copy", "Персонаж → противник", 200, 95, 260, "copy", "")
        _global.__tgButton(p, "save", "Сохранить", W - 300, 95, 138, "save", "")
        _global.__tgButton(p, "load", "Загрузить", W - 150, 95, 126, "load", "")
        _global.__tgText(p, "levelHint", "Базовый уровень:", 24, H - 141, 125, 23, False)
        levels = draft.skills.split(",")
        currentLevel = Math.max(Number(levels[0]), Number(levels[1]), Number(levels[2]), Number(levels[3]), Number(levels[4]))
        _global.__tgText(p, "presetLevel", String(currentLevel), 155, H - 141, 42, 23, True)
        _global.__tgButton(p, "setlevel", "Задать", 203, H - 141, 78, "setlevel", "")
        _global.__tgText(p, "levelExplanation", "Уровень персонажа определяется старшим навыком.", 292, H - 141, W - 320, 28, False)
        return
    _global.__tgText(p, "catalogueTitle", "КАТАЛОГ СНАРЯЖЕНИЯ", 24, 90, 135, 45, False)
    _global.__tgText(p, "query", _global.__tgFilterQuery, 157, 190, 135, 24, True)
    _global.__tgButton(p, "search", "Найти", 300, 190, 57, "search", "")
    levelLabel = "Ур. " + String(_global.__tgFilterLevel)
    if _global.__tgFilterLevel == 0:
        levelLabel = "Все уровни"
    _global.__tgButton(p, "levelfilter", levelLabel + " ▼", 157, 126, 96, "filtermenu", "level")
    lineLabel = _global.__tgLine
    if lineLabel == "all":
        lineLabel = "A/G/К"
    _global.__tgButton(p, "linefilter", lineLabel + " ▼", 260, 126, 97, "filtermenu", "line")
    upgradeLabel = "Без чертежа"
    if _global.__tgUpgrade == "modified":
        upgradeLabel = "С улучшением"
    if _global.__tgUpgrade == "all":
        upgradeLabel = "Все улучшения"
    _global.__tgButton(p, "upgradefilter", upgradeLabel + " ▼", 157, 158, 200, "filtermenu", "upgrade")
    p.upgradefilter._visible = _global.__tgTab != "mob" and _global.__tgCategory == "weapon"
    p.levelfilter._visible = _global.__tgCategory != "ammo" and _global.__tgCategory != "medicine"
    p.linefilter._visible = _global.__tgTab != "mob" and _global.__tgCategory != "ammo" and _global.__tgCategory != "medicine"
    if _global.__tgTab != "mob":
        cats = ["weapon", "armour", "pouch", "ammo", "medicine", "set"]
        labels = ["Оружие", "Броня", "Подсумки", "Патроны", "Медицина", "Комплекты"]
        i = 0
        while i < 6:
            _global.__tgButton(p, "cat" + String(i), labels[i], 24, 155 + i * 32, 120, "category", cats[i])
            i = i + 1
        classNames = ["Пистолеты", "Дробовики", "Автоматы", "Винтовки", "Пулемёты", "Пистолет-пулемёты", "Ближний бой"]
        classLabel = "Тип оружия"
        if _global.__tgClass >= 0:
            classLabel = classNames[_global.__tgClass]
        _global.__tgButton(p, "classfilter", classLabel + " ▼", 157, 95, 200, "filtermenu", "class")
        p.classfilter._visible = _global.__tgCategory == "weapon"
        p.upgradefilter._visible = _global.__tgCategory == "weapon"
        draft = _global.__tgPlayer
        if _global.__tgTab == "enemy" or _global.__tgTab == "enemygear":
            draft = _global.__tgEnemy
        _global.__tgButton(p, "skillsbtn", "Уровни и навыки", 370, 95, 190, "category", "skills")
        _global.__tgText(p, "gearhelp", "Первое оружие — основное, второе — запасное, остальные — в рюкзаке. Броня заменяется по слоту. Количество задаётся до выбора.", 370, 138, W - 550, 95, False)
        _global.__tgText(p, "qlabel", "Количество выбранного предмета:", 370, 250, W - 395, 22, False)
        _global.__tgText(p, "amount", "1", 370, 278, 65, 25, True)
        _global.__tgButton(p, "minus", "−", 445, 278, 30, "count", 0 - 1)
        _global.__tgButton(p, "plus", "+", 481, 278, 30, "count", 1)
        _global.__tgButton(p, "clear", "Очистить снаряжение", 370, 319, 220, "clear", "")
        _global.__tgButton(p, "removeLast", "Убрать последний", 600, 319, W - 625, "removeLast", "")
        _global.__tgButton(p, "selectedUp", "▲", W - 57, 358, 28, "selectedscroll", 0 - 1)
        _global.__tgButton(p, "selectedDown", "▼", W - 57, 390, 28, "selectedscroll", 1)
        _global.__tgText(p, "selected", _global.__tgSelected(draft), 370, 358, W - 435, H - 465, False)
    else:
        _global.__tgText(p, "picked", "Моб: " + _global.__tgMobName, 370, 150, W - 395, 65, False)
        modeName = "Моб из игры"
        if _global.__tgMode == "fighter":
            modeName = "Настраиваемый боец"
        _global.__tgButton(p, "mode", modeName, 370, 225, 240, "mode", "")
    _global.__tgButton(p, "prev", "←", 157, H - 140, 40, "page", 0 - 1)
    _global.__tgButton(p, "next", "→", 205, H - 140, 40, "page", 1)
    _global.__tgText(p, "page", "", 255, H - 140, 100, 24, False)
    _global.__tgRequestList()

def __tgDropdown():
    p = _global.__tgPanel
    if p.filtermenu:
        p.filtermenu.removeMovieClip()
    if p.choices:
        visible = p.choices._visible
        p.choices.removeMovieClip()
        if visible:
            return
    if not p.__rows:
        return
    box = p.createEmptyMovieClip("choices", p.getNextHighestDepth())
    rows = p.__rows
    i = 0
    pitch = Math.min(25, (p.__h - 395) / 10)
    while i < len(rows.ids):
        b = _global.__tgButton(box, "row" + String(i), rows.labels[i], 157, 254 + i * pitch, 200, "pick", rows.ids[i])
        b.__icon = rows.icons[i]
        b.__group = rows.groups[i]
        b.__groupSlots = rows.group_slots[i]
        b.__label = rows.labels[i]
        i = i + 1

def __tgList(rows):
    p = _global.__tgPanel
    if not p or not p.page:
        return
    p.page.text = String(Number(rows.page) + 1) + " / " + String(Math.max(1, Math.ceil(Number(rows.total) / 10)))
    p.__rows = rows
    if p.choices:
        p.choices.removeMovieClip()
    i = 0
    while i < len(rows.ids):
        if _global.__tgTab != "mob" and _global.__tgCategory != "set":
            _global.__tgNames[rows.ids[i]] = rows.labels[i]
            _global.__tgSlots[rows.ids[i]] = rows.slots[i]
        i = i + 1
    _global.__tgButton(p, "choose", "Выбрать из списка ▼", 157, 226, 200, "dropdown", "")
    hint = ""
    if rows.total == 0:
        hint = "По этим фильтрам ничего не найдено."
    _global.__tgText(p, "choice", hint, 157, 255, 200, 65, False)

def __tgFilterMenu(key):
    p = _global.__tgPanel
    if p.filtermenu:
        p.filtermenu.removeMovieClip()
        return
    if p.choices:
        p.choices.removeMovieClip()
    labels = ["Все", "A", "G", "Контрабанда"]
    values = ["all", "A", "G", "C"]
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
        while i <= 17:
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
        _global.__tgButton(box, "choice" + String(i), labels[i], 157 + col * 105, 154 + row * 26, width, "filter", {"key":key, "value":values[i]})
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
        if value.key == "class":
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
    if op == "dropdown":
        _global.__tgDropdown()
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
        if p.distance:
            _global.__tgDistance = Number(p.distance.text)
        _global.__tgTab = value
        if value == "player" or value == "enemy":
            _global.__tgCategory = "skills"
        if value == "gear" or value == "enemygear":
            _global.__tgCategory = "weapon"
        _global.__tgPage = 0
        _global.__tgBuild()
        return
    if op == "setlevel":
        n = Math.max(1, Math.min(17, Number(p.presetLevel.text)))
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
        _global.__tgDistance = Number(p.distance.text)
        _global.__tgStationary = 1 - _global.__tgStationary
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
        if _global.__tgTab != "mob":
            if not p.preview:
                preview = lol.display.DisplaySprite.create(p, "preview", p.getNextHighestDepth())
                preview._x = p.__w - 150
                preview._y = 144
                preview._xscale = 75
                preview._yscale = 75
            p.preview.display(String(this.__icon) + "_icon", lol.services.SSEmulator.getIcon(this.__icon))
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
                        _global.__tgNames[t] = name.string + " (тестовая версия)"
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
        if _global.__tgProfileKey(_global.__tgPlayer) != _global.__tgPlayerKey or (_global.__tgMode == "fighter" and _global.__tgProfileKey(_global.__tgEnemy) != _global.__tgEnemyKey):
            p.status.text = "Сначала примените изменённые пресеты персонажа и противника."
            return
        if p.distance:
            _global.__tgDistance = Number(p.distance.text)
        m = _global.__tgSend("start")
        m.addProp("mob", _global.__tgMob)
        m.addProp("mode", "@" + _global.__tgMode + "@")
        m.addProp("stationary", _global.__tgStationary)
        m.addProp("distance", _global.__tgDistance)
        _global.__tgTransmit(m)

def __tgNotifyWrapper(cmd):
    if cmd.messID != "tg":
        this.__tgNotifyOrig(cmd)
        return
    v = cmd.params
    if v.op == "types":
        _global.__tgEpoch = _global.__tgEpoch + 1
        i = 0
        while i < len(v.copies):
            _global.__tgCopies[v.copies[i]] = v.sources[i]
            i = i + 1
    if v.op == "state":
        _global.__tgLocations = v.locations
        _global.__tgLocationLabels = v.location_labels
        _global.__tgLocation = v.location
        _global.__tgDistance = v.distance
        _global.__tgStationary = v.stationary
        _global.__tgMob = v.selected_mob
        _global.__tgMode = v.selected_mode
        if _global.__tgFilterLevel == None:
            _global.__tgFilterLevel = v.level
        _global.__tgRules = v.rules
        _global.__tgVirtualUID = v.virtual_uid
        _global.__tgLive = {}
        i = 0
        while i < len(v.live_oids):
            _global.__tgLive[v.live_oids[i]] = True
            i = i + 1
        refresh = _global.__tgApplying == "player"
        _global.__tgHUDClose()
        _global.__tgToken = v.token
        _global.__tgActive = True
        _global.__tgStatus = "Уровень " + v.level + " · HP " + v.hp + " · Выносливость " + v.sp + " · ОД " + v.ap + " " + v.message
        player = {"skills":v.skills.join(","), "specs":v.specs.join(","), "gear":v.gear}
        enemy = {"skills":v.enemy_skills.join(","), "specs":v.enemy_specs.join(","), "gear":v.enemy_gear}
        _global.__tgPlayerKey = _global.__tgProfileKey(player)
        _global.__tgEnemyKey = _global.__tgProfileKey(enemy)
        if not _global.__tgPlayer or _global.__tgApplying == "player":
            _global.__tgPlayer = player
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
            if _global.__tgPanel.selected:
                draft = _global.__tgPlayer
                if _global.__tgTab == "enemy" or _global.__tgTab == "enemygear":
                    draft = _global.__tgEnemy
                _global.__tgPanel.selected.text = _global.__tgSelected(draft)
    if v.op == "open":
        _global.__tgMob = v.mob
        _global.__tgBuild()
    if v.op == "catalogue":
        _global.__tgList(v)
    if v.op == "error":
        _global.__tgApplying = ""
        _global.__tgStatus = v.message
        if _global.__tgPanel:
            _global.__tgPanel.status.text = v.message
        else:
            alert = lol.core.SceneShifter.openNewAlert("topSimple")
            alert.label = v.message
    if v.op == "result":
        _global.__tgReport = v.message
    if v.op == "exit":
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
        _global.__tgPlayer = None
        _global.__tgEnemy = None
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
            label = parts[0] + " (тестовая версия)"
            i = 1
            while i < len(parts):
                label = label + "$" + parts[i]
                i = i + 1
            item._name = label

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
    if len(_global.__tgObjects) == 0 or (not force and (factory.callCount > 0 or len(factory.callStack) > 0)):
        return
    keep = []
    i = 0
    while i < len(_global.__tgObjects):
        item = _global.__tgObjects[i]
        if _global.__tgLive[item.id]:
            keep.push(item)
        else:
            item.removeEventListener("itemUpdate", lol.core.Master.getInstance().gamer.equipment)
            proto = factory.getProtoItem(item.typeID)
            proto.removeEventListener("itemUpdate", item)
            lol.utils.StringCollector.getInstance().removeEventListener("update", item, item.stringUpdate)
            _global.__tgDeleteItem(item.id)
        i = i + 1
    _global.__tgObjects = keep

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
    _global.__tgPlayer = None
    _global.__tgEnemy = None
    _global.__tgActive = False

def __tgSocketWrapper():
    _global.__tgCleanup()
    this.__tgSocketOrig()

def __tgConnectionCloseWrapper():
    _global.__tgCleanup()
    this.__tgConnectionCloseOrig()

def __tgSave():
    store = SharedObject.getLocal("lavaTrainingPresets_v1_" + _global.__hcEncode(_global.__hcEndpoint + "|" + _global.__tgOwner))
    p = _global.__tgPlayer
    e = _global.__tgEnemy
    store.data.player = {"skills":p.skills, "specs":p.specs, "gear":p.gear}
    store.data.enemy = {"skills":e.skills, "specs":e.specs, "gear":e.gear}
    result = store.flush()
    _global.__tgPanel.status.text = "Пресеты сохранены локально."
    if result == False:
        _global.__tgPanel.status.text = "Не удалось сохранить пресет в локальном хранилище."
    if result == "pending":
        _global.__tgPanel.status.text = "Для сохранения требуется разрешение локального хранилища Flash."

def __tgLoad():
    store = SharedObject.getLocal("lavaTrainingPresets_v1_" + _global.__hcEncode(_global.__hcEndpoint + "|" + _global.__tgOwner))
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
    _global.__tgPlayer = {"skills":p.skills, "specs":p.specs, "gear":p.gear}
    _global.__tgEnemy = {"skills":e.skills, "specs":e.specs, "gear":e.gear}
    _global.__tgStatus = "Пресеты загружены. Примените их перед боем."
    _global.__tgBuild()

def __tgIcon(typeID):
    source = _global.__tgCopies[typeID]
    if source:
        typeID = source
    return this.__tgIconOrig(typeID)

def __tgInstall():
    _global.__tgEpoch = 0
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
    _global.__tgCopies = {}
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
    _global.__tgDistance = 12
    _global.__tgStationary = 0
    _global.__tgMode = "mob"
    _global.__tgMob = 0
    _global.__tgMobName = "не выбран"
    _global.__tgReport = "Результаты появятся после боя."
    _global.__tgStatus = ""
'''


def patches(Asm, undef):
    compiler = Compiler(Asm, undef)
    functions = compiler.functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
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
