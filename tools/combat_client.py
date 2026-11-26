"""Combat presentation, nearby loot and specialization-window lifecycle fixes."""
from avm_codegen import Compiler

SOURCE = '''
def __bfLevelNeeds(obj):
    # Native Item.initialize ignores additional protocol fields. Keep these
    # on the prototype so instances inherit them through Item.getProp.
    this.equip_level = obj.equip_level
    this.equip_allowance = obj.equip_allowance
    this.buff_level = obj.buff_level
    return this.__bfLevelNeedsOrig(obj)

def __bfLevelRead(arr, titleArr):
    item = this.item
    if item and (item.rootID == 0 or item.rootID == 1 or item.rootID == 5):
        level = item.getProp("equip_level")
        if level and level > 0 and titleArr == this.skillsTitle and arr == item.getProp("need_skills"):
            # Shooting/melee are the character-level gate for equipment.
            # Retain independent medicine, industry and production needs.
            text = ""
            i = 2
            while i < len(titleArr):
                if arr[i]:
                    text = text + titleArr[i] + " " + String(arr[i]) + "\\r"
                i = i + 1
            if text != "":
                return text
            return
    return this.__bfLevelReadOrig(arr, titleArr)

def __bfAnnotationRow(title, value):
    if title == "Необходимые\\rнавыки" or title == "Необходимые навыки":
        item = this.item
        level = None
        if item and (item.rootID == 0 or item.rootID == 1 or item.rootID == 5):
            level = item.getProp("equip_level")
        elif item and item.rootID == 2:
            level = item.getProp("buff_level")
        if level and level > 0:
            text = String(level)
            if item.rootID != 2 and item.getProp("equip_allowance") == 3:
                text = text + "(-3)"
            this.__bfAnnotationRowOrig("Требуемый уровень:", text)
    # Native item cards emit fighter requirement 0 and empty effect bonuses.
    if value == 0:
        if title == "Необходимый навык бойца" or title.indexOf("Бонус") == 0:
            return
    return this.__bfAnnotationRowOrig(title, value)

def __bfEffectRows(panel, effect):
    panel.addItem("Время действия", lol.gpui.Annotation.getTextDuration(effect.work_time))
    if effect.update_delta and not isNaN(effect.update_delta):
        panel.addItem("Интервал активации", lol.gpui.Annotation.getTextDuration(effect.update_delta))
    arrays = [["Бонусы\\rк аттрибутам", effect.bonusAttribs, panel.attribsTitle], ["Бонусы\\rк навыкам", effect.bonusSkills, panel.skillsTitle], ["Бонусы\\rк специализациям", effect.bonusSpecs, panel.specTitle]]
    i = 0
    while i < len(arrays):
        row = arrays[i]
        panel.addItem(row[0], panel.readArray(row[1], row[2]))
        i = i + 1
    scalars = [["Бонус к здоровью", effect.max_hp], ["Бонус к выносливости", effect.max_sp], ["Бонус\\rк очкам действия", effect.max_od], ["Бонус\\rк критическому попаданию", effect.critical_probability], ["Бонус\\rк избеганию крита", effect.critical_evade], ["Бонус к броне", effect.armor]]
    i = 0
    while i < len(scalars):
        row = scalars[i]
        if row[1] and not isNaN(row[1]):
            panel.addItem(row[0], row[1])
        i = i + 1
    # Protocol factors are direct multipliers, shared with server effects.
    modifiers = [["к опыту с мобов", effect.mob_exp], ["к опыту с игроков", effect.player_exp], ["к луту с мобов", effect.mob_drop]]
    i = 0
    while i < len(modifiers):
        row = modifiers[i]
        if row[1] != None and not isNaN(row[1]) and row[1] != 1:
            percent = Math.round((row[1] - 1) * 100)
            if percent > 0:
                panel.addItem("Бонус\\r" + row[0], "+" + String(percent) + "%")
            elif percent < 0:
                panel.addItem("Штраф\\r" + row[0], String(percent) + "%")
        i = i + 1
    # Player-drop protection has separate semantics; keep its native formula.
    if effect.player_drop != None and not isNaN(effect.player_drop) and effect.player_drop != 1:
        panel.addItem("Защита вашего дропа", String(Math.round((1 - effect.player_drop) * 100)) + "%")

def __bfEffectAnnotation(effect):
    if this._fullAnnotation:
        rows = []
        this.addDesc(rows)
        i = 0
        while i < len(rows):
            this.addItem(rows[i][0], rows[i][1])
            i = i + 1
    _global.__bfEffectRows(this, effect)

def __bfEffectsInfo(effects, effects_prob, full, mine):
    # Retain native title/icon/layout lifecycle for the list of item effects.
    this._fullAnnotation = full
    if mine:
        this.back.my_mc._alpha = 100
        this.myFlag = True
    if full:
        lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CTRL, this, this.showFullAnnotation)
    this.cont_mc.removeMovieClip()
    this.cont_mc = this.createEmptyMovieClip("cont_mc", this.getNextHighestDepth())
    this.cont_mc._x = 13
    style = new(TextFormat)
    style.bold = True
    this.name_txt.htmlText = "ЭФФЕКТЫ"
    this.name_txt.setTextFormat(style)
    this.arrItem = []
    this.arrLine = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if effect:
            title = this.cont_mc.attachMovie("effect_title", "effect_title", this.cont_mc.getNextHighestDepth())
            line = this.cont_mc.attachMovie("annotation_line", "annotation_line", this.cont_mc.getNextHighestDepth())
            title.effect_name.autoSize = True
            title.effect_name.html = True
            title.effect_name.htmlText = effect.name
            title.effect_prob.autoSize = True
            title.effect_prob.html = True
            title.effect_prob.htmlText = "Вероятность срабатывания: " + String(effects_prob[i])
            title.effect_prob._y = title.effect_name._y + title.effect_name._height + 1
            icon = lol.services.SSEmulator.getEffectIcon(effect.res_icon)
            title.effect_icon = lol.display.DisplaySprite.create(title, String(i) + "_effect_icon", 0)
            title.effect_icon.autoSize = False
            title.effect_icon.display(String(i) + "_effect_icon", icon)
            this.arrItem.push(title)
            this.arrLine.push(line)
            _global.__bfEffectRows(this, effect)
        i = i + 1
    this.doLater("align")

def __bfNPCInfo(obj):
    # These two native flag types belong only to restored clan bases.
    this.__bfBaseFlag = obj.param.res == 4427 or obj.param.res == 4428
    return this.__bfNPCInfoOrig(obj)

def __bfFlagContact(obj):
    result = this.__bfFlagContactOrig(obj)
    master = lol.core.Master.getInstance()
    npc = master.getPlayer(obj.id)
    # Native Gamer.proposeContact stops at a Trader with no trade/repair
    # service. The base flag deliberately has only its treasury quest.
    if not npc or not npc.__bfBaseFlag or not npc.playerInfo.ally:
        return result
    if npc.canTrade or npc.canRepair or npc.canTrophy or not npc.hasAvailableQuests():
        return result
    location = master.currentLocation
    cell = location.getCellFromNumber(this.walker.numPos)
    if cell == obj.targetCell or location.isSiblings(cell, obj.targetCell):
        lol.core.player.NPCService.openService(npc.id)
    return result

def __bfBaseCaption(panel):
    if not panel.player.__bfBaseFlag:
        return
    member = panel.player.clanMemberInfo
    title = "Незанятая клановая база"
    if member.clanReg and member.clanInfo.clanName:
        title = "Клановая база\\r" + member.clanInfo.clanName
    # A clan name is plain text, never markup or a replacement ClanInfo name.
    panel.info_txt.multiline = True
    panel.info_txt.text = title
    panel.infoShadow_txt.multiline = True
    panel.infoShadow_txt.text = title
    anchor = panel.sBar._y
    if panel.hBar._visible:
        anchor = panel.hBar._y - 5
    panel.info_txt._y = Math.round(anchor - panel.info_txt.textHeight)
    panel.infoShadow_txt._y = panel.info_txt._y + 1

def __bfInfoUpdate(obj):
    this.__bfInfoUpdateOrig(obj)
    _global.__bfBaseCaption(this)

def __bfClanCaption():
    this.__bfClanCaptionOrig()
    _global.__bfBaseCaption(this)

def __bfSyncAP(obj):
    if obj.param.amax != None:
        ceiling = Number(obj.param.amax)
        if not isNaN(ceiling) and ceiling > 0:
            # setAP/warState refill AP and replace the combat regeneration interval.
            # Only the maximum changes; the native setter accepts the paid balance.
            this._maxAP = ceiling
    return this.__bfSyncAPOrig(obj)

def __bfCritCard():
    this.__bfCritCardOrig()
    if _global.__tgActive and _global.__tgCombatStats:
        return
    gamer = lol.core.Master.getInstance().gamer
    weapon = gamer.equipment.primaryItem
    if not weapon or weapon.rootID != lol.core.objects.Item.FIRE_ARM:
        return
    value = parseFloat(this.critDodge_txt.text)
    if isNaN(value):
        return
    correction = 0
    i = 0
    while i < gamer.effects.getFXArrayLength():
        effect = gamer.effects.getEffect(i)
        if effect and effect.critical_evade:
            # Native showKrit adds critical_probability in the evade branch.
            correction = correction + effect.critical_evade - effect.critical_probability
        i = i + 1
    if correction:
        this.critDodge_txt.text = String(value + correction) + " %"

def __bfArmorCard():
    this.__bfArmorCardOrig()
    if _global.__tgActive and _global.__tgCombatStats:
        return
    equipment = lol.core.Master.getInstance().gamer.equipment
    slots = [equipment.head, equipment.armor, equipment.camouflage, equipment.belt, equipment.legs, equipment.boots]
    correction = 0
    i = 0
    while i < len(slots):
        item = slots[i].item
        if item:
            remaining = item.getProp("__break")
            if remaining != None and remaining <= 0:
                correction = correction + item.getProp("armor_class")
        i = i + 1
    if correction:
        this.ArmorClassValue.value.text = Number(this.ArmorClassValue.value.text) - correction

def __bfRemotePrimary(obj):
    # Native ss_obj_move constructs a type-0 firearm for an empty hand.
    # Empty snapshots must use PersEquip's existing bare-fist fallback.
    if not this.isGamer and obj.param.to == 512 and obj.param.obj == "0":
        this.primaryItem = None
        return
    return this.__bfRemotePrimaryOrig(obj)

def __bfFirearmInit(obj):
    # Item.initialize can synchronously publish cached names via itemUpdate.
    # Char.changeWeapon needs the stance before that first notification;
    # mobs do not request DI that could otherwise trigger a later refresh.
    this.weapon_type = obj.weapon_type
    return this.__bfFirearmInitOrig(obj)

def __bfTrainingClose(obj):
    if obj:
        if obj.target:
            obj.target.removeEventListener("close", this)
    else:
        cluster = new(lol.data.BigUINTCluster, 0)
        number = new(lol.data.BigUINT, cluster)
        message = new(lol.server.mess.CSM_SSUpdate, lol.core.player.Training.UPD_CLOSE, number)
        this.XMC.Send(message)
    this.dispatchEvent({"type":"close"})
    avatar = lol.core.SceneShifter.linkGame.visavisAvatar
    if avatar:
        avatar.removeMovieClip()
    this.kill()

def __bfLootOpen(pos):
    this.walker.removeEventListener("finishMove", this)
    loc = lol.core.Master.getInstance().currentLocation
    here = loc.getCellFromNumber(this.walker.numPos)
    bag = loc.getCellFromNumber(pos)
    if here and bag and loc.locationGrid.getHexDistance(here, bag) <= Number("1.01"):
        this.loot = new(lol.core.player.Loot)
        this.loot.createSession(pos)

def __bfLootReachable(loc, here, cell):
    width = 30
    height = 40
    if lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.PATH_FINDING):
        width = loc.locInfo.width
        height = loc.locInfo.height
    x = Math.max(0, Math.floor((cell.gx + here.gx - width) / 2))
    y = Math.max(0, Math.floor((cell.gy + here.gy - height) / 2))
    if Math.abs(cell.gx - here.gx) > width or Math.abs(cell.gy - here.gy) > height:
        return False
    path = loc.locationGrid.searchWay(here.gx - x, here.gy - y, cell.gx - x, cell.gy - y, x, y, width, height)
    size = len(path)
    return size > 0 and path[size - 1][0] == cell.gx and path[size - 1][1] == cell.gy

def __bfLootGo(pos):
    if _global.__bfDefer(this, "gotoLoot", [pos]):
        return
    loc = lol.core.Master.getInstance().currentLocation
    here = loc.getCellFromNumber(this.walker.numPos)
    bag = loc.getCellFromNumber(pos)
    if not here or not bag:
        return
    if loc.locationGrid.getHexDistance(here, bag) <= Number("1.01"):
        this.createLoot(pos)
        return
    choices = loc.locationGrid.getSiblings(bag).concat([])
    best = None
    while len(choices) > 0 and not best:
        distance = 1000000
        index = 0
        i = 0
        while i < len(choices):
            d = loc.locationGrid.getHexDistance(here, choices[i])
            if d < distance:
                index = i
                distance = d
            i = i + 1
        cell = choices[index]
        choices.splice(index, 1)
        if not cell.busy and not cell.alwaysBusy and not cell.unreachable:
            if _global.__bfLootReachable(loc, here, cell):
                best = cell
    if best:
        this.walker.removeEventListener("finishMove", this)
        this.stuff_param = pos
        this.stuff_func = this.createLoot
        this.walker.addEventListener("finishMove", this)
        loc.movePlayer(best)

def __bfHealth(percent, value):
    p = Number(percent)
    if isNaN(p):
        p = 0
    this.__bfHealthOrig(Math.max(0, Math.min(100, p)), value)

def __bfStamina(percent, value):
    p = Number(percent)
    if isNaN(p):
        p = 0
    this.__bfStaminaOrig(Math.max(0, Math.min(100, p)), value)

def __bfFaceAim(figure, aim):
    if not figure or not aim or aim.ang == None:
        return
    direction = Number(aim.ang)
    if isNaN(direction) or direction < 1 or direction > 8 or Math.floor(direction) != direction:
        return
    # Native direction schedules gradual rotation on later frames. A queued
    # confirmed volley may fire immediately: face it before FIRE_IN instead.
    if figure.deleteEnterFrame and figure.rotate:
        figure.deleteEnterFrame(figure.rotate)
    figure.__direction = direction

def __bfVisualStart(scene, figure, bundle):
    bundle.active = True
    figure.__fireCount = 0
    figure.__bfPlayback = None
    if bundle.timing:
        figure.__bfPlayback = {"start":getTimer(), "duration":bundle.timing.duration, "frames":bundle.timing.frames, "painted":0}
    _global.__bfFaceAim(figure, bundle.aim)
    scene.__bfAimOrig(bundle.aim)
    i = 0
    while i < len(bundle.events):
        scene.__bfFireOrig(bundle.events[i])
        i = i + 1
    bundle.events = []

def __bfAimSound(scene, aim):
    # Snapshot the aiming weapon intentionally: a fallback for that confirmed
    # volley must not take the sound of a newly switched weapon.
    if scene.master:
        player = scene.master.getPlayer(aim)
        if player and player.equipment:
            item = player.equipment.primaryItem
            if item and item.getProp:
                weapon = item.getProp("weapon_type")
                if weapon == lol.core.objects.FireArm.PISTOL:
                    return lol.sound.SoundEvent.PISTOL_FIRE
                if weapon == lol.core.objects.FireArm.SHOTGUN:
                    return lol.sound.SoundEvent.SHOTGUN_FIRE
                if weapon == lol.core.objects.FireArm.ASSAULT:
                    return lol.sound.SoundEvent.ASSAULT_FIRE
                if weapon == lol.core.objects.FireArm.RIFLE:
                    return lol.sound.SoundEvent.RIFLE_FIRE
                if weapon == lol.core.objects.FireArm.MACHINEGUN:
                    return lol.sound.SoundEvent.MACHINEGUN_FIRE
                if weapon == lol.core.objects.FireArm.SMG:
                    return lol.sound.SoundEvent.SMG_FIRE
    return None

def __bfPresentInterrupted(scene, figure, event):
    # A confirmed volley must not become completely invisible when the next
    # authoritative action interrupts its first visual frame. Show at most
    # one captured trace per unplayed volley, not its entire remaining burst.
    bundle = event.__bfBundle
    if not bundle or bundle.shown or event.__bfPresented or not event.shot or not event.access:
        return
    if figure.animationEnabled == False or figure.isActive == False or not event.hits or len(event.hits) == 0:
        return
    bundle.shown = True
    scene.applyFireAck(event)
    event.__bfPresented = True
    if lol.sound and lol.sound.SoundManager:
        sound = bundle.sound or lol.sound.SoundEvent.FIREARM_FIRE
        lol.sound.SoundManager.getInstance().playEventSound(sound)

def __bfVisualFlush(scene, figure, draw):
    bursts = figure.__bfBursts or []
    bullets = figure.burstArr or []
    figure.__bfBursts = []
    figure.burstArr = []
    figure.__bfIncoming = None
    figure.__bfAdvanceReady = False
    figure.__bfPlayback = None
    figure.removeEventListener("finalFrame", scene, scene.shotgunFireAck)
    figure.removeEventListener("finalFrame", scene, scene.busrtFireAck)
    i = 0
    while i < len(bullets):
        if draw != False:
            scene.applyFireAck(bullets[i])
        else:
            _global.__bfPresentInterrupted(scene, figure, bullets[i])
        i = i + 1
    i = 0
    while i < len(bursts):
        bundle = bursts[i]
        j = 0
        while j < len(bundle.events):
            event = bundle.events[j]
            if event.access:
                scene.addFireAckReport(event)
                if draw != False:
                    scene.applyFireAck(event)
                else:
                    _global.__bfPresentInterrupted(scene, figure, event)
            j = j + 1
        i = i + 1
    scene.showFireAckReport()
    figure.removeEventListener("finalFrame", scene, _global.__bfVisualFinal)

def __bfVisualFinal(obj):
    figure = obj.target
    if not figure.__bfBursts or len(figure.__bfBursts) == 0:
        return
    if obj.data == "die" or obj.data == "run":
        _global.__bfVisualFlush(this, figure, False)
        return
    current = figure.__bfBursts[0]
    if current.got < current.expected:
        return
    if obj.data != "fire_out" and obj.data != "stand":
        return
    # This listener can run before the native burst cleanup on the same
    # finalFrame. Drop unplayed cosmetic traces without another visual cycle.
    bullets = figure.burstArr
    figure.burstArr = []
    i = 0
    while i < len(bullets):
        _global.__bfPresentInterrupted(this, figure, bullets[i])
        i = i + 1
    if len(bullets) > 0:
        this.showFireAckReport()
    figure.__bfBursts.shift()
    figure.__bfPlayback = None
    if len(figure.__bfBursts) > 0:
        figure.__bfAdvanceReady = True
    else:
        figure.__bfIncoming = None
        figure.removeEventListener("finalFrame", this, _global.__bfVisualFinal)

def __bfAim(obj):
    figure = this.getWalker(obj.aim)
    if not figure:
        this.__bfAimOrig(obj)
        return
    figure.__bfScene = this
    if not obj.aim:
        _global.__bfOwnerFigure = figure
    figure.__bfSkipVisual = figure.animationEnabled == False or figure.isActive == False
    if figure.__bfSkipVisual:
        if figure.__bfBursts and len(figure.__bfBursts) > 0:
            _global.__bfVisualFlush(this, figure)
        _global.__bfFaceAim(figure, obj)
        this.__bfAimOrig(obj)
        return
    if not figure.__bfBursts:
        figure.__bfBursts = []
    if len(figure.__bfBursts) > 0 and figure.__bfBursts[0].got == 0:
        figure.__bfBursts.shift()
    if len(figure.__bfBursts) >= 8:
        _global.__bfVisualFlush(this, figure, False)
    bundle = {"aim":obj, "expected":Math.max(1, obj.num_shots), "got":0, "events":[], "active":False, "shown":False, "sound":_global.__bfAimSound(this, obj.aim)}
    figure.__bfIncoming = bundle
    figure.__bfBursts.push(bundle)
    figure.addEventListener("finalFrame", this, _global.__bfVisualFinal)
    if len(figure.__bfBursts) == 1:
        _global.__bfVisualStart(this, figure, bundle)

def __bfFire(event):
    figure = this.getWalker(event.gunnerID)
    if figure and event.shot and event.access:
        # Delayed cosmetic playback must not follow figures to new cells.
        event.__bfOrigin = {"x":figure._x, "y":figure._y - 50}
        i = 0
        while event.hits and i < len(event.hits):
            hit = event.hits[i]
            if hit.type == "target":
                target = this.getWalker(hit.targetID)
                if target:
                    hit.__bfPoint = {"x":target._x, "y":target._y - 50}
            i = i + 1
    if figure and figure.__bfSkipVisual:
        if event.access:
            this.addFireAckReport(event)
            this.applyFireAck(event)
            this.showFireAckReport()
        return
    if not figure or not figure.__bfIncoming:
        this.__bfFireOrig(event)
        return
    bundle = figure.__bfIncoming
    bundle.melee = not event.shot
    event.__bfBundle = bundle
    timing = _global.__bfShotTiming
    if timing and timing.animation_frames > 0 and timing.recovery_ms > 0:
        bundle.timing = {"duration":timing.recovery_ms, "frames":timing.animation_frames}
        if bundle.active:
            figure.__bfPlayback = {"start":getTimer(), "duration":timing.recovery_ms, "frames":timing.animation_frames, "painted":0}
    bundle.got = bundle.got + 1
    if bundle.active:
        this.__bfFireOrig(event)
    else:
        bundle.events.push(event)

def __bfApplyFire(event):
    if event.shot:
        if event.__bfPresented:
            return
        event.__bfPresented = True
        if event.__bfBundle:
            event.__bfBundle.shown = True
    if not event.__bfOrigin:
        return this.__bfApplyFireOrig(event)
    point = None
    while len(event.hits) > 0:
        hit = event.hits.shift()
        if hit.type == "point":
            point = this.hitPoint(hit)
        elif hit.type == "wall":
            point = this.hitWall(hit)
        elif hit.type == "target":
            point = this.hitTarget(hit)
    if event.shot and point:
        this.traceShot(event.gunnerID, point, event.__bfOrigin)

def __bfTraceShot(gunnerID, point, origin):
    if not origin:
        return this.__bfTraceShotOrig(gunnerID, point)
    if not point:
        return
    trace = new(lol.fx.ShotTrace)
    trace.traceShot(this.helpers_mc, origin, {"x":point.x + Math.random() * 20 - 10, "y":point.y + Math.random() * 20 - 10})

def __bfBurstFinal(obj):
    if obj.data != "fire" and obj.target.burstArr:
        _global.__bfVisualFlush(this, obj.target, False)
    this.__bfBurstFinalOrig(obj)

def __bfShotgunFinal(obj):
    if obj.data != "fire" and obj.target.burstArr:
        _global.__bfVisualFlush(this, obj.target, False)
    this.__bfShotgunFinalOrig(obj)

def __bfDead(obj):
    if not obj.dead:
        _global.__bfClearInput()
    figure = this.getWalker(obj.dead)
    if figure and figure.__bfBursts:
        _global.__bfVisualFlush(this, figure, False)
    this.__bfDeadOrig(obj)
'''


