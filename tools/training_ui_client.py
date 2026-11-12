"""Private styling for new range panels only; no prototype or asset mutations."""
SOURCE = r'''

def __tgMenusClose(p):
    names = ["profiles", "kitMenu", "filtermenu", "supplyOptions", "spawns", "locations", "choices"]
    i = 0
    while i < len(names):
        box = p[names[i]]
        if box:
            box._visible = False
            box.removeMovieClip()
            p[names[i]] = None
        i = i + 1
    p.__menuKey = None

def __tgMenuToggle(p, key):
    same = p.__menuKey == key
    _global.__tgMenusClose(p)
    return same

def __tgMenuAnchor(p, key):
    names = {"profiles":"profileSelect", "kit:level":"kitLevel", "kit:line":"kitLine", "kit:class":"kitClass", "filter:level":"levelfilter", "filter:line":"linefilter", "filter:upgrade":"upgradefilter", "filter:category":"category", "filter:class":"class", "supply:line":"line", "supply:level":"level", "supply:detail":"detail", "supply:variant":"variantNext", "supply:category":"all", "spawns":"spawn", "locations":"location"}
    return p[names[key]]

def __tgMenuBox(p, name, key, x, y, w, h):
    box = p.createEmptyMovieClip(name, p.getNextHighestDepth())
    # A previous assignment of undefined shadows Flash's automatic child name.
    # Always bind the newly created clip explicitly, including on re-opening.
    p[name] = box
    box.__tgStyled = True
    p.__menuKey = key
    x = Math.max(16, Math.min(x, p.__w - w - 16))
    y = Math.max(88, Math.min(y, p.__h - h - 80))
    box.__menuX = x
    box.__menuY = y
    box.__menuWidth = w
    box.__menuHeight = h
    background = _global.__tgUIRect(box, "menuBackground", x, y, w, h, 8749686, 100)
    background.onRelease = _global.__tgMenuNoop
    background.useHandCursor = False
    _global.__tgUIWell(box, "menuBorder", x, y, w, h)
    anchor = _global.__tgMenuAnchor(p, key)
    if anchor:
        anchor.swapDepths(p.getNextHighestDepth())
    return box

def __tgMenuMouseDown():
    p = this
    if p != _global.__tgPanel or not p.__menuKey or _global.__tgResetDialog:
        return
    anchor = _global.__tgMenuAnchor(p, p.__menuKey)
    if _global.__tgMenuAnchorHit(anchor):
        return
    names = ["profiles", "kitMenu", "filtermenu", "supplyOptions", "spawns", "locations", "choices"]
    i = 0
    while i < len(names):
        box = p[names[i]]
        if box and box._xmouse >= box.__menuX and box._xmouse <= box.__menuX + box.__menuWidth and box._ymouse >= box.__menuY and box._ymouse <= box.__menuY + box.__menuHeight:
            return
        i = i + 1
    # The anchor's release toggles/replaces its menu itself. Closing it here
    # would make a second click immediately reopen the same list.
    anchors = ["all", "profileSelect", "kitLevel", "kitLine", "kitClass", "levelfilter", "linefilter", "upgradefilter", "category", "class", "line", "level", "detail", "variantNext", "location", "spawn"]
    i = 0
    while i < len(anchors):
        b = p[anchors[i]]
        if _global.__tgMenuAnchorHit(b):
            return
        i = i + 1
    _global.__tgMenusClose(p)

def __tgMenuAnchorHit(b):
    # Use the button's own mouse coordinates: parent bounds can change when
    # a native window is moved/scaled or the dropdown raises its anchor.
    if not b or not b._visible or b._xmouse == None or b._ymouse == None:
        return False
    return b._xmouse >= 0 and b._xmouse <= b.__width and b._ymouse >= 0 and b._ymouse <= b.__height

def __tgMenuNoop():
    return

def __tgEscape():
    p = _global.__tgPanel
    if not p:
        return False
    if _global.__tgResetDialog or _global.__tgResetPending:
        _global.__tgResetClose()
        return True
    if lol.core.SceneShifter._ref.UIPanels.query.instance:
        return False
    if p.__menuKey:
        _global.__tgMenusClose(p)
    else:
        _global.__tgClose()
    return True

def __tgKeysDown():
    if Key.getCode() == 27:
        if this.__tgEscapeHeld:
            return
        if _global.__tgEscape():
            this.__tgEscapeHeld = True
            return
    return this.__tgKeysDownOrig()

def __tgKeysUp():
    if Key.getCode() == 27 and this.__tgEscapeHeld:
        this.__tgEscapeHeld = False
        return
    return this.__tgKeysUpOrig()

def __tgUITextFit(f):
    # Fit once when content changes, never in an onEnterFrame loop.
    fmt = f.getTextFormat()
    while fmt.size > 13 and (Number(f.textHeight or 0) > f._height - 2 or (not f.wordWrap and Number(f.textWidth or 0) > f._width - 4)):
        fmt.size = fmt.size - 1
        f.setTextFormat(fmt)
        f.setNewTextFormat(fmt)

def __tgUIOwned(p):
    depth = 0
    while p and depth < 6:
        if p.__tgStyled:
            return True
        p = p._parent
        depth = depth + 1
    return False

def __tgUIRect(p, name, x, y, w, h, color, alpha):
    c = p.createEmptyMovieClip(name, p.getNextHighestDepth())
    c._x = Math.round(x)
    c._y = Math.round(y)
    c.beginFill(color, alpha)
    c.moveTo(0, 0)
    c.lineTo(w, 0)
    c.lineTo(w, h)
    c.lineTo(0, h)
    c.lineTo(0, 0)
    c.endFill()
    return c

def __tgUIWell(p, name, x, y, w, h):
    c = _global.__tgUIRect(p, name, x, y, w, h, 8749686, 16)
    c.lineStyle(1, 5592137, 45)
    c.moveTo(0, h)
    c.lineTo(0, 0)
    c.lineTo(w, 0)
    c.lineStyle(1, 11183764, 35)
    c.moveTo(w, 0)
    c.lineTo(w, h)
    c.lineTo(0, h)
    return c

def __tgUIFrame(p, W, H):
    p.__tgStyled = True
    art = _global.__onlineArt(p)
    _global.__tgTile(p, "inside", art["in"], 8, 8, W - 16, H - 16)
    _global.__tgUIRect(p, "tone", 14, 14, W - 28, H - 28, 5592136, 10)
    _global.__tgTile(p, "top", art.t, 22, 0, W - 44, 22)
    _global.__tgTile(p, "bottom", art.b, 22, H - 22, W - 44, 22)
    _global.__tgTile(p, "left", art.l, 0, 22, 22, H - 44)
    _global.__tgTile(p, "right", art.r, W - 22, 22, 22, H - 44)
    _global.__tgTile(p, "tl", art.tl, 0, 0, 22, 22)
    _global.__tgTile(p, "tr", art.tr, W - 22, 0, 22, 22)
    _global.__tgTile(p, "bl", art.bl, 0, H - 22, 22, 22)
    _global.__tgTile(p, "br", art.br, W - 22, H - 22, 22, 22)
    if _global.__tgSupply:
        # Open columns: no bottom border may run through the action footer.
        _global.__tgUIRect(p, "filterDivider", 178, 88, 1, H - 190, 5592137, 30)
        _global.__tgUIRect(p, "previewDivider", W - 277, 124, 1, H - 254, 5592137, 30)
    elif _global.__tgTab == "mob":
        _global.__tgUIRect(p, "categoryDivider", 194, 95, 1, H - 226, 5592137, 30)
    return p

def __tgUISurface(p, name, x, y, w, h):
    art = _global.__onlineArt(p)
    c = p.createEmptyMovieClip(name, p.getNextHighestDepth())
    c.__tgStyled = True
    c._x = Math.round(x)
    c._y = Math.round(y)
    c.__width = w
    c.__height = h
    if h == 25:
        face = c.createEmptyMovieClip("face", c.getNextHighestDepth())
        matrix = new(flash.geom.Matrix)
        matrix.createGradientBox(w - 4, h - 4, 157 / 100, 2, 2)
        face.beginGradientFill("linear", [7960939, 7039838, 6053200], [100, 100, 100], [0, 115, 255], matrix)
        face.moveTo(2, 2)
        face.lineTo(w - 2, 2)
        face.lineTo(w - 2, h - 2)
        face.lineTo(2, h - 2)
        face.lineTo(2, 2)
        face.endFill()
        face.lineStyle(1, 5131843, 70)
        face.moveTo(2, h - 2)
        face.lineTo(2, 2)
        face.lineTo(w - 2, 2)
        face.lineTo(w - 2, h - 2)
        face.lineTo(2, h - 2)
    else:
        _global.__tgTile(c, "texture", art["in"], 0, 0, w, h)
        _global.__tgUIRect(c, "shade", 0, 0, w, h, 5921360, 35)
    c.lineStyle(1, 11710106, 45)
    c.moveTo(1, h - 1)
    c.lineTo(1, 1)
    c.lineTo(w - 1, 1)
    c.lineStyle(1, 4802879, 60)
    c.lineTo(w - 1, h - 1)
    c.lineTo(1, h - 1)
    shine = _global.__tgUIRect(c, "shine", 2, 2, w - 4, h - 4, 11052667, 10)
    shine._visible = False
    mark = _global.__tgUIRect(c, "selectedMark", 2, h - 3, w - 4, 2, 11907981, 90)
    mark._visible = False
    return c

def __tgUIEnable(b, enabled):
    if not b:
        return
    b.enabled = enabled
    b._alpha = 100
    if not enabled:
        b._alpha = 45

def __tgUISelect(b, selected):
    if not b or not b.__tgStyled:
        return
    b.__selected = selected
    b.shine._visible = selected
    b.selectedMark._visible = selected
    b.caption.textColor = 14999243
    if selected:
        b.caption.textColor = 15657956

def __tgUICaption(b, op):
    if not b.__tgStyled:
        return
    fmt = b.caption.getTextFormat()
    fmt.align = "center"
    if op == "pick" or op == "category" or op == "mobgroup":
        fmt.align = "left"
    b.caption.multiline = False
    b.caption.wordWrap = False
    b.caption.setTextFormat(fmt)
    b.caption.setNewTextFormat(fmt)
    _global.__tgUITextFit(b.caption)

def __tgUISupplySelection(p):
    _global.__tgUISelect(p.shelf, not _global.__tgSupplyBag)
    _global.__tgUISelect(p.returnBag, _global.__tgSupplyBag)
    _global.__tgUISelect(p.all, _global.__tgSupplyCategory == "all" and _global.__tgSupplyClass < 0)
    i = 0
    while i < p.__categoryCount:
        button = p["cat" + String(i)]
        active = button.__value == _global.__tgSupplyCategory
        if _global.__tgContext == "weapons":
            active = button.__value == _global.__tgSupplyClass
        _global.__tgUISelect(button, active)
        i = i + 1


def __tgGearBuild(p, W, H):
    _global.__tgButton(p, "gearBack", "← Выбор снаряжения", 28, 100, 235, "enemylook", "")
    _global.__tgText(p, "gearNotice", "Выбранный пресет. Изменения вступят в силу после «Применить противника».", 275, 100, W - 303, 40, False)
    slots = [256, 512, 258, 257, 513, 259, 260, 261]
    titles = ["Шлем", "Основное оружие", "Бронежилет", "Одежда", "Второе оружие", "Подсумок", "Ноги", "Обувь"]
    bySlot = {}
    pairs = _global.__tgEnemy.gear.split(",")
    i = 0
    while i < len(pairs):
        fields = pairs[i].split(":")
        if len(fields) == 2:
            source = Number(fields[0])
            slot = _global.__tgSlots[source]
            if slot:
                bySlot[slot] = source
        i = i + 1
    p.__gearViews = []
    width = (W - 72) / 3
    pitch = (H - 280) / 3
    i = 0
    while i < len(slots):
        holder = p.createEmptyMovieClip("gearSlot" + String(i), p.getNextHighestDepth())
        holder.__panel = p
        holder._x = Math.round(28 + (i % 3) * (width + 8))
        holder._y = Math.round(148 + Math.floor(i / 3) * pitch)
        holder.__width = width
        holder.__cardHeight = pitch - 26
        _global.__tgText(holder, "slotTitle", titles[i], 0, 0, width, 21, False)
        source = bySlot[slots[i]]
        t = _global.__tgPreviewTypes[source]
        if source and t:
            holder.__source = source
            holder.__proto = lol.core.objects.ItemFactory.createPrototype(t)
            if holder.__proto.inited:
                _global.__tgGearReady.apply(holder, [{"target":holder.__proto}])
            else:
                holder.__proto.addEventListener("itemUpdate", holder, _global.__tgGearReady)
        else:
            _global.__tgUIWell(holder, "empty", 0, 24, width - 4, pitch - 31)
            _global.__tgText(holder, "missing", "Не выбрано", 8, 28, width - 20, 22, False)
        p.__gearViews.push(holder)
        i = i + 1

def __tgGearReady(event):
    holder = this
    p = _global.__tgPanel
    if not p or holder.__panel != p or holder.__proto != event.target:
        return
    proto = event.target
    proto.removeEventListener("itemUpdate", holder, _global.__tgGearReady)
    cls = lol.core.objects.ItemFactory.getClass(proto.rootID)
    item = new(cls, 1, proto.typeID, proto.rootID)
    _global.__tgItemName(item)
    holder.__item = item
    card = holder.attachMovie("itemCont", "card", holder.getNextHighestDepth())
    card._y = 24
    card.item = item
    card.attachIcon(item)
    card.bg_mc.onPress = None
    card.bg_mc.onRelease = None
    card.reload_btn._visible = False
    card.onMouseUp = None
    scale = Math.min((holder.__width - 4) / Math.max(1, card._width), holder.__cardHeight / Math.max(1, card._height)) * 100
    card._xscale = scale
    card._yscale = scale

def __tgGearClear(p):
    i = 0
    while p.__gearViews and i < len(p.__gearViews):
        holder = p.__gearViews[i]
        proto = holder.__proto
        item = holder.__item
        if proto:
            proto.removeEventListener("itemUpdate", holder, _global.__tgGearReady)
        if item:
            if holder.card:
                item.removeEventListener("itemUpdate", holder.card)
            proto.removeEventListener("itemUpdate", item)
            lol.utils.StringCollector.getInstance().removeEventListener("update", item, item.stringUpdate)
        if holder.card:
            icon = holder.card.icon_mc
            if icon.src:
                icon.src.removeEventListener("onLoadSource", icon)
            if icon.mcl_list:
                icon.mcl_list.onLoadInit = None
            holder.card.kill()
        holder.__panel = None
        holder.removeMovieClip()
        i = i + 1
    p.__gearViews = None

'''
