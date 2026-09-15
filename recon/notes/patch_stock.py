import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace("import accounts\nimport world",
              "import accounts\nimport items\nimport world")

old = '''        if root == world.TRADER:
            # An empty stock still opens the trade window; goods come later.
            params.update(can_trade=1, can_repair=1, type_list=[],
                          bg_objects=[], bg_obj_rep_req=[],
                          pmod=1, smod=1, rmod=1)'''
new = '''        if root == world.TRADER:
            # type_list is the price list itself, in order: the client builds a
            # TradeItem per entry and later refers to a purchase by that index,
            # not by the item's own id.
            params.update(can_trade=1, can_repair=1,
                          type_list=items.stock_for(type_id),
                          bg_objects=[], bg_obj_rep_req=[],
                          pmod=1, smod=1, rmod=1)'''
assert old in s
s = s.replace(old, new)

anchor = '''    def cmd_ss_get(self, p):'''
addition = '''    def cmd_ss_get_si(self, p):
        """Static info for one item type.

        ItemFactory keeps at most five of these in flight and only releases a
        slot when the answer arrives, so an unknown type still has to be
        answered or the queue never drains and the shop stays empty.
        """
        type_id = int(p.get("type", 0))
        info = items.static_info(type_id)
        if not info:
            log.warning("  ??    no such item type %d", type_id)
            return
        command, params = info
        self.send(command, **params)

    def cmd_ss_create(self, p):
        """Open a session with an NPC: trade, bank, training and the rest."""
        self.send("cmdAck", res=0)

    def cmd_ss_upd(self, p):
        self.send("cmdAck", res=0)

    def cmd_ss_get_s_si(self, p):
        # Nothing belongs to a set yet, but the request still needs answering.
        self.send("ss_si_set", type=int(p.get("type", 0)), res=0, name=0,
                  desc="")

    def cmd_ss_get(self, p):'''
assert anchor in s
s = s.replace(anchor, addition, 1)
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
