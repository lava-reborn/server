"""Native AVM1 training terminal using the game's settings-window artwork."""
from avm_codegen import Compiler
from functools import lru_cache

SOURCE = '''
def __tgSend(op):
    m = new(lol.server.mess.CSMessage)
    m._name = "tg"
    m.addProp("op", "@" + op + "@")
    m.addProp("token", "@" + _global.__tgToken + "@")
    return m

def __tgServiceActivate():
    m = _global.__tgSend(this.__op)
    m.addProp("npc", this.mob_id)
    _global.__tgTransmit(m)
    lol.core.SceneShifter.closeWindow("support")

def __tgNPCWrapper(obj):
    this.__tgNPCOrig(obj)
    this.__tgTerminal = Boolean(obj.param.tg_terminal)
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

def __tgOpenService(id):
    npc = lol.core.Master.getInstance().getPlayer(id)
    if _global.__tgActive and npc.__tgTerminal and len(npc.supportList) == 1:
        choices = lol.core.player.NPCService.getServiceList(id)
        if len(choices) == 1 and choices[0] == "support" and not npc.hasQuests():
            service = npc.supportList[0]
            if service.__op == "open":
                service.activate()
                return
    return lol.core.player.NPCService.__tgOpenServiceOrig(id)

def __tgText(p, name, value, x, y, w, h, input):
    if _global.__tgUIOwned(p):
        x = Math.round(x)
        y = Math.round(y)
        w = Math.round(w)
        h = Math.round(h)
    p.createTextField(name, p.getNextHighestDepth(), x, y, w, h)
    f = p[name]
    f.embedFonts = False
    f.wordWrap = True
    f.multiline = True
    f.selectable = input
    fmt = new("TextFormat")
    fmt.font = "Tahoma"
    fmt.size = 12
    if _global.__tgUIOwned(p):
        fmt.font = "Arial"
        fmt.bold = False
        fmt.italic = False
        fmt.size = 16
        f.filters = []
    fmt.color = 13616814
    if _global.__tgUIOwned(p):
        fmt.color = 2697507
        if p.__width:
            fmt.color = 14999243
    f.setNewTextFormat(fmt)
    f.text = value
    if input:
        f.type = "input"
        f.border = True
        f.borderColor = 5394505
        f.background = True
        f.backgroundColor = 3552308
        f.maxChars = 400
        if _global.__tgUIOwned(p):
            f.multiline = False
            f.wordWrap = False
            f.backgroundColor = 10131336
            f.borderColor = 9868418
            if name != "query":
                fmt.align = "center"
                f.setTextFormat(fmt)
                f.setNewTextFormat(fmt)
    if _global.__tgUIOwned(p):
        _global.__tgUITextFit(f)
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
    if _global.__tgUIOwned(p):
        return _global.__tgUISurface(p, name, x, y, w, h)
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
    _global.__tgText(b, "caption", label, 5, 1, w - 10, 23, False)
    _global.__tgUICaption(b, op)
    b.__op = op
    b.__value = value
    b.onRelease = _global.__tgClick
    b.onRollOver = _global.__tgHover
    b.onRollOut = _global.__tgUnhover
    b.hintTitle_str = label
    return b

def __tgHUDResize():
    frame = lol.core.SceneShifter._ref
    ui = frame.currentScene
    originX = Math.round((frame.minW - Stage.width) / 2)
    originY = Math.round((frame.minH - Stage.height) / 2)
    width = 150
    x = originX + Stage.width - width - 16
    y = originY + 48
    if ui.__rfButton:
        bounds = ui.__rfButton.getBounds(_root)
        x = bounds.xMax - width
        y = bounds.yMax + 6
    # Reserve the popup's right edge even while it is closed: opening the
    # online list must not cover or move the training return button.
    if ui.__onlinePanel:
        bounds = ui.__onlinePanel.getBounds(_root)
        x = Math.max(x, bounds.xMax + 20)
    this._x = Math.round(Math.max(originX + 8, Math.min(originX + Stage.width - width - 8, x)))
    this._y = Math.round(Math.max(originY + 8, Math.min(originY + Stage.height - 33, y)))

def __tgHUD(phase):
    old = _global.__tgHUDPanel
    if old:
        Stage.removeListener(old)
        Mouse.removeListener(old)
        old.removeMovieClip()
    hud = _root.createEmptyMovieClip("__tgHUDPanel", _root.getNextHighestDepth())
    _global.__tgHUDPanel = hud
    hud.__tgStyled = True
    _global.__tgButton(hud, "main", "К компьютеру", 0, 0, 150, "return", "")
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
    _global.__tgResetClose()
    p = _global.__tgPanel
    if p:
        _global.__tgMenusClose(p)
        p.stopDrag()
        Stage.removeListener(p)
        Mouse.removeListener(p)
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
    if this.__tgStyled:
        this.shine._visible = True
        this.caption.textColor = 15657956
    lol.gpui.HintManager.showHint(this.hintTitle_str, 0, this._width)

def __tgUnhover():
    if this.__tgStyled:
        _global.__tgUISelect(this, Boolean(this.__selected))
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
    p.__catalogueLevels = []
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
    p._x = Math.round(Math.max(left, Math.min(right, p._x)))
    p._y = Math.round(Math.max(top, Math.min(bottom, p._y)))

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
    _global.__tgMaybeDetach()

def __tgBuild():
    _global.__tgResetClose()
    old = _global.__tgPanel
    hadOld = Boolean(old)
    if old:
        oldX = old._x
        oldY = old._y
        old.stopDrag()
        Stage.removeListener(old)
        Mouse.removeListener(old)
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
    p.onMouseDown = _global.__tgMenuMouseDown
    p.onMouseWheel = _global.__tgRuleWheel
    Mouse.addListener(p)
    _global.__tgUIFrame(p, W, H)
    drag = _global.__tgUIRect(p, "drag", 24, 15, W - 80, 29, 0, 0)
    title = _global.__tgText(drag, "title", _global.__tgPostTitle, 4, 5, W - 88, 22, False)
    fmt = title.getTextFormat()
    fmt.align = "center"
    fmt.bold = True
    title.setTextFormat(fmt)
    title.setNewTextFormat(fmt)
    drag.onPress = _global.__tgDragStart
    drag.onRelease = _global.__tgDragStop
    drag.onReleaseOutside = _global.__tgDragStop
    _global.__tgButton(p, "cross", "×", W - 51, 24, 27, "close", "")
    if _global.__tgSupply:
        _global.__tgSupplyBuild(p, W, H)
        return
    tabs = ["mob", "enemy", "enemygear", "result", "rules", "reset"]
    labels = ["Мобы и боссы", "Навыки противника", "Снаряжение противника", "Условия", "Правила", "Сброс"]
    if _global.__tgContext != "computer":
        tabs = ["gear"]
        labels = [_global.__tgPostTitle]
        if _global.__tgContext == "player":
            tabs = ["player", "kits"]
            labels = ["Навыки и специализации", "Готовые наборы"]
    i = 0
    tabw = (W - 48) / len(tabs)
    tabx = 24
    weights = [116, 156, 192, 88, 88, 88]
    while i < len(tabs):
        if _global.__tgContext == "computer":
            tabw = (W - 48) * weights[i] / 728
        button = _global.__tgButton(p, "tab" + String(i), labels[i], tabx, 53, tabw - 5, "tab", tabs[i])
        tabx = tabx + tabw
        if _global.__tgTab == tabs[i]:
            _global.__tgUISelect(button, True)
        i = i + 1
    _global.__tgUIRect(p, "sectionHead", 24, 84, W - 48, 1, 10460554, 65)
    _global.__tgUIRect(p, "sectionFoot", 24, H - 115, W - 48, 1, 10460554, 65)
    _global.__tgText(p, "status", _global.__tgStatus, 24, H - 109, W - 48, 25, False)
    if _global.__tgContext == "computer":
        _global.__tgButton(p, "start", "Вызвать противника", 24, H - 54, 205, "start", "")
        _global.__tgButton(p, "exit", "Покинуть полигон", W - 225, H - 54, 200, "exit", "")
        if _global.__tgTab == "enemy" or _global.__tgTab == "enemygear":
            _global.__tgButton(p, "applyEnemy", "Применить противника", 250, H - 54, 190, "apply", "")
        modeLabel = "Будет вызван: моб / босс"
        if _global.__tgMode == "fighter":
            modeLabel = "Будет вызван: настроенный боец"
        _global.__tgText(p, "modeLabel", modeLabel, 24, H - 80, W - 48, 18, False)
    else:
        _global.__tgButton(p, "apply", "Выдать выбранное снаряжение", 24, H - 54, 245, "apply", "")
        _global.__tgButton(p, "close", "Закрыть", W - 150, H - 54, 125, "close", "")
        if _global.__tgContext == "player":
            p.apply.caption.text = "Применить навыки"
            _global.__tgButton(p, "recover", "Восстановить HP / ОД", 280, H - 54, 210, "recover", "")
    if _global.__tgTab == "kits" and _global.__tgContext == "player":
        _global.__tgKitBuild(p, W, H)
        return
    if _global.__tgTab == "reset":
        _global.__tgText(p, "resetTitle", "Начать настройку персонажа с нуля", 28, 105, W - 56, 30, False)
        _global.__tgText(p, "resetInfo", "Персонаж на полигоне вернётся на 1-й уровень. Навыки и специализации будут сброшены, все вещи и активные эффекты удалены.\\n\\nОсновной персонаж и другие участники не изменятся. Правила боя, противник и площадка сохранятся. Очистку нельзя отменить.", 28, 145, W - 56, 155, False)
        _global.__tgButton(p, "resetPlayer", "Очистить всё", 28, 320, 210, "reset_prepare", "")
        return
    if _global.__tgTab == "rules":
        _global.__tgRulesControls(p, W, H)
        return
    if _global.__tgContext == "player" or _global.__tgTab == "enemy":
        _global.__tgSkillsControls(p, W, H)
        return
    if _global.__tgTab == "result":
        column = (W - 72) / 2
        right = 44 + column
        _global.__tgButton(p, "location", "Площадка: выбрать ▼", 28, 103, column, "locations", "")
        _global.__tgButton(p, "mode", "Цель: моб / босс · изменить", right, 103, column, "mode", "")
        if _global.__tgMode == "fighter":
            p.mode.caption.text = "Цель: настроенный боец · изменить"
        _global.__tgText(p, "info", "Участников: " + String(_global.__tgParticipants) + ". Площадка общая; её смена переносит всех. Вещи и опыт в основную игру не переносятся.", 28, 136, W - 56, 36, False)
        _global.__tgButton(p, "spawn", _global.__tgSpawnLabels[_global.__tgSpawnPoint] + " ▼", 28, 180, column, "spawns", "")
        _global.__tgText(p, "distanceInfo", "До цели: около " + String(_global.__tgDistance) + " гексов", 28, 210, column, 22, False)
        behaviour = "Активный противник · агро 100+"
        if _global.__tgStationary:
            behaviour = "Неподвижная мишень"
        _global.__tgButton(p, "stationary", behaviour, right, 180, column, "stationary", "")
        healing = "Боец: без лечения"
        if _global.__tgEnemyHealing:
            healing = "Боец: боевая медицина включена"
        _global.__tgButton(p, "healing", healing, 28, 242, column, "enemyhealing", "")
        _global.__tgText(p, "belowLabel", "Порог HP / Ст, %", right, 242, column - 80, 24, False)
        _global.__tgText(p, "healBelow", String(_global.__tgHealBelow), W - 98, 242, 70, 24, True)
        _global.__tgText(p, "countLabel", "Лечений за бой", 28, 276, column - 80, 24, False)
        _global.__tgText(p, "healCount", String(_global.__tgHealCount), 28 + column - 70, 276, 70, 24, True)
        _global.__tgText(p, "hpLabel", "HP / выносливость, %", right, 276, column - 80, 24, False)
        _global.__tgText(p, "mobHealth", String(_global.__tgMobHealth), W - 98, 276, 70, 24, True)
        _global.__tgText(p, "damageLabel", "Урон противника, %", 28, 310, column - 80, 24, False)
        _global.__tgText(p, "mobDamage", String(_global.__tgMobDamage), 28 + column - 70, 310, 70, 24, True)
        _global.__tgText(p, "scaleHint", "25–300%. 100% - исходный моб.", right, 310, column, 24, False)
        chosen = _global.__tgMobName
        if _global.__tgMode == "fighter":
            chosen = _global.__tgEnemyPreset
        fighter = _global.__tgMode == "fighter"
        p.healing._visible = fighter
        p.belowLabel._visible = fighter and Boolean(_global.__tgEnemyHealing)
        p.healBelow._visible = p.belowLabel._visible
        p.countLabel._visible = p.belowLabel._visible
        p.healCount._visible = p.belowLabel._visible
        p.hpLabel._visible = not fighter
        p.mobHealth._visible = not fighter
        p.damageLabel._visible = not fighter
        p.mobDamage._visible = not fighter
        p.scaleHint._visible = not fighter
        if not fighter:
            _global.__tgText(p, "healingHint", "Лечение настраивается для бойца, а не для моба.", 28, 242, W - 56, 24, False)
        _global.__tgText(p, "targetSummary", "Противник: " + chosen, 28, 344, W - 56, 36, False)
        _global.__tgText(p, "report", _global.__tgReport, 28, 386, W - 56, Math.max(20, H - 510), False)
        return
    _global.__tgCatalogueControls(p, W, H)

def __tgClearNotice():
    notice = _global.__tgNotice
    _global.__tgNotice = None
    if notice:
        top = lol.core.SceneShifter._ref.currentScene.topWindow
        if top.content == notice:
            top.close()
        else:
            notice.removeMovieClip()

def __tgResetClose():
    _global.__tgResetPending = False
    dialog = _global.__tgResetDialog
    _global.__tgResetDialog = None
    if dialog:
        dialog.removeEventListener("click", _global, _global.__tgResetAnswer)
        if lol.core.SceneShifter._ref.UIPanels.query.instance.content == dialog:
            lol.core.SceneShifter.closeWindow("query")

def __tgResetPrompt(v):
    waiting = _global.__tgResetPending
    _global.__tgResetPending = False
    context = "computer"
    if v.op == "kit_confirm":
        context = "player"
    if not waiting or not _global.__tgActive or v.token != _global.__tgToken or not _global.__tgPanel or _global.__tgContext != context:
        return
    if lol.core.SceneShifter._ref.UIPanels.query.instance:
        return
    dialog = lol.core.SceneShifter.openNewWindow("query").content
    _global.__tgResetDialog = dialog
    dialog.__tgResetToken = v.token
    dialog.__tgResetConfirmation = v.confirmation
    dialog.label = "Очистить тренировочного персонажа?\\n\\nУровень станет 1-м. Навыки, специализации, все вещи и эффекты будут сброшены.\\n\\nОсновной персонаж не изменится. Отменить очистку нельзя."
    dialog.__tgAction = "reset_player"
    dialog.__tgContext = context
    if v.op == "kit_confirm":
        dialog.__tgAction = "kit_apply"
        dialog.label = "Применить набор: " + v.title + "?\\n\\nТекущие вещи, навыки, специализации и эффекты клона будут заменены.\\n\\nОсновной персонаж не изменится. Отменить замену нельзя."
    dialog.addEventListener("click", _global, _global.__tgResetAnswer)

def __tgResetAnswer(event):
    dialog = _global.__tgResetDialog
    if not dialog or event.target != dialog:
        return
    token = dialog.__tgResetToken
    confirmation = dialog.__tgResetConfirmation
    action = dialog.__tgAction
    context = dialog.__tgContext
    _global.__tgResetClose()
    if not event.success or not _global.__tgActive or token != _global.__tgToken or _global.__tgContext != context:
        return
    m = _global.__tgSend(action)
    m.addProp("confirmation", "@" + confirmation + "@")
    _global.__tgApplying = "player"
    _global.__tgTransmit(m)

def __tgProfileTexts(values, codec):
    result = []
    i = 0
    while values and i < len(values):
        text = values[i]
        if codec == 1:
            text = text.split("%3B").join(";").split("%3D").join("=").split("%7C").join("|")
            text = lol.server.XMLString.unescape(text)
        result.push(text)
        i = i + 1
    return result

def __tgProfileAvailable(index):
    return kind(index) == "number" and _global.__tgProfileTitles and index >= 0 and index < len(_global.__tgProfileTitles) and Boolean(_global.__tgProfileTitles[index]) and Boolean(_global.__tgProfileKeys[index]) and Boolean(_global.__tgProfileValues[index])

def __tgProfilesLoad(v):
    _global.__tgProfileKeys = v.profile_keys or []
    _global.__tgProfileTitles = _global.__tgProfileTexts(v.profile_titles, v.profile_text_codec)
    _global.__tgProfileValues = v.profile_values or []
    _global.__tgProfileNotes = _global.__tgProfileTexts(v.profile_notes, v.profile_text_codec)
    _global.__tgProfileOffsets = v.profile_offsets or []
    _global.__tgProfileCounts = v.profile_counts or []
    _global.__tgProfileSelected = v.profile_selected
    _global.__tgProfilePersonal = v.profile_personal or []
    _global.__tgProfileBases = v.profile_bases or []

def __tgRulesControls(p, W, H):
    if not _global.__tgProfileAvailable(_global.__tgProfileSelected):
        _global.__tgButton(p, "profileSelect", "Профили не загружены", 28, 100, W - 56, "profiles", "")
        _global.__tgUIEnable(p.profileSelect, False)
        _global.__tgText(p, "ruleDescription", "Закройте панель и снова откройте компьютер. Действующие правила не изменены.", 28, 150, W - 56, 70, False)
        return
    _global.__tgButton(p, "profileSelect", "Профиль: " + _global.__tgProfileTitles[_global.__tgProfileSelected] + " ▼", 28, 100, W - 56, "profiles", "")
    if _global.__tgPersonalMode:
        _global.__tgPersonalForm(p, W, H)
        return
    if _global.__tgRuleDetails:
        _global.__tgRuleDescription(p, W, H)
        return
    _global.__tgText(p, "ruleHint", "Множители действуют поверх выбранного профиля. ×1 - без изменения.", 28, 132, W - 56, 24, False)
    values = _global.__tgRuleDraftValues.split(",")
    labels = ["Сила ×", "Ловкость ×", "Телосложение ×", "Восприятие ×", "Интеллект ×", "Максимум HP ×", "Максимум выносливости ×", "Вся броня ×", "Разброс ×", "Добавка брони от эффекта"]
    i = 0
    cw = (W - 65) / 2
    rulePitch = Math.min(29, Math.max(25, (H - 405) / 5))
    ruleButtonsY = 160 + 5 * rulePitch + 6
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
    _global.__tgButton(p, "rulesInfo", "Описание профиля", 230, ruleButtonsY + 35, 210, "rulesinfo", "")
    _global.__tgPersonalButtons(p, W, H)
    return

def __tgPersonalButtons(p, W, H):
    y = H - 165
    _global.__tgButton(p, "profileCreate", "Создать копию", 28, y, 170, "profileform", "create")
    _global.__tgButton(p, "profileEdit", "Сохранить изменения", 208, y, 205, "profileform", "edit")
    _global.__tgButton(p, "profileDelete", "Удалить профиль", 423, y, 180, "profileform", "delete")
    personal = Boolean(_global.__tgProfilePersonal[_global.__tgProfileSelected])
    _global.__tgUIEnable(p.profileEdit, personal)
    _global.__tgUIEnable(p.profileDelete, personal)
    _global.__tgText(p, "personalHint", "Личные профили сохраняются для этого персонажа. Встроенные изменить нельзя.", 28, H - 137, W - 56, 20, False)

def __tgPersonalForm(p, W, H):
    deleting = _global.__tgPersonalMode == "delete"
    message = "Название личного профиля (до 32 символов):"
    if deleting:
        message = "Удалить этот личный профиль? Применённые параметры боя останутся прежними."
    _global.__tgText(p, "personalTitle", message, 28, 150, W - 56, 55, False)
    field = _global.__tgText(p, "profileName", _global.__tgPersonalName, 28, 216, W - 56, 28, not deleting)
    field.maxChars = 32
    field.restrict = "a-zA-Zа-яА-ЯёЁ0-9 _.()"
    _global.__tgText(p, "personalInfo", "Сохраняются текущие множители и выбранная основа формул. Сохранение не применяет их к бою автоматически.", 28, 268, W - 56, 65, False)
    if deleting:
        p.personalInfo.text = "Будет удалена только ваша запись в списке профилей. Персонаж, вещи и другие игроки не изменятся."
    _global.__tgButton(p, "personalConfirm", "Сохранить", 28, H - 170, 180, "profilecommit", "")
    if deleting:
        p.personalConfirm.caption.text = "Удалить"
    _global.__tgButton(p, "personalCancel", "Отмена", 220, H - 170, 140, "profilecancel", "")

def __tgRuleDescription(p, W, H):
    selected = _global.__tgProfileSelected
    paragraphs = []
    offset = _global.__tgProfileOffsets[selected]
    count = _global.__tgProfileCounts[selected]
    i = 0
    while i < count:
        paragraphs.push(_global.__tgProfileNotes[offset + i])
        i = i + 1
    if _global.__tgProfilePersonal[selected]:
        baseIndex = 0
        while baseIndex < len(_global.__tgProfileKeys):
            if _global.__tgProfileKeys[baseIndex] == _global.__tgProfileBases[selected]:
                baseOffset = _global.__tgProfileOffsets[baseIndex]
                j = 0
                while j < _global.__tgProfileCounts[baseIndex]:
                    paragraphs.push(_global.__tgProfileNotes[baseOffset + j])
                    j = j + 1
            baseIndex = baseIndex + 1
    if len(paragraphs) == 0:
        paragraphs = ["Описание не загружено. Откройте компьютер заново."]
    _global.__tgText(p, "ruleInfoHint", "Описание можно прокручивать колёсиком мыши.", 28, 138, W - 56, 25, False)
    field = _global.__tgText(p, "ruleDescription", paragraphs.join("\\n\\n"), 28, 172, W - 100, H - 392, False)
    fmt = field.getTextFormat()
    fmt.size = 16
    field.setTextFormat(fmt)
    field.setNewTextFormat(fmt)
    field.scroll = 1
    _global.__tgButton(p, "ruleUp", "▲", W - 60, 172, 28, "rulescroll", 0 - 5)
    _global.__tgButton(p, "ruleDown", "▼", W - 60, H - 245, 28, "rulescroll", 5)
    _global.__tgButton(p, "rulesInfo", "Настроить множители", 28, H - 205, 230, "rulesinfo", "")
    _global.__tgButton(p, "applyRules", "Применить правила", 270, H - 205, 210, "rulesapply", "")
    _global.__tgPersonalButtons(p, W, H)

def __tgRuleScroll(delta):
    p = _global.__tgPanel
    if not p or not p.ruleDescription or p.__menuKey or _global.__tgPersonalMode:
        return
    field = p.ruleDescription
    field.scroll = Math.max(1, Math.min(field.maxscroll, field.scroll + Number(delta)))

def __tgRuleWheel(delta):
    p = this
    if p != _global.__tgPanel or not p.ruleDescription:
        return
    f = p.ruleDescription
    if p._xmouse >= f._x and p._xmouse <= f._x + f._width and p._ymouse >= f._y and p._ymouse <= f._y + f._height:
        _global.__tgRuleScroll(0 - delta * 3)

def __tgSkillsControls(p, W, H):
    draft = _global.__tgPlayer
    if _global.__tgTab == "enemy" or _global.__tgTab == "enemygear":
        draft = _global.__tgEnemy
    values = draft.skills.split(",").concat(draft.specs.split(","))
    titles = ["Ближний бой", "Стрельба", "Медицина", "Промышленность", "Производство", "Рукопашный бой", "Режущее оружие", "Пистолеты", "Дробовики", "Автоматы", "Винтовки", "Ручные пулемёты", "Пистолет-пулемёты", "Хирургия", "Первая помощь", "Добыча", "Переработка", "Мастер свинца", "Мастер селитры", "Мастер меди"]
    if W < 880:
        titles[5] = "Рукопашный бой"
        titles[11] = "Пулемёты"
        titles[12] = "ПП"
    skillsWidth = Math.min(270, (W - 72) * 33 / 100)
    specX = 48 + skillsWidth
    specWidth = (W - specX - 28) / 2
    _global.__tgText(p, "skillsHeading", "Основные навыки", 28, 103, skillsWidth, 24, False)
    _global.__tgText(p, "specsHeading", "Специализации", specX, 103, W - specX - 28, 24, False)
    _global.__tgUIRect(p, "skillsRule", 28, 129, skillsWidth - 8, 1, 11183252, 45)
    _global.__tgUIRect(p, "specsRule", specX, 129, W - specX - 28, 1, 11183252, 45)
    _global.__tgUIRect(p, "skillsDivider", specX - 12, 103, 1, H - 288, 11183252, 35)
    pitch = Math.min(36, (H - 350) / 5)
    i = 0
    while i < 17:
        cw = skillsWidth
        x = 28
        row = i
        key = "skill" + String(i)
        low = 0
        high = 20
        if i >= 5:
            index = i - 5
            cw = specWidth
            x = specX + Math.floor(index / 6) * cw
            row = index % 6
            key = "spec" + String(index)
            low = 0 - 1
            high = _global.__tgSpecMax
        y = 144 + row * pitch
        _global.__tgText(p, key + "label", titles[i], x, y, cw - 100, 23, False)
        _global.__tgText(p, key, values[i], x + cw - 94, y, 34, 23, True)
        _global.__tgButton(p, key + "minus", "−", x + cw - 55, y, 22, "adjust", {"field":key, "step":0 - 1, "low":low, "high":high})
        _global.__tgButton(p, key + "plus", "+", x + cw - 29, y, 22, "adjust", {"field":key, "step":1, "low":low, "high":high})
        i = i + 1
    if _global.__tgTab == "enemy":
        _global.__tgButton(p, "copy", "Скопировать моего персонажа", 28, H - 178, 280, "copy", "")
    _global.__tgText(p, "levelHint", "Базовый уровень:", 24, H - 141, 125, 23, False)
    levels = draft.skills.split(",")
    currentLevel = Math.max(Number(levels[0]), Number(levels[1]), Number(levels[2]), Number(levels[3]), Number(levels[4]))
    _global.__tgText(p, "presetLevel", String(currentLevel), 155, H - 141, 42, 23, True)
    _global.__tgButton(p, "setlevel", "Задать", 203, H - 141, 78, "setlevel", "")
    _global.__tgText(p, "levelExplanation", "Уровень персонажа определяется старшим навыком.", 292, H - 141, W - 320, 23, False)
    return
def __tgCatalogueControls(p, W, H):
    if _global.__tgTab == "enemygear" and _global.__tgEnemyLook:
        _global.__tgGearBuild(p, W, H)
        return
    left = 24
    area = W - 340
    if _global.__tgTab == "mob":
        left = 205
        area = W - 230
        groups = ["all", "camps", "mines", "bosses", "crocodiles", "animals", "patrols", "caravans"]
        labels = ["Все противники", "Бойцы лагерей", "Шахты", "Боссы лагерей", "Крокодилы", "Животные", "Патрули Магриба", "Караваны"]
        i = 0
        while i < len(groups):
            button = _global.__tgButton(p, "group" + String(i), labels[i], 24, 105 + i * 33, 165, "mobgroup", groups[i])
            if _global.__tgMobGroup == groups[i]:
                _global.__tgUISelect(button, True)
            i = i + 1
        _global.__tgText(p, "picked", "Выбрано: " + _global.__tgMobName, left, H - 180, area, 34, False)
    else:
        _global.__tgText(p, "kitTitle", _global.__tgEnemyPreset, W - 292, 96, 265, 48, False)
        _global.__tgText(p, "qlabel", "Количество", W - 292, 145, 150, 22, False)
        _global.__tgText(p, "amount", "1", W - 292, 173, 70, 25, True)
        _global.__tgButton(p, "minus", "−", W - 210, 173, 32, "count", 0 - 1)
        _global.__tgButton(p, "plus", "+", W - 170, 173, 32, "count", 1)
        _global.__tgButton(p, "gearLook", "Осмотр снаряжения", W - 292, 218, 265, "enemylook", "")
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
    levelWidth = Math.min(100, Math.floor(area * 30 / 100))
    lineWidth = Math.min(85, Math.floor(area * 25 / 100))
    upgradeWidth = Math.min(140, area - levelWidth - lineWidth - 12)
    if _global.__tgTab != "mob" and not _global.__tgFilterLevel:
        levelLabel = "Ур.: все"
    _global.__tgButton(p, "levelfilter", levelLabel + " ▼", left, 103, levelWidth, "filtermenu", "level")
    lineLabel = _global.__tgLine
    if lineLabel == "all":
        lineLabel = "Все версии"
    _global.__tgButton(p, "linefilter", lineLabel + " ▼", left + levelWidth + 6, 103, lineWidth, "filtermenu", "line")
    upgradeLabel = "Все улучшения"
    if _global.__tgUpgrade == "base":
        upgradeLabel = "Без чертежа"
    if _global.__tgUpgrade == "modified":
        upgradeLabel = "С улучшением"
    _global.__tgButton(p, "upgradefilter", upgradeLabel + " ▼", left + levelWidth + lineWidth + 12, 103, upgradeWidth, "filtermenu", "upgrade")
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
    _global.__tgGearClear(p)
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
    _global.__tgPreviewTypes = _global.__tgPreviewTypes or {}
    p.__catalogueLevels = rows.available_levels
    if rows.selected_level != None:
        _global.__tgFilterLevel = Number(rows.selected_level)
        label = "Любой уровень"
        if _global.__tgFilterLevel:
            label = "Ур. " + String(_global.__tgFilterLevel)
        if _global.__tgTab != "mob" and not _global.__tgFilterLevel:
            label = "Ур.: все"
        p.levelfilter.caption.text = label + " ▼"
        _global.__tgPage = Number(rows.page)
    _global.__tgReleaseRows(p)
    p.page.text = String(Number(rows.page) + 1) + " / " + String(Math.max(1, Math.ceil(Number(rows.total) / 10)))
    _global.__tgUIEnable(p.prev, Number(rows.page) > 0)
    _global.__tgUIEnable(p.next, (Number(rows.page) + 1) * 10 < Number(rows.total))
    p.cards = p.createEmptyMovieClip("cards", p.getNextHighestDepth())
    width = (p.__listWidth - 10) / 2
    pitch = Math.min(57, (p.__h - 370) / 5)
    i = 0
    while i < len(rows.ids):
        if _global.__tgCategory != "mob" and _global.__tgCategory != "set":
            _global.__tgNames[rows.ids[i]] = rows.labels[i]
            _global.__tgSlots[rows.ids[i]] = rows.slots[i]
            if rows.types:
                _global.__tgPreviewTypes[rows.ids[i]] = rows.types[i]
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
            _global.__tgText(b, "badge", "[" + String(rows.levels[i]) + "]", 6, 4, 46, 18, False)
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
    if _global.__tgMenuToggle(p, "filter:" + key):
        return
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
        i = 0
        if p.__catalogueLevels:
            while i < len(p.__catalogueLevels):
                level = Number(p.__catalogueLevels[i])
                labels.push(String(level) + " уровень")
                values.push(level)
                i = i + 1
    width = 230
    if key == "level":
        width = 145
    rows = Math.min(9, Math.max(1, Math.floor((p.__h - 225) / 30)))
    columns = Math.ceil(len(values) / rows)
    box = _global.__tgMenuBox(p, "filtermenu", "filter:" + key, p.__listX, 133, columns * width + 8, Math.min(rows, len(values)) * 30 + 8)
    i = 0
    while i < len(values):
        _global.__tgButton(box, "choice" + String(i), labels[i], box.__menuX + 4 + Math.floor(i / rows) * width, box.__menuY + 4 + (i % rows) * 30, width - 4, "filter", {"key":key, "value":values[i]})
        i = i + 1


def __tgClick():
    p = _global.__tgPanel
    op = this.__op
    value = this.__value
    if op != "profiles" and op != "kit_menu" and op != "filtermenu" and op != "spawns" and op != "locations":
        _global.__tgMenusClose(p)
    if op == "kit_menu" or op == "kit_filter" or op == "kit_prepare":
        _global.__tgKitClick(op, value)
        return
    if op == "reset_prepare":
        if _global.__tgResetPending or _global.__tgResetDialog or not _global.__tgActive or _global.__tgContext != "computer":
            return
        if lol.core.SceneShifter._ref.UIPanels.query.instance:
            return
        _global.__tgResetPending = True
        _global.__tgTransmit(_global.__tgSend("reset_prepare"))
        return
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
    if op == "profileform":
        if value != "create" and not _global.__tgProfilePersonal[_global.__tgProfileSelected]:
            return
        _global.__tgRuleDraft()
        _global.__tgPersonalMode = value
        _global.__tgPersonalName = _global.__tgProfileTitles[_global.__tgProfileSelected]
        if value == "create":
            _global.__tgPersonalName = "Мой профиль"
        _global.__tgBuild()
        return
    if op == "profilecancel":
        _global.__tgPersonalMode = None
        _global.__tgBuild()
        return
    if op == "profilecommit":
        selected = _global.__tgProfileSelected
        action = "profile_save"
        if _global.__tgPersonalMode == "delete":
            action = "profile_delete"
        m = _global.__tgSend(action)
        if _global.__tgPersonalMode != "create":
            m.addProp("key", "@" + _global.__tgProfileKeys[selected] + "@")
        m.addProp("base", "@" + _global.__tgProfileBases[selected] + "@")
        m.addProp("name", "@" + lol.server.XMLString.escape(p.profileName.text) + "@")
        m.addProp("values", "@" + _global.__tgRuleDraftValues + "@")
        _global.__tgTransmit(m)
        return
    if op == "rulescroll":
        _global.__tgRuleScroll(Number(value))
        return
    if op == "profiles":
        if not _global.__tgProfileAvailable(_global.__tgProfileSelected):
            return
        if _global.__tgMenuToggle(p, "profiles"):
            return
        count = len(_global.__tgProfileTitles)
        menu = _global.__tgMenuBox(p, "profiles", "profiles", 28, 128, p.__w - 56, count * 30 + 8)
        i = 0
        while i < count:
            _global.__tgButton(menu, "profile" + String(i), _global.__tgProfileTitles[i], menu.__menuX + 4, menu.__menuY + 4 + i * 30, p.__w - 64, "rulespreset", i)
            i = i + 1
        return
    if op == "rulesinfo":
        _global.__tgPersonalMode = None
        _global.__tgRuleDraft()
        _global.__tgRuleDetails = not _global.__tgRuleDetails
        _global.__tgBuild()
        return
    if op == "rulespage":
        _global.__tgRulePage = value
        _global.__tgBuild()
        return
    if op == "rulespreset":
        _global.__tgPersonalMode = None
        if not _global.__tgProfileAvailable(value):
            return
        _global.__tgRuleDetails = True
        _global.__tgRulePage = 0
        _global.__tgProfileSelected = value
        _global.__tgRuleDraftValues = _global.__tgProfileValues[_global.__tgProfileSelected]
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
        if not _global.__tgProfileAvailable(_global.__tgProfileSelected):
            return
        _global.__tgRuleDraft()
        m = _global.__tgSend("rules")
        m.addProp("profile", "@" + _global.__tgProfileKeys[_global.__tgProfileSelected] + "@")
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
        if _global.__tgMenuToggle(p, "spawns"):
            return
        box = _global.__tgMenuBox(p, "spawns", "spawns", 28, 209, 420, len(_global.__tgSpawnLabels) * 30 + 8)
        i = 0
        while i < len(_global.__tgSpawnLabels):
            _global.__tgButton(box, "option" + String(i), _global.__tgSpawnLabels[i], box.__menuX + 4, box.__menuY + 4 + i * 30, 412, "spawn", i)
            i = i + 1
        return
    if op == "spawn":
        m = _global.__tgSend("spawn")
        m.addProp("spawn_point", Number(value))
        _global.__tgTransmit(m)
        return
    if op == "locations":
        if _global.__tgMenuToggle(p, "locations"):
            return
        box = _global.__tgMenuBox(p, "locations", "locations", 28, 135, 350, len(_global.__tgLocationLabels) * 30 + 8)
        i = 0
        while i < len(_global.__tgLocationLabels):
            _global.__tgButton(box, "option" + String(i), _global.__tgLocationLabels[i], box.__menuX + 4, box.__menuY + 4 + i * 30, 342, "location", _global.__tgLocations[i])
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
        _global.__tgStatus = "Пресет скопирован. Нажмите «Применить противника»."
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
    if op == "enemylook":
        _global.__tgEnemyLook = not _global.__tgEnemyLook
        _global.__tgBuild()
        return
    if op == "tab":
        _global.__tgEnemyLook = False
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
        _global.__tgMenusClose(panel)

def __tgNotifyWrapper(cmd):
    if cmd.messID != "tg":
        this.__tgNotifyOrig(cmd)
        return
    v = cmd.params
    if v.op == "supply_list" or v.op == "supply_variants" or v.op == "supply_bag" or v.op == "supply_done":
        _global.__tgSupplyReceive(v)
        return
    if v.op == "profiles":
        _global.__tgProfilesLoad(v)
        _global.__tgPersonalMode = None
        _global.__tgRuleDraftValues = _global.__tgProfileValues[_global.__tgProfileSelected]
        _global.__tgRuleDetails = True
        if _global.__tgPanel and _global.__tgContext == "computer" and _global.__tgTab == "rules":
            _global.__tgBuild()
            _global.__tgPanel.status.text = v.message
        return
    if v.op == "types":
        _global.__tgActive = True
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
        _global.__tgRetireItems()
        _global.__tgEquipmentKey = v.live_oids.join(",")
        _global.__tgPlayer.gear = v.gear
        _global.__tgPlayerKey = _global.__tgProfileKey({"skills":v.skills.join(","), "specs":v.specs.join(","), "gear":v.gear})
        _global.__tgOutfitRevision = v.outfit_rev
    if v.op == "map":
        _global.__tgLocation = v.location
        _global.__tgArenaWidth = v.arena_width
        _global.__tgArenaHeight = v.arena_height
        _global.__tgNativeMap = Boolean(v.native_map)
        return
    if v.op == "state":
        _global.__tgNativeMap = Boolean(v.native_map)
        _global.__tgClearNotice()
        _global.__tgMobName = v.mob_label
        _global.__tgEnemyPreset = v.enemy_preset
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
        _global.__tgRetireItems()
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
        _global.__tgPreviewTypes = _global.__tgPreviewTypes or {}
        _global.__tgOwner = v.owner
        _global.__tgSpecMax = v.spec_max
        i = 0
        while i < len(v.gear_ids):
            _global.__tgNames[v.gear_ids[i]] = v.gear_labels[i]
            _global.__tgSlots[v.gear_ids[i]] = v.gear_slots[i]
            if v.gear_types:
                _global.__tgPreviewTypes[v.gear_ids[i]] = v.gear_types[i]
            i = i + 1
        i = 0
        while i < len(v.enemy_ids):
            _global.__tgNames[v.enemy_ids[i]] = v.enemy_labels[i]
            _global.__tgSlots[v.enemy_ids[i]] = v.enemy_slots[i]
            if v.enemy_types:
                _global.__tgPreviewTypes[v.enemy_ids[i]] = v.enemy_types[i]
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
            if _global.__tgPanel.kitTitle:
                _global.__tgPanel.kitTitle.text = _global.__tgEnemyPreset
            if _global.__tgPanel.picked:
                _global.__tgPanel.picked.text = "Выбрано: " + _global.__tgMobName
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
            _global.__tgProfilesLoad(v)
            _global.__tgPersonalMode = None
            _global.__tgRuleDraftValues = _global.__tgRuleValues
            _global.__tgRuleDetails = True
            _global.__tgRulePage = 0
            _global.__tgTab = "mob"
            _global.__tgMode = "mob"
        if v.context == "player":
            _global.__tgTab = "player"
        _global.__tgBuild()
    if v.op == "catalogue":
        _global.__tgList(v)
    if v.op == "kit_preview":
        _global.__tgKitPreview(v)
    if v.op == "reset_confirm" or v.op == "kit_confirm":
        _global.__tgResetPrompt(v)
    if v.op == "error":
        _global.__tgResetPending = False
        _global.__tgSupplyPending = 0
        _global.__tgRulesApplying = False
        _global.__tgApplying = ""
        _global.__tgStatus = v.message
        if _global.__tgPanel:
            _global.__tgPanel.status.text = v.message
            if _global.__tgPanel.__supply:
                _global.__tgUIEnable(_global.__tgPanel.give, _global.__tgPanel.__supplySource != None)
        else:
            _global.__tgClearNotice()
            alert = lol.core.SceneShifter.openNewAlert("topSimple")
            alert.label = v.message
            _global.__tgNotice = alert
    if v.op == "result":
        _global.__tgClearNotice()
        _global.__tgReport = v.message
    if v.op == "exit_pending":
        _global.__tgClearNotice()
        _global.__tgExitPending()
    if v.op == "exit":
        _global.__tgClearNotice()
        _global.__tgExitPending()
        inspector = lol.core.quests.QuestInspector.getInstance()
        inspector.clear()
        inspector.quester = None
        inspector.lockUpdate = False
        _global.__tgEpoch = _global.__tgEpoch + 1
        _global.__tgReturnEquipment = True
        _global.__tgReturnBagPending = True
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

def __tgWeaponAmount(value):
    # A queued native showAmount may arrive after the private equipment was
    # replaced. Read the current hand, never the cached WeaponPan.item.
    if this.equipment.__tgManaged:
        item = this.equipment.primaryItem
        if not item or (item.rootID != lol.core.objects.Item.FIRE_ARM and item.rootID != lol.core.objects.Item.HEAL_ITEM):
            value = ""
    this.__tgWeaponAmountOrig(value)

def __tgWeaponIcon(item):
    this.__tgWeaponIconOrig(item)
    if this.equipment.__tgManaged:
        current = this.equipment.primaryItem
        if not current or (current.rootID != lol.core.objects.Item.FIRE_ARM and current.rootID != lol.core.objects.Item.HEAL_ITEM):
            this.showAmount("")

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
        if not _global.__tgNativeMap:
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
            result.__tgEpoch = _global.__tgEpoch
            _global.__tgObjects.push(result)
    return result

def __tgRetireItems():
    i = 0
    while i < len(_global.__tgObjects):
        item = _global.__tgObjects[i]
        item.__tgRetired = not Boolean(_global.__tgLive[item.id])
        i = i + 1

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
        if not force and (_global.__tgLive[item.id] or (_global.__tgActive and not item.__tgRetired and item.__tgEpoch == _global.__tgEpoch)):
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
    if _global.__tgReturnBagPending and not _global.__tgActive and Math.floor(Number(obj.data) / 8) % 2 == 1:
        _global.__tgReturnBagPending = False
    _global.__tgMaybeDetach()

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
        if copy != Boolean(_global.__tgActive) or (copy and not _global.__tgLive[item.id] and (item.__tgRetired or item.__tgEpoch != _global.__tgEpoch)):
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
    _global.__tgProfileKeys = []
    _global.__tgProfileTitles = []
    _global.__tgProfileValues = []
    _global.__tgProfileNotes = []
    _global.__tgProfileOffsets = []
    _global.__tgProfileCounts = []
    _global.__tgProfileSelected = None
    _global.__tgPreviewTypes = {}
    _global.__tgEnemyLook = False
    _global.__tgPersonalMode = None
    _global.__tgProfilePersonal = []
    _global.__tgProfileBases = []
    _global.__tgRuleDraftValues = None
    _global.__tgRuleValues = None
    _global.__tgRulesApplying = False
    _global.__tgPlayer = None
    _global.__tgEnemy = None
    _global.__tgActive = False
    _global.__tgSupply = False
    _global.__tgSupplyPending = 0

    _global.__tgReturnBagPending = False
    _global.__tgSnapshotPending = False
    if _global.__tgHooksActive:
        _global.__tgMaybeDetach()

def __tgSocketWrapper():
    native = this.__tgSocketOrig
    _global.__tgCleanup()
    return native.apply(this, [])

def __tgConnectionCloseWrapper():
    native = this.__tgConnectionCloseOrig
    _global.__tgCleanup()
    return native.apply(this, [])

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
    if _global.__tgHooksActive:
        return
    if _global.__tgEpoch == None:
        _global.__tgEpoch = 0
    _global.__tgSupply = False
    _global.__tgSupplySequence = 0
    _global.__tgSupplyPending = 0
    _global.__tgCombatStats = None
    _global.__tgOutfitRevision = 0 - 1
    _global.__tgCopies = {}
    _global.__tgPreviewTypes = {}
    _global.__tgEnemyLook = False
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
    _global.__tgNativeMap = False
    _global.__tgArenaWidth = 72
    _global.__tgArenaHeight = 144
    _global.__tgParticipants = 1
    _global.__tgDistance = 0
    _global.__tgSpawnPoint = 2
    _global.__tgSpawnLabels = ["Ближняя", "Средняя", "Дальняя - справа сверху"]
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
    _global.__tgProfileKeys = []
    _global.__tgProfileTitles = []
    _global.__tgProfileValues = []
    _global.__tgProfileNotes = []
    _global.__tgProfileOffsets = []
    _global.__tgProfileCounts = []
    _global.__tgProfileSelected = None
    _global.__tgPreviewTypes = {}
    _global.__tgEnemyLook = False
    _global.__tgPersonalMode = None
    _global.__tgProfilePersonal = []
    _global.__tgProfileBases = []
    _global.__tgRuleDraftValues = None
    _global.__tgRuleValues = None
    _global.__tgRulesApplying = False
    _global.__tgReturnBagPending = False
    _global.__tgAttachHooks()
    _global.__tgBindEvents()
    _global.__tgBindSocket()
'''


