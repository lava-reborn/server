#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тот же Store, но поверх Postgres.

    LAVA_DB_URL=postgresql://lava:ПАРОЛЬ@172.18.0.1:5432/lava_test \\
        python3 server/test_storage_pg.py

Без `LAVA_DB_URL` набор молча пропускается: на машине разработчика
Postgres может и не стоять, а обычный прогон должен оставаться зелёным.

Проверяется не SQL как таковой, а то, ради чего затевался storage.py:
что одни и те же методы Store дают в Postgres тот же результат, что в
SQLite, — включая места, где диалекты расходятся: новый идентификатор,
INSERT OR REPLACE, уникальность логина, состав таблицы.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DSN = os.environ.get("LAVA_DB_URL", "").strip()
if not DSN:
    print("storage(pg): пропущено, LAVA_DB_URL не задан")
    sys.exit(0)

import accounts  # noqa: E402
import progression  # noqa: E402
import storage  # noqa: E402

checks = 0


def ok(cond, what):
    global checks
    assert cond, what
    checks += 1


def fresh_store():
    """Store на чистой схеме: таблицы сносим и создаём заново."""
    db = storage.connect()
    for table in ("mail", "map_marks", "items", "char_quests_done", "char_quests",
                  "char_stats", "online", "heartbeat", "admin_actions",
                  "characters", "accounts"):
        db.execute("DROP TABLE IF EXISTS %s CASCADE" % table)
    db.commit()
    db.close()
    return accounts.Store()


store = fresh_store()
ok(storage.using_postgres(), "работаем именно с Postgres")

# --- учётные записи --------------------------------------------------------
aid, err = store.register("боец", "пароль")
ok(err is None and aid, "учётка создана: %s %s" % (aid, err))
again, err = store.register("боец", "другой")
ok(again is None and err, "второй раз тот же логин не заводится: %r" % err)
ok(store.account_by_login("боец")["id"] == aid, "учётка ищется по логину")

# --- персонаж и его статы --------------------------------------------------
char_id, slot = store.create_character(aid, "Ветеран", 0, "45676")
ok(char_id and slot == 0, "персонаж создан: id %s, слот %s" % (char_id, slot))
rows = store.load_stats(char_id)
ok(len(rows) == len(progression.starting_rows()),
   "новорождённому розданы все статы: %d" % len(rows))

store.save_stats(char_id, [("skill", 1, 7, 640, 1280)])
after = {(r["kind"], r["idx"]): r for r in store.load_stats(char_id)}
ok(after[("skill", 1)]["value"] == 7 and after[("skill", 1)]["xp"] == 640,
   "перезапись стата прошла (ON CONFLICT): %s" % dict(after[("skill", 1)]))
ok(len(after) == len(rows), "перезапись не наплодила строк")

store.save_character_state(char_id, gold=500, afro=7)
row = store.character(char_id)
ok(row["gold"] == 500 and row["afro"] == 7, "деньги записались: %s" % dict(row))

# --- вещи, квесты, письма: у всех свой ключ --------------------------------
item = store.create_item(char_id, 45676, 1, count=3)
ok(item and item["uniq"], "предмет создан, ключ uniq: %s" % dict(item))
ok(item["count"] == 3, "поля предмета на месте")

q_id = store.take_quest(char_id, 1, {"step": 0}, False)
ok(q_id, "квест взят, ключ q_id: %s" % q_id)
ok(store.has_quest(char_id, 1), "квест виден")

letter = store.mail_send(char_id, char_id, 0, "привет", "текст", 0, 0, "[]")
ok(letter and letter["id"], "письмо отправлено, ключ id: %s" % letter["id"])

# --- очередь админки -------------------------------------------------------
action = store.admin_push("polestvr", "money", char_id=char_id, account_id=aid,
                          afro=100)
ok(action, "действие встало в очередь: %s" % action)
pending = store.admin_pending()
ok(len(pending) == 1 and pending[0]["kind"] == "money", "оно видно серверу игры")
store.admin_done(pending[0]["id"], "начислено")
ok(not store.admin_pending(), "после отметки очередь пуста")
ok(store.admin_recent()[0]["result"] == "начислено", "результат записан")

# --- схема -----------------------------------------------------------------
cols = store.db.columns("characters")
for col in ("id", "account_id", "name", "gold", "afro", "level", "rep"):
    ok(col in cols, "в characters есть %s" % col)

store.db.close()
print("storage(pg): %d проверок, все зелёные" % checks)
