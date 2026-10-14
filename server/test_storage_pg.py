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
INSERT OR REPLACE, уникальность логина, состав таблицы, rowcount,
транзакция после ошибки. И переезд: база, которую оставил прежний сервер
(без auction_lots, migrations и bank_steps), открывается новым — в том
числе двумя процессами разом, как их поднимает docker compose.

База под набор нужна своя: таблицы сносятся и создаются заново.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DSN = os.environ.get("LAVA_DB_URL", "").strip()
if not DSN:
    print("storage(pg): пропущено, LAVA_DB_URL не задан")
    sys.exit(0)

import psycopg  # noqa: E402

import accounts  # noqa: E402
import progression  # noqa: E402
import storage  # noqa: E402

checks = 0
TABLES = ("mail", "map_marks", "items", "char_quests_done", "char_quests",
          "char_stats", "online", "heartbeat", "admin_actions", "auction_lots",
          "migrations", "trophies", "clan_ledger", "clan_relations", "clan_members",
          "clans", "characters", "accounts", "money_ledger", "char_lent", "ground",
          "boss_kills", "clan_holdings", "clan_holding_log", "site_orders")
RELINK = "heal-relink-2026-09-23"


def ok(cond, what):
    global checks
    assert cond, what
    checks += 1


def fresh_store():
    """Store на чистой схеме: таблицы сносим и создаём заново."""
    db = storage.connect()
    for table in TABLES:
        db.execute("DROP TABLE IF EXISTS %s CASCADE" % table)
    db.commit()
    db.close()
    return accounts.Store()


def raises(fn, *exc):
    try:
        fn()
    except exc:
        return True
    return False


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
# Старт, вытянутый при создании (server.START_PLACES), ложится в ту же
# строку и местом, и пропиской; без него оба пусты, как у всех прежних.
west_acc, _ = store.register("западный", "пароль")
west_id, _ = store.create_character(west_acc, "Западный", 0, "1", home=(183, 6262, 1825))
row = store.character(west_id)
ok([row[k] for k in ("loc", "gx", "gy", "home_loc", "home_gx", "home_gy")]
   == [183, 6262, 1825, 183, 6262, 1825],
   "новичок записан со своим стартом — место и прописка одним INSERT: %s" % dict(row))
row = store.character(char_id)
ok([row[k] for k in ("loc", "gx", "gy", "home_loc", "home_gx", "home_gy")] == [None] * 6,
   "без старта место и прописка пусты: %s" % dict(row))
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
ok(row["bank_steps"] == 0, "bank_steps у новорождённого 0")
store.save_character_state(char_id, bank_steps=2)
ok(store.character(char_id)["bank_steps"] == 2, "покупка хранилища записывается")

# --- вещи, квесты, письма: у всех свой ключ --------------------------------
item = store.create_item(char_id, 45676, 1, count=3)
ok(item and item["uniq"], "предмет создан, ключ uniq: %s" % dict(item))
ok(item["count"] == 3, "поля предмета на месте")

# Мешки на земле прошлого запуска: строки ничьи (char_id 0, combat.LOOT_OWNER).
# Сервер игры стирает их при старте и пишет в журнал, сколько, — rowcount.
ground = [store.create_item(0, 6910, 4)["uniq"] for _ in range(2)]
ok(store.clear_ground(0) == 2, "ничьи вещи с земли стираются, счёт по rowcount")
ok([store.item(u) for u in ground] == [None, None], "их больше нет")
ok(store.item(item["uniq"]) is not None, "а вещь персонажа на месте")
ok(store.clear_ground(0) == 0, "на пустой земле — ноль, не ошибка")

q_id = store.take_quest(char_id, 1, {"step": 0}, False)
ok(q_id, "квест взят, ключ q_id: %s" % q_id)
ok(store.has_quest(char_id, 1), "квест виден")

# Дневной лимит считает только повторяемые: types — список «IN (?, ?)».
for t in (1, 2, 2, 5):
    store.finish_quest(0, char_id, t, when=1000)
ok(store.quests_done_since(char_id, 999) == 4, "сдачи с момента: все")
ok(store.quests_done_since(char_id, 999, [2, 5]) == 3, "сдачи с момента: только этих типов")
ok(store.quests_done_since(char_id, 999, []) == 0, "пустой список типов — ноль, не ошибка")
ok(store.quests_done_since(char_id, 1001, [2, 5]) == 0, "раньше момента не считаются")
# Какая ветка выбора сдана первой (Session.excluded): раньше по done_at, а в
# одну секунду — та, что записана первой.
ok(store.first_done(char_id, [5, 2]) == 2, "первая сдача: в одну секунду — по порядку записи")
store.finish_quest(0, char_id, 7, when=900)
ok(store.first_done(char_id, [2, 7]) == 7, "первая сдача: раньше по времени, хоть и записана позже")
ok(store.first_done(char_id, [42]) is None, "не сдан ни один из типов — None")
ok(store.first_done(char_id, []) is None, "пустой список типов — None, не ошибка")

letter = store.mail_send(char_id, char_id, 0, "привет", "текст", 0, 0, "[]")
ok(letter and letter["id"], "письмо отправлено, ключ id: %s" % letter["id"])

# --- метки карты: rowcount -------------------------------------------------
# PgCursor не знал rowcount, и update_mark (updMark с клиента) падал на
# AttributeError — ещё в сервере, который работал на Postgres до этой правки.
idx = store.insert_mark(char_id, 6000, 1700, "Лагерь", "")
ok(store.update_mark(char_id, idx, "Лагерь мобов", "стая") is True,
   "правка метки: update_mark по rowcount отвечает True")
ok([(m["title"], m["info"]) for m in store.marks(char_id)] == [("Лагерь мобов", "стая")],
   "правка записана")
ok(store.update_mark(char_id, 7, "x", "y") is False, "метки 7 нет: False, а не исключение")
ok(store.remove_mark(char_id, idx) and store.marks(char_id) == [], "метка удаляется")

# --- ошибка не оставляет соединение без базы -------------------------------
# В Postgres неудачный оператор обрывает всю транзакцию, и без отката
# соединение на всё отвечает «current transaction is aborted». У сервера
# игры оно одно на всех игроков.
ok(raises(lambda: store.db.execute("SELECT no_such_column FROM accounts"), psycopg.Error),
   "кривой запрос падает")
ok(store.account_by_login("боец")["id"] == aid, "а следующий запрос отвечает")
store.add_money(char_id, afro=1)
ok(store.character(char_id)["afro"] == 8, "и запись после ошибки фиксируется")


def half_done():
    with store.db:
        store.db.execute("UPDATE characters SET afro = 999 WHERE id = ?", (char_id,))
        store.db.execute("SELECT no_such_column FROM accounts")


ok(raises(half_done, psycopg.Error), "ошибка посреди with доходит до вызывающего")
ok(store.character(char_id)["afro"] == 8, "и откатывает всю транзакцию, как в SQLite")
# То, чем это грозило на деле: сумма из панели за пределами BIGINT. SQLite
# отказывает ещё в драйвере (OverflowError), Postgres — самой базой, и
# без отката очередь админки после этого не могла даже отметить действие
# сделанным (admin_done) и повторяла его каждую секунду.
ok(raises(lambda: store.add_money(char_id, afro=10 ** 19), psycopg.Error),
   "10**19 афро не влезает в BIGINT")
store.admin_done(0, "проверка")
ok(store.money(char_id) == (8, 500), "кошелёк цел, а соединение пишет дальше")
# Деньги, репутация, bank_steps досоздаются через ALTER TABLE (migrate), и
# тип им должен достаться тот же, что остальным: INTEGER в SQLite — 64 бита.
types = {r["column_name"]: r["data_type"] for r in store.db.execute(
    "SELECT column_name, data_type FROM information_schema.columns"
    " WHERE table_name = 'characters'")}
ok({types[c] for c, _d in accounts.CHARACTER_COLUMNS} == {"bigint"},
   "досозданные колонки characters — BIGINT: %s" % types)
store.add_money(char_id, afro=3 * 10 ** 9)
ok(store.money(char_id)[0] == 3 * 10 ** 9 + 8, "три миллиарда афро помещаются, как в SQLite")
store.add_money(char_id, afro=-3 * 10 ** 9)

# --- аукцион: транзакции, identity, письма от персонажа 0 -------------------
other_acc, _ = store.register("покупатель", "пароль")
other, _ = store.create_character(other_acc, "Покупатель", 0, "1")
now = time.time()


def lot_fields(row, **kw):
    snap = {"uniq": row["uniq"], "type_id": row["type_id"], "root": row["root"]}
    snap.update({f: row[f] for f in accounts.ITEM_FIELDS})
    return dict(dict(type_id=row["type_id"], root=row["root"], item_json=json.dumps(snap),
                     seller=char_id, seller_name="Ветеран", currency=0, start_bid=100,
                     buyout=500, fee=5, hours=24, created_at=int(now), ends_at=now + 60), **kw)


def letter_to(to_char, **kw):
    return dict(dict(to_char=to_char, from_char=0, kind=0, subject="Аукцион: ",
                     body="", afro=0, gold=0, items_json="[]"), **kw)


gun = store.create_item(char_id, 25586, 3)
lot = store.auction_list(gun["uniq"], char_id, lot_fields(gun), purse=(char_id, 3, 500))
ok(lot and lot["id"] and lot["item_uniq"] == gun["uniq"], "лот выставлен: %s" % lot)
ok(isinstance(lot["ends_at"], float) and abs(lot["ends_at"] - (now + 60)) < 1e-3,
   "ends_at — число с дробью, как REAL в SQLite: %r" % lot["ends_at"])
ok(store.item(gun["uniq"]) is None, "вещь ушла из items")
ok(store.money(char_id) == (3, 500), "кошелёк продавца записан той же транзакцией")
ok(store.auction_lot_by_item(gun["uniq"])["id"] == lot["id"], "лот ищется по вещи")
ok(store.auction_count(char_id, now) == 1 and len(store.auction_active(now)) == 1
   and store.auction_due(now) == [], "счёт, активные и истёкшие")

theirs = store.create_item(other, 25586, 3)
ok(raises(lambda: store.auction_list(theirs["uniq"], char_id, lot_fields(theirs)), ValueError),
   "чужую вещь выставить нельзя")
ok(store.item(theirs["uniq"]) is not None, "и она не тронута")


def twice():
    with store.db:
        store.db.insert("INSERT INTO auction_lots (%s) VALUES (%s)"
                        % (", ".join(store.AUCTION_COLS), ", ".join("?" * len(store.AUCTION_COLS))),
                        [dict(lot_fields(gun), item_uniq=gun["uniq"])[c]
                         for c in store.AUCTION_COLS])


ok(raises(twice, storage.IntegrityError), "одна вещь — один лот: UNIQUE (item_uniq) доехал")
ok(len(store.auction_active(now)) == 1, "и соединение после этого живое")

sent = store.auction_rebid(lot["id"], 150, other, "Покупатель",
                           [letter_to(char_id, afro=100)], purse=(other, 850, 0))
ok([(m["from_char"], m["to_char"], m["afro"]) for m in sent] == [(0, char_id, 100)],
   "письмо от персонажа 0 проходит: внешних ключей в Postgres нет")
ok(store.auction_lot(lot["id"])["bid"] == 150 and store.money(other) == (850, 0),
   "ставка и кошелёк покупателя записаны вместе")
