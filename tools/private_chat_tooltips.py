"""Private-tab nickname hints: native artwork, 11 px text, cancellable 500 ms delay."""
from avm_codegen import Compiler

SOURCE = '''
def __pmTipStop(button):
    button.__pmHover = False
    clearInterval(button.__pmTipTimer)
    if _global.__pmTipOwner == button:
        _global.__pmTipOwner = None
        lol.gpui.HintManager.closeHint()

def __pmTipShow(button):
    clearInterval(button.__pmTipTimer)
    if not button.__pmHover or _global.__pmTipOwner != button or not button._parent._visible:
        return
    lol.gpui.HintManager.closeHint()
    lol.gpui.HintManager._showHint(button.__pmNick, button._ymouse, button._width - button._ymouse)
    lol.gpui.HintManager.hint_mc.__pmNicknameTip = True

def __pmTipUnload():
    _global.__pmTipStop(this)

def __pmTipOver():
    if not this.__pmNick:
        this.__pmTipOverOrig()
        return
    if _global.__pmTipOwner:
        _global.__pmTipStop(_global.__pmTipOwner)
    text = this.hintTitle_str
    this.hintTitle_str = None
    this.__pmTipOverOrig()
    this.hintTitle_str = text
    this.__pmHover = True
    _global.__pmTipOwner = this
    this.__pmTipTimer = setInterval(_global.__pmTipShow, 500, this)

def __pmTipOut():
    if this.__pmNick:
        _global.__pmTipStop(this)
    this.__pmTipOutOrig()

def __pmTipPress():
    if this.__pmNick:
        _global.__pmTipStop(this)
    this.__pmTipPressOrig()

def __pmTipOutside():
    if this.__pmNick:
        _global.__pmTipStop(this)
    this.__pmTipOutsideOrig()

def __pmTipInit():
    if not this.__pmNicknameTip:
        this.__pmTipInitOrig()
        return
    fmt = new("TextFormat")
    fmt.font = "Arial"
    fmt.size = 11
    fmt.bold = False
    this.title_txt.autoSize = True
    this.title_txt.text = this.title_str
    this.title_txt.setTextFormat(fmt)
    this.hintSize()
'''


def patches(Asm, undef):
    functions=Compiler(Asm,undef).functions(SOURCE)
    bodies={name:(params,body) for name,params,body in functions}
    methods=(('onRollOver','__pmTipOverOrig','__pmTipOver'),
             ('onRollOut','__pmTipOutOrig','__pmTipOut'),
             ('onPress','__pmTipPressOrig','__pmTipPress'),
             ('onReleaseOutside','__pmTipOutsideOrig','__pmTipOutside'))
    wraps=[]
    for method,keep,helper in methods:
        params,body=bodies[helper]
        wraps.append((('gpui','controls','ToggleButton'),method,keep,params,body))
    params,body=bodies['__pmTipInit']
    wraps.append((('gpui','Hint'),'init','__pmTipInitOrig',params,body))
    return dict(globals=functions[:3],wraps=tuple(wraps))
