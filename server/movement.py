"""One room clock and next-hex claims; no per-step packets or database reads."""
import asyncio
from dataclasses import dataclass

import mobs
import progression
import world

TIME_EPSILON = 1e-9


def elapsed_ms(t, began):
    """Floor milliseconds without losing one to binary float subtraction."""
    return max(0, int((t - began + TIME_EPSILON) * 1000))


@dataclass
class Walk:
    actor: object
    cells: list
    began: float
    index: int = 0


class Motion:
    def __init__(self, room):
        self.room = room
        # Resolve only when a room is created: mobs -> inventory -> rooms can
        # import this module before mobs has finished defining its constants.
        self.step = mobs.HEX_MS / 1000.0
        self.walks = {}
        self.timer = None
        self.advancing = False

    def actors(self):
        for sess in self.room.players:
            if not getattr(getattr(sess, 'combat', None), 'dead', False):
                yield sess
        rc = getattr(self.room, "combat", None)
        if rc is not None:
            yield from (m for m in rc.mobs.values() if m.alive)

    def cell(self, actor):
        state = self.walks.get(id(actor))
        if state is not None:
            return state.cells[state.index]
        if hasattr(actor, 'cell'):
            return actor.cell
        return actor.pos if hasattr(actor, 'pos') else actor.live_cell()

    def occupied(self, exclude=None):
        self.advance()
        out = {n.cell for n in self.room.npcs.values() if n.root != world.MOB}
        for actor in self.actors():
            if actor is exclude:
                continue
            out.add(self.cell(actor))
            state = self.walks.get(id(actor))
            if state and state.index + 1 < len(state.cells):
                out.add(state.cells[state.index + 1])
        return out

    def free_cell(self, cell, exclude=None):
        blocked = self.occupied(exclude) | self.room.loc.obstacles
        if cell not in blocked:
            return cell
        queue, seen = [cell], {cell}
        for candidate in queue:
            for n in progression.hex_neighbours(candidate, self.room.loc.width, self.room.loc.height):
                if n in seen or n in self.room.loc.obstacles:
                    continue
                if n not in blocked:
                    return n
                seen.add(n)
                queue.append(n)
        raise ValueError('В локации нет свободной клетки')

    def accept(self, actor, cells, began):
        self.advance()
        if len(cells) < 2:
            self.walks.pop(id(actor), None)
            self.schedule()
            return
        self.walks[id(actor)] = Walk(actor, cells, began)
        self.schedule()

    def forget(self, actor):
        removed = self.walks.pop(id(actor), None)
        if removed is not None and not self.advancing:
            self.schedule()

    def stop(self, state):
        actor, cell = state.actor, state.cells[state.index]
        self.walks.pop(id(actor), None)
        if isinstance(actor, mobs.Mob):
            actor.cell, actor.walk = cell, None
            actor.busy_until = asyncio.get_running_loop().time() + mobs.STUCK_WAIT
            npc = self.room.npcs.get(actor.eid)
            if npc is not None:
                self.room.npcs[actor.eid] = npc._replace(cell=cell)
            eid = actor.eid
        else:
            # A delayed room tick may process several edges. Charge only the
            # edges completed before this collision, not elapsed wall time.
            actor.combat.settle_walk(stop=True, completed_steps=state.index)
            actor.walk = None
            actor._completed_walk = None
            actor.pos = cell
            actor.cancel_passage()
            eid = actor.pid
        self.room.broadcast(('actionCancel', dict(id=eid, pos=cell, stop_aim=1)))
        if not isinstance(actor, mobs.Mob):
            actor.combat.c_ap()

    def advance(self, t=None):
        if self.advancing or not self.walks:
            return
        t = asyncio.get_running_loop().time() if t is None else t
        # Most position reads happen inside a step. No actor scan is needed
        # until an edge can finish; departures explicitly forget their walk.
        deadline = min(s.began + (s.index + 1) * self.step for s in self.walks.values())
        if deadline > t + TIME_EPSILON:
            return
        self.advancing = True
        try:
            present = {id(a) for a in self.actors()}
            for key, state in list(self.walks.items()):
                if key not in present or getattr(state.actor, 'walk', None) is None:
                    self.walks.pop(key, None)
            # Complete each claimed edge before claiming the next. Claims keep
            # simultaneous arrivals and head-on swaps out of the same hex.
            while self.walks:
                deadline = min(s.began + (s.index + 1) * self.step for s in self.walks.values())
                if deadline > t + TIME_EPSILON:
                    break
                due = [s for s in self.walks.values() if s.began + (s.index + 1) * self.step <= deadline + TIME_EPSILON]
                due_ids = {id(state.actor) for state in due}
                for state in due:
                    state.index += 1
                    if state.index == len(state.cells) - 1:
                        actor = state.actor
                        if not isinstance(actor, mobs.Mob):
                            actor._completed_walk = actor.walk
                        actor.walk = None
                        self.walks.pop(id(actor), None)
                occupied = {n.cell for n in self.room.npcs.values() if n.root != world.MOB}
                claims = {}
                for actor in self.actors():
                    occupied.add(self.cell(actor))
                    state = self.walks.get(id(actor))
                    if state and id(actor) not in due_ids:
                        claims[state.cells[state.index + 1]] = actor
                for state in due:
                    if id(state.actor) not in self.walks:
                        continue
                    dest = state.cells[state.index + 1]
                    if dest in occupied or dest in claims:
                        self.stop(state)
                    else:
                        claims[dest] = state.actor
        finally:
            self.advancing = False

    def tick(self):
        self.timer = None
        self.advance()
        self.schedule()

    def schedule(self):
        deadline = (min(s.began + (s.index + 1) * self.step for s in self.walks.values())
                    if self.walks else None)
        # Route changes often retain the current edge. Keep its scheduled
        # tick instead of churning cancelled handles in the event-loop heap.
        if self.timer is not None:
            if not self.timer.cancelled() and self.timer.when() == deadline:
                return
            self.timer.cancel()
            self.timer = None
        if deadline is not None:
            self.timer = asyncio.get_running_loop().call_at(deadline, self.tick)


def get(room):
    clock = getattr(room, 'motion', None)
    if clock is None:
        clock = room.motion = Motion(room)
    return clock
