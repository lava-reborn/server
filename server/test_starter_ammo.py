"""Gift rounds: affordable trade, ordinary death drops, exclusive weapon compatibility.

No database or running server is needed. LAVA_RES must name client resources.
"""
import os
import sys
from types import SimpleNamespace

os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import items
import inventory
import combat
from testkit import check, fails

AMMO = items.STARTER_ROUNDS
p = items.params_of(AMMO)
check("gift ammunition costs 20 afro a pack, no gold", (p["cost"], p["g_cost"], p["sell_num"]), (20, 0, 20))
check("one round costs one afro", inventory.buy_price(p, items.AMMO, 1), 1)
check("no skill or level requirement for rounds", bool(p.get("need_skills") or p.get("need_specs")), False)
check("starter kit uses the same rounds", inventory.STARTER_AMMO, AMMO)
check("20 rounds cost 20 afro", inventory.buy_price(p, items.AMMO, 20), 20)
check("ordinary rounds still fall", combat.drops_on_death(6094), True)
check("gift rounds remain droppable", combat.drops_on_death(AMMO), True)
row = dict(uniq=1, type_id=AMMO, root=items.AMMO, slot=inventory.BAG, count=20)
check("a stack of twenty still loses seven rounds at death",
      [(r["type_id"], n) for r, n in combat.death_losses([row])], [(AMMO, 7)])

# Inspect every effective firearm, including modified weapons.
expected = {25562, 43338, 43341, 43344, 43347, 43350, 43353,
            43356, 43359, 43362, 43365, 43368, 43371}
compatible = {t for t, (root, _name) in items.catalogue().items()
              if root == items.FIRE_ARM and AMMO in items.params_of(t).get("comp_array", [])}
check("only Samostrel and its twelve modified variants accept gift rounds", compatible, expected)

class Shop:
    def __init__(self, trader, loc, afro=100):
        self.trade = SimpleNamespace(trader_type=trader, loc_id=loc)
        self.purse = (afro, 0)
        self.acks = []
        self.created = []
    def ack(self, code): self.acks.append(code)
    def total_weight(self): return 0
    def money(self): return self.purse
    def set_money(self, afro, gold, *args): self.purse = (afro, gold)
    def create(self, t, n):
        self.created.append((t, n))
        return {}
    def push_status(self, *args): pass
    def push_di(self, *args): pass
    def push_money(self): pass

for trader, loc in ((5218, 181), (5219, 183), (5212, 185)):
    stock = items.stock_for(trader, loc)
    check("trader %d stocks gift rounds" % trader, AMMO in stock, True)
    request = dict(obj=format(stock.index(AMMO), "x"), param=20)
    shop = Shop(trader, loc)
    inventory.Inventory.buy(shop, request, inventory.UPD_BUY)
    check("afro purchase works with zero gold: %d" % trader,
          (shop.acks, shop.purse, shop.created), ([inventory.RES_OK], (80, 0), [(AMMO, 20)]))
    shop = Shop(trader, loc, afro=0)
    inventory.Inventory.buy(shop, request, inventory.UPD_BUY)
    check("cannot buy without afro", (shop.acks, shop.created), ([inventory.RES_NO_MONEY], []))
    shop = Shop(trader, loc)
    inventory.Inventory.buy(shop, request, inventory.UPD_BUY_GOLD)
    check("gold purchase refused", (shop.acks, shop.created), ([inventory.RES_REFUSED], []))

# Exercise the real reload rejection before any inventory mutations.
for t in (25566, 25576, 25951):
    gun = dict(root=items.FIRE_ARM, type_id=t)
    stack = dict(root=items.AMMO, type_id=AMMO)
    acks = []
    fake = SimpleNamespace(find=lambda value: gun if value == "gun" else stack, ack=acks.append)
    inventory.Inventory.use_load(fake, dict(obj="gun", target="ammo"))
    check("reload rejects gift rounds in firearm %d" % t, acks, [inventory.RES_WRONG_AMMO])
if fails:
    print("\n".join(fails))
    sys.exit(1)
