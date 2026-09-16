"""Check the world tables in data/ against the client and against each other.

Runs under WSL with the client resources present (server/world.py finds
them). Plain asserts, no framework, like the server's own test sets:

    wsl.exe -e python3 data/test_world_data.py
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world  # noqa: E402

FILES = ["npc_names.json", "npc_wiki.json", "trader_stock_wiki.json",
         "loot_wiki.json", "mob_types.json", "mob_curves.json",
         "exits_sides.json", "exits.json", "settlements_wiki.json",
         "quests_wiki.json", "settlements.json", "settlements_verified.json"]

# The sixteen hand-made names that predate the wiki pass; they must survive
# every rebuild untouched.
ORIGINAL = {"711": "Золотая лотерея", "2424": "Аарон", "1200": "Пистолеты и патроны",
            "1201": "Дробовики и патроны", "1202": "Винтовки и патроны",
            "1203": "Пистолет-пулеметы и патроны", "653": "Шихаб", "1205": "Хамис",
            "1204": "Ваккас", "636": "Савин", "5": "Мастер Тиль", "1152": "Однопальцый",
            "1206": "Люций", "1207": "Магдалена", "2279": "Точильный камень",
            "652": "Техногик"}


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    data = {name: load(name) for name in FILES}
    print("json valid: %d files" % len(data))
    mt = world.mob_types()
    static = data["exits_sides.json"]["summary"]

    # --- npc_names.json ---------------------------------------------------
    names = data["npc_names.json"]["names"]
    for tid, name in names.items():
        assert int(tid) in mt, "npc_names: type %s not in mobs.xml" % tid
        assert mt[int(tid)][0] != 0, "npc_names: type %s is a mob, not an NPC" % tid
        assert name.strip(), "npc_names: empty name for %s" % tid
    for tid, name in ORIGINAL.items():
        assert names.get(tid) == name, "npc_names: original entry %s changed" % tid
    conf = data["npc_names.json"].get("confidence", {})
    assert all(conf.get(k) == "verified" for k in ORIGINAL), "originals must stay verified"
    assert all(conf.get(k) in ("verified", "high", "medium") for k in names), \
        "npc_names carries a low-confidence entry"
    assert len(names) >= 100, "npc_names: expected at least 100 names, got %d" % len(names)
    print("npc_names: %d names, originals intact" % len(names))

    # --- exits_sides.json ---------------------------------------------------
    locs = data["exits_sides.json"]["locations"]
    with_sides = overflow = 0
    for loc_id, cells in locs.items():
        meta = static[loc_id]
        size = meta["width"] * meta["height"]
        for cell, side in cells.items():
            # The files put the southern exit row at y == height, one row
            # past the grid; the client's zones do the same, so it stays.
            assert 0 <= int(cell) < size + meta["width"], \
                "exits_sides: cell %s outside %s" % (cell, loc_id)
            overflow += int(cell) >= size
            assert side in "WNESab", "exits_sides: bad side %s in %s" % (side, loc_id)
        if cells:
            with_sides += 1
    assert with_sides >= 1300, "exits_sides: only %d locations with sides" % with_sides
    print("exits_sides: %d locations, %d with sides, %d cells on the row past "
          "the grid" % (len(locs), with_sides, overflow))

    # --- mob_types.json / mob_curves.json -----------------------------------
    types = data["mob_types.json"]["types"]
    curves = data["mob_curves.json"]
    levelled = [tid for tid, (root, name, _r) in mt.items() if re.search(r"_lvl(\d+)", name)]
    missing = [t for t in levelled if str(t) not in types]
    assert not missing, "mob_types: %d _lvlN types missing, e.g. %s" % (len(missing), missing[:5])
    for tid, rec in types.items():
        assert int(tid) in mt, "mob_types: %s not in mobs.xml" % tid
        assert isinstance(rec["level"], int) and 0 <= rec["level"] <= 33, tid
        assert rec["weapon_class"] in curves["weapon_classes"], (tid, rec["weapon_class"])
        assert rec["role"] in curves["roles"], (tid, rec["role"])
        assert str(rec["level"]) in curves["levels"], tid
    hp = [curves["levels"][str(n)]["hp"] for n in range(34)]
    assert all(a <= b for a, b in zip(hp, hp[1:])) and hp[1] == 120 and hp[20] == 400, hp
    mobs_all = sum(1 for root, _n, _r in mt.values() if root == 0)
    assert sum(1 for r in types.values() if r["root"] == 0) == mobs_all
    print("mob_types: %d types, all %d _lvlN covered, all %d mobs covered" % (
        len(types), len(levelled), mobs_all))

    # --- exits.json ---------------------------------------------------------
    doors = data["exits.json"]["doors"]
    n_target = 0
    for loc_id, rec in doors.items():
        sides = static[loc_id]["sides"]
        for e in rec["doors"]:
            assert e["side"] in sides, "exits: %s has no side %s" % (loc_id, e["side"])
            if e["target_loc_id"] is not None:
                assert str(e["target_loc_id"]) in static, (loc_id, e)
                assert e["confidence"] in ("high", "medium", "low"), e
                n_target += 1
    assert n_target >= 400, "exits: only %d doors with a target" % n_target
    print("exits: %d files with doors, %d door sides with a target" % (len(doors), n_target))

    # --- settlements_wiki.json (must not touch the real tables) ---------------
    proposals = data["settlements_wiki.json"]["cells"]
    real = data["settlements.json"]["cells"]
    for cell, rec in proposals.items():
        assert re.match(r"^\d{4},\d{4}$", cell), cell
        assert str(rec["loc_id"]) in static, rec
        if rec["status"] == "already":
            assert real.get(cell) == rec["loc_id"], cell
    print("settlements_wiki: %d proposals, settlements.json untouched (%d cells)" % (
        len(proposals), len(real)))

    # --- quests_wiki.json ---------------------------------------------------
    quests = data["quests_wiki.json"]["quests"]
    bound = 0
    for key, q in quests.items():
        assert q["kind"] in ("kill_mobs", "bring_l_obj", "del_obj"), q["kind"]
        assert q["type"] == int(key)
        for k in ("name", "start_desc", "notfinish_desc", "finish_desc"):
            assert isinstance(q[k], str), (key, k)
        for tid in q["give"] + q["take"]:
            assert tid in mt and mt[tid][0] != 0, (key, tid)
        if q["bound"]:
            assert q["give"], key
            bound += 1
        assert q["strings"]["name"] == 2_000_000 + 4 * q["type"]
    assert bound >= 300, "quests: only %d bound to a giver" % bound
    print("quests: %d, %d bound to a giver type id" % (len(quests), bound))

    # --- loot_wiki.json / trader_stock_wiki.json --------------------------------
    loot = data["loot_wiki.json"]
    for tid, drops in loot["by_type"].items():
        assert int(tid) in mt, tid
        for d in drops:
            assert 0 < d["chance"] <= 1, d
    for tid, rec in data["trader_stock_wiki.json"]["by_type"].items():
        assert int(tid) in mt and mt[int(tid)][0] == 1, "trader_stock: %s is not a trader" % tid
        assert rec["items"], tid
    print("loot: %d types with drops; trader stock: %d traders" % (
        len(loot["by_type"]), len(data["trader_stock_wiki.json"]["by_type"])))
    print("ok")


if __name__ == "__main__":
    main()