ok(store.db.execute(
    "SELECT COUNT(*) c FROM information_schema.table_constraints"
    " WHERE constraint_type = 'FOREIGN KEY'").fetchone()["c"] == 0,
   "ни одного FOREIGN KEY в схеме")

lot2 = store.auction_list(theirs["uniq"], other, lot_fields(theirs, seller=other))


def broken_close():
    store.auction_close(lot2["id"], [letter_to(other, subject=None)])


ok(raises(broken_close, psycopg.Error), "закрытие с негодным письмом падает")
ok(store.auction_lot(lot2["id"]) is not None, "и откатывается целиком: лот на месте")
sent = store.auction_close(lot["id"], [letter_to(other, items_json=lot["item_json"])])
ok(len(sent) == 1 and json.loads(sent[0]["items_json"])["uniq"] == gun["uniq"],
   "лот закрыт, вещь уехала письмом")
ok(store.auction_close(lot["id"], []) is None, "и закрыт один раз")
ok(store.auction_rebid(lot["id"], 200, other, "x") is None, "ставка на закрытый лот: None")
ok(lot2["id"] > lot["id"], "id лотов раздаёт identity")

# --- бартер: обе половины одной транзакцией ---------------------------------
# Вещь переходит UPDATE-ом, который называет её такой, какой её выложили;
# rowcount решает, прошла ли она, а неудача на любой вещи откатывает и те,
# что прошли до неё, и оба кошелька (Store.barter_swap).
mine = store.create_item(char_id, 25586, 0, brk=80, max_break_cur=100)
yours = store.create_item(other, 6188, 3, count=20)
store.save_character_state(char_id, afro=100, gold=0)
store.save_character_state(other, afro=0, gold=40)
ok(store.barter_swap([(mine, other), (yours, char_id)],
                     [(char_id, 70, 15), (other, 30, 25)]) is None,
   "бартер прошёл: None")
ok((store.item(mine["uniq"])["char_id"], store.item(yours["uniq"])["char_id"])
   == (other, char_id), "вещи поменялись хозяевами")
ok((store.money(char_id), store.money(other)) == ((70, 15), (30, 25)),
   "и кошельки записаны той же транзакцией")
mine, yours = store.item(mine["uniq"]), store.item(yours["uniq"])
store.update_item(yours["uniq"], count=19)
ok(store.barter_swap([(mine, char_id), (yours, other)],
                     [(char_id, 0, 0), (other, 0, 0)]) == yours["uniq"],
   "стопка изменилась после того, как её выложили: её номер назад")
ok((store.item(mine["uniq"])["char_id"], store.item(yours["uniq"])["char_id"])
   == (other, char_id), "и откат целиком: даже первая вещь осталась, где была")
ok((store.money(char_id), store.money(other)) == ((70, 15), (30, 25)),
   "кошельки не тронуты")
ok(store.characters(aid) is not None, "и соединение после отката живое")

# --- журнал денег: строка на каждое изменение кошелька ------------------------
# Строка пишется в той же транзакции, что и кошелёк (accounts.book): разница
# с тем, что было в строке персонажа, источник и уровень. Откат бартера выше
# не оставил своих строк -- их и не было: кошельки не тронуты.
led = store.ledger(char_id)
ok([(r["source"], r["afro"], r["gold"]) for r in led][:1] == [("start", progression.START_AFRO, 0)],
   "первая строка -- кошелёк новорождённого: %s" % led[:1])
ok([(r["source"], r["ref"], r["afro"], r["gold"]) for r in led if r["source"] == "barter"]
   == [("barter", other, -30, 15)], "бартер записан один раз, с другой стороной: %s" % led)
ok([(r["source"], r["ref"], r["afro"], r["gold"]) for r in store.ledger(other)
    if r["source"] == "barter"] == [("barter", char_id, 30, -15)], "и у другой стороны")
ok(sum(r["afro"] for r in led) == store.money(char_id)[0]
   and sum(r["gold"] for r in led) == store.money(char_id)[1],
   "сумма журнала -- это кошелёк: %s" % (store.money(char_id),))
with store.booked_as("quest", 9):
    store.save_character_state(char_id, afro=70, gold=115, level=3)
last = store.ledger(char_id)[-1]
ok((last["source"], last["ref"], last["afro"], last["gold"], last["level"])
   == ("quest", 9, 0, 100, 3), "источник из booked_as, уровень из той же записи: %s" % last)
n = len(store.ledger(char_id))
store.save_character_state(char_id, afro=70, gold=115)
ok(len(store.ledger(char_id)) == n, "запись без изменения денег строки не пишет")
ok(isinstance(last["id"], int) and last["id"] > led[-1]["id"], "id раздаёт identity")
store.note_lent(char_id, 90013, 1000)
store.note_lent(char_id, 90013, 2000)
ok(store.lent_at(char_id, 90013) == 2000 and store.lent_at(char_id, 1) is None,
   "выданные патроны: одна строка на квест, перезапись через ON CONFLICT")
store.forget_lent(char_id, 90013)
ok(store.lent_at(char_id, 90013) is None, "заём вычеркнут: всё вернулось неизрасходованным")

# --- гибель: всё, что выпало, одной транзакцией -----------------------------
# Целая вещь уходит на землю (char_id 0) под своим номером, от стопки
# отщепляется новая строка — её uniq раздаёт identity через RETURNING, — а
# строка, изменившаяся после чтения, откатывает всю гибель (Store.drop_items).
boots = store.create_item(char_id, 10183, 1, slot=261, brk=70, max_break_cur=75)
stack = store.create_item(char_id, 6188, 3, count=20)
ground = store.drop_items(char_id, [(boots, None), (stack, 7)], 0, 2048)
ok(ground is not None and [(r["char_id"], r["slot"], r["count"]) for r in ground]
   == [(0, 2048, 1), (0, 2048, 7)], "выпало: сапоги целиком и семь патронов: %r" % ground)
ok(ground[0]["uniq"] == boots["uniq"] and ground[0]["brk"] == 70,
   "сапоги — та же строка, с износом")
ok(ground[1]["uniq"] > stack["uniq"] and ground[1]["type_id"] == 6188,
   "семь патронов — новая строка с новым uniq")
ok(store.item(stack["uniq"])["count"] == 13, "в стопке осталось тринадцать")
other = store.create_item(char_id, 25566, 0, brk=50, max_break_cur=50)
ok(store.drop_items(char_id, [(other, None), (stack, 7)], 0, 2048) is None,
   "стопка уже не та, что прочитана: None")
ok(store.item(other["uniq"])["char_id"] == char_id
   and store.item(stack["uniq"])["count"] == 13,
   "и откат целиком: и вещь перед ней осталась у персонажа")
ok(store.characters(aid) is not None, "и соединение после отката живое")

# --- трофеи: вещь и её слова одной транзакцией, регистрация — тоже ----------
# Трофей — строка items (корень 6) и строка trophies под тем же uniq: ключ
# раздаёт identity items через RETURNING, в trophies он вписан явно (своего
# счётчика там нет). Регистрация (trophies.Collection.register) — одна
# транзакция: вещь из рюкзака, слова в коллекцию, кошелёк и навык бойца.
T0 = 1_790_000_000
buyer = store.character_by_name("Покупатель")["id"]


def words(**kw):
    return dict(dict(killer_id=char_id, killer_name="Ветеран", killer_lvl=0,
                     victim_id=buyer, victim_name="Покупатель", victim_lvl=0,
                     victim_clan="", killed_at=T0), **kw)


ok(store.db.execute("SELECT data_type FROM information_schema.columns WHERE table_name ="
                    " 'trophies' AND column_name = 'registered_at'").fetchone()["data_type"]
   == "bigint", "trophies.registered_at — BIGINT, NULL разрешён")
ear = store.create_trophy(0, 2048, 1495, 6, words())
ok(ear["uniq"] and store.trophy(ear["uniq"])["type_id"] == 1495
   and store.trophy(ear["uniq"])["registered_at"] is None,
   "трофей создан: вещь на земле и её слова под одним uniq: %s" % ear["uniq"])
store.update_item(ear["uniq"], char_id=char_id)
ear = store.item(ear["uniq"])
store.save_character_state(char_id, afro=100, gold=0, rep=0)
store.update_item(ear["uniq"], slot=4096)
ok(store.register_trophy(ear, store.trophy(ear["uniq"]), char_id, T0 + 60, True,
                         (char_id, 75, 0), 10) is False,
   "вещь уже не там, где её прочли: регистрация отказана")
ok(store.item(ear["uniq"]) is not None and store.trophy(ear["uniq"])["registered_at"] is None
   and store.money(char_id) == (100, 0) and store.character(char_id)["rep"] == 0,
   "и откат целиком: вещь, слова, кошелёк, навык")
store.update_item(ear["uniq"], slot=2048)
ear = store.item(ear["uniq"])
ok(store.register_trophy(ear, store.trophy(ear["uniq"]), char_id, T0 + 60, True,
                         (char_id, 75, 0), 10) is True, "регистрация прошла")
kept = store.trophies_of(char_id)
ok(store.item(ear["uniq"]) is None and [(r["uniq"], r["owner"], r["paid_at"]) for r in kept]
   == [(ear["uniq"], char_id, T0 + 60)] and store.money(char_id) == (75, 0)
   and store.character(char_id)["rep"] == 10,
   "вещи нет, слова в коллекции, оплачено; кошелёк и навык записаны: %s" % kept)
ok(store.trophy_paid_since(char_id, buyer, T0 + 60 - 3600)
   and not store.trophy_paid_since(char_id, buyer, T0 + 60),
   "пара оплачена в этот час, и не позже")
second = store.create_trophy(char_id, 2048, 1495, 6, words(killed_at=T0 + 600, victim_lvl=1))
into = store.trophy_like(char_id, 1495, buyer)
ok(into and into["uniq"] == ear["uniq"], "второе ухо той же жертвы находит первое")
ok(store.register_trophy(second, store.trophy(second["uniq"]), char_id, T0 + 700, False,
                         (char_id, 50, 0), 10, into) is True, "и вливается в него")
kept = store.trophies_of(char_id)
ok([(r["kills"], r["killed_at"], r["victim_lvl"], r["paid_at"]) for r in kept]
   == [(2, T0 + 600, 1, T0 + 60)] and store.trophy(second["uniq"]) is None,
   "одна запись: два убийства, время и уровни новее, отметка оплаты прежняя: %s" % kept)
ok(store.register_trophy(second, words(), char_id, T0 + 800, False, (char_id, 0, 0), 10)
   is False and store.money(char_id) == (50, 0), "повтор той же вещи: отказ, кошелёк цел")
lost = store.create_trophy(char_id, 2048, 1492, 6, words())
store.rekey_trophy(lost["uniq"], lost["uniq"] + 1000)
ok(store.trophy(lost["uniq"]) is None and store.trophy(lost["uniq"] + 1000)["type_id"] == 1492,
   "слова идут за трофеем под новый uniq (письмо)")
lying = store.create_trophy(0, 2048, 1493, 6, words())
on_ground = len(store.items_of(0))      # with what the death above left there
ok(store.clear_ground(0) == on_ground and store.trophy(lying["uniq"]) is None
   and store.trophies_of(char_id), "чистка земли уносит слова лежавшего, коллекцию — нет")