from training_supply_client import SOURCE as SUPPLY_SOURCE
from training_ui_client import SOURCE as UI_SOURCE
from training_presets_client import SOURCE as PRESETS_SOURCE
from training_bootstrap_client import SOURCE as BOOTSTRAP_SOURCE
SOURCE += SUPPLY_SOURCE + UI_SOURCE + PRESETS_SOURCE + BOOTSTRAP_SOURCE

HOOKS = ((('services', 'HotKeyManager'), 'onKeyDown', '__tgKeysDownOrig', '__tgKeysDown', False),
 (('services', 'HotKeyManager'), 'onKeyUp', '__tgKeysUpOrig', '__tgKeysUp', False),
 (('gpui', 'WeaponPan'), 'showAmount', '__tgWeaponAmountOrig', '__tgWeaponAmount', False),
 (('gpui', 'WeaponPan'), 'attachIcon', '__tgWeaponIconOrig', '__tgWeaponIcon', False),
 (('gpui', 'Annotation'), 'addCost', '__tgAnnotationPriceOrig', '__tgAnnotationPrice', False),
 (('gpui', 'CharInterface'), 'showArmorLevel', '__tgArmorCardOrig', '__tgArmorCard', False),
 (('gpui', 'CharInterface'), 'showKrit', '__tgCritCardOrig', '__tgCritCard', False),
 (('gpui', 'CharInterface'), 'showMeleeEvade', '__tgDodgeCardOrig', '__tgDodgeCard', False),
 (('gpui', 'ItemContainer'), 'attachBack', '__tgBackOrig', '__tgBack', False),
 (('gpui', 'ExtItemContainer'), 'attachBtn', '__tgInfoButtonOrig', '__tgInfoButton', False),
 (('gpui', 'ItemContainer'), 'showCost', '__tgShowCostOrig', '__tgShowCost', False),
 (('core', 'player', 'PersEquip'), 'itemUpdate', '__tgBagUpdateOrig', '__tgBagItemUpdate', False),
 (('core', 'player', 'StuffManager'), 'getStuff', '__tgGetStuffOrig', '__tgGetStuff', False),
 (('core', 'Master'), 'lenter', '__tgEnterOrig', '__tgEnterWrapper', False),
 (('core', 'player', 'PersAttributes'), 'rp_info', '__tgStatsOrig', '__tgStatsWrapper', False),
 (('core', 'player', 'NPC'), 'userInfo', '__tgNPCOrig', '__tgNPCWrapper', False),
 (('core', 'location', 'Location'), 'movePlayer', '__tgMoveOrig', '__tgMoveWrapper', False),
 (('server', 'XMLConnection'), 'close', '__tgConnectionCloseOrig', '__tgConnectionCloseWrapper', False),
 (('server', 'XMLConnection'), 'onClose', '__tgSocketOrig', '__tgSocketWrapper', False),
 (('core', 'player', 'PersEquip'), 'ss_ack', '__tgEquipOrig', '__tgEquipWrapper', False),
 (('core', 'objects', 'Item'), 'itemUpdate', '__tgItemOrig', '__tgItemWrapper', False),
 (('core', 'objects', 'TradeItem'), 'initParams', '__tgTradeParamsOrig', '__tgTradeParams', False),
 (('core', 'player', 'NPCService'), 'openService', '__tgOpenServiceOrig', '__tgOpenService', True),
 (('core', 'location', 'LDParser'), 'parseLD', '__tgParseOrig', '__tgParse', True),
 (('core', 'objects', 'ItemFactory'), 'create', '__tgCreateOrig', '__tgCreate', True),
 (('core', 'objects', 'ItemFactory'), 'updateCall', '__tgUpdateOrig', '__tgUpdateCall', True),
 (('services', 'SSEmulator'), 'getIcon', '__tgIconOrig', '__tgIcon', True))


