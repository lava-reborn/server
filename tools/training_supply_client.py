"""Small paged supply services, reusing the native item card and window artwork."""
SOURCE = r'''
def __tgSupplyButton(p, name, label, x, y, w, op, value):
    b = _global.__tgButton(p, name, label, x, y, w, op, value)
    b.onRelease = _global.__tgSupplyClick
    return b

def __tgSupplyBuild(p, W, H):
    p.__supply = True
    p.__right = W - 270
    _global.__tgText(p, "status", "Предметы остаются на полигоне.", 24, H - 56, W - 48, 30, False)
    _global.__tgSupplyButton(p, "shelf", "Получить", 24, 57, 130, "shelf", 0)
    _global.__tgSupplyButton(p, "returnBag", "Сдать из рюкзака", 160, 57, 170, "shelf", 1)
    _global.__tgText(p, "query", "", 185, 96, W - 470, 24, True)
    _global.__tgSupplyButton(p, "search", "Найти", W - 280, 96, 75, "search", 0)
    _global.__tgSupplyButton(p, "line", "Версия: все", 24, 96, 150, "line", 0)
    _global.__tgSupplyButton(p, "level", "Уровень: все", 24, 128, 150, "level", 0)
    _global.__tgText(p, "levelHint", "Выберите категорию и вариант предмета.", 24, 160, 150, 48, False)
    _global.__tgSupplyButton(p, "detail", "Фильтр: все", 24, 164, 150, "detail", 0)
    p.levelHint._visible = False
    _global.__tgSupplyButton(p, "all", "Все категории", 24, 212, 150, "category", "all")
    labels = []
    values = []
    if _global.__tgContext == "weapons":
        labels = ["Пистолеты", "Дробовики", "Автоматы", "Винтовки", "Пулемёты", "Пистолет-пулемёты", "Холодное оружие"]
        values = [0, 1, 2, 3, 4, 5, 6]
    if _global.__tgContext == "armoury":
        labels = ["Полные комплекты", "Части брони"]
        values = ["set", "armour"]
    if _global.__tgContext == "supplies":
        labels = ["Боеприпасы", "Подсумки"]
        values = ["ammo", "pouch"]
    if _global.__tgContext == "medical":
        p.all._y = 128
        p.all.__op = "categorymenu"
        p.all.caption.text = "Медицина ▼"
        p.all.hintTitle_str = "Категория: Медицина"
    if _global.__tgContext == "specialist":
        p.all.__op = "categorymenu"
        p.all.caption.text = "Все категории ▼"
        p.all.hintTitle_str = "Категория: Все категории"
        _global.__tgUITextFit(p.all.caption)
    if _global.__tgContext == "archive":
        labels = ["Сувениры", "Неработающие эффекты", "Старые предметы"]
        values = ["souvenir", "unsupported", "legacy"]
    i = 0
    while i < len(labels):
        _global.__tgSupplyButton(p, "cat" + String(i), labels[i], 24, 244 + i * 30, 150, "category", values[i])
        i = i + 1
    p.__categoryCount = len(labels)
    p.level._visible = _global.__tgContext != "boosts" and _global.__tgContext != "medical"
    p.all._visible = _global.__tgContext != "boosts"
    p.detail._visible = _global.__tgContext != "boosts" and _global.__tgContext != "archive"
    _global.__tgText(p, "previewTitle", "Выберите предмет", p.__right, 132, 245, 40, False)
    _global.__tgText(p, "variantTitle", "", p.__right, 177, 245, 25, False)
    _global.__tgSupplyButton(p, "variantPrev", "←", p.__right, 206, 40, "variant", 0 - 1)
    _global.__tgSupplyButton(p, "variantNext", "Улучшение: выбрать ▼", p.__right + 46, 206, 195, "variantmenu", 0)
    priceY = 382
    if H < 610:
        priceY = 355
    _global.__tgText(p, "price", "", p.__right, priceY, 245, 42, False)
    _global.__tgText(p, "profileNote", "Описание - наведением на карточку. Итог боя зависит от выбранных правил.", p.__right, 428, 245, 70, False)
    p.profileNote._visible = H >= 610
    if _global.__tgContext == "archive":
        p.profileNote.text = "Архив: эффекты могут быть не подключены, параметры - заглушки. Эти предметы не подходят для оценки боевого баланса."
    _global.__tgText(p, "amountLabel", "Количество", p.__right, H - 117, 100, 24, False)
    _global.__tgText(p, "amount", "1", p.__right + 106, H - 117, 60, 24, True)
    p.amount.restrict = "0-9"
    p.amount.maxChars = 4
    _global.__tgSupplyButton(p, "give", "Получить", p.__right, H - 88, 241, "give", 0)
    _global.__tgSupplyButton(p, "prev", "←", 185, H - 88, 40, "page", 0 - 1)
    _global.__tgSupplyButton(p, "next", "→", 230, H - 88, 40, "page", 1)
    _global.__tgText(p, "page", "", 280, H - 88, 120, 25, False)
    _global.__tgSupplyPage = 0
    _global.__tgSupplyLine = 0
    _global.__tgSupplyLevel = 0
    _global.__tgSupplyClass = 0 - 1
    _global.__tgSupplyCategory = "all"
    if _global.__tgContext == "medical":
        _global.__tgSupplyCategory = "medicine"
    _global.__tgSupplyDetail = "all"
    _global.__tgSupplyBag = False
    _global.__tgSupplyRequest()

def __tgSupplyClear(p):
    if not p:
        return
    _global.__tgMenusClose(p)
    if p.__supplyProto:
        p.__supplyProto.removeEventListener("itemUpdate", p, _global.__tgSupplyReady)
        p.__supplyProto = None
    if p.__supplyItem:
        item = p.__supplyItem
        item.removeEventListener("itemUpdate", p, _global.__tgSupplyReady)
        if p.supplyCard:
            item.removeEventListener("itemUpdate", p.supplyCard)
        proto = lol.core.objects.ItemFactory.getProtoItem(item.typeID)
        proto.removeEventListener("itemUpdate", item)
        lol.utils.StringCollector.getInstance().removeEventListener("update", item, item.stringUpdate)
        p.__supplyItem = None
    if p.supplyCard:
        icon = p.supplyCard.icon_mc
        if icon.src:
            icon.src.removeEventListener("onLoadSource", icon)
        if icon.mcl_list:
            icon.mcl_list.onLoadInit = None
        p.supplyCard.kill()
        p.supplyCard.removeMovieClip()
    p.__supplySource = None
    p.__variants = None
    _global.__tgUIEnable(p.give, False)
    if p.__supply and p.amount:
        p.amount._visible = False
        p.amountLabel._visible = False
        p.variantPrev._visible = False
        p.variantNext._visible = False

def __tgSupplyRequest():
    p = _global.__tgPanel
    if not p or not p.__supply:
        return
    p.__supplyLevels = []
    p.status.text = "Загрузка списка…"
    _global.__tgUIEnable(p.prev, False)
    _global.__tgUIEnable(p.next, False)
    _global.__tgUISupplySelection(p)
    _global.__tgSupplyClear(p)
    p.__variants = None
    p.previewTitle.text = "Выберите предмет"
    p.variantTitle.text = ""
    p.price.text = ""
    if p.supplyRows:
        p.supplyRows.removeMovieClip()
    op = "supply_list"
    if _global.__tgSupplyBag:
        op = "supply_bag"
    m = _global.__tgSend(op)
    _global.__tgCatalogueRequest = _global.__tgCatalogueRequest + 1
    m.addProp("request_id", _global.__tgCatalogueRequest)
    m.addProp("page", _global.__tgSupplyPage)
    m.addProp("level", _global.__tgSupplyLevel)
    lines = ["all", "A", "P", "G", "C"]
    m.addProp("line", "@" + lines[_global.__tgSupplyLine] + "@")
    m.addProp("wclass", _global.__tgSupplyClass)
    m.addProp("category", "@" + _global.__tgSupplyCategory + "@")
    m.addProp("detail", "@" + _global.__tgSupplyDetail + "@")
    m.addProp("query", "@" + p.query.text.split("@").join("") + "@")
    _global.__tgTransmit(m)

def __tgSupplyList(v):
    p = _global.__tgPanel
    if not p or not p.__supply or v.context != _global.__tgContext or v.request_id != _global.__tgCatalogueRequest:
        return
    if p.supplyRows:
        p.supplyRows.removeMovieClip()
    p.supplyRows = p.createEmptyMovieClip("supplyRows", p.getNextHighestDepth())
    _global.__tgSupplyPage = Number(v.page)
    if not _global.__tgSupplyBag:
        p.__supplyLevels = v.available_levels
        if v.selected_level != None:
            _global.__tgSupplyLevel = Number(v.selected_level)
            p.level.caption.text = "Уровень: все"
            if _global.__tgSupplyLevel:
                p.level.caption.text = "Ур. " + String(_global.__tgSupplyLevel)
    p.page.text = String(Number(v.page) + 1) + " / " + String(Math.max(1, Math.ceil(Number(v.total) / 10)))
    pitch = Math.min(39, (p.__h - 248) / 10)
    i = 0
    while i < len(v.ids):
        b = _global.__tgSupplyButton(p.supplyRows, "row" + String(i), v.labels[i], 185, 138 + i * pitch, p.__w - 470, "pick", v.ids[i])
        b.__row = i
        b.caption._height = pitch - 3
        b.caption._y = 1
        i = i + 1
    _global.__tgUISupplySelection(p)
    p.__supplyRows = v
    _global.__tgUIEnable(p.prev, Number(v.page) > 0)
    _global.__tgUIEnable(p.next, (Number(v.page) + 1) * 10 < Number(v.total))
    p.status.text = "Выберите предмет. Предметы остаются на полигоне."
    if _global.__tgContext == "archive":
        p.status.text = "Архивные предметы: не использовать для оценки боевого баланса."
    if v.total == 0:
        _global.__tgText(p.supplyRows, "empty", "Ничего не найдено", 185, 150, 240, 50, False)

def __tgSupplyShow(index):
    p = _global.__tgPanel
    rows = p.__variants
    if not rows or len(rows.ids) == 0:
        return
    _global.__tgSupplyClear(p)
    p.__variants = rows
    _global.__tgUIEnable(p.give, not _global.__tgSupplyPending)
    i = (index + len(rows.ids)) % len(rows.ids)
    p.__variantIndex = i
    p.__supplySource = rows.ids[i]
    p.__maximum = rows.maximum[i]
    p.previewTitle.text = rows.labels[i]
    p.variantTitle.text = rows.variants[i] + " · " + String(i + 1) + " / " + String(len(rows.ids))
    if rows.bundle:
        p.variantTitle.text = rows.variants[i]
    p.give.caption.text = "Получить"
    if _global.__tgSupplyBag:
        p.give.caption.text = "Сдать"
    elif rows.bundle:
        p.give.caption.text = "Получить комплект"
    p.amount.text = "1"
    p.amount._visible = p.__maximum > 1
    p.amountLabel._visible = p.__maximum > 1
    p.variantPrev._visible = len(rows.ids) > 1
    p.variantNext._visible = len(rows.ids) > 1
    price = _global.__tgReferencePrice({"typeID":rows.types[i]})
    currency = " афро"
    if price.gold:
        currency = " G"
    priceTitle = "Базовая цена за шт.: "
    p.variantNext.caption.text = "Улучшение: выбрать ▼"
    if rows.bundle:
        priceTitle = "Базовая цена части: "
        p.variantNext.caption.text = "Часть комплекта ▼"
    p.price.text = priceTitle + String(price.value) + currency
    proto = lol.core.objects.ItemFactory.createPrototype(rows.types[i])
    p.__supplyProto = proto
    if proto.inited:
        _global.__tgSupplyReady.apply(p, [{"target":proto}])
    else:
        proto.addEventListener("itemUpdate", p, _global.__tgSupplyReady)

def __tgSupplyReady(event):
    p = _global.__tgPanel
    if not p or p != this or not p.__supply or p.__supplyProto != event.target:
        return
    proto = event.target
    proto.removeEventListener("itemUpdate", p, _global.__tgSupplyReady)
    cls = lol.core.objects.ItemFactory.getClass(proto.rootID)
    item = new(cls, 1, proto.typeID, proto.rootID)
    _global.__tgItemName(item)
    p.__supplyItem = item
    card = p.attachMovie("itemCont", "supplyCard", p.getNextHighestDepth())
    card._x = p.__right
    card._y = 240
    card.item = item
    card.attachIcon(item)
    card.bg_mc.onPress = None
    card.bg_mc.onRelease = None
    card.reload_btn._visible = False
    card.onMouseUp = None
    if p.__h < 610:
        card._xscale = 85
        card._yscale = 85

def __tgSupplyMenu(kind):
    p = _global.__tgPanel
    if _global.__tgMenuToggle(p, "supply:" + kind):
        return
    labels = ["Все версии", "A", "P", "G", "Контрабанда"]
    values = [0, 1, 2, 3, 4]
    x = 24
    y = 125
    width = 150
    columns = 1
    if kind == "category":
        labels = ["Медицина", "Ивентовое лечение"]
        values = ["medicine", "event_medicine"]
        y = 157
        width = 210
        if _global.__tgContext == "specialist":
            labels = ["Все категории", "Контрабанда / коллекции", "Специальное / прототипы"]
            values = ["all", "special_weapon", "experimental_weapon"]
            y = 241
            width = 260
    if kind == "detail":
        labels = ["Все предметы"]
        values = ["all"]
        y = 193
        width = 210
        if _global.__tgContext == "supplies":
            labels = ["Все припасы", "Под оружие в руках", "Патроны: пистолеты", "Патроны: дробовики", "Патроны: автоматы", "Патроны: винтовки", "Патроны: пулемёты", "Патроны: ПП"]
            values = ["all", "held", "w0", "w1", "w2", "w3", "w4", "w5"]
        if _global.__tgContext == "armoury":
            labels = ["Все части", "Шлемы", "Одежда", "Бронежилеты", "Ноги", "Обувь"]
            values = ["all", "head", "camo", "body", "legs", "feet"]
        if _global.__tgContext == "medical":
            labels = ["Все средства", "Боевая медицина", "Вне боя", "Здоровье", "Выносливость"]
            values = ["all", "battle", "peace", "health", "stamina"]
        if _global.__tgContext == "weapons" or _global.__tgContext == "specialist":
            labels = ["Все улучшения", "Без улучшения", "С улучшением"]
            values = ["all", "base", "modified"]
    if kind == "level":
        labels = ["Все уровни"]
        values = [0]
        i = 0
        if p.__supplyLevels:
            while i < len(p.__supplyLevels):
                level = Number(p.__supplyLevels[i])
                labels.push("Ур. " + String(level))
                values.push(level)
                i = i + 1
        y = 157
        width = 100
        columns = 3
    if kind == "variant":
        if not p.__variants:
            return
        labels = p.__variants.variants
        values = []
        i = 0
        while i < len(labels):
            values.push(i)
            i = i + 1
        x = p.__right - 180
        y = 235
        width = 205
        columns = 2
    box = _global.__tgMenuBox(p, "supplyOptions", "supply:" + kind, x, y, columns * width + 8, Math.ceil(len(labels) / columns) * 29 + 8)
    i = 0
    while i < len(labels):
        b = _global.__tgSupplyButton(box, "option" + String(i), labels[i], box.__menuX + 4 + (i % columns) * width, box.__menuY + 4 + Math.floor(i / columns) * 29, width - 4, kind + "set", values[i])
        b.__label = labels[i]
        i = i + 1

def __tgSupplyReceive(v):
    p = _global.__tgPanel
    if v.op == "supply_list" or v.op == "supply_bag":
        _global.__tgSupplyList(v)
    if v.op == "supply_variants":
        if p and p.__supply and v.context == _global.__tgContext and v.request_id == _global.__tgCatalogueRequest:
            p.__variants = v
            _global.__tgSupplyShow(0)
    if v.op == "supply_done":
        if v.sequence == _global.__tgSupplyPending:
            _global.__tgSupplyPending = 0
            if p and p.__supply:
                p.status.text = v.message
                _global.__tgUIEnable(p.give, p.__supplySource != None)
                if _global.__tgSupplyBag:
                    _global.__tgSupplyRequest()

def __tgSupplyClick():
    p = _global.__tgPanel
    if not p or not p.__supply:
        return
    op = this.__op
    value = this.__value
    selectedLabel = this.__label
    if op == "line" or op == "level" or op == "variantmenu" or op == "detail" or op == "categorymenu":
        kind = op
        if op == "variantmenu":
            kind = "variant"
        if op == "categorymenu":
            kind = "category"
        _global.__tgSupplyMenu(kind)
        return
    _global.__tgMenusClose(p)
    if op == "variantset":
        _global.__tgSupplyShow(Number(value))
        return
    if op == "pick":
        if _global.__tgSupplyBag:
            r = p.__supplyRows
            i = this.__row
            p.__variants = {"ids":[r.ids[i]], "types":[r.types[i]], "maximum":[r.maximum[i]], "labels":[r.labels[i]], "variants":["Из рюкзака"]}
            _global.__tgSupplyShow(0)
        else:
            _global.__tgSupplyClear(p)
            _global.__tgCatalogueRequest = _global.__tgCatalogueRequest + 1
            m = _global.__tgSend("supply_variants")
            m.addProp("source", value)
            m.addProp("bundle", Number(Boolean(p.__supplyRows.bundle)))
            m.addProp("request_id", _global.__tgCatalogueRequest)
            _global.__tgTransmit(m)
        return
    if op == "variant":
        _global.__tgSupplyShow(p.__variantIndex + Number(value))
        return
    if op == "give":
        if not p.__supplySource or _global.__tgSupplyPending:
            return
        count = Math.max(1, Math.min(p.__maximum, Math.floor(Number(p.amount.text))))
        if isNaN(count):
            return
        action = "supply_get"
        if _global.__tgSupplyBag:
            action = "supply_return"
        m = _global.__tgSend(action)
        _global.__tgSupplySequence = _global.__tgSupplySequence + 1
        _global.__tgSupplyPending = _global.__tgSupplySequence
        m.addProp("sequence", _global.__tgSupplySequence)
        m.addProp("source", "@" + String(p.__supplySource) + "@")
        m.addProp("count", count)
        m.addProp("bundle", Number(Boolean(p.__variants.bundle)))
        p.status.text = "Обработка запроса…"
        _global.__tgUIEnable(p.give, False)
        _global.__tgTransmit(m)
        return
    if op == "shelf":
        _global.__tgSupplyBag = Boolean(value)
        p.give.caption.text = "Получить"
        if _global.__tgSupplyBag:
            p.give.caption.text = "Сдать"
        visible = not _global.__tgSupplyBag
        p.line._visible = visible
        p.level._visible = visible and _global.__tgContext != "boosts" and _global.__tgContext != "medical"
        p.levelHint._visible = False
        p.detail._visible = visible and _global.__tgContext != "boosts" and _global.__tgContext != "archive"
        p.query._visible = visible
        p.search._visible = visible
        p.all._visible = visible and _global.__tgContext != "boosts"
        i = 0
        while i < p.__categoryCount:
            p["cat" + String(i)]._visible = visible
            i = i + 1
    if op == "lineset":
        _global.__tgSupplyLine = Number(value)
        labels = ["все", "A", "P", "G", "контрабанда"]
        p.line.caption.text = "Версия: " + labels[_global.__tgSupplyLine]
    if op == "levelset":
        _global.__tgSupplyLevel = Number(value)
        p.level.caption.text = "Уровень: " + String(_global.__tgSupplyLevel)
        if _global.__tgSupplyLevel == 0:
            p.level.caption.text = "Уровень: все"
    if op == "detailset":
        _global.__tgSupplyDetail = value
        p.detail.caption.text = selectedLabel or "Фильтр: все"
        p.detail.hintTitle_str = p.detail.caption.text
        _global.__tgUITextFit(p.detail.caption)
        if _global.__tgContext == "armoury" and value != "all":
            _global.__tgSupplyCategory = "armour"
    if op == "categoryset":
        _global.__tgSupplyCategory = value
        _global.__tgSupplyDetail = "all"
        _global.__tgSupplyLevel = 0
        p.level.caption.text = "Уровень: все"
        p.all.caption.text = selectedLabel + " ▼"
        p.all.hintTitle_str = "Категория: " + selectedLabel
        p.detail.caption.text = "Фильтр: все"
        p.detail.hintTitle_str = "Фильтр: все"
        _global.__tgUITextFit(p.all.caption)
    if op == "category":
        _global.__tgSupplyDetail = "all"
        p.detail.caption.text = "Фильтр: все"
        p.detail.hintTitle_str = "Фильтр: все"
        _global.__tgSupplyClass = 0 - 1
        _global.__tgSupplyCategory = "all"
        if _global.__tgContext == "weapons" and value != "all":
            _global.__tgSupplyClass = Number(value)
        elif value != "all":
            _global.__tgSupplyCategory = value
    if op == "page":
        _global.__tgSupplyPage = Math.max(0, _global.__tgSupplyPage + Number(value))
    else:
        _global.__tgSupplyPage = 0
    _global.__tgSupplyRequest()
'''