ok(store.delete_trophy(ear["uniq"], buyer) is False and store.delete_trophy(ear["uniq"], char_id)
   and store.trophies_of(char_id) == [], "чужой не удалит, хозяин — да")
ok(store.trophy_paid_since(char_id, buyer, T0 + 60 - 3600)
   and store.trophy_like(char_id, 1495, buyer) is None
   and store.delete_trophy(ear["uniq"], char_id) is False,
   "удалённая запись хранит отметку оплаты пары: час не сбрасывается")
ok(store.characters(aid) is not None, "и соединение после всего этого живое")

# --- витрина трофеев: место записи коллекции и купленные места ----------------
# trophies.shown — место записи на витрине (NULL — только в коллекции),
# characters.trophy_places — сколько мест куплено; обе колонки досоздаются
# ALTER TABLE (accounts.TROPHY_COLUMNS, CHARACTER_COLUMNS) и в Postgres
# должны выйти BIGINT, как соседние.
for table, col in (("trophies", "shown"), ("characters", "trophy_places")):
    ok(store.db.execute("SELECT data_type FROM information_schema.columns WHERE table_name ="
                        " ? AND column_name = ?", (table, col)).fetchone()["data_type"]
       == "bigint", "%s.%s — BIGINT" % (table, col))


def registered(type_id, victim):
    t = store.create_trophy(char_id, 2048, type_id, 6, words(victim_id=victim))
    ok(store.register_trophy(t, store.trophy(t["uniq"]), char_id, T0 + 900, False,
                             (char_id, 50, 0), 10), "запись %d в коллекции" % t["uniq"])
    return t["uniq"]


skull, scalp = registered(1492, buyer + 100), registered(1493, buyer + 101)
ok(store.shown_trophies(char_id) == {}, "на витрине пусто")
ok(store.show_trophy(char_id, 0, skull) and store.show_trophy(char_id, 2, skull)
   and sorted(store.shown_trophies(char_id)) == [2],
   "запись переезжает с места на место, а не встаёт дважды")
ok(store.show_trophy(char_id, 2, scalp) and store.trophy(skull)["shown"] is None
   and store.shown_trophies(char_id)[2]["uniq"] == scalp,
   "другая на то же место — прежняя обратно только в коллекцию")
ok(store.show_trophy(buyer, 0, scalp) is False and store.show_trophy(char_id, 2, 999999) is False
   and store.shown_trophies(char_id)[2]["uniq"] == scalp,
   "чужую и несуществующую не показать, и отказ места не освобождает (откат)")
ok(store.delete_trophy(scalp, char_id) and store.shown_trophies(char_id) == {}
   and store.trophy(scalp)["shown"] is None, "удалённая уходит и с витрины")
ok(store.show_trophy(char_id, 1, skull) and store.show_trophy(char_id, 1)
   and store.shown_trophies(char_id) == {}, "пустой obj освобождает место")
store.save_character_state(char_id, afro=700, gold=3)
ok(store.character(char_id)["trophy_places"] == 0
   and store.buy_trophy_place(char_id, 0, 200, 3) == 1
   and store.character(char_id)["trophy_places"] == 1 and store.money(char_id) == (200, 3),
   "место куплено: счётчик и кошелёк одной транзакцией")
ok(store.buy_trophy_place(char_id, 0, 0, 0) is None
   and store.character(char_id)["trophy_places"] == 1 and store.money(char_id) == (200, 3),
   "покупка по устаревшему счётчику не проходит, кошелёк цел")
ok(store.characters(aid) is not None, "и соединение после витрины живое")

# --- земля: где лежит вещь и до каких пор (таблица ground) --------------------
# Правило владельца (2026-09-28): вещь на земле лежит 15 минут с того мига,
# как легла, есть кто в локации или нет, и перезапуск этого не обрывает.
# Место и срок — строка ground под uniq вещи: ключ вписан явно (identity
# его не раздаёт), gx/gy — NULL у места, которое одна комната, срок — в
# долях секунды (DOUBLE PRECISION), lay_down поверх записанной — ON CONFLICT.
T = 1_800_000_000.5
keep, late, gone_, bare = [store.create_item(0, 6910, 4)["uniq"] for _ in range(4)]
store.lay_down({keep: T + 100, gone_: T - 1}, (100, None, None), 4363)
store.lay_down({late: T + 50.25}, (7, 5833, 1600), 9)
ok([(r["uniq"], r["loc"], r["gx"], r["gy"], r["cell"], r["expires_at"])
    for r in store.on_ground(0)]
   == [(keep, 100, None, None, 4363, T + 100), (late, 7, 5833, 1600, 9, T + 50.25),
       (gone_, 100, None, None, 4363, T - 1)],
   "записано: место, клетка карты или NULL, срок до долей секунды: %s" % store.on_ground(0))
store.lay_down({keep: T + 300}, (100, None, None), 4430)
ok([(r["cell"], r["expires_at"]) for r in store.on_ground(0) if r["uniq"] == keep]
   == [(4430, T + 300)], "записанная второй раз — переписана, не задвоена")
ok(store.clear_ground(0, T) == 2 and [store.item(u) for u in (gone_, bare)] == [None, None]
   and [r["uniq"] for r in store.on_ground(0)] == [keep, late],
   "старт: истёкшая и никогда не записанная стёрты (rowcount), остальные лежат")
store.pick_up([keep], char_id, 2048)
ok(store.item(keep)["char_id"] == char_id and [r["uniq"] for r in store.on_ground(0)] == [late],
   "подобрал: вещь его под тем же uniq, строки земли у неё нет")
store.lay_down({keep: T + 100}, (100, None, None), 4363)
ok(store.clear_ground(0, T) == 0 and store.item(keep)["char_id"] == char_id
   and store.db.execute("SELECT COUNT(*) c FROM ground").fetchone()["c"] == 1,
   "строка земли у чужой вещи стирается, сама вещь — нет")
ear2 = store.create_trophy(0, 2048, 1492, 6, words())
store.lay_down({ear2["uniq"]: T + 10}, (100, None, None), 4363)
store.lay_down({keep: T + 100}, (100, None, None), 4363)
store.sweep_ground([late, ear2["uniq"], keep], 0)
ok(store.item(late) is None and store.item(ear2["uniq"]) is None
   and store.trophy(ear2["uniq"]) is None and store.item(keep)["char_id"] == char_id
   and store.on_ground(0) == []
   and store.db.execute("SELECT COUNT(*) c FROM ground").fetchone()["c"] == 0,
   "срок вышел: вещь, слова трофея и строка — одной транзакцией; чужая вещь цела")
for col, kind in (("expires_at", "double precision"), ("gx", "bigint"), ("uniq", "bigint")):
    ok(store.db.execute("SELECT data_type FROM information_schema.columns WHERE table_name ="
                        " 'ground' AND column_name = ?", (col,)).fetchone()["data_type"] == kind,
       "ground.%s — %s" % (col, kind))
ok(store.characters(aid) is not None, "и соединение после земли живое")

# --- боссы, убитые в своё окно часов (таблица boss_kills) ---------------------
# Убитый босс ждёт следующего часа, и перезапуск посреди окна не должен
# ставить его снова (со слитками в мешке): убийство записано строкой по
# месту босса, окно — секунда его начала (DOUBLE PRECISION), повторное
# убийство пишет поверх (ON CONFLICT по spot).
KAIS, DOUGLAS = "87:-:-:4321:314", "34:-:-:99:2103"
W18, W20 = 1_791_558_000.0, 1_791_565_200.0
ok(store.boss_kills([KAIS, DOUGLAS]) == {}, "пока никто не убит — пусто")
store.boss_killed(KAIS, W18)
store.boss_killed(DOUGLAS, W18)
store.boss_killed(KAIS, W20)
ok(store.boss_kills([KAIS, DOUGLAS, "1:-:-:1:1"]) == {KAIS: W20, DOUGLAS: W18},
   "записано по месту, второе убийство переписало первое: %s"
   % store.boss_kills([KAIS, DOUGLAS]))
ok(store.db.execute("SELECT COUNT(*) c FROM boss_kills").fetchone()["c"] == 2,
   "по строке на босса, не задвоено")
ok(store.boss_kills([]) == {}, "пустой список мест — пусто, без запроса")
ok(store.db.execute("SELECT data_type FROM information_schema.columns WHERE table_name ="
                    " 'boss_kills' AND column_name = 'slot'").fetchone()["data_type"]
   == "double precision", "boss_kills.slot — double precision")
ok(store.characters(aid) is not None, "и соединение после боссов живое")

# --- очередь админки -------------------------------------------------------
action = store.admin_push("Archivist", "money", char_id=char_id, account_id=aid,
                          afro=100)
ok(action, "действие встало в очередь: %s" % action)
pending = store.admin_pending()
ok(len(pending) == 1 and pending[0]["kind"] == "money", "оно видно серверу игры")
store.admin_done(pending[0]["id"], "начислено")
ok(not store.admin_pending(), "после отметки очередь пуста")
ok(store.admin_recent()[0]["result"] == "начислено", "результат записан")

# --- кланы: каждая перемена одной транзакцией -------------------------------
# Схема: UNIQUE имени написан в CREATE TABLE, а не отдельным CREATE UNIQUE
# INDEX, — pg_schema дописывает IF NOT EXISTS только обычному индексу, и
# второй запуск сервера на Postgres упал бы. Проверяем, что он доехал и что
# схема ложится второй раз без ошибки.
ok({"clans", "clan_members", "clan_relations", "clan_ledger"}
   <= {r["table_name"] for r in store.db.execute(
       "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")},
   "четыре клановые таблицы созданы")
# Чтение в Postgres тоже открывает транзакцию; прежде чем второй Store
# пройдёт migrate (ALTER TABLE ждёт всех читавших), эту закрываем.
store.db.commit()
again = accounts.Store()
ok(again.clan_all() == [], "схема легла второй раз без ошибки")
again.close()
ok({"clan_no_invites", "seen_at"} <= store.db.columns("characters"),
   "в characters есть clan_no_invites и seen_at")
store.save_character_state(char_id, afro=1000, gold=2500)
store.save_character_state(buyer, afro=10, gold=0)
wolves = store.clan_create(char_id, "Волки", "волки", "стая", (char_id, 1000, 1500))
ok(wolves and store.clan(wolves)["head"] == char_id
   and store.clan_member(char_id)["perm"] == 65535,
   "клан основан, глава с 65535: id %s" % wolves)
ok(store.money(char_id) == (1000, 1500) and [(r["source"], r["ref"], r["gold"])
                                             for r in store.ledger(char_id)][-1]
   == ("clan_create", wolves, -1000), "взнос списан и записан clan_create той же транзакцией")
ok(store.clan_create(buyer, "ВОЛКИ", "волки", "", (buyer, 10, 0)) is None,
   "то же имя (ключ) второй раз: None — UNIQUE (name_key) доехал")
ok(store.clan_member(buyer) is None and store.money(buyer) == (10, 0),
   "и ни члена, ни списания; соединение живое")
ok(raises(lambda: store.clan_create(buyer, "Лисы", "лисы", "", (buyer, None, 0)), TypeError),
   "основание с негодным кошельком падает")
ok(store.clan_by_key("лисы") is None and store.clan_member(buyer) is None,
   "и откатывается целиком: ни клана, ни члена")
