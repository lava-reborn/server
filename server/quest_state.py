"""One database read for a burst of NPC quest availability requests.

Only quest history is cached. Level, equipment, money, events and territory
checks still run against the current state. Taking/handing in uses live SQL.
"""

SNAPSHOT_TTL = 2.0


class QuestState:
    def __init__(self, db, char_id, day_start, types=None):
        self.types = None if types is None else frozenset(types)
        self.active = set()
        self.history = {}
        self.loans = {}
        scope = "" if self.types is None else " AND type IN (%s)" % ",".join("?" for _ in self.types)
        if self.types == frozenset():
            scope = " AND 1 = 0"
        scope_args = tuple(self.types or ())
        args = (day_start, char_id, *scope_args, char_id, char_id,
                char_id, *scope_args)
        # Group once, then use the existing (char_id,type,done_at,id) index
        # for the first event's tie-break. A window over every history row
        # is unnecessary; id alone cannot substitute for chronological order.
        rows = db.execute("""
            WITH history AS (
                SELECT type, MIN(done_at) AS first_at, MAX(done_at) AS last_at,
                       SUM(CASE WHEN done_at >= ? THEN 1 ELSE 0 END) AS today
                FROM char_quests_done WHERE char_id = ? {scope}
                GROUP BY type
            )
            SELECT 0 AS source, type, 0 AS first_at, 0 AS first_id,
                   0 AS last_at, 0 AS today FROM char_quests WHERE char_id = ?
            UNION ALL
            SELECT 1, h.type, h.first_at,
                   (SELECT MIN(d.id) FROM char_quests_done d
                    WHERE d.char_id = ? AND d.type = h.type AND d.done_at = h.first_at),
                   h.last_at, h.today FROM history h
            UNION ALL
            SELECT 2, type, 0, 0, lent_at, 0 FROM char_lent WHERE char_id = ? {scope}
            """.format(scope=scope), args).fetchall()
        for row in rows:
            kind, t = row["source"], row["type"]
            if kind == 0:
                self.active.add(t)
            elif kind == 1:
                self.history[t] = (row["first_at"], row["first_id"],
                                   row["last_at"], row["today"])
            else:
                self.loans[t] = row["last_at"]

    def done(self, quest_type):
        return quest_type in self.history

    def today(self, quest_type):
        return self.history.get(quest_type, (0, 0, 0, 0))[3]

    def last(self, quest_type):
        row = self.history.get(quest_type)
        return row[2] if row else None

    def first_done(self, types):
        present = (t for t in types if t in self.history)
        return min(present, key=lambda t: self.history[t][:2], default=None)
