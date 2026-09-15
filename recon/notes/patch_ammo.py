import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/items.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace('''SLOT_HEAD, SLOT_CAMO, SLOT_ARMOR, SLOT_BELT, SLOT_LEGS, SLOT_BOOTS = range(6)''',
'''# Calibres the client already knows, by their own type ids. A weapon with an
# empty comp_array accepts nothing at all and cannot be loaded.
AMMO_9MM, AMMO_762x39, AMMO_12MM, AMMO_762x51 = 1, 8, 9, 23

AMMO_FOR = {
    PISTOL: [AMMO_9MM],
    SMG: [AMMO_9MM],
    SHOTGUN: [AMMO_12MM],
    ASSAULT: [AMMO_762x39],
    RIFLE: [AMMO_762x51],
    MACHINEGUN: [AMMO_762x51],
}

SLOT_HEAD, SLOT_CAMO, SLOT_ARMOR, SLOT_BELT, SLOT_LEGS, SLOT_BOOTS = range(6)''')

s = s.replace("            comp_array=[])",
              "            comp_array=AMMO_FOR.get(cls, [AMMO_9MM]))")

# sell_num divides the displayed price, and an absent one reads as undefined
s = s.replace('''        cost=price, g_cost=0, bg_p_cost=0,''',
              '''        cost=price, g_cost=0, bg_p_cost=0,
        # A trade pack of one. The client divides the price by this, so leaving
        # it out makes the shop show an undefined price rather than no price.
        sell_num=1,''')
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