ok(store.clan_member_add(buyer, wolves, 0x2, "Боец", char_id) is True
   and store.clan_member(buyer)["post"] == "Боец", "вступление")
ok(raises(lambda: store.clan_member_add(buyer, wolves, 0x2, "", char_id), storage.IntegrityError),
   "второй клан одному персонажу — IntegrityError, наружу, а не внутри транзакции")
ok(store.clan_member(buyer)["clan_id"] == wolves, "и соединение живое, членство прежнее")
ok(store.clan_treasury_adjust(wolves, 300, "admin") == 300, "казна пополнена админом")
ok(store.clan_treasury_move(wolves, buyer, 5, (buyer, 5, 0)) == 305
   and store.money(buyer) == (5, 0), "взнос члена: казна и кошелёк одной транзакцией")
ok([(r["source"], r["afro"]) for r in store.clan_ledger_rows(wolves)]
   == [("deposit", 5), ("admin", 300)], "журнал казны: %s" % store.clan_ledger_rows(wolves))
ok(store.clan_treasury_move(wolves, buyer, -400, (buyer, 405, 0)) is None
   and store.money(buyer) == (5, 0) and store.clan_treasury(wolves) == 305,
   "снять больше, чем в казне: None, ничего не записано")

# Две сессии снимают всю казну разом: строку clans держит первый UPDATE,
# второй ждёт его фиксации, перечитывает условие (afro >= ?) и не находит
# строки — снято один раз.
import threading  # noqa: E402

store.db.commit()
second = accounts.Store()
first = storage.connect()
first.execute("UPDATE clans SET afro = afro - 305 WHERE id = ? AND afro >= 305", (wolves,))
race = {}
worker = threading.Thread(target=lambda: race.update(
    got=second.clan_treasury_move(wolves, buyer, -305, (buyer, 310, 0))))
worker.start()
time.sleep(0.7)
ok(worker.is_alive(), "вторая сессия ждёт блокировку строки казны")
first.commit()
worker.join(15)
ok(race.get("got", "нет ответа") is None and store.clan_treasury(wolves) == 0
   and store.money(buyer) == (5, 0), "и после фиксации первой не снимает ничего: %s" % race)
first.close()
second.close()

# Уход главы: клан переходит к старшему; уход последнего — роспуск, казна
# в кошелёк уходящего (переданный — живого Character, или строки), одной
# транзакцией.
ok(store.clan_leave(char_id, wolves, purse=(char_id, 1000, 1500))
   == {"new_head": buyer, "disbanded": False, "paid": 0}
   and store.clan(wolves)["head"] == buyer and store.clan_member(buyer)["perm"] == 65535
   and store.clan_member(char_id) is None, "глава ушёл: клан у оставшегося, 65535 у него")
store.clan_treasury_adjust(wolves, 40, "admin")
ok(raises(lambda: store.clan_leave(buyer, wolves, purse=(buyer, None, 0)), TypeError)
   and store.clan(wolves)["afro"] == 40 and store.clan_member(buyer) is not None,
   "роспуск с негодным кошельком откатывается целиком: клан, член и казна на месте")
ok(store.clan_leave(buyer, wolves, purse=(buyer, 5, 0))
   == {"new_head": None, "disbanded": True, "paid": 40}
   and store.clan(wolves) is None and store.money(buyer) == (45, 0),
   "последний ушёл: клан распущен, 40 афро в кошелёк")
ok([(r["source"], r["ref"], r["afro"]) for r in store.ledger(buyer)][-1]
   == ("clan_disband", wolves, 40)
   and [(r["source"], r["afro"]) for r in store.clan_ledger_rows(wolves)][0] == ("disband", -40),
   "в обоих журналах: clan_disband +40 и disband -40")
foxes = store.clan_create(char_id, "Лисы", "лисы", "", None)
store.clan_member_add(buyer, foxes, 0x2, "", char_id)
store.clan_relation_set(foxes, 999, -1)
store.clan_relation_set(foxes, 999, 1)
ok(store.clan_relations_of(foxes) == {999: 1} and store.clan_relation(999, foxes) == 0,
   "отношение перезаписывается (ON CONFLICT), и оно одностороннее")
store.clan_treasury_adjust(foxes, 70, "admin")
ok(store.clan_disband(foxes, buyer) == 70 and store.money(buyer) == (115, 0)
   and store.clan_relations_of(foxes) == {} and store.clan_member(buyer) is None,
   "админский роспуск: казна в кошелёк строки, отношения и члены ушли")
ok(store.clan_disband(foxes, buyer) is None, "второй роспуск того же клана: None")
bears = store.clan_create(buyer, "Медведи", "медведи", "", None)
store.clan_member_add(char_id, bears, 0x100 | 0x2, "", buyer)
with store.db:
    handed = accounts.clan_hand_over(store.db, buyer)
ok(handed == (bears, char_id, 0) and store.clan(bears)["head"] == char_id,
   "инструмент админа передаёт клан удаляемого главы: %s" % (handed,))
ok(store.characters(aid) is not None, "и соединение после кланов живое")

# --- склады кланов (clan_holdings, clan_holding_log; server/holdings.py) ----------
# Кто держит склад, пишется INSERT ... SELECT ... WHERE EXISTS ... ON CONFLICT:
# только за клан, который ещё есть, и поверх прежнего держателя. У приказа
# админки by_char и slot — NULL, параметры без типа, и в Postgres они должны
# лечь в типы колонок. Тот же клан второй раз не пишет ничего; снять склад
# можно только с клана, который его держит; роспуск забирает склады той же
# транзакцией и пишет каждому строку 'disband'.
rivals = store.clan_create(west_id, "Соперники", "соперники", "", None)
ok(store.holding("wh_sever") is None and store.holdings() == [], "склады пока ничьи")
ok(store.holding_set("wh_sever", bears, "admin") == (None, "ok"),
   "приказ админки: Северный склад у Медведей")
held = store.holding("wh_sever")
ok((held["clan_id"], held["name"], held["by_char"], held["slot"]) == (bears, "Медведи", None, None)
   and isinstance(held["since"], float), "строка с названием клана, by_char и slot — NULL: %s" % held)
ok(store.holding_set("wh_sever", bears, "admin") == (bears, "same")
   and len(store.holding_log("wh_sever")) == 1, "тот же клан ещё раз: ничего не записано")
ok(store.holding_set("wh_sever", 999999, "capture", by_char=char_id, slot=W18) == (bears, "gone")
   and store.holding("wh_sever")["clan_id"] == bears, "клана нет: ничего не записано")
ok(store.holding_set("wh_sever", rivals, "capture", by_char=west_id, slot=W18) == (bears, "ok"),
   "захват поверх прежнего держателя (ON CONFLICT)")
held = store.holding("wh_sever")
ok((held["clan_id"], held["by_char"], held["slot"]) == (rivals, west_id, W18),
   "держатель, кому зачтено, окно: %s" % held)
store.holding_logged("wh_sever", "defend", rivals, by_char=west_id, slot=W20)
ok(store.holding_clear("wh_sever", "admin", clan_id=bears) is None
   and store.holding("wh_sever")["clan_id"] == rivals, "снять с клана, который не держит: ничего")
ok([(r["how"], r["clan_id"], r["prev"], r["slot"]) for r in store.holding_log("wh_sever")]
   == [("defend", rivals, rivals, W20), ("capture", rivals, bears, W18), ("admin", bears, None, None)],
   "журнал склада, новые сверху: %s" % store.holding_log("wh_sever"))
store.holding_set("wh_ug", rivals, "admin")
ok(store.clan_disband(rivals, west_id) == 0 and store.holdings() == []
   and store.holdings_lost(rivals) == ["wh_sever", "wh_ug"],
   "роспуск забрал оба склада той же транзакцией")
ok([(r["how"], r["clan_id"], r["prev"]) for r in store.holding_log(limit=2)]
   == [("disband", None, rivals)] * 2, "и каждому — строка 'disband'")
for table, col, kind in (("clan_holdings", "since", "double precision"),
                         ("clan_holdings", "clan_id", "bigint"),
                         ("clan_holding_log", "slot", "double precision")):
    ok(store.db.execute("SELECT data_type FROM information_schema.columns WHERE table_name = ?"
                        " AND column_name = ?", (table, col)).fetchone()["data_type"] == kind,
       "%s.%s — %s" % (table, col, kind))
ok(store.characters(aid) is not None, "и соединение после складов живое")

# --- приказы сайта: таблица site_orders ----------------------------------------
# Сайт пишет приказ своей ролью: INSERT ... RETURNING id, ключ — identity, и
# права на последовательность роли не нужны. Игра читает ждущие
# (site_pending), отказ пишет site_done, а шаг отношения отмечает приказ
# выполненным в своей же транзакции (clan_stance_step с order). Здесь — что
# типы доехали (made_at и done_at — double precision), что ответ ставится
# один раз, что шаг откатывается вместе с отметкой, когда приказ уже
# отвечен, и что две сессии, взявшиеся за один приказ разом, шаг не сделают
# дважды.
order_cols = {r["column_name"]: (r["data_type"], r["is_identity"]) for r in store.db.execute(
    "SELECT column_name, data_type, is_identity FROM information_schema.columns"
    " WHERE table_name = 'site_orders'")}
ok(order_cols == {"id": ("bigint", "YES"), "made_at": ("double precision", "NO"),
                  "login": ("text", "NO"), "char_id": ("bigint", "NO"),
                  "clan_id": ("bigint", "NO"), "other": ("bigint", "NO"),
                  "stat_from": ("bigint", "NO"), "dir": ("bigint", "NO"),
                  "done_at": ("double precision", "NO"), "code": ("text", "NO"),
                  "result": ("text", "NO")}, "site_orders: столбцы и типы: %s" % order_cols)
sid, _ = store.register("посол", "пароль")
envoy, _ = store.create_character(sid, "Посол", 0, 1)
rival, _ = store.create_character(sid, "Сосед", 0, 1)
owls = store.clan_create(envoy, "Совы", "совы", "", None)
ravens = store.clan_create(rival, "Вороны", "вороны", "", None)
store.clan_treasury_adjust(owls, 1100, "admin")


def site_order(made_at, stat_from, step):
    """Строка так, как её пишет сайт (lava-site api/db.py queue_stance)."""
    oid = store.db.insert(
        "INSERT INTO site_orders (made_at, login, char_id, clan_id, other, stat_from, dir)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)", (made_at, "посол", envoy, owls, ravens, stat_from, step))
    store.db.commit()
    return oid


now = time.time()
up = site_order(now, 0, 1)
refused = site_order(now - 0.25, 0, 5)
ok(isinstance(up, int) and refused == up + 1, "RETURNING id отдаёт новый ключ: %s %s"
   % (up, refused))
pending = store.site_pending()
ok([(r["id"], r["made_at"], r["done_at"]) for r in pending] == [(up, now, None),
                                                                (refused, now - 0.25, None)],
   "ждущие по порядку, made_at с долями секунды: %s" % [dict(r) for r in pending])
ok(store.site_done(refused, "R7", "Приказ отклонён.", when=now) is True
   and store.site_done(refused, "R7", "второй раз", when=now + 1) is False,
   "отказ пишется один раз")
row = store.site_order(refused)
ok((row["code"], row["result"], row["done_at"]) == ("R7", "Приказ отклонён.", now),
   "и первый ответ остаётся: %s" % row)
