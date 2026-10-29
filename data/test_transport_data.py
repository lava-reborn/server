"""Check data/transport.json against the client's files and against itself.

Runs under WSL with the client resources present (server/world.py finds
them). Plain asserts, no framework, like the other data sets:

    wsl.exe -e python3 data/test_transport_data.py

What is pinned here is what would break silently in the game: an icon that
does not exist (the rental window draws an empty slot), a number so far out
that the map becomes unusable, a string id the HTTP preload never saw (which
costs the player a trip back to the login screen, PROTOCOL.md 9), and a
rental list pointing at an NPC that is not a lessor.
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
import names  # noqa: E402
import transport  # noqa: E402
import world  # noqa: E402


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def swf_ids():
    folder = os.path.join(world.RES, "transport")
    out = set()
    for fn in os.listdir(folder):
        stem, ext = os.path.splitext(fn)
        if ext.lower() == ".swf" and stem.isdigit():
            out.add(int(stem))
    return out


def main():
    data = load("transport.json")
    types = {int(k): v for k, v in data["types"].items()}
    icons = swf_ids()
    print("json valid: %d vehicles, %d icons on disk" % (len(types), len(icons)))

    # --- every type is a file the client can actually load -----------------
    assert icons, "no res/transport/*.swf found: LAVA_RES wrong?"
    assert set(data["icons"]) == icons, "the icon list has drifted from the disk"
    for type_id, rec in sorted(types.items()):
        assert rec["res"] in icons, \
            "type %d has no res/transport/%d.swf" % (type_id, rec["res"])
        assert rec["type"] == type_id, "type %d disagrees with its key" % type_id
        assert rec["name"].strip(), "type %d has no name" % type_id
        assert rec["in_manifest"], \
            "type %d is not in res/xml/transport.xml" % type_id

    # Pinned from visual inspection of the original SWFs, not the builder's map.
    expected = {1: ("Ослик Панург",5), 2: ("Верблюд",1), 3: ("Мотоцикл",6),
                4: ("УАЗ",2), 5: ("Хаммер",3), 6: ("Багги",4), 7: ("Ларва",7)}
    for t, (name, icon) in expected.items():
        assert (types[t]["name"], types[t]["res"]) == (name,icon), (t,types[t])
        assert transport.si_frame(t)["type"] == t  # persistent rental ID unchanged
    print("basic rental images visually verified: donkey/camel/moto/UAZ/Hummer/buggy/Larva")

    # --- numbers inside sane bounds ----------------------------------------
    # Transport exists to be faster than walking, and the client prints
    # (speed_mod - 1) * 100 as the percentage, so anything at or below 1
    # would read as "no better than on foot" or worse.
    for type_id, rec in sorted(types.items()):
        speed = rec["speed_mod"]
        assert 1.0 < speed <= 100.0, "type %d: speed_mod %r" % (type_id, speed)
        aggro = rec["aggro_mod"]
        assert 0.0 <= aggro <= 1.0, "type %d: aggro_mod %r" % (type_id, aggro)
        assert rec["premium"] in (0, 1, 2), "type %d: premium %r" % (type_id, rec["premium"])
        assert rec["cost"] >= 0 and rec["g_cost"] >= 0, type_id
        # The client shows a gold price when g_cost is set and an afro one
        # otherwise (TransRentInterface.printTxt), so the two are exclusive:
        # an afro price beside a gold one would never be charged.
        assert not (rec["cost"] and rec["g_cost"]), \
            "type %d is priced in both currencies at once" % type_id
        assert rec["cost"] <= 100000 and rec["g_cost"] <= 200000, \
            "type %d: a day's rent is out of scale" % type_id
        assert rec["max_days"] == data["max_days"] == 365, type_id
        assert rec["source"] in ("wiki", "wiki+designed", "designed"), rec["source"]
        if rec["source"] == "wiki":
            assert not rec["designed"], "type %d says wiki but designs %r" % (
                type_id, rec["designed"])
        else:
            assert rec["designed"], "type %d says designed but designs nothing" % type_id

    # The ordinary rental yard must stay affordable in the order it is
    # offered: a ladder that is not monotone in speed is a table someone
    # edited by hand and did not re-read.
    ladder = [types[t]["speed_mod"] for t in data["default_lessor"]]
    assert ladder == sorted(ladder), "the default set is not ordered by speed"
    assert len(data["default_lessor"]) >= 5, "a rental yard with nothing in it"

    assert (types[4]["cost"],types[4]["g_cost"],types[4]["required_status"]) == (0,70,0)
    assert (types[5]["cost"],types[5]["g_cost"],types[5]["required_status"]) == (0,90,0)
    for offer, base, cost, status in ((17,4,35000,1),(18,5,45000,2)):
        rec = transport.get(offer)
        assert (rec["base_type"],rec["cost"],rec["g_cost"],rec["required_status"]) == (base,cost,0,status)
        assert cost == types[base]["g_cost"] * 50000 // 100
        assert transport.si_frame(offer)["premium"] == status
        assert names.known(transport.NAME_ID_OFFSET + offer)
        assert names.known(transport.DESC_ID_OFFSET + offer)
        assert (rec["speed_mod"],rec["aggro_mod"],rec["res"]) == tuple(types[base][k] for k in ("speed_mod","aggro_mod","res"))
    # Every lessor, including clan/fallback types, uses the same verified art and labels.
    lessors_all = [t for t,r in world.mob_types().items() if r[0] == world.LESSOR]
    for npc in lessors_all:
        for vehicle in transport.offered_by(npc):
            base = transport.vehicle_type(vehicle)
            assert base in expected, (npc,vehicle)
            assert transport.si_frame(vehicle)["res"] == expected[base][1], (npc,vehicle)
            assert transport.get(vehicle)["name"].split(" (")[0].split("$")[0] == expected[base][0], (npc,vehicle)
        for base, offer in ((4,17),(5,18)):
            assert (base in transport.offered_by(npc)) == (offer in transport.offered_by(npc))
    print("all %d lessor types checked, including fallback/clan lists" % len(lessors_all))

    # --- string ids ---------------------------------------------------------
    for type_id in types:
        for sid in (transport.NAME_ID_OFFSET + type_id,
                    transport.DESC_ID_OFFSET + type_id):
            if sid in transport.strings():
                assert names.known(sid), \
                    "string %d is sent but not preloaded" % sid
    assert names.known(transport.UNKNOWN_NAME_ID), "the placeholder name is missing"
    # The transport block must not tread on the item or quest blocks.
    for sid in transport.strings():
        assert 6_000_000 <= sid < 7_000_000, sid
    print("strings: %d ids, all in names.ALL" % len(transport.strings()))

    # --- who rents what ------------------------------------------------------
    mt = world.mob_types()
    for npc_type, offer in sorted(data["lessors"].items()):
        npc_type = int(npc_type)
        assert npc_type in mt, "lessor type %d is not in mobs.xml" % npc_type
        assert mt[npc_type][0] == world.LESSOR, \
            "type %d (%s) is not a Lessor" % (npc_type, mt[npc_type][1])
        assert offer, "lessor %d offers nothing" % npc_type
        for t in offer:
            assert int(t) in types, "lessor %d offers unknown type %r" % (npc_type, t)
    for t in data["default_lessor"]:
        assert int(t) in types, "the default set names unknown type %r" % t

    # The Wadi-Halfa desk is the one a player meets first: 653 wh_Lessor, the
    # only lessor spawned in location 102 (the black market the game starts in).
    lessor_102 = [t for _cell, t in world.location(102).spawns
                  if mt.get(t, (None,))[0] == world.LESSOR]
    assert lessor_102 == [653], "location 102's lessor moved: %r" % lessor_102
    assert transport.offered_by(653), "the Wadi-Halfa desk rents nothing"
    print("lessors: %d bound by the wiki, %d in the default yard, 653 offers %d"
          % (len(data["lessors"]), len(data["default_lessor"]),
             len(transport.offered_by(653))))

    # --- the frame the client will read --------------------------------------
    for type_id in sorted(types):
        si = transport.si_frame(type_id)
        assert set(si) == {"type", "speed_mod", "aggro_mod", "g_cost", "cost",
                           "res", "premium", "name", "desc"}, si
        # ItemContainer builds transport/<res>.swf, not transport/<type>.swf.
        assert si["res"] == types[type_id]["res"], type_id
        assert si["res"] in icons, type_id
        assert si["name"] == transport.NAME_ID_OFFSET + type_id, type_id
    print("ok")


if __name__ == "__main__":
    main()