def patches(Asm, undef, *, training=False):
    source = SOURCE
    if not training:
        source = source.replace('    if _global.__tgActive and _global.__tgCombatStats:\n        return\n', '')
    functions = Compiler(Asm, undef).functions(source)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('core','objects','Item'), 'parseNeedBonus', '__bfLevelNeedsOrig', '__bfLevelNeeds'),
        (('gpui','Annotation'), 'readArray', '__bfLevelReadOrig', '__bfLevelRead'),
        (('gpui','Annotation'), 'addItem', '__bfAnnotationRowOrig', '__bfAnnotationRow'),
        (('gpui','Annotation'), 'effectAnnotation', '__bfEffectAnnotationOrig', '__bfEffectAnnotation'),
        (('gpui','Annotation'), 'showEffectsInfo', '__bfEffectsInfoOrig', '__bfEffectsInfo'),
        (('core','player','NPC'), 'userInfo', '__bfNPCInfoOrig', '__bfNPCInfo'),
        (('core','player','Gamer'), 'proposeContact', '__bfFlagContactOrig', '__bfFlagContact'),
        (('core','location','CharInfo'), 'userInfoUpdate', '__bfInfoUpdateOrig', '__bfInfoUpdate'),
        (('core','location','CharInfo'), 'clanNameUpdate', '__bfClanCaptionOrig', '__bfClanCaption'),
        (('core','player','APManager'), 'syncAPtoServer', '__bfSyncAPOrig', '__bfSyncAP'),
        (('gpui','CharInterface'), 'showKrit', '__bfCritCardOrig', '__bfCritCard'),
        (('gpui','CharInterface'), 'showArmorLevel', '__bfArmorCardOrig', '__bfArmorCard'),
        (('core','player','PersEquip'), 'ss_obj_move', '__bfRemotePrimaryOrig', '__bfRemotePrimary'),
        (('core','objects','FireArm'), 'initialize', '__bfFirearmInitOrig', '__bfFirearmInit'),
        (('core','player','Training'), 'close', '__bfTrainingCloseOrig', '__bfTrainingClose'),
        (('core','player','Gamer'), 'gotoLoot', '__bfLootGoOrig', '__bfLootGo'),
        (('core','player','Gamer'), 'createLoot', '__bfLootOpenOrig', '__bfLootOpen'),
        (('core','location','CharInfo'), 'showHealth', '__bfHealthOrig', '__bfHealth'),
        (('core','location','CharInfo'), 'showStamina', '__bfStaminaOrig', '__bfStamina'),
        (('core','location','DisplayLocScene'), 'aim', '__bfAimOrig', '__bfAim'),
        (('core','location','DisplayLocScene'), 'fireAck', '__bfFireOrig', '__bfFire'),
        (('core','location','DisplayLocScene'), 'applyFireAck', '__bfApplyFireOrig', '__bfApplyFire'),
        (('core','location','DisplayLocScene'), 'traceShot', '__bfTraceShotOrig', '__bfTraceShot'),
        (('core','location','DisplayLocScene'), 'busrtFireAck', '__bfBurstFinalOrig', '__bfBurstFinal'),
        (('core','location','DisplayLocScene'), 'shotgunFireAck', '__bfShotgunFinalOrig', '__bfShotgunFinal'),
        (('core','location','DisplayLocScene'), 'dead', '__bfDeadOrig', '__bfDead'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    from action_recovery_client import patches as recovery_patches
    recovery = recovery_patches(Asm, undef)
    from medicine_cooldown_client import patches as medicine_patches
    medicine = medicine_patches(Asm, undef)
    from respawn_client import patches as respawn_patches
    respawn = respawn_patches(Asm, undef)
    from weapon_range_client import patches as range_patches
    ranges = range_patches(Asm, undef)
    from right_click_client import patches as right_click_patches
    right_click = right_click_patches(Asm, undef)
    from chat_bubbles_client import patches as bubble_patches
    bubbles = bubble_patches(Asm, undef)
    return dict(globals=functions + recovery['globals'] + medicine['globals'] + respawn['globals'] + ranges['globals'],
                wraps=tuple(wraps) + recovery['wraps'] + medicine['wraps'] + respawn['wraps'] + ranges['wraps'] + right_click['wraps'] + bubbles['wraps'])
