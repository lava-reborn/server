"""Small private instructor preset selector; reuses range-only UI components."""
SOURCE = r'''
def __tgKitBuild(p, W, H):
    p.apply._visible = False
    p.recover._visible = False
    if not _global.__tgKitLevel:
        _global.__tgKitLevel = 1
        _global.__tgKitLine = "A"
        _global.__tgKitClass = 0
    _global.__tgKitClasses = ["Пистолеты", "Дробовики", "Автоматы", "Винтовки", "Пулемёты", "Пистолет-пулемёты", "Холодное оружие"]
    _global.__tgButton(p, "kitLevel", "Уровень: " + String(_global.__tgKitLevel) + " ▼", 28, 103, 200, "kit_menu", "level")
    _global.__tgButton(p, "kitLine", "Версия: " + _global.__tgKitLine + " ▼", 28, 143, 200, "kit_menu", "line")
    _global.__tgButton(p, "kitClass", _global.__tgKitClasses[_global.__tgKitClass] + " ▼", 28, 183, 200, "kit_menu", "class")
    _global.__tgText(p, "kitHint", "Заменяет настройки и вещи клона.\n\nБроня и оружие надеваются, припасы - в рюкзак. Оружие нужно зарядить.\n\nСостав и уровни вещей указаны справа.", 28, 227, 200, H - 348, False)
    _global.__tgText(p, "kitHeading", "Загрузка состава…", 250, 103, W - 278, 25, False)
    _global.__tgText(p, "kitSummary", "", 250, 135, W - 278, 90, False)
    _global.__tgText(p, "kitContents", "", 250, 230, W - 278, H - 350, False)
    _global.__tgButton(p, "kitApply", "Применить готовый набор", 24, H - 54, 245, "kit_prepare", "")
    _global.__tgUIEnable(p.kitApply, False)
    _global.__tgUIEnable(p.kitLevel, False)
    _global.__tgKitRequest()

def __tgKitRequest():
    _global.__tgKitSeq = Number(_global.__tgKitSeq or 0) + 1
    m = _global.__tgSend("kit_preview")
    m.addProp("request_id", _global.__tgKitSeq)
    m.addProp("level", _global.__tgKitLevel)
    m.addProp("line", "@" + _global.__tgKitLine + "@")
    m.addProp("wclass", _global.__tgKitClass)
    _global.__tgTransmit(m)

def __tgKitPreview(v):
    p = _global.__tgPanel
    if not p or _global.__tgContext != "player" or _global.__tgTab != "kits" or v.request_id != _global.__tgKitSeq:
        return
    _global.__tgKitLevel = v.level
    _global.__tgKitLine = v.line
    _global.__tgKitClass = v.wclass
    _global.__tgKitLevels = v.levels
    p.kitLine.caption.text = "Версия: " + v.line + " ▼"
    p.kitClass.caption.text = _global.__tgKitClasses[v.wclass] + " ▼"
    _global.__tgUIEnable(p.kitLevel, len(v.levels) > 0)
    p.kitLevel.caption.text = "Уровень: " + String(v.level) + " ▼"
    p.kitHeading.text = v.title
    p.kitSummary.text = v.summary
    p.kitContents.text = v.contents
    _global.__tgUITextFit(p.kitSummary)
    _global.__tgUITextFit(p.kitContents)
    _global.__tgUITextFit(p.kitClass.caption)
    _global.__tgUIEnable(p.kitApply, Boolean(v.available))

def __tgKitMenu(key):
    p = _global.__tgPanel
    if _global.__tgMenuToggle(p, "kit:" + key):
        return
    labels = ["A - афро", "G - голд"]
    values = ["A", "G"]
    if key == "class":
        labels = _global.__tgKitClasses
        values = [0, 1, 2, 3, 4, 5, 6]
    if key == "level":
        labels = []
        values = _global.__tgKitLevels or []
        i = 0
        while i < len(values):
            labels.push(String(values[i]) + " уровень")
            i = i + 1
    rows = Math.min(10, Math.max(1, Math.floor((p.__h - 225) / 30)))
    width = 230
    y = 132
    if key == "line":
        y = 172
    if key == "class":
        y = 212
    box = _global.__tgMenuBox(p, "kitMenu", "kit:" + key, 28, y, Math.ceil(len(values) / rows) * width + 8, Math.min(rows, len(values)) * 30 + 8)
    i = 0
    while i < len(values):
        x = box.__menuX + 4 + Math.floor(i / rows) * width
        y = box.__menuY + 4 + (i % rows) * 30
        _global.__tgButton(box, "option" + String(i), labels[i], x, y, width - 4, "kit_filter", {"key":key, "value":values[i]})
        i = i + 1


def __tgKitClick(op, value):
    if _global.__tgContext != "player" or _global.__tgTab != "kits":
        return
    if op == "kit_menu":
        _global.__tgKitMenu(value)
        return
    if op == "kit_filter":
        if value.key == "level":
            _global.__tgKitLevel = value.value
        if value.key == "line":
            _global.__tgKitLine = value.value
        if value.key == "class":
            _global.__tgKitClass = value.value
        _global.__tgBuild()
        return
    if op == "kit_prepare":
        if _global.__tgResetPending or _global.__tgResetDialog or lol.core.SceneShifter._ref.UIPanels.query.instance:
            return
        _global.__tgResetPending = True
        m = _global.__tgSend("kit_prepare")
        m.addProp("level", _global.__tgKitLevel)
        m.addProp("line", "@" + _global.__tgKitLine + "@")
        m.addProp("wclass", _global.__tgKitClass)
        _global.__tgTransmit(m)
'''