@lru_cache(maxsize=1)
def patches(Asm, undef):
    compiler = Compiler(Asm, undef)
    functions = compiler.functions(SOURCE)
    from training_bootstrap_client import loader, registry, transmit
    functions = [(name, params, body) for name, params, body in functions if name != '__tgTransmit']
    functions.append(('__tgTransmit', ('m',), transmit(Asm)))
    functions += registry(Asm, undef, HOOKS)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('server','XMLConnection'), 'Send', '__tgHandshakeOrig', '__tgHandshakeSend'),
        (('server','XMLConnection'), 'sendNotification', '__tgNotifyOrig', '__tgBootstrapNotify'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    from avm_codegen import protected_call
    functions += [('__tgSafeSave', (), protected_call(Asm, '__tgSave', (), undef)),
                  ('__tgSafeLoad', (), protected_call(Asm, '__tgLoad', (), undef))]
    delete = Asm()
    delete.var('lol').member('core', 'objects', 'ItemFactory', 'itemStore').var('oid')
    delete.op('delete').op('pop')
    functions.append(('__tgDeleteItem', ('oid',), delete))
    bootstrap_names = frozenset(('__tgHandshakeSend', '__tgBootstrapNotify', '__tgTransmit'))
    bootstrap = [row for row in functions if row[0] in bootstrap_names]
    private = [row for row in functions if row[0] not in bootstrap_names]
    loads = loader(Asm, private)
    return dict(globals=tuple(functions + loads), bootstrap=tuple(bootstrap + loads), wraps=tuple(wraps))
