"""Cross-system release contracts: capture ranking and all retail resale paths."""
import itertools
import math
import random
import unittest

import gold_trade
import holdings
import inventory
import items
import progression
import shop_bands
import world
from testkit import run_cases


def reference_winner(snapshot,squad,minimum,excluded):
    """Independent rule: only the finishing clan can meet the squad condition."""
    clan=snapshot['killer_clan']
    if clan is None or clan in excluded or snapshot['killer'] is None:
        return None
    people=[p for p in snapshot['fighters'] if p['clan']==clan and p['here']]
    present={p['char'] for p in people if p['alive'] and p['level']>=minimum and p['harm']>0}
    if len(present)<squad or snapshot.get('killer_actor',snapshot['killer']) not in present:
        return None
    damage=min(snapshot['pool'],sum(p['harm'] for p in people))
    return clan,people[0]['clan_name'],damage,snapshot['killer']


class ReleaseIntegrity(unittest.TestCase):
    def test_capture_selection_matches_all_eligibility_boundaries_and_is_order_independent(self):
        rng=random.Random(20261124)
        for squad,minimum in ((2,8),(2,12),(2,16),(2,17),(3,12),(3,16)):
            for iteration in range(400):
                people=[dict(char=i+1,clan=rng.choice((None,1,2,3)),
                    clan_name='',here=rng.choice((True,True,False)),
                    alive=rng.choice((True,True,False)),
                    level=rng.choice((minimum-1,minimum,minimum+1)),
                    harm=rng.choice((0,1,50,500))) for i in range(12)]
                for person in people:
                    person['clan_name']='clan%s'%person['clan']
                snapshot=dict(fighters=people,pool=1000,killer=people[-1]['char'],
                              killer_clan=people[-1]['clan'])
                if iteration%2:
                    snapshot['killer_actor']=rng.choice(people)['char']
                excluded={2} if iteration%3==0 else set()
                expected=reference_winner(snapshot,squad,minimum,excluded)
                self.assertEqual(holdings.winner(snapshot,squad,minimum,excluded),expected)
                rng.shuffle(people)
                self.assertEqual(holdings.winner(snapshot,squad,minimum,excluded),expected)

    def test_every_site_requires_its_own_distinct_present_live_damagers_at_or_above_its_level(self):
        for base in holdings.table().sites.values():
            squad = holdings.BASE_SQUAD if base.kind == 'base' else holdings.table().squad
            people=[dict(char=i+1,clan=1,clan_name='owner',here=True,alive=True,
                         level=base.min_level,harm=10) for i in range(squad)]
            snapshot=dict(fighters=people,pool=1000,killer=1,killer_clan=1)
            self.assertEqual(holdings.winner(snapshot,squad,base.min_level)[0],1)
            for key,value in (('here',False),('alive',False),('harm',0),('level',base.min_level-1)):
                prior=people[-1][key]
                people[-1][key]=value
                self.assertIsNone(holdings.winner(snapshot,squad,base.min_level),(base.key,key))
                people[-1][key]=prior
            for person in people:
                person['level']=base.min_level+1
            self.assertEqual(holdings.winner(snapshot,squad,base.min_level)[0],1)

    def test_all_released_retail_types_have_no_purchase_to_base_buyback_profit(self):
        stock=set()
        for location in shop_bands.CITY_OF:
            loc=world.location(location)
            traders={type_id for _,type_id in loc.spawns}
            traders.update(row['type'] for row in world.placed_in(location))
            for trader in traders:
                stock.update(items.stock_for(trader,location))
        discounted=set()
        for base in holdings.table().sites.values():
            if base.kind=='base':
                for location,trader in itertools.product(base.rooms,base.traders):
                    discounted.update(items.stock_for(trader,location))
        checked=0
        exchange=progression.GOLD_TO_AFRO_RATE/progression.GOLD_OUNCE
        for type_id in sorted(stock|discounted):
            params=items.params_of(type_id)
            if not params or gold_trade.protected(type_id,params) or items.acquisition_blocked(type_id):
                continue
            root=items.root_of(type_id)
            unit=(gold_trade.sale_unit(type_id,params,gold_trade.BASE_SALE_SHARE)
                  if gold_trade.gold_priced(type_id,params) else
                  gold_trade.afro_sale_unit(type_id,params,gold_trade.BASE_SALE_SHARE))
            if not unit:
                unit=params.get('cost',0)*float(gold_trade.BASE_SALE_SHARE)*params.get('sell_mod',1)/(params.get('sell_num') or 1)
            cap=gold_trade.afro_sale_cap(type_id,params)
            if cap:
                unit=min(unit,cap)
            quantities=(1,2,20,100,5000) if root==items.AMMO else (1,)
            for quantity,gold in itertools.product(quantities,(False,True)):
                if params.get('g_cost' if gold else 'cost',0)<=0:
                    continue
                rates=dict(pmod=.9 if type_id in discounted else inventory.PMOD)
                paid=inventory.buy_price(params,root,quantity,gold,
                                         inventory.purchase_pmod(type_id,rates))
                value=paid*(exchange if gold else 1)
                self.assertGreater(paid,0,(type_id,quantity,gold))
                payout=max(1,math.floor(unit*quantity))
                split_payout=quantity*max(1,math.floor(unit))
                self.assertLessEqual(max(payout,split_payout),value+1e-7,
                                     (type_id,quantity,gold,payout,split_payout,value))
                checked+=1
        self.assertGreater(checked,1000)


if __name__=='__main__':
    run_cases(ReleaseIntegrity)