ok(store.clan_stance_step(owls, ravens, 0, 1, 1000, envoy, need=0x2000, when=now,
                          order=(up, "Готово")) == 100,
   "шаг по приказу: цена списана, остаток 100")
row = store.site_order(up)
ok((row["code"], row["result"], row["done_at"]) == ("OK", "Готово", float(int(now))),
   "и приказ отмечен в той же транзакции: %s" % row)
ok([r["id"] for r in store.site_pending()] == [], "ждущих больше нет")
ok(store.clan_stance_step(owls, ravens, 1, 0, 100, envoy, need=0x2000,
                          order=(up, "ещё раз")) is None,
   "тот же приказ второй раз: None")
ok((store.clan_treasury(owls), store.clan_relation(owls, ravens),
    [r["source"] for r in store.clan_ledger_rows(owls)], store.site_order(up)["result"])
   == (100, 1, ["diplomacy", "admin"], "Готово"),
   "и откат целиком: казна, отношение, журнал и ответ прежние")

# Две сессии разом: первая отвечает на приказ и держит строку, вторая
# делает по нему шаг — её UPDATE site_orders ждёт блокировку, после фиксации
# первой перечитывает done_at IS NULL, не находит строки и откатывает шаг.
race_order = site_order(time.time(), 1, -1)
store.db.commit()
second = accounts.Store()
first = storage.connect()
first.execute("UPDATE site_orders SET done_at = 1, code = 'R6', result = 'опоздал'"
              " WHERE id = ? AND done_at IS NULL", (race_order,))
race = {}
worker = threading.Thread(target=lambda: race.update(got=second.clan_stance_step(
    owls, ravens, 1, 0, 100, envoy, need=0x2000, order=(race_order, "Готово"))))
worker.start()
time.sleep(0.7)
ok(worker.is_alive(), "шаг второй сессии ждёт строку приказа")
first.commit()
worker.join(15)
ok(race.get("got", "нет ответа") is None, "и после фиксации первой не делается: %s" % race)
ok((store.clan_treasury(owls), store.clan_relation(owls, ravens),
    store.site_order(race_order)["code"]) == (100, 1, "R6"),
   "ни цены, ни отношения; ответ первой сессии на месте")
first.close()
second.close()
ok(store.characters(aid) is not None, "и соединение после приказов сайта живое")

# --- схема -----------------------------------------------------------------
cols = store.db.columns("characters")
for col in ("id", "account_id", "name", "gold", "afro", "level", "rep", "bank_steps",
            "trophy_places"):
    ok(col in cols, "в characters есть %s" % col)
ok([r["name"] for r in store.db.execute("SELECT name FROM migrations")
    if r["name"] == RELINK] == [RELINK],
   "на чистой базе перенос лекарств отмечен сразу")
store.db.close()


# --- переезд: база прежнего сервера ------------------------------------------
# Та, что работает сейчас: без auction_lots, migrations и bank_steps, с
# лекарствами 6067..6072 в рюкзаке и в письме. keep_lots оставляет
# auction_lots с лотом-лекарством — чтобы перенос прошёл и по лотам.
def old_database(keep_lots=False, trophies_unshown=False):
    """trophies_unshown: база сервера 2026-09-25 — trophies уже есть, с
    записью в коллекции, но без места на витрине (shown), и купленных мест
    нет ни у кого (trophy_places). Иначе trophies нет вовсе."""
    st = fresh_store()
    acc, _ = st.register("старожил", "пароль")
    cid, _ = st.create_character(acc, "Старожил", 0, "1")
    for type_id, uses in ((6071, 20), (6067, 3), (6043, 5), (6904, 7)):
        st.create_item(cid, type_id, 2, use_count=uses)
    st.mail_send(cid, cid, 0, "Посылка", "", 100, 0, json.dumps(
        [{"uniq": 90, "type_id": 6069, "root": 2, "use_count": 12},
         {"uniq": 91, "type_id": 3577, "root": 1}]))
    if keep_lots:
        heal = st.create_item(cid, 6072, 2, use_count=20)
        st.auction_list(heal["uniq"], cid, dict(lot_fields(heal), seller=cid))
    else:
        st.db.execute("DROP TABLE auction_lots")
    st.db.execute("DROP TABLE migrations")
    if trophies_unshown:
        ear = st.create_trophy(cid, 2048, 1495, 6, dict(
            killer_id=cid, killer_name="Старожил", killer_lvl=0, victim_id=cid + 1,
            victim_name="Жертва", victim_lvl=0, victim_clan="", killed_at=1_790_000_000))
        st.register_trophy(ear, st.trophy(ear["uniq"]), cid, 1_790_000_060, True,
                           (cid, 0, 0), 10)
        st.db.execute("ALTER TABLE trophies DROP COLUMN shown")
    else:
        st.db.execute("DROP TABLE trophies")
    # Nor had it the journal of money, nor the record of rounds lent.
    st.db.execute("DROP TABLE money_ledger")
    st.db.execute("DROP TABLE char_lent")
    # Nor the ground table: a bag it left out is a row of nobody's, and
    # nothing more.
    st.create_item(0, 6910, 4)
    st.db.execute("DROP TABLE ground")
    st.db.execute("ALTER TABLE characters DROP COLUMN bank_steps")
    st.db.execute("ALTER TABLE characters DROP COLUMN trophy_places")
    # Nor any clan (2026-09-28).
    for table in ("clans", "clan_members", "clan_relations", "clan_ledger"):
        st.db.execute("DROP TABLE %s" % table)
    st.db.execute("ALTER TABLE characters DROP COLUMN clan_no_invites")
    st.db.execute("ALTER TABLE characters DROP COLUMN seen_at")
    st.db.commit()
    st.close()
    return cid


cid = old_database(keep_lots=True)
db = storage.connect()
ok("bank_steps" not in db.columns("characters"), "старая база: bank_steps нет")
db.close()
up = accounts.Store()
ok("bank_steps" in up.db.columns("characters") and up.character(cid)["bank_steps"] == 0,
   "ALTER TABLE добавил bank_steps, у старожила 0")
ok((up.character(cid)["clan_no_invites"], up.character(cid)["seen_at"], up.clan_all(),
    up.clan_member(cid)) == (0, 0, [], None),
   "база без кланов: таблицы созданы, у старожила 0 в новых колонках и ни клана")
ok({"uniq", "killer_id", "victim_id", "registered_at", "paid_at"} <= up.db.columns("trophies")
   and up.trophies_of(cid) == [], "старая база без trophies: таблица создана, пустая")
ok(set(accounts.Store.GROUND_COLUMNS) <= up.db.columns("ground") and up.on_ground(0) == []
   and up.clear_ground(0) == 1 and up.items_of(0) == [],
   "старая база без ground: таблица создана; мешок прежнего сервера, без строки"
   " земли, стирается на старте, как раньше")
ok(up.db.execute("SELECT data_type FROM information_schema.columns WHERE table_name ="
                 " 'characters' AND column_name = 'bank_steps'").fetchone()["data_type"]
   == "bigint", "и BIGINT, как соседние колонки перенесённой базы")
ok([(r["type_id"], r["use_count"]) for r in up.items_of(cid)]
   == [(6908, 20), (6904, 3), (6043, 5), (6904, 7)],
   "лекарства в рюкзаке переехали на 6904..6909 со своими зарядами: %s"
   % [(r["type_id"], r["use_count"]) for r in up.items_of(cid)])
letter = up.db.execute("SELECT items_json FROM mail").fetchone()["items_json"]
ok([(s["type_id"], s.get("use_count")) for s in json.loads(letter)] == [(6906, 12), (3577, None)],
   "и в письме: %s" % letter)
lot = up.db.execute("SELECT type_id, item_json FROM auction_lots").fetchone()
ok((lot["type_id"], json.loads(lot["item_json"])["type_id"]) == (6909, 6909),
   "и на аукционе — и тип лота, и снимок")
ok([r["name"] for r in up.db.execute("SELECT name FROM migrations")
    if r["name"] == RELINK] == [RELINK],
   "перенос отмечен один раз")
ok([(r["source"], r["afro"], r["gold"]) for r in up.ledger(cid)]
   == [("opening", progression.START_AFRO, 0)],
   "журнал денег открыт кошельком старожила, одной строкой: %s" % up.ledger(cid))
up.create_item(cid, 6067, 2, use_count=5)
up.close()

# Второй раз: ничего не повторяется — и INSERT в migrations даже не
# пробуется. Иначе каждая страница регистрации (она открывает Store на
# каждый запрос) писала бы в журнал Postgres ERROR о дубле ключа.
refused = []
_execute = storage.PostgresDB.execute


def spying(self, sql, args=()):
    try:
        return _execute(self, sql, args)
    except storage.IntegrityError:
        refused.append(sql)
        raise


storage.PostgresDB.execute = spying
try:
    up = accounts.Store()
finally:
    storage.PostgresDB.execute = _execute
ok(refused == [], "второе открытие не упирается в ключ migrations: %s" % refused)
ok(up.items_of(cid)[-1]["type_id"] == 6067, "выданное после переноса 6067 так и осталось")
ok(up.db.execute("SELECT COUNT(*) c FROM migrations WHERE name = ?", (RELINK,)).fetchone()["c"] == 1,
   "строка миграции всё ещё одна")
up.close()

# --- переезд: база сервера 2026-09-25, трофеи без витрины --------------------
# Таблица trophies уже есть, с записью в коллекции, но без места на витрине
# (trophies.shown), а у персонажей нет купленных мест (trophy_places).
cid = old_database(trophies_unshown=True)
db = storage.connect()
ok("shown" not in db.columns("trophies") and "trophy_places" not in db.columns("characters"),
   "старая база: ни места на витрине, ни купленных мест")
db.close()
up = accounts.Store()
ok("shown" in up.db.columns("trophies") and up.character(cid)["trophy_places"] == 0,
   "ALTER TABLE добавил trophies.shown и characters.trophy_places, у старожила 0 купленных")
kept = up.trophies_of(cid)
ok(len(kept) == 1 and kept[0]["shown"] is None and up.shown_trophies(cid) == {},
   "его запись коллекции цела и не стоит ни на каком месте: %s" % kept)
ok(up.show_trophy(cid, 0, kept[0]["uniq"]) and list(up.shown_trophies(cid)) == [0],
   "и её можно выставить")
up.close()

# --- журнал денег: персонаж без статов в базе до журнала ---------------------
# migrate даёт ему кошелёк новорождённого и записывает это (seed_stats), а
# открытие журнала -- остаток: кошелёк минус то, что в журнале уже есть
# (open_ledger, LEFT JOIN на суммы). Сумма строк -- снова кошелёк.
cid = old_database()
db = storage.connect()
db.execute("DELETE FROM char_stats WHERE char_id = ?", (cid,))
db.execute("UPDATE characters SET afro = 5, gold = 7 WHERE id = ?", (cid,))
db.commit()
db.close()
up = accounts.Store()
ok([(r["source"], r["afro"], r["gold"]) for r in up.ledger(cid)]
   == [("start", progression.START_AFRO - 5, -7), ("opening", 5, 7)],
   "персонаж без статов: пересев записан, открытие -- остаток: %s" % up.ledger(cid))
