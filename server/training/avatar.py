"""Training range: avatar."""
import inventory
import mail
import mobs
import progression
import quests
import rooms
import time
import world
from protocol import Str
from training import layout as training_layout, opponents as training_opponents, party as training_party
from training.settings import EXIT_QUEST, PLAY_COMMANDS, READ_COMMANDS


def clone_class(base):
    class Clone(base):
        """Only a whitelist of base handlers is reachable; persistence stays local."""
        @property
        def pid(self):
            return self.training_pid

        def char_for_entity(self, entity_id):
            peer = self.room.view_player(entity_id)
            return peer.char_id if peer is not None else None

        def send(self, *cmd, **p):
            if cmd and cmd[0] == 'userInfo' and self.room is not None:
                npc = self.room.npcs.get(p.get('id'))
                if npc is not None and npc.type_id in training_opponents.RECORDS:
                    p['name'] = training_opponents.NAME_BASE + npc.type_id
            if cmd and cmd[0] == 'cmdAck':
                self.training_acks = getattr(self, 'training_acks', 0) + 1
            return super().send(*cmd, **p)

        def close(self, force=False):
            # A private actor must never reach Session.close: its local
            # char_id may coincide with an unrelated live database character.
            ground = self.ground
            if ground.closed:
                return
            if ground.owner.training_ground is ground:
                ground.owner.close(force=True)
            else:
                ground.exit(notify=False)

        def save_place(self):
            pass

        def fee_recount(self):
            pass

        def skill_recount(self):
            pass

        def fee_gate(self, params):
            return params

        def skill_gate(self, params):
            return params

        def terminal_quest(self, p):
            ground = self.ground
            if int(p.get('mob', 0)) != ground.terminal_id:
                raise ValueError('Подойдите к компьютеру')
            ground.require_terminal()
            return quests.get(EXIT_QUEST)

        def cmd_q_st(self, p):
            raise ValueError('Для выхода используйте кнопку «Покинуть полигон» у компьютера')

        def cmd_q_co(self, p):
            quest = self.terminal_quest(p)
            row = self.inv.store.quest(int(p.get('q_id', 0)))
            if not row or row['char_id'] != self.char_id or row['type'] != EXIT_QUEST:
                raise ValueError('Задание недоступно')
            if not row['complete']:
                raise ValueError('Задание ещё не выполнено')
            # Success disposes this entire private journal. Keep the row until
            # the durable presence checkpoint succeeds, so a failed exit retries.
            self.ground.exit(quest_ack=True)

        def cmd_q_ca(self, p):
            q_id = int(p.get('q_id', 0))
            row = self.inv.store.quest(q_id)
            if not row or row['char_id'] != self.char_id or row['type'] != EXIT_QUEST:
                raise ValueError('Задание недоступно')
            self.inv.store.drop_quest(q_id, self.char_id)
            self.ground.save_settings()
            self.send('cmdAck', res=0)

        def cmd_q_di(self, p):
            q_id = int(p.get('q_id', 0))
            row = self.inv.store.quest(q_id)
            if row and row['char_id'] == self.char_id and row['type'] == EXIT_QUEST:
                command, fields = quests.get(EXIT_QUEST).di_frame(q_id, {'obj': 1}, True)
            else:
                command, fields = quests.stub_di(q_id)
            self.send(command, **fields)

        def cmd_q_status(self, p):
            t = int(p.get('q_type', 0))
            q = quests.get(t)
            available = False
            self.send('q_status', type=t, status=int(available),
                      name=q.string_id(quests.NAME) if q else 0, q_type=q.q_type if q else 0)

        def cmd_ah_search(self, p):
            self.send('ah_sresult', page=0, count=0, next=0)

        def count_bag(self):
            pass

        def arm_passage(self, *args):
            pass

        def take_passage(self, *args):
            pass

        @property
        def party_member_id(self):
            return self.ground.owner.char_id if self is self.ground.clone else None

        def party(self):
            return self.ground.owner.party() if self is self.ground.clone else None

        def push_stats(self, **groups):
            self.ground.combat_stats(self)
            self.send('rp_info', **self.character().rp_info(**groups))

        def enter_location(self):
            # Deliver geometry before lcall: cached XML can finish loading immediately.
            self.send('tg', op='map', location=self.ground.location,
                      arena_width=self.loc.width, arena_height=self.loc.height,
                      native_map=int(self.ground.location == 59))
            self.send('lcall', id=self.ground.location, ws=int(self.room.ws), ie=0,
                      g_id=1 << 26)

        def cmd_lenter(self, p):
            ground = self.ground
            if ground.phase == 'loading':
                ground.phase = 'fight'
                ground.room.ws = True
                ground.started = time.monotonic()
                if ground.enemy is not None:
                    ground.enemy.combat.entered()
            if self not in self.room.players:
                self.pos = training_party.free_spawn(self.room, self.pos, excluded=self)
            self.combat.amax_sent = self.character().ap_ceiling
            self.send('lenter', pos=self.pos, aspd=progression.AP_REGEN, amax=self.character().ap_ceiling)
            if self in self.room.players:
                self.room.snapshot_for(self)
            else:
                self.room.enter(self)
            self.combat.entered()
            self.send_player_info()
            self.push_stats()
            self.push_vitals()
            self.ground.state()
            if getattr(ground, 'open_after_load', False):
                ground.open_after_load = False
                self.send('tg', op='open', mob=ground.mob_type)

        def cmd_getInfo(self, p):
            target = int(p.get('id', 0))
            if not target:
                self.send_player_info()
                self.push_vitals()
            elif self.room.view_player(target) is not None:
                peer = self.room.view_player(target)
                fields = rooms.player_info(peer)
                fields.update(name=Str(peer.nick), ally=int(self.combat.allied(peer.combat)))
                self.send('userInfo_Player', **fields)
                self.send('usrUp', **rooms.player_health(peer))
            else:
                self.send_npc_info(target)

        def send_npc_info(self, eid):
            npc = self.room.npc(eid)
            if npc is None:
                return
            post = self.ground.posts.get(eid)
            if post is None:
                return super().send_npc_info(eid)
            self.send(world.USERINFO[world.COMMONER], id=eid,
                      name=training_layout.NAME_IDS[post.key], sex=0, res=post.resource,
                      ail=0, ally=1, lvl=1, rep=[0], bg_rep=0, bg_pen=0,
                      give_quests=[],
                      take_quests=[], m_hello=[], can_set_home=0,
                      can_banking=0, can_trophy=0, can_repair=0, can_trade=0,
                      tg_terminal=1, tg_supply=int(bool(post.line)),
                      tg_station=Str(post.key), tg_title=Str(post.title))

        def cmd_ss_get_di(self, p):
            parsed = inventory.parse_oid(p.get('obj'))
            if parsed:
                for ground in self.room.grounds.values():
                    if ground.serial_base <= parsed[0] < ground.serial_base + (1 << 20):
                        row = ground.store.item(parsed[0])
                        if row and (row['type_id'], row['root']) == parsed[1:]:
                            self.send(inventory.DI_COMMAND[row['root']], **inventory.di_params(row, ground.store))
                            return
                if any(parsed[0] == mobs.VIRTUAL_BASE + ground.mob_eid
                       for ground in self.room.grounds.values() if ground.mob_eid is not None):
                    return self.combat.ss_get_di(p)
            return self.inv.ss_get_di(p)

        def cmd_ss_get(self, p):
            peer = self.room.view_player(int(p.get('target', 0) or 0))
            if peer is not None and peer is not self:
                # Read-only view: never switch the receiving clone's store.
                reader = inventory.Inventory(self, peer.inv.store)
                reader.shown, reader.acked = self.inv.shown, self.inv.acked
                reader.ss_get(p)
            elif not self.combat.ss_get(p):
                self.inv.ss_get(p)

        def handle_training(self, cmd, p):
            # Clan identity belongs to the owner, never to the sandbox clone.
            # Only public/member lists and creation prices are read here;
            # treasury, membership changes and rights still hit the refusal.
            if cmd == 'gg_info' and p.get('det') in (1, 5, 6):
                owner = self.ground.owner
                owner.training_clan_read = True
                try:
                    owner.cmd_gg_info(p)
                finally:
                    owner.training_clan_read = False
                return
            if cmd == 'p_op':
                training_party.command(self.ground, p)
                return
            if cmd == 'ss_create':
                if int(p.get('s_type', -1)) == inventory.SESSION_TRADE:
                    self.inv.open_trade(p)
                else:
                    self.send('cmdAck', res=inventory.RES_REFUSED)
                return
            if cmd == 'ss_upd':
                self.inv.ss_upd(p)
                return
            if cmd == 'lcall':
                self.enter_location()
                return
            if cmd == 'lenter':
                self.cmd_lenter(p)
                return
            if cmd == 'userMsg':
                if str(p.get('entry', '')).lstrip().startswith('/') and not ('group' not in p and p.get('to')):
                    self.send('cmdAck', res=0)
                    self.answer('Игровые команды недоступны в тренировке. Используйте компьютер полигона.')
                else:
                    owner = self.ground.owner
                    owner.training_chat = True
                    try:
                        owner.cmd_userMsg(p)
                    finally:
                        owner.training_chat = False
                return
            if cmd == 'chkml':
                owner = self.ground.owner
                owner.training_mail_read = True
                try:
                    owner.cmd_chkml(p)
                finally:
                    owner.training_mail_read = False
                return
            if cmd == 'q_list':
                rows = self.inv.store.quests(self.char_id)
                self.send('q_list', q_id=[r['q_id'] for r in rows], q_types=[r['type'] for r in rows])
                return
            if cmd in ('q_st', 'q_co', 'q_ca'):
                getattr(self, 'cmd_' + cmd)(p)
                return
            if cmd == 'ss_move' and (int(p.get('to', inventory.BAG)) not in inventory.WEAR_SLOTS + inventory.HAND_SLOTS + (inventory.BAG,) or int(p.get('from', inventory.BAG)) not in inventory.WEAR_SLOTS + inventory.HAND_SLOTS + (inventory.BAG,)):
                self.send('cmdAck', res=inventory.RES_REFUSED)
                return
            if cmd in READ_COMMANDS or (cmd in PLAY_COMMANDS and self.ground.phase in ('ready', 'fight')):
                if cmd == 'getInfo' and int(p.get('id', 0)) not in (0, *self.ground.posts) \
                        and self.room.view_player(int(p.get('id', 0))) is None \
                        and int(p.get('id', 0)) not in self.room.combat.mobs:
                    return
                if cmd == 'moveTo':
                    path = p.get('path', [])
                    limit = self.loc.width * self.loc.height
                    if not isinstance(path, list) or len(path) > limit or any(
                            not isinstance(c, int) or c < 0 or c >= limit or c in self.loc.obstacles for c in path):
                        cell = self.live_cell()
                        self.pos = cell
                        self.send('breakMv', id=0, pos=cell)
                        return
                fn = getattr(self, 'cmd_' + cmd)
                fn(p)
                if cmd in ('ss_move', 'ss_use'):
                    self.inv.refresh_gear()
                    self.ground.remember_outfit()
                    self.ground.combat_stats(self)
                return
            if cmd == 'moveTo':
                self.send('breakMv', id=0, pos=self.live_cell())
                return
            module = __import__(base.__module__)
            if module.expects_ack(cmd, p):
                self.send('cmdAck', res=inventory.RES_REFUSED)
    return Clone
