"""A mob's loot is durable and visible before its cosmetic corpse timer."""
import asyncio
import unittest
import logging
from types import SimpleNamespace as NS
from unittest.mock import patch
logging.disable(logging.CRITICAL)
import accounts
import combat
import inventory
from testkit import run_cases


class LootTiming(unittest.IsolatedAsyncioTestCase):
    async def test_loot_is_persisted_and_published_before_corpse_delay(self):
        store=accounts.Store(':memory:')
        self.addCleanup(store.close)
        published=[]
        mob=NS(is_player=False, walk=None, cell=42,eid=7,type_id=100,aim=None,
               stats=NS(name='fixture'))
        room=NS(motion=None,npcs={7:mob},players=[],broadcast=lambda e: published.append(e[0]))
        rc=NS(store=store,room=room,place=(100,0,0),quest_wants=lambda *a: frozenset(),
              settle_xp=lambda _: None,calm=lambda:None,corpse_gone=lambda *a:None)
        def drop(_):
            fields=inventory.new_fields(2258,2)
            root=fields.pop('root')
            return [store.create_item(combat.LOOT_OWNER,2258,root,**fields)]
        def show(cell,rows,until):
            self.assertEqual(cell,42)
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM ground').fetchone()[0],1)
            published.append('bag')
        rc.drop_loot=drop
        rc.add_to_bag=show
        with patch('holdings.snapshot',return_value=None), patch.object(asyncio.get_running_loop(),'call_later') as later:
            combat.RoomCombat.kill(rc,mob,None)
            combat.RoomCombat.materialize_loot(rc,mob)
            self.assertEqual(published.count('bag'),1)
            self.assertEqual(len(store.items_of(combat.LOOT_OWNER)),1)
            later.assert_called_once()


if __name__ == '__main__':
    run_cases(LootTiming)