ok(tuple(up.money(cid)) == (progression.START_AFRO, 0)
   and sum(r["afro"] for r in up.ledger(cid)) == progression.START_AFRO
   and sum(r["gold"] for r in up.ledger(cid)) == 0, "и сумма журнала -- кошелёк")
up.close()

# --- переезд двумя процессами разом ----------------------------------------
# docker compose поднимает сервер игры и страницу регистрации вместе, и оба
# открывают базу. Без storage.PostgresDB.schema_lock второй CREATE TABLE
# падал на pg_type_typname_nsp_index, второй ALTER — на «already exists».
CHILD = r"""
import sys, time
sys.path.insert(0, %r)
import accounts
time.sleep(max(0.0, float(sys.argv[1]) - time.time()))
accounts.Store().close()
"""
for attempt in range(3):
    cid = old_database()
    start = time.time() + 1.5
    procs = [subprocess.Popen([sys.executable, "-c", CHILD % HERE, str(start)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
             for _ in range(8)]
    outs = [p.communicate(timeout=120)[0] for p in procs]
    bad = [o.strip().splitlines()[-1] for p, o in zip(procs, outs) if p.returncode]
    ok(not bad, "попытка %d: восемь процессов открыли старую базу разом: %s" % (attempt, bad))
    db = storage.connect()
    ok(db.execute("SELECT COUNT(*) c FROM migrations WHERE name = ?", (RELINK,)).fetchone()["c"] == 1
       and "bank_steps" in db.columns("characters")
       and "trophy_places" in db.columns("characters")
       and "shown" in db.columns("trophies")
       and {"clan_no_invites", "seen_at"} <= db.columns("characters")
       and {"name_key", "afro"} <= db.columns("clans") and db.columns("clan_ledger")
       and "expires_at" in db.columns("ground")
       and db.execute("SELECT COUNT(*) c FROM auction_lots").fetchone()["c"] == 0,
       "попытка %d: схема доведена один раз" % attempt)
    ok([r["type_id"] for r in db.execute(
        "SELECT type_id FROM items WHERE char_id = ? ORDER BY uniq", (cid,))]
       == [6908, 6904, 6043, 6904], "попытка %d: лекарства перенесены один раз" % attempt)
    db.close()

# --- подарки админки персонажу не в игре -------------------------------------
# До 2026-09-29 такая вещь ложилась голой строкой: ствол 0 из 0 (NaN у
# клиента, мимо окна ремонта), дробовик на выключенном режиме огня,
# лекарство без зарядов. Один раз на базу их дозаполняет сервер при старте
# (inventory.OFFLINE_GIFTS_FIX через run_once) -- в рюкзаке, в письме и на
# аукционе. Здесь -- что тот же SELECT с IN, UPDATE и JSON проходят в Postgres.
import inventory  # noqa: E402

WALTHER, SHOTGUN, MEDICINE = 25636, 7072, 6049
store = fresh_store()
aid, _ = store.register("даритель", "пароль")
cid, _ = store.create_character(aid, "Одарённый", 0, 1)
bare = {t: store.create_item(cid, t, root) for t, root in
        ((WALTHER, 0), (SHOTGUN, 0), (MEDICINE, 2))}
worn = store.create_item(cid, WALTHER, 0, brk=0, max_break_cur=500)
posted = store.create_item(cid, WALTHER, 0)
snap = {f: posted[f] for f in accounts.ITEM_FIELDS}
snap.update(uniq=posted["uniq"], type_id=WALTHER, root=0)
store.delete_item(posted["uniq"])
letter = store.mail_send(cid, cid, 0, "подарок", "", 0, 0, json.dumps([snap]))
listed = store.create_item(cid, SHOTGUN, 0)
lsnap = {f: listed[f] for f in accounts.ITEM_FIELDS}
lsnap.update(uniq=listed["uniq"], type_id=SHOTGUN, root=0)
lot = store.auction_list(listed["uniq"], cid, dict(
    type_id=SHOTGUN, root=0, item_json=json.dumps(lsnap), seller=cid, seller_name="Одарённый",
    currency=0, start_bid=1, buyout=0, fee=0, hours=24, created_at=int(time.time()),
    ends_at=time.time() + 86400))
ok(accounts.run_once(store.db, inventory.OFFLINE_GIFTS_FIX, inventory.fill_offline_gifts)
   and not accounts.run_once(store.db, inventory.OFFLINE_GIFTS_FIX, inventory.fill_offline_gifts),
   "подарки дозаполнены один раз")


def fields(r):
    return (r["brk"], r["max_break_cur"], r["cur_mode"], r["use_count"])


got = [fields(store.item(bare[t]["uniq"])) for t in (WALTHER, SHOTGUN, MEDICINE)]
ok(got == [(500, 500, 0, 0), (400, 400, 2, 0), (0, 0, 0, 10)],
   "в рюкзаке -- как новые: %s" % got)
ok(fields(store.item(worn["uniq"])) == (0, 500, 0, 0), "сломанный, но не голый, не тронут")
ok([fields(s) for s in json.loads(store.mail_letter(letter["id"])["items_json"])]
   == [(500, 500, 0, 0)]
   and fields(json.loads(store.auction_lot(lot["id"])["item_json"])) == (400, 400, 2, 0),
   "и в письме, и на аукционе")
store.close()

# --- чистка (P): места и вещи -----------------------------------------------
# Два run_once от 2026-10-02 (accounts.relocate_retired_places,
# retire_premium_things; README «Чистка (P)»): кто стоит в (P)-лагерях
# 124/125/130 или в отрезанном квартале 447 или прописан там -- на Причал;
# вещи (P) -- из рюкзака, банка, с земли, с аукциона (ставка письмом назад)
# и из писем. Здесь -- что те же IN, DELETE, UPDATE и INSERT письма идут в
# Postgres и что вторым открытием ничего не повторяется. Полный набор на
# SQLite -- server/test_premium_cut.py.
import items  # noqa: E402
import mail  # noqa: E402

MASK_P, BERETTA = 6511, 25586                   # hermit_mask_pm (P); Беретта 92
store = fresh_store()
aid, _ = store.register("премиум", "пароль")
who = {}
for name, loc in (("в124", 124), ("в447", 447), ("в125", 125), ("в130", 130), ("на причале", 41)):
    c, _ = store.create_character(aid, name, 0, 1)
    store.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5968, gy = 1726, on_map = 0,"
                     " home_loc = ? WHERE id = ?", (loc, 124 if name == "в130" else 41, c))
    who[name] = c
store.db.commit()
keeper, bidder = who["на причале"], who["в130"]
in_bag = store.create_item(keeper, MASK_P, 1)
in_bank = store.create_item(keeper, MASK_P, 1, slot=inventory.BANK)
kept = store.create_item(keeper, BERETTA, 3)
lying = store.create_item(0, MASK_P, 1)
store.lay_down({lying["uniq"]: 9e9}, (36, None, None), 100)
selling = store.create_item(keeper, MASK_P, 1)
psnap = {"uniq": selling["uniq"], "type_id": MASK_P, "root": 1}
plot = store.auction_list(selling["uniq"], keeper, dict(
    type_id=MASK_P, root=1, item_json=json.dumps(psnap), seller=keeper, seller_name="на причале",
    currency=1, start_bid=100, buyout=0, fee=0, hours=24, created_at=int(time.time()),
    ends_at=time.time() + 86400))
store.db.execute("UPDATE auction_lots SET bid = 250, bidder = ?, bidder_name = 'в130'"
                 " WHERE id = ?", (bidder, plot["id"]))
mixed = store.mail_send(bidder, keeper, mail.LETTER, "смешанное", "", 10, 0, json.dumps(
    [{"uniq": 900, "type_id": MASK_P, "root": 1}, {"uniq": 901, "type_id": BERETTA, "root": 3}]))
trade = store.mail_send(bidder, keeper, mail.TRADE, "торговое", "", 500, 0, json.dumps(
    [{"uniq": 902, "type_id": MASK_P, "root": 1}]))
store.db.execute("DELETE FROM migrations WHERE name IN (?, ?)",
                 (accounts.RETIRED_PLACES_FIX, accounts.PREMIUM_THINGS_FIX))
store.db.commit()
store.close()

up = accounts.Store()
rows = {n: up.character(c) for n, c in who.items()}
ok({n: (r["loc"], r["gx"], r["gy"], r["on_map"], r["pos"]) for n, r in rows.items()}
   == dict({n: (41, 5965, 1728, 0, None) for n in ("в124", "в447", "в125", "в130")},
           **{"на причале": (41, 5968, 1726, 0, 77)}),
   "из 124/447/125/130 -- на Причал, на его клетку, без клетки старого файла: %s"
   % {n: (r["loc"], r["pos"]) for n, r in rows.items()})
ok((rows["в130"]["home_loc"], rows["в130"]["home_gx"], rows["в130"]["home_gy"]) == (41, 5965, 1728),
   "прописка в 124 -- теперь Причал")
ok([up.item(r["uniq"]) is None for r in (in_bag, in_bank, lying)] == [True] * 3
   and up.item(kept["uniq"]) is not None
   and up.db.execute("SELECT COUNT(*) c FROM ground").fetchone()["c"] == 0,
   "вещи (P) ушли из рюкзака, банка и с земли, Беретта осталась")
ok(up.db.execute("SELECT COUNT(*) c FROM auction_lots").fetchone()["c"] == 0, "лот (P) снят")
back = [dict(r) for r in up.db.execute(
    "SELECT to_char, afro, gold, items_json FROM mail WHERE subject = ?",
    ("Аукцион: ставка возвращена",)).fetchall()]
ok(back == [{"to_char": bidder, "afro": 0, "gold": 250, "items_json": "[]"}],
   "ставка 2,50 G вернулась письмом в золоте: %s" % back)
letters = {r["subject"]: r for r in up.db.execute("SELECT * FROM mail")}
ok((json.loads(letters["смешанное"]["items_json"]), letters["смешанное"]["afro"],
    json.loads(letters["торговое"]["items_json"]), letters["торговое"]["afro"])
   == ([{"uniq": 901, "type_id": BERETTA, "root": 3}], 10, [], 0),
   "из писем -- только (P); торговое без вещей ничего не просит")
ok(sorted(r["name"] for r in up.db.execute(
    "SELECT name FROM migrations WHERE name IN (?, ?)",
    (accounts.RETIRED_PLACES_FIX, accounts.PREMIUM_THINGS_FIX)))
   == sorted([accounts.RETIRED_PLACES_FIX, accounts.PREMIUM_THINGS_FIX]), "обе отмечены")
up.create_item(keeper, MASK_P, 1)
up.db.execute("UPDATE characters SET loc = 124 WHERE id = ?", (keeper,))
up.db.commit()
up.close()
up = accounts.Store()
ok((up.character(keeper)["loc"], [r["type_id"] for r in up.items_of(keeper)].count(MASK_P))
   == (124, 1), "второе открытие ничего не повторяет")
ok(items.premium(MASK_P), "маска отшельника -- в самом деле (P)")
up.close()

# --- чистка Хальфы: места и журналы ---------------------------------------------
# run_once от 2026-10-09 (accounts.relocate_halfa_cut; README «Чистка Хальфы»):
# кто стоит в вещевом рынке 468, у ремесленников 452/456/457 или в файлах
# кланбазы KKND (297, 383, 384, 938, 961, 1189) или прописан там -- на Причал;
# из журналов уходят 238, 239 и строки ремесленников 11000-11499. Здесь --
# что те же IN, UPDATE, COUNT и DELETE с диапазоном идут в Postgres и что
# вторым открытием ничего не повторяется. Полный набор на SQLite --
# server/test_halfa_cut.py.
store = fresh_store()
aid, _ = store.register("хальфа", "пароль")
who = {}
for name, loc, home in (("в468", 468, 41), ("в457", 457, 41), ("в1189", 1189, 41),
                        ("прописан в452", 36, 452), ("в447", 447, 41), ("на причале", 41, 41)):
    c, _ = store.create_character(aid, name, 0, 1)
    store.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5969, gy = 1729, on_map = 0,"
                     " home_loc = ?, home_gx = 5969, home_gy = 1729 WHERE id = ?", (loc, home, c))
    who[name] = c
