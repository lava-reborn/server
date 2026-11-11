"""Emitted AVM1: the buttons that opened the old site's profile page are hidden.

«Изменить внешность» in the inventory, the top-up buttons of the bank, the
trade window, the gold exchange and the resurrection window, and the
location's top-up message. The wrapper runs the panel's own init (or the
resurrection window's uiUpd, which shows its button again), then hides the
button; the handlers do nothing. The wiring into the injected code is
checked by test_widescreen.py (WIRED).
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import widescreen as w
from avm_test import Function
from testkit import check, fails


def panel(original, members, shows=False):
    """A panel whose original init records the call (and, like uiUpd, may
    show the buttons again) with every button visible."""
    ui = {m: {"_visible": True} for m in members}
    ui["calls"] = []

    def orig(*args):
        ui["calls"].append(args)
        if shows:
            for m in members:
                ui[m]["_visible"] = True
    ui[original] = orig
    return ui


for cls, original, members in (
        ("EquipInterface", "__siteSkinInitOrig", ("changeSkin_btn",)),
        ("BankInterface", "__siteBankInitOrig", ("addGold_btn",)),
        ("TradeInterface", "__siteTradeInitOrig", ("addGold_btn",)),
        ("GoldToAfroInterface", "__siteExchangeInitOrig", ("addGold_btn",)),
        ("RegenerationInterface", "__siteRegenInitOrig", ("addMoney_btn", "addMoney_txt")),
        ("RegenerationInterface", "__siteRegenUpdOrig", ("addMoney_btn", "addMoney_txt"))):
    ui = panel(original, members, shows=True)
    body = w.fn_site_hide(original, (), members).assemble()
    Function((), body, {}).invoke(ui, [])
    check("%s.%s: the original runs once" % (cls, original), ui["calls"], [()])
    check("%s.%s: the old site's button is hidden" % (cls, original),
          [ui[m]["_visible"] for m in members], [False] * len(members))

# Arguments reach the original in order.
ui = panel("__orig", ("b",))
Function(("x", "y"), w.fn_site_hide("__orig", ("x", "y"), ("b",)).assemble(), {}).invoke(ui, [1, 2])
check("arguments reach the original in order", ui["calls"], [(1, 2)])

# The handlers: nothing opens.
opened = []
target = {"getURL": lambda *a: opened.append(a)}
env = {"lol": {"core": {"SceneShifter": {"_ref": {"getProfileUrl": lambda: "http://lava-online.ru/"}}}}}
check("a handler that opened the old site returns nothing",
      Function(("str",), w.fn_site_nothing().assemble(), env).invoke(target, ["msg"]), None)
check("and opens nothing", opened, [])

if fails:
    for failure in fails:
        print("FAILED: " + failure)
    sys.exit(1)
print("site buttons OK")
