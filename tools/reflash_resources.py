"""Retry failed visible-player resources; never evict healthy shared bitmaps."""
from avm_codegen import Compiler

STALL_TIMEOUT_MS = 15_000
MAX_RESOURCE_RETRIES = 8

SOURCE = '''
def __rfFreshURL(url):
    if url.indexOf("http://") == 0 or url.indexOf("https://") == 0:
        sep = "?"
        if url.indexOf("?") >= 0:
            sep = "&"
        return url + sep + "reflash=" + _global.__rfNonce
    return url

def __rfSourceLoad(url):
    if not this.status:
        this.__rfStarted = getTimer()
        this.__rfProgressAt = this.__rfStarted
        this.__rfBytesLoaded = 0
        this.__rfFailed = False
        if not this.__rfRetrying:
            this.__rfBaseURL = url
    this.__rfSourceLoadOrig(url)

def __rfSourceProgress(target, loaded, total):
    if loaded > (this.__rfBytesLoaded or 0):
        this.__rfBytesLoaded = loaded
        this.__rfProgressAt = getTimer()
    this.__rfSourceProgressOrig(target, loaded, total)

def __rfSourceError(target, error, httpStatus):
    this.__rfFailed = True
    this.__rfSourceErrorOrig(target, error, httpStatus)

def __rfCanRetry():
    return (_global.__rfResources or 0) < __MAX_RESOURCE_RETRIES__

def __rfRetrySource(source):
    if not source or source.loaded or source.status == "loaded" or source.__rfAttempt == _global.__rfGeneration or not _global.__rfCanRetry():
        return
    if not source.__rfFailed:
        progress = source.__rfProgressAt
        if progress == None:
            progress = source.__rfStarted
        if source.status != "loading" or progress == None or getTimer() - progress < __STALL_TIMEOUT_MS__:
            return
    base = source.__rfBaseURL or source.sourceURL
    if not base:
        return
    source.__rfAttempt = _global.__rfGeneration
    source.__rfBaseURL = base
    if source.mcl:
        source.mcl.removeListener(source.mcl_list)
        source.mcl.unloadClip(source.cont_mc)
    source.mcl = None
    source.mcl_list = None
    source.frame_arr = []
    source.status = None
    source.loaded = False
    source.__rfFailed = False
    source.__rfRetrying = True
    source.loadSource(_global.__rfFreshURL(base))
    source.__rfRetrying = False
    _global.__rfResources = (_global.__rfResources or 0) + 1

def __rfAFFailed(obj):
    this.__rfXmlFailed = True

def __rfAFInit():
    this.__rfXmlStarted = getTimer()
    this.__rfXmlFailed = False
    this.__rfAFInitOrig()
    if this.HR:
        this.HR.addEventListener("failed", this, _global.__rfAFFailed)

def __rfAFKill():
    if this.HR:
        this.HR.removeEventListener("failed", this, _global.__rfAFFailed)
    this.__rfAFKillOrig()

def __rfRetryXML(af):
    if not af or af.infoLoaded or af.__rfXmlAttempt == _global.__rfGeneration or not _global.__rfCanRetry():
        return
    if not af.__rfXmlFailed:
        if af.__rfXmlStarted == None or getTimer() - af.__rfXmlStarted < __STALL_TIMEOUT_MS__:
            return
    af.__rfXmlAttempt = _global.__rfGeneration
    af.killHR()
    af.AnimationList = []
    af.__rfXmlStarted = getTimer()
    af.__rfXmlFailed = False
    af.HR = new(lol.server.HTTPRequest)
    af.HR.addEventListener("onXML", af)
    af.HR.addEventListener("failed", af, _global.__rfAFFailed)
    af.HR.Send("", _global.__rfFreshURL(lol.services.SSEmulator.getPersInfoURL(af.persName)))
    _global.__rfResources = (_global.__rfResources or 0) + 1

def __rfRetryPlayerResources(player):
    walker = player.walker
    if not walker or walker.persType == None:
        return
    factory = lol.display.AnimationFactory
    library = lol.display.SourceLibrary._lib
    if not factory or not factory.persList or not library or not library.store_arr:
        return
    af = factory.persList["player" + String(walker.persType)]
    if not af:
        return
    if not af.infoLoaded:
        _global.__rfRetryXML(af)
        return
    kinds = ["fist", "knife", "pistol", "rifle"]
    actions = ["stand", "stand_mili", "run", "fire_in", "fire", "fire_out", "arm_in", "arm_out", "reload", "use", "damage", "die"]
    weapon = player.primaryItem
    weaponName = None
    if weapon and weapon.itemName:
        weaponName = lol.utils.ParseString.replaceAll(weapon.itemName, "/", "")
    i = 0
    while i < len(kinds):
        records = af.AnimationList[kinds[i]]
        if records:
            j = 0
            while j < len(actions):
                record = records[actions[j]]
                if record and record.action:
                    _global.__rfRetrySource(library.store_arr[af.aName + record.action])
                    if af.composite and weaponName:
                        _global.__rfRetrySource(library.store_arr[af.aName + weaponName + record.action])
                j = j + 1
        i = i + 1
'''


def patches(Asm, undef):
    source = SOURCE.replace('__STALL_TIMEOUT_MS__', str(STALL_TIMEOUT_MS))
    source = source.replace('__MAX_RESOURCE_RETRIES__', str(MAX_RESOURCE_RETRIES))
    functions=Compiler(Asm,undef).functions(source)
    bodies={name:(params,body) for name,params,body in functions}
    wraps=[]
    for path,method,keep,helper in (
        (('display','ExternalSource'),'loadSource','__rfSourceLoadOrig','__rfSourceLoad'),
        (('display','SpriteSource'),'onLoadError','__rfSourceErrorOrig','__rfSourceError'),
        (('display','SpriteSource'),'onLoadProgress','__rfSourceProgressOrig','__rfSourceProgress'),
        (('display','AnimationFactory'),'init','__rfAFInitOrig','__rfAFInit'),
        (('display','AnimationFactory'),'killHR','__rfAFKillOrig','__rfAFKill'),
    ):
        params,body=bodies[helper]
        wraps.append((path,method,keep,params,body))
    return dict(globals=functions,wraps=tuple(wraps))