store.db.commit()
keeper = who["на причале"]
for t in (238, 239, 11000, 11499, 11500, 119):
    store.take_quest(keeper, t, {}, True)
done = store.take_quest(keeper, 238, {}, True)
store.finish_quest(done, keeper, 238)
store.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.HALFA_CUT_FIX,))
store.db.commit()
store.close()

up = accounts.Store()
rows = {n: up.character(c) for n, c in who.items()}
ok({n: (r["loc"], r["gx"], r["gy"], r["on_map"], r["pos"]) for n, r in rows.items()}
   == {"в468": (41, 5965, 1728, 0, None), "в457": (41, 5965, 1728, 0, None),
       "в1189": (41, 5965, 1728, 0, None), "прописан в452": (36, 5969, 1729, 0, 77),
       "в447": (447, 5969, 1729, 0, 77), "на причале": (41, 5969, 1729, 0, 77)},
   "из 468/457/1189 -- на Причал, 447 (чистка (P), давно прошла) и Причал не тронуты: %s"
   % {n: (r["loc"], r["pos"]) for n, r in rows.items()})
ok((rows["прописан в452"]["home_loc"], rows["прописан в452"]["home_gx"],
    rows["прописан в452"]["home_gy"]) == (41, 5965, 1728), "прописка в 452 -- теперь Причал")
ok(sorted(r["type"] for r in up.quests(keeper)) == [119, 11500],
   "из журнала ушли 238, 239, 11000, 11499; 119 и 11500 остались: %s"
   % sorted(r["type"] for r in up.quests(keeper)))
ok(up.quest_done(keeper, 238), "история сдачи 238 осталась")
ok(accounts.relocate_halfa_cut(up.db) == dict(moved=0, homes=0, journal=0),
   "повторный проход ничего не находит")
up.db.commit()
up.db.execute("UPDATE characters SET loc = 468 WHERE id = ?", (keeper,))
up.db.commit()
up.close()
up = accounts.Store()
ok(up.character(keeper)["loc"] == 468 and accounts.ran(up.db, accounts.HALFA_CUT_FIX),
   "второе открытие ничего не повторяет")
up.close()

# --- чистка ФСЦ Хальфы: аэроплощадка и база НИЛ-1 -------------------------------
# run_once от 2026-10-10 (accounts.relocate_halfa_fsc; README «Чистка Хальфы»,
# «ФСЦ»): кто стоит на аэроплощадке 528 или на базе «НИЛ-1» 522 или прописан
# там -- на Причал; журналы не трогаются (ни один квест туда не ведёт). Здесь --
# что те же IN и UPDATE идут в Postgres и второе открытие ничего не повторяет.
# Полный набор на SQLite -- server/test_halfa_cut.py, раздел «the ФСЦ».
store = fresh_store()
aid, _ = store.register("фсц", "пароль")
who = {}
for name, loc, home in (("в528", 528, 41), ("в522", 522, 41), ("прописан в528", 36, 528),
                        ("в468", 468, 41), ("на причале", 41, 41)):
    c, _ = store.create_character(aid, name, 0, 1)
    store.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5970, gy = 1727, on_map = 0,"
                     " home_loc = ?, home_gx = 5970, home_gy = 1727 WHERE id = ?", (loc, home, c))
    who[name] = c
store.db.commit()
keeper = who["в528"]
for t in (119, 11500):
    store.take_quest(keeper, t, {}, True)
store.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.HALFA_FSC_FIX,))
store.db.commit()
store.close()

up = accounts.Store()
rows = {n: up.character(c) for n, c in who.items()}
ok({n: (r["loc"], r["gx"], r["gy"], r["on_map"], r["pos"]) for n, r in rows.items()}
   == {"в528": (41, 5965, 1728, 0, None), "в522": (41, 5965, 1728, 0, None),
       "прописан в528": (36, 5970, 1727, 0, 77), "в468": (468, 5970, 1727, 0, 77),
       "на причале": (41, 5970, 1727, 0, 77)},
   "из 528/522 -- на Причал, 468 (чистка 10-09, давно прошла) и Причал не тронуты: %s"
   % {n: (r["loc"], r["pos"]) for n, r in rows.items()})
ok((rows["прописан в528"]["home_loc"], rows["прописан в528"]["home_gx"],
    rows["прописан в528"]["home_gy"]) == (41, 5965, 1728), "прописка в 528 -- теперь Причал")
ok(sorted(r["type"] for r in up.quests(keeper)) == [119, 11500],
   "журнал не тронут: %s" % sorted(r["type"] for r in up.quests(keeper)))
ok(accounts.relocate_halfa_fsc(up.db) == dict(moved=0, homes=0),
   "повторный проход ничего не находит")
up.db.commit()
up.db.execute("UPDATE characters SET loc = 522 WHERE id = ?", (keeper,))
up.db.commit()
up.close()
up = accounts.Store()
ok(up.character(keeper)["loc"] == 522 and accounts.ran(up.db, accounts.HALFA_FSC_FIX),
   "второе открытие ничего не повторяет")
up.close()

# --- чистка Абри: ремесленники, Авиабаза ЦСЦ, улучшение сетов, Liberty ----------
# run_once от 2026-10-12 (accounts.relocate_abri_cut; README «Абри»): кто стоит
# в кварталах ремесленников 453/454/458/459, на Авиабазе ЦСЦ 427, в квартале
# 450, в файлах кланбазы Liberty (328, 327 и прочие), на Аэроплощадке ФСЦ 529
# или в файлах кланбазы Blackwater (317 и прочие) или прописан там -- на
# Портовый рынок Абри 187 (5860,1835); журналы не трогаются (ни один квест туда
# не ведёт). Здесь -- что те же IN и UPDATE идут в Postgres и второе открытие
# ничего не повторяет. Полный набор на SQLite -- server/test_abri_cut.py.
store = fresh_store()
aid, _ = store.register("абри", "пароль")
who = {}
for name, loc, home in (("в427", 427, 41), ("в453", 453, 41), ("в936", 936, 41),
                        ("в529", 529, 41), ("в317", 317, 41),
                        ("прописан в328", 187, 328), ("в528", 528, 41), ("в187", 187, 187)):
    c, _ = store.create_character(aid, name, 0, 1)
    store.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5866, gy = 1836, on_map = 0,"
                     " home_loc = ?, home_gx = 5866, home_gy = 1836 WHERE id = ?", (loc, home, c))
    who[name] = c
store.db.commit()
keeper = who["в427"]
for t in (119, 11500):
    store.take_quest(keeper, t, {}, True)
store.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.ABRI_CUT_FIX,))
store.db.commit()
store.close()

up = accounts.Store()
rows = {n: up.character(c) for n, c in who.items()}
ok({n: (r["loc"], r["gx"], r["gy"], r["on_map"], r["pos"]) for n, r in rows.items()}
   == {"в427": (187, 5860, 1835, 0, None), "в453": (187, 5860, 1835, 0, None),
       "в936": (187, 5860, 1835, 0, None), "в529": (187, 5860, 1835, 0, None),
       "в317": (187, 5860, 1835, 0, None), "прописан в328": (187, 5866, 1836, 0, 77),
       "в528": (528, 5866, 1836, 0, 77), "в187": (187, 5866, 1836, 0, 77)},
   "из 427/453/936/529/317 -- на Портовый рынок Абри, 528 (чистка 10-10, давно прошла) и 187 не тронуты: %s"
   % {n: (r["loc"], r["pos"]) for n, r in rows.items()})
ok((rows["прописан в328"]["home_loc"], rows["прописан в328"]["home_gx"],
    rows["прописан в328"]["home_gy"]) == (187, 5860, 1835), "прописка в 328 -- теперь Портовый рынок Абри")
ok(sorted(r["type"] for r in up.quests(keeper)) == [119, 11500],
   "журнал не тронут: %s" % sorted(r["type"] for r in up.quests(keeper)))
ok(accounts.relocate_abri_cut(up.db) == dict(moved=0, homes=0),
   "повторный проход ничего не находит")
up.db.commit()
up.db.execute("UPDATE characters SET loc = 427 WHERE id = ?", (keeper,))
up.db.commit()
up.close()
up = accounts.Store()
ok(up.character(keeper)["loc"] == 427 and accounts.ran(up.db, accounts.ABRI_CUT_FIX),
   "второе открытие ничего не повторяет")
up.close()

# --- лагеря за рекой и вещевой рынок Абри ------------------------------------------
# run_once от 2026-10-12 (accounts.relocate_river_camps и relocate_abri_clothes;
# README «Лагеря за рекой»): кто стоит в лагерях сопротивления 429-432 или
# прописан там -- на Причал (5965,1728), кто стоит на вещевом рынке Абри 378 или
# прописан там -- на Портовый рынок Абри 187 (5860,1835); журналы не трогаются.
# Здесь -- что те же IN и UPDATE идут в Postgres и второе открытие ничего не
# повторяет. Полный набор на SQLite -- server/test_river_camps_cut.py и
# server/test_abri_cut.py (раздел 8).
store = fresh_store()
aid, _ = store.register("заречье", "пароль")
who = {}
for name, loc, home in (("в429", 429, 41), ("в431", 431, 41), ("в432", 432, 41),
                        ("прописан в430", 433, 430), ("в378", 378, 41), ("прописан в378", 188, 378),
                        ("в427", 427, 41), ("на причале", 41, 41)):
    c, _ = store.create_character(aid, name, 0, 1)
    store.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5943, gy = 1723, on_map = 0,"
                     " home_loc = ?, home_gx = 5943, home_gy = 1723 WHERE id = ?", (loc, home, c))
    who[name] = c
store.db.commit()
keeper = who["в429"]
for t in (119, 11500):
    store.take_quest(keeper, t, {}, True)
store.db.execute("DELETE FROM migrations WHERE name IN (?, ?)",
                 (accounts.RIVER_CAMPS_FIX, accounts.ABRI_CLOTHES_FIX))
store.db.commit()
store.close()

up = accounts.Store()
rows = {n: up.character(c) for n, c in who.items()}
ok({n: (r["loc"], r["gx"], r["gy"], r["on_map"], r["pos"]) for n, r in rows.items()}
   == {"в429": (41, 5965, 1728, 0, None), "в431": (41, 5965, 1728, 0, None),
       "в432": (41, 5965, 1728, 0, None), "прописан в430": (433, 5943, 1723, 0, 77),
       "в378": (187, 5860, 1835, 0, None), "прописан в378": (188, 5943, 1723, 0, 77),
       "в427": (427, 5943, 1723, 0, 77), "на причале": (41, 5943, 1723, 0, 77)},
   "из 429/431/432 -- на Причал, из 378 -- на Портовый рынок, 427 (чистка Абри, давно прошла) и"
   " Причал не тронуты: %s" % {n: (r["loc"], r["pos"]) for n, r in rows.items()})
