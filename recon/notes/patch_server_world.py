import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace("from protocol import FrameReader, decode, frame, Str",
              "import world\nfrom protocol import FrameReader, decode, frame, Str")

s = s.replace('''# "Вади Хальфа: жилой квартал", chosen because it is one of the 168 locations
# with war="0": no combat mode, so action points are not consumed by walking.
# Cell 490 is the first entry point in its <inzones> list, at grid (42, 7) on a
# 64-wide grid, and pos is gy * width + gx.
START_LOC = 36
START_POS = 490''',
'''# "Черный рынок Вади-Хальфы": peaceful (war="0", so walking costs no action
# points) and already populated in its own XML with 21 traders, an upgrader,
# a lessor and several commoners.
START_LOC = int(os.environ.get("LAVA_LOC", "102"))

# The avatar id must exist in avatars/list.xml, which holds only eight, and
# must also have a folder under res/personages or the body silently falls back
# to a different character than the portrait. Ids 0, 3, 131 and 133 satisfy
# both; the rest give a face that does not match the figure on screen.
START_RES = int(os.environ.get("LAVA_RES_ID", "0"))

LOCATION = world.Location(START_LOC)
MOB_TYPES = world.mob_types()
# Entity ids: 0 is always the player, so anything placed in the world starts
# above that.
FIRST_NPC_ID = 100''')

io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