ok([(rows[n]["home_loc"], rows[n]["home_gx"], rows[n]["home_gy"]) for n in ("прописан в430", "прописан в378")]
   == [(41, 5965, 1728), (187, 5860, 1835)], "прописка в 430 -- Причал, в 378 -- Портовый рынок")
ok(sorted(r["type"] for r in up.quests(keeper)) == [119, 11500],
   "журнал не тронут: %s" % sorted(r["type"] for r in up.quests(keeper)))
ok(accounts.relocate_river_camps(up.db) == dict(moved=0, homes=0)
   and accounts.relocate_abri_clothes(up.db) == dict(moved=0, homes=0),
   "повторный проход ничего не находит")
up.db.commit()
up.db.execute("UPDATE characters SET loc = 429 WHERE id = ?", (keeper,))
up.db.commit()
up.close()
up = accounts.Store()
ok(up.character(keeper)["loc"] == 429 and accounts.ran(up.db, accounts.RIVER_CAMPS_FIX)
   and accounts.ran(up.db, accounts.ABRI_CLOTHES_FIX), "второе открытие ничего не повторяет")
up.close()

# --- всё за рекой ------------------------------------------------------------------------
# run_once от 2026-10-13 (accounts.relocate_river_all; README «Всё за рекой»): кто
# стоит в местах того берега или прописан там -- с того берега у Абри и из мест
# Эвана на Портовый рынок Абри 187 (5860,1835), из остальных -- на Причал
# (5965,1728); журналы не трогаются. Здесь -- что оба IN и UPDATE идут в Postgres и
# второе открытие ничего не повторяет. Полный набор на SQLite --
# server/test_river_all_cut.py (раздел 7).
store = fresh_store()
aid, _ = store.register("тотберег", "пароль")
who = {}
for name, loc, home in (("в433", 433, 41), ("в474", 474, 41), ("в1197", 1197, 41), ("прописан в323", 36, 323),
                        ("в434", 434, 187), ("в325", 325, 187), ("прописан в513", 188, 513),
                        ("в429", 429, 41), ("на причале", 41, 41)):
    c, _ = store.create_character(aid, name, 0, 1)
    store.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5943, gy = 1722, on_map = 0,"
                     " home_loc = ?, home_gx = 5943, home_gy = 1722 WHERE id = ?", (loc, home, c))
    who[name] = c
store.db.commit()
keeper = who["в433"]
for t in (119, 11500):
    store.take_quest(keeper, t, {}, True)
store.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.RIVER_ALL_FIX,))
store.db.commit()
store.close()

up = accounts.Store()
rows = {n: up.character(c) for n, c in who.items()}
ok({n: (r["loc"], r["gx"], r["gy"], r["on_map"], r["pos"]) for n, r in rows.items()}
   == {"в433": (41, 5965, 1728, 0, None), "в474": (41, 5965, 1728, 0, None), "в1197": (41, 5965, 1728, 0, None),
       "прописан в323": (36, 5943, 1722, 0, 77), "в434": (187, 5860, 1835, 0, None),
       "в325": (187, 5860, 1835, 0, None), "прописан в513": (188, 5943, 1722, 0, 77),
       "в429": (429, 5943, 1722, 0, 77), "на причале": (41, 5943, 1722, 0, 77)},
   "из 433/474/1197 -- на Причал, из 434/325 -- на Портовый рынок, 429 (лагеря, давно прошло) и Причал"
   " не тронуты: %s" % {n: (r["loc"], r["pos"]) for n, r in rows.items()})
ok([(rows[n]["home_loc"], rows[n]["home_gx"], rows[n]["home_gy"]) for n in ("прописан в323", "прописан в513")]
   == [(41, 5965, 1728), (187, 5860, 1835)], "прописка в 323 -- Причал, в 513 -- Портовый рынок")
ok(sorted(r["type"] for r in up.quests(keeper)) == [119, 11500],
   "журнал не тронут: %s" % sorted(r["type"] for r in up.quests(keeper)))
ok(accounts.relocate_river_all(up.db) == dict(moved=0, homes=0), "повторный проход ничего не находит")
up.db.commit()
up.db.execute("UPDATE characters SET loc = 433 WHERE id = ?", (keeper,))
up.db.commit()
up.close()
up = accounts.Store()
ok(up.character(keeper)["loc"] == 433 and accounts.ran(up.db, accounts.RIVER_ALL_FIX),
   "второе открытие ничего не повторяет")
up.close()

# --- чистка Донголы -------------------------------------------------------------------
# run_once от 2026-10-13 (accounts.relocate_dongola_cut; README «Донгола»): кто стоит
# в убранных местах Донголы (ремесленники, вещевой рынок, аэроплощадка ФСЦ, кланбазы,
# копия лагеря Миротворцев, «Засада») или прописан там -- на Вокзал Донголы 49
# (5877,2010); журналы не трогаются. Здесь -- что IN и UPDATE идут в Postgres и второе
# открытие ничего не повторяет. Полный набор на SQLite -- server/test_dongola_cut.py
# (раздел 7).
store = fresh_store()
aid, _ = store.register("донгола", "пароль")
who = {}
for name, loc, home in (("в469", 469, 49), ("в455", 455, 49), ("в382", 382, 49), ("в1171", 1171, 49),
                        ("в389", 389, 49), ("прописан в530", 197, 530), ("в378", 378, 187),
                        ("на вокзале", 49, 49)):
    c, _ = store.create_character(aid, name, 0, 1)
    store.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5878, gy = 2013, on_map = 0,"
                     " home_loc = ?, home_gx = 5878, home_gy = 2013 WHERE id = ?", (loc, home, c))
    who[name] = c
store.db.commit()
keeper = who["в469"]
for t in (119, 11500):
    store.take_quest(keeper, t, {}, True)
store.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.DONGOLA_CUT_FIX,))
store.db.commit()
store.close()

up = accounts.Store()
rows = {n: up.character(c) for n, c in who.items()}
ok({n: (r["loc"], r["gx"], r["gy"], r["on_map"], r["pos"]) for n, r in rows.items()}
   == {"в469": (49, 5877, 2010, 0, None), "в455": (49, 5877, 2010, 0, None), "в382": (49, 5877, 2010, 0, None),
       "в1171": (49, 5877, 2010, 0, None), "в389": (49, 5877, 2010, 0, None),
       "прописан в530": (197, 5878, 2013, 0, 77), "в378": (378, 5878, 2013, 0, 77),
       "на вокзале": (49, 5878, 2013, 0, 77)},
   "из 469/455/382/1171/389 -- на Вокзал Донголы, 378 (вещевой рынок Абри, давно прошло) и вокзал не"
   " тронуты: %s" % {n: (r["loc"], r["pos"]) for n, r in rows.items()})
ok((rows["прописан в530"]["home_loc"], rows["прописан в530"]["home_gx"], rows["прописан в530"]["home_gy"])
   == (49, 5877, 2010), "прописка в 530 -- Вокзал Донголы")
ok(sorted(r["type"] for r in up.quests(keeper)) == [119, 11500],
   "журнал не тронут: %s" % sorted(r["type"] for r in up.quests(keeper)))
ok(accounts.relocate_dongola_cut(up.db) == dict(moved=0, homes=0), "повторный проход ничего не находит")
up.db.commit()
up.db.execute("UPDATE characters SET loc = 469 WHERE id = ?", (keeper,))
up.db.commit()
up.close()
up = accounts.Store()
ok(up.character(keeper)["loc"] == 469 and accounts.ran(up.db, accounts.DONGOLA_CUT_FIX),
   "второе открытие ничего не повторяет")
up.close()

# --- чистка Абу-Хамеда ----------------------------------------------------------------
# run_once от 2026-10-14 (accounts.relocate_abuhamed_cut; README «Абу-Хамед»): кто
# стоит в убранных местах Абу-Хамеда (ремесленники, улучшение сетов, вещевой рынок,
# аэроплощадка ФСЦ, кланбазы СМЕРШ, ВЭС и ZEON, заброшенная кланбаза) или прописан
# там -- на Вокзал Абу-Хамеда 126 (6182,1976); журналы не трогаются. Здесь -- что IN
# и UPDATE идут в Postgres и второе открытие ничего не повторяет. Полный набор на
# SQLite -- server/test_abuhamed_cut.py (раздел 7).
store = fresh_store()
aid, _ = store.register("абухамед", "пароль")
who = {}
for name, loc, home in (("в467", 467, 126), ("в451", 451, 126), ("в194", 194, 126), ("в118", 118, 126),
                        ("в609", 609, 126), ("прописан в527", 127, 527), ("в469", 469, 49),
                        ("на вокзале", 126, 126)):
    c, _ = store.create_character(aid, name, 0, 1)
    store.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 6184, gy = 1974, on_map = 0,"
                     " home_loc = ?, home_gx = 6184, home_gy = 1974 WHERE id = ?", (loc, home, c))
    who[name] = c
store.db.commit()
keeper = who["в467"]
for t in (119, 11500):
    store.take_quest(keeper, t, {}, True)
store.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.ABUHAMED_CUT_FIX,))
store.db.commit()
store.close()

up = accounts.Store()
rows = {n: up.character(c) for n, c in who.items()}
ok({n: (r["loc"], r["gx"], r["gy"], r["on_map"], r["pos"]) for n, r in rows.items()}
   == {"в467": (126, 6182, 1976, 0, None), "в451": (126, 6182, 1976, 0, None),
       "в194": (126, 6182, 1976, 0, None), "в118": (126, 6182, 1976, 0, None),
       "в609": (126, 6182, 1976, 0, None), "прописан в527": (127, 6184, 1974, 0, 77),
       "в469": (469, 6184, 1974, 0, 77), "на вокзале": (126, 6184, 1974, 0, 77)},
   "из 467/451/194/118/609 -- на Вокзал Абу-Хамеда, 469 (вещевой рынок Донголы, давно прошло) и вокзал"
   " не тронуты: %s" % {n: (r["loc"], r["pos"]) for n, r in rows.items()})
ok((rows["прописан в527"]["home_loc"], rows["прописан в527"]["home_gx"], rows["прописан в527"]["home_gy"])
   == (126, 6182, 1976), "прописка в 527 -- Вокзал Абу-Хамеда")
ok(sorted(r["type"] for r in up.quests(keeper)) == [119, 11500],
   "журнал не тронут: %s" % sorted(r["type"] for r in up.quests(keeper)))
ok(accounts.relocate_abuhamed_cut(up.db) == dict(moved=0, homes=0), "повторный проход ничего не находит")
up.db.commit()
up.db.execute("UPDATE characters SET loc = 467 WHERE id = ?", (keeper,))
up.db.commit()
up.close()
up = accounts.Store()
ok(up.character(keeper)["loc"] == 467 and accounts.ran(up.db, accounts.ABUHAMED_CUT_FIX),
   "второе открытие ничего не повторяет")
up.close()

print("storage(pg): %d проверок, все зелёные" % checks)
