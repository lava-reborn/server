# LAVA Online — ревизия прототипа и проект «нормального» сервера

Дата: 2026-09-16. Основание: `server/*.py` (1 616 строк кода + 900 тестов), `PROTOCOL.md`,
`ROADMAP.md`, `run.sh`, клиентские классы в `recon/as-src/lol/` (ссылки вида
`Файл.as:строка` ведут туда), `logs/game.log` живой сессии.

Ключевой вывод: прототип правильно решил всё, что *нельзя* было угадать (кодек,
инварианты очередей, разрешение id локаций, ловушка строк), и сделал это
проверяемо. Его структура — один класс `Session` с состоянием мира внутри —
исчерпана: мультиплеер, мобы и таймеры в неё не помещаются. Дальше нужен не
«ещё один cmd_*», а другой скелет, в который существующие обработчики
переезжают почти без изменений.

---

## 1. Ревизия

### 1.1 Что сделано правильно и должно остаться

| Что | Где | Почему это ценность |
|---|---|---|
| Кодек: префиксы типов, таблица экранирования с причудой `"`→`%5C`, однопроходный `unescape`, маркер `Str` для «числоподобных» строк, позиционное имя команды (коллизия с параметром `name`) | `protocol.py:40-68`, `:72-110`, `:95-105` | Выведено из `SCDataParser`/`XMLString` и закреплено 40 тестами; менять нечего, только вынести в `net/codec.py` как есть |
| UTF-8 на проводе, а не cp1251, с объяснением, *почему* (курсор парсера двигается на длину в символах) | `protocol.py:11-19` | Это тот класс ошибок, который не даёт внятного сбоя; знание задокументировано в коде |
| Инварианты протокола реализованы, а не только описаны: отказ `res=3` для нереализованных команд, ждущих `cmdAck`; **отсутствие** ack на `selPers`; ack на `lenter` только при отказе; всегда-ответ на конвейерные `ss_get`/`q_list`/`ss_get_si` | `server.py:34-42`, `:137-142`, `:237-239`, `:286-294`, `:588-601`, `:615-623` | Нарушение любого из них вешает клиент без ошибки (`XMLCCallStack.as:49-58`: снимается *первый* обработчик) |
| Разрешение id локации в файл ровно как `SSEmulator.getLocDescription`: static → deadloc → упакованная клетка пустоши | `world.py:61-110`, тест `test_locations.py:30-46` | Сервер и клиент читают сетку проходимости из одного файла; расхождение = хождение сквозь стены |
| Локация как разобранная структура (obstacles, inzones, spawns с type_id) с кэшем | `world.py:113-174` | Спавны и проходимость — единственное, что уцелело от серверных данных |
| Таблица «клетка → посёлок» как данные с ручными перекрытиями, а не хардкод | `world.py:177-209`, `data/build_settlements.py`, `data/settlements_verified.json` | Восстанавливаемо и проверяемо тестами `test_locations.py:92-144` |
| Ворота `names.known()` перед отправкой любого string id + статический обход всех спавнов в тесте + проверка предзагрузки `?all=1` | `names.py:49-56`, `server.py:313`, `test_locations.py:73-90`, `test_bootstrap.py:98-113` | Единственная защита от «строка после входа = экран логина» (`PROTOCOL.md` §9) |
| Модель учётки: дайджест `md5(cp1251(password+login))` — и credential, и ключ; отказ при совпадении дайджестов | `accounts.py:48-50`, `:87-94` | Клиент никогда не шлёт пароль; это осознано и закреплено `test_accounts.py:28-33` |
| Тесты воспроизводят *реальные* последовательности клиента, выведенные из AS-исходников, против живого сервера-подпроцесса; регрессии закреплены по месту (коллизия `name`, ненулевые делители, `g_id`) | `test_world.py`, `test_handshake.py`, `test_bootstrap.py` | Подход верный: клиент — единственный оракул, и его поведение переписано в утверждения |
| Изоляция ошибок обработчика от соединения | `server.py:143-147` | Одна ошибка не роняет игрока |
| Комментарии в коде объясняют *почему*, с указанием класса клиента | везде | Это и есть документация протокола второго уровня; при переезде переносить дословно |

### 1.2 Техдолг (с адресами)

**Архитектурный**

| # | Долг | Где | Следствие |
|---|---|---|---|
| T1 | Всё состояние мира живёт в `Session`: локация, гекс, клетка карты, летящий «leg», словарь NPC | `server.py:102-122` | Второй игрок в той же локации не существует для первого; нет объекта «комната», нечего рассылать |
| T2 | Ид NPC назначаются **на сессию**: `FIRST_NPC_ID + len(self.npcs)` | `server.py:71`, `:317` | У двух игроков один торговец имеет разные id; id игрока может совпасть с id NPC |
| T3 | Глобальные константы и побочные эффекты на импорте: `STORE = accounts.Store()`, `START_LOC`, `AVATARS`, `MOB_TYPES` читают диск при импорте модуля | `server.py:26-63`, `names.py:24-46` | Невозможно поднять два экземпляра/тест без подпроцесса; порядок импортов = порядок инициализации |
| T4 | Диспетчер `getattr(self, "cmd_"+cmd)` без схемы параметров и без проверки состояния сессии | `server.py:132-147` | `selPers`/`actPlayer`/`lenter`/`moveTo` принимаются от неавторизованного сокета (`:237-247`, `:275-277`, `:286-295`) и ведут в мир с `default_character()` (`:66-68`, `:413`, `:511`) |
| T5 | Список «кто ждёт cmdAck» — отдельное множество, не связанное с обработчиками | `server.py:34-42` | Инвариант «ровно один ack» держится на дисциплине автора, не на коде |
| T6 | Нет tick-цикла: таймеры — `loop.call_later` на сессию | `server.py:482-486` | Не сохранить/восстановить, не протестировать детерминированно, не масштабировать на мобов/респаун/ОД |
| T7 | Хардкод контента в коде: `STOCK`, `CLASS_SHAPE`, `AMMO_FOR`, `rp_info` со всеми пятёрками, `constants` | `items.py:43-94`, `server.py:187-195`, `:564-586` | Баланс из вики некуда класть, кроме как в Python |
| T8 | Синтетические string id: `name=type_id` для существ, `STRING_ID_OFFSET + type_id` для предметов | `server.py:540`, `items.py:100`, `names.py:22-33` | Два пространства склеены смещением; квесты/описания/реплики некуда нумеровать; `texts.xml` строится из имён клиента, а не из контента |
| T9 | dict-параметры без схемы: `int(p.get("sex", 0))`, `p.get("res", AVATARS[0][0])` без проверки, что `res` — из списка аватаров | `server.py:228-229`, `:240`, `:473-474` | Мусор от модифицированного клиента попадает в БД |
| T10 | `accounts.Store.__init__` мутирует модульный `DB_PATH`; `connect()` гоняет `executescript(SCHEMA)` на каждое соединение; HTTP открывает новое соединение на каждый запрос | `accounts.py:61-66`, `:53-58`, `bootstrap_http.py:187-204` | Нет миграций, нет WAL, нет одной точки владения БД |
| T11 | Пути к ресурсам и репозиторию захардкожены на конкретную машину | `world.py:19-25`, `run.sh:21-23` | Не разворачивается ни у кого другого |
| T12 | Тесты: собственный `check()`, фиксированные порты, ожидания по времени | `test_world.py:14`, `:65-77`; `test_handshake.py:6`; `test_bootstrap.py:5` | Нельзя гонять параллельно; риск флаки; нет фикстур |

**Конкретные риски**

| # | Риск | Где | Оценка |
|---|---|---|---|
| R1 | **Блокирующий SQLite в event loop**: каждый `login`, `newPers`, `save_position` делает `commit()` синхронно; БД лежит на `/mnt/c` (drvfs через OneDrive) — fsync там медленный и подвержен конфликтам синхронизации | `server.py:163`, `:172`, `:211`, `:224-230`; `accounts.py:18-21` | При 20+ игроках паузы на всех; при конфликте OneDrive — повреждение файла |
| R2 | **Нет graceful shutdown**: `run.sh stop` шлёт `pkill` (SIGTERM), обработчика сигнала нет, `finally: sess.close()` не выполняется → позиции всех онлайн-игроков теряются | `run.sh:45`, `server.py:706-718`, `:690-694` | Воспроизводится каждой остановкой |
| R3 | **Неограниченный буфер кадра**: `FrameReader._buf` растёт, пока не придёт `\0` | `protocol.py:174-187` | Один сокет без NUL = OOM |
| R4 | **Нет rate-limit и нет таймаута hello**: сокет может молчать вечно или слать 10⁵ `getInfo`/с; каждый кадр логируется на INFO целиком | `server.py:666-694`, `:129`, `:133` | Тривиальный DoS; лог растёт на гигабайты |
| R5 | **Путь не проверяется**: сервер эхом возвращает любой `path`, ставит `pos = path[-1]` | `server.py:646-663` | Телепорт сквозь стены модифицированным клиентом; `PROTOCOL.md` §11 прямо требует проверки |
| R6 | **`close()` вызывается дважды** (`cmd_logout` + `finally`) → двойной `save_position`, `writer.close()` на закрытом транспорте | `server.py:205-213`, `:694` | Пока безвредно; станет гонкой с write-behind |
| R7 | **Молчаливый пустой контент**: `names.py` глотает любое исключение при чтении `mobs.xml`/`objects.xml` → `ALL = {}` → `known()` всегда False → `populate()` тихо ставит 0 NPC | `names.py:24-33`, `server.py:313-315` | Сервер «работает», мир пустой, в логе только «0 inhabitants» |
| R8 | **Кадры-«взрывы» без интереса**: `populate()` шлёт 2×N кадров всем спавнам локации; клиент исполняет очередь по 40 мс на кадр (`SCMCommands.as:41-57`) | `server.py:297-332` | На локации с 60 спавнами — секунды прогрузки; с игроками сверху — больше |
| R9 | **Вероятный дубль в чате**: клиент печатает своё сообщение сам по `cmdAck res=0` (`Chat.as:242-256`: `sendFromID = Gamer.ID; newMessage(...)`), а сервер ещё и эхо шлёт | `server.py:411-415` | Проверить на живом клиенте; для мультиплеера эхо отправителю не нужно |
| R10 | Гонок asyncio сейчас **нет** (все обработчики синхронные, общих изменяемых структур между сессиями нет, кроме кэшей) — но именно это и сломается при появлении комнат и таймеров, если не зафиксировать правило «весь мир мутируется только из одного loop» | `server.py:682-689` | Нужно закрепить как принцип до появления `Room` |
| R11 | HTTP-бутстрап слушает только `127.0.0.1` жёстко, игровой — `0.0.0.0` | `bootstrap_http.py:281`, `server.py:26` | Внешний игрок не получит `main.swf`/`texts.xml` |

---

## 2. Целевая архитектура

Python 3.12, asyncio, один процесс, **один event loop владеет всем состоянием
мира**. Никаких потоков в игровой логике; потоки — только для БД (write-behind)
и HTTP статики. Никаких блокирующих вызовов в обработчиках.

### 2.1 Модули и границы

```
server/
  main.py              композиция: Config → Content → World → Persist → Net; сигналы
  config.py            dataclass Config из env + YAML (ни одного пути в коде)

  net/                 «провод», ничего не знает про игру
    codec.py           = protocol.py (без изменений)
    connection.py      FrameReader с лимитом, очередь исходящих + drain, rate-limit,
                       policy-file, таймаут hello, per-connection id
    dispatcher.py      реестр команд: имя → (handler, schema, states, ack_policy);
                       валидация параметров, зеркало FilterManager, контроль «ровно один ack»

  session/             «кто на проводе»
    session.py         Session: state ∈ {CONNECTED, HELLO, AUTHED, CHAR, IN_LOCATION,
                       ON_MAP, CHANGING, DEAD}; account, character, player-entity
    handlers/          auth.py, character.py, location.py, map.py, chat.py,
                       items.py, quests.py, mail.py, social.py (заглушки с ack)

  world/               «где что стоит», единственный владелец изменяемого состояния
    world.py           World: реестр Room по loc_id (ленивый), GlobalMap, IdAllocator,
                       Scheduler, tick()
    room.py            Room = экземпляр локации: сетка, entities, subscribers,
                       broadcast(frame_fn), enter/leave, spawns/respawn
    gmap.py            GlobalMap: позиции игроков, радиус интереса v_rad, heartbeat ≤3 с,
                       «legs» перелётов
    geometry.py        = world.py (разбор файлов, pack/unpack, location_at) + соседство
                       гексов и проверка пути
    entities.py        Entity(id, kind, pos) → Player(session, character), NPC(type,
                       services), Mob(type, hp, ai)
    scheduler.py       heapq таймеров на виртуальных часах; выполняется из tick()
    ai.py              поведение мобов (idle/patrol/aggro/attack/flee)
    combat.py          выстрел/удар: ОД, дальность, попадание, faAim/faShot/faHit/…

  game/                правила, не зависящие от сети
    inventory.py       oid, слоты, стопки, вес, ss_* ответы
    trade.py, bank.py, quests.py, mail.py, chat.py, party.py

  content/             данные → dataclasses, валидация на старте
    loader.py          YAML/JSON → Mobs, Items, Stocks, Quests, Constants
    strings.py         реестр string id (замена names.py) + генерация texts.xml

  persist/
    db.py              соединение, PRAGMA, миграции (schema_version)
    repo.py            AccountRepo, CharacterRepo, ItemRepo, QuestRepo, MailRepo
    writer.py          write-behind: очередь «грязных» агрегатов → поток → commit батчами

  http/
    bootstrap.py       = bootstrap_http.py; texts.xml отдаётся из предсобранного файла

tests/
  unit/                codec, geometry, content, strings, scheduler, dispatcher
  integration/         FakeClient (из test_world.Client) + два клиента
```

Правила границ:

* `net` импортирует только `codec`. `session` знает `net` и `world`. `world` не
  знает про `session` (рассылает через абстракцию `Subscriber.send(frame)`).
  `game` не знает ни про сеть, ни про БД (чистые функции над сущностями).
  `persist` знает про сущности, `world` про `persist` — только через
  `mark_dirty()`.
* Никакой модуль не читает диск при импорте (снимает T3, R7: ошибка загрузки
  контента = падение на старте с понятным сообщением, а не пустой мир).

### 2.2 Поток кадра

```
 TCP ──► Connection.read()
          │ FrameReader (лимит 64 КБ/кадр, лимит 200 кадров/с)
          ▼
        codec.decode ──► (name, params)
          │
          ▼
        Dispatcher.dispatch(session, name, params)
          ├─ 1. состояние: name ∈ allowed[session.state]?      (зеркало FilterManager.as:28-52)
          ├─ 2. схема: типы/диапазоны обязательных параметров    (снимает T9)
          ├─ 3. вызов handler(ctx, params)                       (ctx = session, world, content, now)
          └─ 4. ack-контроль: если name ∈ EXPECTS_ACK и handler
                не вызвал ctx.ack(res) ровно один раз → ctx.ack(3) + ERROR в лог (снимает T5)
          │
          ▼
        Handler мутирует World: room.move(player, path) / gmap.travel(...) / inventory.use(...)
          │ (внутри — ни одного await; всё синхронно на loop)
          ▼
        World испускает события → Room.broadcast(lambda viewer: frame) / session.send(frame)
          │  frame_fn получает viewer, потому что id=0 всегда «сам» (Gamer.as:31)
          ▼
        Connection.queue.put(bytes) → задача-писатель → writer.write + drain (backpressure)

 Tick (600 мс, отдельная задача):  World.tick(now)
   ├─ Scheduler.run_due(now)          прибытия на карте, респаун, перезарядка, эффекты
   ├─ APManager для war-локаций       +aspd ОД, рассылка c_ap при расхождении
   ├─ Mob AI step                     маршруты (200 мс/гекс = 3 гекса за тик)
   ├─ GlobalMap.heartbeat             userMove vx=0 для стоящих, кому не слали >2.5 с
   └─ Persist.flush_dirty()           не чаще раза в N с
```

Все `send()` в обработчике только кладут байты в очередь; `drain` делает
писатель. Так исчезает ситуация «сотня кадров `populate()` до первого drain»
(`server.py:682-689`) и появляется контроль переполнения очереди (медленный
клиент отключается, а не тормозит loop).

### 2.3 Комната и сущности

```python
class Entity:            # world/entities.py
    id: int              # глобально уникальный, > 0; 0 зарезервирован под «сам»
    kind: Kind           # PLAYER | NPC | MOB
    room: Room | None
    pos: int             # гекс
    rtype: int           # что слать в lch: 0..7 для NPC/MOB (Entity.as:17-24), -1 для игрока
    hp, hp_max, sp, sp_max
    def info_frame(self, viewer) -> (name, params)   # userInfo*/userInfo_Player

class Player(Entity):   session, character_id, stats, inventory, quests, ap, war_timer, on_map, gx, gy, leg
class NPC(Entity):      type_id, services (trade/repair/bank/heal/home), stock_id, give_quests
class Mob(Entity):      type_id, ai_state, spawn_point, respawn_at, loot_table, aggro_target

class Room:              # world/room.py
    loc: geometry.Location
    entities: dict[int, Entity]
    players: set[Player]                 # подписчики
    war: bool
    def enter(self, p: Player, pos): ...  # lch;newUser остальным, снимок новичку
    def leave(self, p: Player): ...       # lch;lostUser остальным
    def broadcast(self, frame_fn, exclude=None)
    def move(self, e: Entity, path) -> bool   # проверка соседства/препятствий/занятости
```

Комнаты создаются лениво при первом входе и выгружаются через N минут без
игроков (мобы «замораживаются» с сохранением респауна). Пустошь — тоже
комнаты, ключ — упакованная клетка; для них разумный TTL меньше.

### 2.4 Tick-цикл и таймеры

* Один `asyncio.Task` `World.run()`: `while True: await sleep(next_tick - now); tick(now)`.
  Период 600 мс — период `APManager.dt` клиента (`APManager.as:10`), внутри —
  подшаги по 200 мс для движения мобов, если понадобится.
* `Scheduler`: `heapq` пар `(due, seq, callback, args)`; `schedule(delay, fn)`.
  Всё, что сейчас `loop.call_later` (`server.py:486`), переезжает сюда.
  Часы инжектируются (`clock: Callable[[], float]`) — интеграционные тесты
  крутят время вручную, а не ждут 5 секунд (`test_world.py:229`).
* Тик измеряется; если `tick()` > 100 мс — WARN с разбивкой по фазам.

### 2.5 Персистентность

Принципы: SQLite остаётся (WAL, `synchronous=NORMAL`), файл — на ext4 внутри
WSL (`~/lava/data/lava.db`), не на `/mnt/c` и не в OneDrive. Все чтения —
при логине/выборе персонажа через `asyncio.to_thread`. Все записи — через
write-behind: сущность помечается `dirty`, писатель раз в 5 с и при
logout/shutdown сбрасывает батчем в одной транзакции. Миграции — нумерованные
файлы `persist/migrations/NNN_*.sql`, версия в `schema_version`.

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE schema_version (version INTEGER NOT NULL);

CREATE TABLE accounts (
  id           INTEGER PRIMARY KEY,
  login        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
  hash         TEXT    NOT NULL UNIQUE,   -- md5(cp1251(password+login)); единственное, что шлёт клиент
  role         TEXT    NOT NULL DEFAULT 'player',   -- player | gm | admin  (dev-команды чата)
  created      INTEGER NOT NULL,
  last_login   INTEGER,
  last_ip      TEXT,
  banned_until INTEGER,                   -- NULL = не забанен; kickban;seconds=
  ban_reason   TEXT
);

CREATE TABLE characters (
  id          INTEGER PRIMARY KEY,
  account_id  INTEGER NOT NULL REFERENCES accounts(id),
  slot        INTEGER NOT NULL,           -- persInfo;num=
  name        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
  sex         INTEGER NOT NULL,           -- persType тела (PersInfo.as:40-44)
  res         TEXT    NOT NULL,           -- id портрета из avatars/list.xml, та же строка
  loc         INTEGER,                    -- id локации: файл или упакованная клетка
  pos         INTEGER,                    -- гекс = gy*width+gx
  gx          REAL, gy REAL,              -- клетка карты (дробная только в полёте — не сохранять)
  on_map      INTEGER NOT NULL DEFAULT 0,
  home_loc    INTEGER,                    -- can_set_home
  dead        INTEGER NOT NULL DEFAULT 0, -- persInfo;death=, resurrect
  created     INTEGER NOT NULL,
  played_sec  INTEGER NOT NULL DEFAULT 0,
  deleted_at  INTEGER,
  UNIQUE (account_id, slot)
);

-- Группы в rp_info идут «маска + плотный список» (server.py:571-586);
-- фиксированные массивы хранятся JSON-ом, чтобы маппинг был тривиальным.
CREATE TABLE character_stats (
  character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
  lvl          INTEGER NOT NULL DEFAULT 1,
  xp           INTEGER NOT NULL DEFAULT 0,
  hp           INTEGER NOT NULL, hp_max INTEGER NOT NULL,
  sp           INTEGER NOT NULL, sp_max INTEGER NOT NULL,
  ap_max       INTEGER NOT NULL DEFAULT 20,
  afro         INTEGER NOT NULL DEFAULT 0,   -- валюта (userInfo_Player;afro=)
  gold         INTEGER NOT NULL DEFAULT 0,   -- премиум-валюта
  rep          INTEGER NOT NULL DEFAULT 0,   -- одна фракция, 9 рангов на клиенте
  bg_rep       INTEGER NOT NULL DEFAULT 0,
  bg_pen       INTEGER NOT NULL DEFAULT 0,
  attribs      TEXT NOT NULL,   -- JSON [5]: сила, ловкость, телосложение, восприятие, интеллект
  skills       TEXT NOT NULL,   -- JSON [5]: уровни
  skills_xp    TEXT NOT NULL,   -- JSON [5]
  specs        TEXT NOT NULL,   -- JSON [15]; -1 = не изучена
  specs_xp     TEXT NOT NULL,   -- JSON [15]
  free_points  INTEGER NOT NULL DEFAULT 0
);

-- Один экземпляр предмета где бы он ни лежал. На проводе oid кодирует тип:
-- oid = (uniq << 24) | (type_id << 8) | root_type_id  (ROADMAP §3 п.4);
-- разрядность uniq в Item.as проверить до реализации (см. задачу P1-12).
CREATE TABLE items (
  id           INTEGER PRIMARY KEY,          -- uniq
  type_id      INTEGER NOT NULL,             -- objects.xml
  owner_kind   TEXT    NOT NULL,             -- char | bank | mail | auction | loot | trader
  owner_id     INTEGER NOT NULL,             -- character_id / mail_id / lootbag_id …
  slot         INTEGER NOT NULL,             -- слот (Slot.as); контейнер = свой slot
  idx          INTEGER NOT NULL DEFAULT 0,   -- позиция внутри контейнера
  count        INTEGER NOT NULL DEFAULT 1,   -- стопка ≤ max_count
  break_abs    INTEGER,                      -- прочность
  ammo_type    INTEGER, ammo_count INTEGER,  -- магазин
  fire_mode    INTEGER NOT NULL DEFAULT 0,
  flags        INTEGER NOT NULL DEFAULT 0,   -- бит0 квестовый, бит1 непередаваемый
  props        TEXT,                         -- JSON: апгрейды, комплект
  created      INTEGER NOT NULL
);
CREATE INDEX items_owner ON items(owner_kind, owner_id, slot, idx);

CREATE TABLE character_quests (
  character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  quest_id     INTEGER NOT NULL,             -- content/quests.yaml
  status       INTEGER NOT NULL,             -- 0 взят, 1 выполнен, 2 сдан, 3 отменён
  progress     TEXT    NOT NULL,             -- JSON: {"kills":{"1234":3},"items":{"4380":1}}
  taken_at     INTEGER NOT NULL,
  done_at      INTEGER,
  PRIMARY KEY (character_id, quest_id)
);
CREATE INDEX quests_done ON character_quests(character_id, status);

CREATE TABLE mail (
  id          INTEGER PRIMARY KEY,
  to_char     INTEGER NOT NULL REFERENCES characters(id),
  from_char   INTEGER REFERENCES characters(id),   -- NULL = система
  from_name   TEXT    NOT NULL,
  subject     TEXT    NOT NULL,
  body        TEXT    NOT NULL,
  tariff      INTEGER NOT NULL DEFAULT 0,   -- 0 обычное, 1 экспресс, 2 клан, 3 экспресс-клан (svml)
  afro        INTEGER NOT NULL DEFAULT 0,
  gold        INTEGER NOT NULL DEFAULT 0,
  flags       INTEGER NOT NULL DEFAULT 0,   -- бит0 прочитано, бит1 вложения забраны (uldml)
  sent_at     INTEGER NOT NULL,
  deliver_at  INTEGER NOT NULL,             -- sent_at + time[tariff]
  expires_at  INTEGER
);
CREATE INDEX mail_inbox  ON mail(to_char, deliver_at);
CREATE INDEX mail_outbox ON mail(from_char, sent_at);
-- вложения = items(owner_kind='mail', owner_id=mail.id)

-- updMark/rmMark адресуют ИНДЕКСОМ в клиентском массиве (PROTOCOL.md §11),
-- поэтому порядок — часть данных.
CREATE TABLE map_marks (
  character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  ord          INTEGER NOT NULL,
  gx           INTEGER NOT NULL, gy INTEGER NOT NULL,
  title        TEXT NOT NULL, info TEXT NOT NULL,
  PRIMARY KEY (character_id, ord)
);

CREATE TABLE bank_accounts (
  character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
  afro         INTEGER NOT NULL DEFAULT 0,
  gold         INTEGER NOT NULL DEFAULT 0,
  weight_cap   INTEGER NOT NULL DEFAULT 50000     -- updWeight
);
-- содержимое банка = items(owner_kind='bank', owner_id=character_id)

CREATE TABLE audit_log (
  id           INTEGER PRIMARY KEY,
  ts           INTEGER NOT NULL,
  account_id   INTEGER, character_id INTEGER,
  kind         TEXT NOT NULL,     -- login, logout, kick, admin_cmd, trade, mail, death …
  data         TEXT               -- JSON
);
CREATE INDEX audit_ts ON audit_log(ts);

-- P3: clans(id, name, head_char, perms_mask, created), clan_members(clan_id, character_id, rank),
--     auction_lots(id, seller, item_id, a_bid, a_buyout, g_bid, g_buyout, ends_at, bidder),
--     bg_ratings(character_id, type, rating)
```

Что из этого нужно уже для перехода с прототипа: `accounts` (+ `role`,
`banned_until`), `characters` (совместимо с текущей, добавляются колонки),
`character_stats`. Остальное — по мере фич, миграциями.

### 2.6 Контент как данные

Каталог `content/` (не `data/` — там сейчас скрипты и БД):

```
content/
  constants.yaml      кадр constants (server.py:187-195) + TRAVEL_SPEED, VIEW_RADIUS, aspd/amax
  start.yaml          стартовая клетка, аватар, стартовые предметы/деньги
  items/              по корневым типам: firearms.yaml, wear.yaml, ammo.yaml, heal.yaml, coldarms.yaml
                      (вывод data/wiki_extract.py + ручные правки; поля 1:1 с ss_si_*)
  stocks.yaml         type_id торговца → [type_id предметов], pmod/smod/rmod
  mobs.yaml           type_id → hp/sp/armor/lvl/xp/speed/aggro/attack/respawn_s/loot/phrases
  loot_tables.yaml    имя → [{type_id, chance, count:[min,max]}]
  quests.yaml         id → {type: kill|bring|deliver, giver, taker, targets, reward, texts}
  npcs.yaml           type_id → services (trade/repair/bank/heal/home/teach), give_quests, hello
  settlements.json    = data/settlements.json (+ verified)
  strings.yaml        ключ → текст (см. 2.7)
  strings.lock.json   ключ → id (генерируется, коммитится, никогда не перенумеровывается)
```

Пример `mobs.yaml`:

```yaml
1234:
  name: "Шакал"                    # → строка mob.1234.name
  lvl: 3
  hp: 60
  sp: 40
  armor: 1
  speed_ms: 250                    # мс на гекс (клиент анимирует 200, LocWalker.as:74)
  aggro_radius: 6
  attack: {kind: melee, dmg: [4, 9], sdmg: [1, 2], ap: 5, range: 1}
  respawn_s: 120
  xp: 25
  loot: jackal_common
  phrases: {idle: [mob.1234.idle.0], detect: [], attack: [], run: [], death: []}
```

`content/loader.py` читает всё на старте, валидирует ссылки (моб → лут → предметы
→ строки; спавны локаций → мобы или явный список «пропускать») и падает с
перечнем ошибок. То, что сейчас делает `test_locations.py:79-90` в тесте,
делается при каждом запуске.

### 2.7 Строки

Единый реестр вместо трёх словарей `names.py:44-46`:

* Ключи — смысловые: `mob.<type_id>.name`, `item.<type_id>.name`,
  `item.<type_id>.desc`, `npc.<type_id>.hello.<n>`, `quest.<id>.title`,
  `quest.<id>.text`, `loc.<id>.title`.
* `strings.lock.json` фиксирует id за ключом. Новые ключи получают следующий
  свободный id; удалённые не переиспользуются. Так id стабильны между
  запусками и версиями, и предзагруженный у клиента `texts.xml` никогда не
  расходится с тем, что шлёт сервер.
* `tools/build_texts.py` собирает `build/texts.xml` (сейчас 1.6 МБ строится
  в памяти на каждый старт HTTP — `names.py:62-72`); HTTP отдаёт файл как
  статику с `Content-Length`, при желании gzip.
* Сервер на старте загружает lock и утверждает: любой id, который может
  попасть на провод (мобы спавнов, предметы стоков, квесты, реплики), есть в
  lock. `strings.known(id)` остаётся последним предохранителем перед `send`.
* Пока настоящие тексты не восстановлены, `strings.yaml` генерируется из
  `mobs.xml`/`objects.xml`/`npc_names.json` тем же инструментом — поведение
  прототипа сохраняется, но через один канал.

Это убирает `STRING_ID_OFFSET` и `name=type_id`: string id перестаёт быть
«type_id с оговорками».

---

## 3. Мультиплеер: что должен получить клиент

Все имена — из `lol/core/location/Location.as`, `lol/core/globmap/GlobalMap.as`,
`lol/core/player/PlayerRegister.as`, `lol/core/Master.as`.

### 3.1 Аксиома: `id=0` — это всегда «я»

`Gamer.ID = 0` (`Gamer.as:31`); `Location.getWalker(id)`: `!id ? gamer.walker :
playerList[id].walker` (`Location.as:157-161`); `PlayerRegister.getPlayer` то же
(`PlayerRegister.as:27-31`); `GlobalMap.userMove`: `!id → gamer`
(`GlobalMap.as:99-102`). Следствие: **один и тот же факт кодируется разными
кадрами для разных получателей**. Если игрок A (id 517) прошёл путь, A получает
`userMove;id=0;path=…`, все остальные — `userMove;id=517;path=…`. Поэтому
`Room.broadcast` принимает не кадр, а функцию `frame_fn(viewer)`, и глобальные
id сущностей никогда не равны 0.

### 3.2 В локации

Клиент подписан (`Location.as:29-43`) на: `lch`, `prepare`, `userMove`, `breakMv`,
`cor_pos`, `ss_loot`, `faAim/faShot/faHit/faWall/faMiss`, `heal`, `caHit/caMiss`.

**Появление другого игрока** — `lch;newUser=<id>;pos=<гекс>;rtype=<r>;`
(`Location.lch`, `Location.as:60-70`: все три поля обязательны, иначе кадр
игнорируется). `rtype` решает класс на клиенте (`PlayerRegister.createPlayer`,
`PlayerRegister.as:63-103`): 0..7 — NPC/моб, **любое другое → `Player`**.
Разумно слать `rtype=-1`: для нового id это `Player`, для уже известного
`PlayerRegister.addPlayer` при `-1` перезапрашивает экипировку
(`PlayerRegister.as:51-62`). Дополнительно: `refl=1` регистрирует сущность без
фигуры (`Location.as:62-65`) — для игроков не нужно.

Что клиент делает сам сразу после `lch` для игрока (и что сервер обязан
ответить каждому подписчику отдельно):

1. `Entity` конструктор → `Player.requestInfo` → **`getInfo;lvl=0;id=<id>;type=0;`**
   (`Entity.as:38-41`, `Player.as:19-24`). Ответ: **`userInfo_Player;id=<id>;name=@…@;sex=;res=@…@;ail=;ally=;lvl=;rep=|…|;bg_rep=;bg_pen=;clan=;hl=;pr=;`**
   — как для себя (`server.py:512-517`), но без `afro/gold/tr` (их читает только
   `Gamer.userInfo`, `Gamer.as:54-62`). Имя — текст, не string id
   (`Entity.userInfo`, `Entity.as:67-70`); пустое имя клиент заменяет на
   «Солдат СА» (`PlayerRegister.as:167-170`). Тело фигуры — из `sex`
   (`PersInfo.as:40-44`), портрет — из `res`.
2. `Player` конструктор в `LOCAL_STATE` → `equipment.getStuff(3, id)` →
   **`ss_get;target=<id>;slot=3;`** с обработчиком в отдельной очереди `ss_ack`
   (`Player.as:11-18`, `StuffManager.as:18-25`). Сервер обязан ответить
   **`ss_ack;o_list=|…|;`** (пусто — допустимо), иначе очередь `ss_ack`
   сдвигается для всех последующих запросов экипировки.
3. Здоровье/выносливость чужого — `usrUp;id=<id>;hcur=;hmax=;scur=;smax=;`
   (`Master.usrUp`, `Master.as:132-137`).

**Движение** — `userMove;id=<id>;path=|a|b|c|;` (`Location.userMove`,
`Location.as:184-200`): клиент строит `createMove` по номерам гексов; 200 мс на
гекс (`LocWalker.as:74`). Первый элемент пути — текущий гекс. Занятость гексов
клиент ведёт сам (`Location.addPlayer:113-118`, `finishPart:167-174`), но это не
освобождает сервер от проверки: путь должен быть цепочкой соседних проходимых
незанятых гексов от текущей позиции сущности.

**Коррекция** — `breakMv;id=;pos=;` (стоп + телепорт, снимает ожидание
`cmdAck` мувера: `Location.as:249-260`) и `cor_pos;id=;pos=;` (то же, но клиент
сам перепрокладывает путь к прежней цели: `:261-273`).

**Исчезновение** — `lch;lostUser=<id>;` (`Location.as:71-75`). Клиент удаляет
фигуру и пишет событие «игрок ушёл» по имени из реестра.

**Отношения** — `lch;enemy=<id>;` (`:79-82`), `lch;dead=<id>;` (`:84-92`),
`prepare;id=;time=;` (`:94-100`). `lch;ws=0|1` переключает war-режим локации
всем (`:56-59`).

**Чат в локации** — `userMsg;entry=@…@;group=0;from=<id>;nick=@…@;`. Без
`nick` клиент берёт имя из реестра игроков (`Chat.getName`, `Chat.as`), поэтому
для каналов, где собеседник не в комнате (мир, торговля, приват), `nick`
обязателен. Своё сообщение клиент печатает сам по `cmdAck;res=0`
(`Chat.as:242-256`) — отправителю рассылка не нужна (см. R9).

### 3.3 Порядок при входе в локацию

Клиентская сторона (`Master.as`): `lcall` → загрузка ресурсов → `lenter;accept=1`
→ ждёт кадр `lenter` → `currentLocation.addGamer(pos)` (`Master.as:278`), т.е.
**себя клиент добавляет сам**, `lch;newUser=<свой id>` слать нельзя. Между
`lcall` и `lenter` клиент в `CW_STATE` и может слать только `lenter`/`gg_info`
(`FilterManager.as:131-137`); сервер в этом окне ничего в комнату не шлёт
(объект `Location` уже подписан на `lch` с момента создания `LocGen`, но сетка
может быть не готова — прототип верно шлёт снимок только после `lenter`,
`server.py:294-295`).

Серверная последовательность `Room.enter(p)`:

```
1. p.session.send  lenter;pos=<гекс>;aspd=;amax=;
2. для каждой сущности e ≠ p в комнате:
       p.session.send  lch;newUser=e.id;pos=e.pos;rtype=e.rtype;
       (NPC/мобам можно сразу и userInfo*, как сейчас; игрокам не надо —
        клиент сам пошлёт getInfo/ss_get)
3. для каждого игрока q ≠ p:
       q.session.send  lch;newUser=p.id;pos=p.pos;rtype=-1;
4. если p шёл по локации в момент входа кого-то — не бывает: вход = стоп.
```

Пункт 2 стоит фильтровать по интересу, когда локация большая (R8): сначала
всё в радиусе N гексов, остальное — по мере приближения (это же даёт
`lch;lostUser` при удалении). Для первого мультиплеера достаточно «вся
комната».

`Room.leave(p)` (chWorld, /goto, logout, обрыв): всем остальным
`lch;lostUser=p.id`. Самому p ничего: на `gmap` клиент убивает `currentLocation`
(`Master.gmap`, `Master.as:189-190`), на новом `lenter` — тоже (`:274`), и в
`kill()` сам вызывает `removePlayer` для всех (`Location.as:743-746`).

Обрыв соединения = `leave` + `dirty` + запись через writer; повторный вход
восстанавливает позицию из БД, как сейчас (`server.py:249-273`).

### 3.4 На глобальной карте

Подписки `GlobalMap.as:19-23`: `newUser`, `userLost`, `userMove`, `moveAck`, `marks`.

* Свои: `gmap;x=;y=;v_rad=;` (радиус интереса — сервер сам задаёт его как
  радиус рассылки), `moveAck;vx=;vy=;t=;` (только скорость; прибытие сервер
  подтверждает `userMove;id=0;…;vx=0;vy=0`).
* Чужой появился: `newUser;id=;dx=;dy=;` — **смещение, и клиент вычитает**:
  `x = gamer.x - dx` (`GlobalMap.as:44-48`). Либо не слать `newUser` вовсе:
  `userMove` с неизвестным id сам добавляет объект (`GlobalMap.as:103-106`) уже
  с абсолютными координатами — проще и без путаницы единиц.
* Чужой двигается/стоит: `userMove;id=;dx=<abs x>;dy=<abs y>;vx=;vy=;t=;`.
  **Heartbeat ≤ 3 с** на каждого видимого, даже стоящего: 3 с тишины — объект
  гаснет, 6 с — удаляется (`MapObject.checkLive`, `MapObject.as:60-84`).
  Реализация: тик карты раз в 600 мс, слать тем, кому не слали > 2.4 с.
* Чужой ушёл из радиуса/в локацию: `userLost;id=;`.
* Интерес: множество видимых = игроки на карте в квадрате `v_rad`; пересчёт на
  тике; разность множеств → `newUser`/`userLost`.

### 3.5 Переход между локациями и картой

```
A в комнате R1 нажимает chWorld
  → cmdAck;res=0 (или 39 — таймер боя, Master.as:157-161)
  → Room R1.leave(A):  всем в R1  lch;lostUser=A
  → GlobalMap.add(A):  A получает gmap;…; соседям — userMove;id=A;… (или newUser)
A на карте нажимает chWorld над клеткой
  → cmdAck;res=0 → GlobalMap.remove(A): соседям userLost;id=A
  → lcall;id=<loc>;ws=;ie=0;g_id=<клетка>  (только A)
  → ждём lenter;accept=1 → Room R2.enter(A) (3.3)
/goto (админ): то же, что вход с карты, минус карта.
```

Состояние сессии на сервере зеркалит `Master.currentState`: `CHANGING` между
`chWorld` и `lenter`; в нём принимаются только `lenter`, `gg_info`, `logout`.

---

## 4. Миграция без остановки входа

Инвариант каждого шага: `bash tools/test.sh` (все шесть наборов) зелёный, и
живой вход через `run.sh` работает. Каждый шаг — отдельный коммит.

| Шаг | Что | Как сохранить зелёные тесты | Новые тесты |
|---|---|---|---|
| 0 | `tools/test.sh`, запускающий шесть наборов; порты тестов — из свободного `socket.bind(0)`, а не константы | Тесты не меняют смысла, только берут порт из env | — |
| 1 | `net/connection.py`: вынести из `handle_client` (`server.py:666-694`) чтение, `FrameReader` с лимитом, очередь исходящих с писателем, policy-запрос, таймаут hello 20 с. `Session.send` → `conn.send` | Кадры и порядок не меняются | `unit/test_connection.py`: лимит кадра, кадры после закрытия, backpressure |
| 2 | `net/dispatcher.py`: реестр `@command("moveTo", ack="explicit", states=...)`; `cmd_*` переезжают в `session/handlers/*.py` как функции `(ctx, p)`; `EXPECTS_ACK` становится метаданными; ack-контроль сначала в режиме «только лог», затем строгий; фильтр состояний тоже сперва «только лог» | `test_world.py` проходит без правок — провод тот же | `unit/test_dispatcher.py`: каждая команда из `EXPECTS_ACK` даёт ровно один `cmdAck` при любых параметрах (fuzz); `selPers` до `login` отвергается; `moveTo` в `CHANGING` отвергается |
| 3 | `world/`: `geometry.py` = текущий `world.py`; `Room`, `Entity`, `IdAllocator`; `Session.loc/pos/npcs` → `Player.room/pos`, `Room.entities`; `populate()` → `Room.snapshot_for(p)`; id NPC глобальные (комната создаёт их один раз) | `test_world.py:113-125` читает `newUser=` из кадра — не привязан к 100+, проходит | `unit/test_room.py`: enter/leave, id стабильны между двумя входами |
| 4 | Broadcast: `Room.players`, `frame_fn(viewer)`, `lch;newUser/lostUser`, `userMove` другим, `userMsg group=0` другим, ответы на `getInfo type=0`/`ss_get target=<id>` для чужих игроков | Одиночные сценарии не меняются | **`integration/test_two_clients.py`** (см. ниже) |
| 5 | `world/scheduler.py` + `World.run()`; `arrive()` через scheduler; `GlobalMap` с интересом и heartbeat; виртуальные часы для тестов | `test_world.py:229-231` ждёт прибытия 5 с — оставить как e2e, но добавить быстрый unit с виртуальным временем | `unit/test_scheduler.py`; `integration/test_map_two_clients.py` |
| 6 | `persist/`: `db.py` с WAL и миграцией 001 (текущая схема + `role`, `banned_until`), `repo.py`, `writer.py`; чтения через `to_thread`; SIGTERM/SIGINT → `shutdown;seconds=` всем, `flush`, закрыть слушатели | `test_accounts.py` переезжает на `AccountRepo` с тем же API | `integration/test_shutdown_saves.py`: SIGTERM после `moveTo` → позиция в БД |
| 7 | `content/` + `loader.py`; `STOCK`/`CLASS_SHAPE`/константы → YAML; `strings.py` + lock + `build_texts.py`; `names.py` остаётся тонкой обёрткой над `strings` | `test_bootstrap.py:104-113` проверяет предзагрузку — проходит, если lock покрывает всё | `unit/test_content.py`: все ссылки разрешаются; `unit/test_strings_lock.py`: lock не перенумеровывается |
| 8 | Мобы (spawn/respawn/AI), бой, инвентарь, квесты — уже фичами на новом скелете | — | по фиче |

**Интеграционный тест с двумя клиентами** (шаг 4), библиотека — `Client` из
`test_world.py:56-80`, вынесенная в `tests/fake_client.py` с методами
`login(cred)`, `enter()`, `expect(name, within=2)`:

```
A и B регистрируются, входят, оба lenter в локацию 102
  B.expect("lch") с newUser=<A.id> и rtype=-1      (порядок входа: A первый → A видит B при его входе)
  A.expect("lch") с newUser=<B.id>
B шлёт getInfo;lvl=0;id=<A.id>;type=0  → B.expect("userInfo_Player") с id=<A.id>, name=@A@
B шлёт ss_get;target=<A.id>;slot=3     → B.expect("ss_ack")
A шлёт moveTo;path=|p0|p1|;            → A.expect("cmdAck"), A.expect("userMove") id=0;
                                          B.expect("userMove") id=<A.id>; path тот же
A шлёт userMsg;entry=@привет@;group=0; → A.expect("cmdAck"); B.expect("userMsg") с from=<A.id>, nick=@A@
A шлёт chWorld                          → B.expect("lch") с lostUser=<A.id>
B шлёт chWorld; оба на карте в одной клетке
  → каждый expect("userMove") с чужим id в течение 3 с (heartbeat), дважды подряд
A входит в клетку (chWorld)             → B.expect("userLost") id=<A.id>
A logout; B шлёт moveTo — сервер жив, B.expect("cmdAck")
```

Плюс негативный: клиент C без `login` шлёт `selPers;num=0;` и `lenter;accept=1;`
— не получает `lcall`/`lenter`, соединение закрыто или команда отвергнута; A и
B этого не замечают.

---

## 5. Операционка

**Конфигурация.** Один `Config` (`config.py`) из `LAVA_*` env с fallback на
`config.yaml`: `res_root`, `db_path`, `game_host/port`, `http_host/port`,
`policy_port`, `content_dir`, `log_level`, `wire_log` (bool), `tick_ms`,
`travel_speed`, `view_radius`, `max_frame`, `frames_per_sec`, `dirty_flush_s`,
`room_ttl_s`, `admin_logins`. Ни одного пути в коде (`world.py:19-25`,
`run.sh:21-23`). Стартовый лог печатает эффективную конфигурацию.

**Логирование.** `logging` с JSON- или key=value-форматом, полем `sid`
(id соединения) и `char` в каждой записи через `ContextVar`; уровни: INFO —
вход/выход/переходы/ошибки, DEBUG — провод (то, что сейчас на INFO,
`server.py:129,133`), включается флагом `wire_log` на лету через админ-команду.
HTTP — тоже через `logging`, не `print` (`bootstrap_http.py:131`). Ротация
`RotatingFileHandler` 50 МБ × 10. Отдельный канал `audit` → таблица
`audit_log`.

**Метрики.** Счётчики в процессе: сессии онлайн, кадры in/out, байты, неизвестные
команды, ack-несоответствия, отвергнутые фильтром, длительность тика (гистограмма),
глубина очереди writer, комнаты в памяти, мобы. Отдаются `GET /metrics` на
HTTP-бутстрапе в формате Prometheus text (пишется вручную, без зависимостей) и
`GET /status` JSON для скриптов. Алерты: тик > 300 мс, очередь writer > 1000,
ack-несоответствия > 0.

**Dev-режим и права.** `accounts.role`: `player | gm | admin`. Чат-команды
(`/goto`, `/where`, `/spawn`, `/give`, `/kick`, `/wire on|off`, `/shutdown N`)
обрабатываются только при `role ≠ player`; для остальных текст с `/` — обычное
сообщение. `Config.dev_mode=true` (только локально) даёт всем `gm`, разрешает
`/goto` и печатает `/where` в ответ. `kickban;admin=;seconds=;reason=` и
`shutdown;seconds=` (`Session.as:199-222`) — штатные админские действия.
Регистрация с сайта в проде — за капчей/лимитом по IP.

**Деплой.** Разработка — как сейчас, WSL (mirrored networking даёт
`127.0.0.1` из Windows). Прод — Docker: `python:3.12-slim`, код в образе,
`res/` — read-only volume (не в образе и не в репозитории — правовая рамка
README), `data/` — named volume на ext4; один контейнер, два слушателя
(game 9775, http 8080, policy 843 через `cap_add: NET_BIND_SERVICE`);
`docker compose` с `restart: unless-stopped`, `stop_grace_period: 30s` (время на
`shutdown;seconds=` и flush). Healthcheck — `GET /status`. Альтернатива без
Docker — systemd unit с `KillSignal=SIGTERM`, `TimeoutStopSec=30`.

**Бэкап БД.** WAL-режим; `sqlite3.Connection.backup()` в `data/backup/lava-YYYYmmdd-HHMM.db`
по таймеру (раз в час) и перед остановкой; ротация 24 часовых + 14 дневных;
копирование вне хоста — `rclone`/`scp` по cron. Восстановление — остановить,
подменить файл, запустить; проверка `PRAGMA integrity_check` в `/status`.
Перенос БД с `/mnt/c/...OneDrive...` (R1) — до всего остального.

---

## 6. Задачи

Размер: S ≤ 0.5 дня, M ≤ 2 дней, L — неделя и больше. Порядок внутри
приоритета — рекомендуемый.

### P0 — без этого «нормального сервера» нет

| # | Задача | Размер | Закрывает |
|---|---|---|---|
| P0-1 | `tools/test.sh` + свободные порты в тестах | S | T12 |
| P0-2 | Перенести БД на ext4 в WSL, включить WAL, `LAVA_DB` обязателен | S | R1 |
| P0-3 | `net/connection.py`: лимит кадра, очередь исходящих с drain, rate-limit, таймаут hello | M | R3, R4 |
| P0-4 | `net/dispatcher.py`: реестр команд, схема параметров, фильтр состояний, ack-контроль | M | T4, T5, T9 |
| P0-5 | Graceful shutdown: сигналы → `shutdown` клиентам → сохранить всех → закрыть; `run.sh stop` ждёт | S | R2, R6 |
| P0-6 | Чтения БД через `to_thread`, write-behind writer, `dirty`-флаг у персонажа | M | R1 |
| P0-7 | `Room`/`Entity`/`IdAllocator`; состояние из `Session` в мир; глобальные id NPC | M | T1, T2 |
| P0-8 | Broadcast и ответы для чужих игроков (`getInfo type=0`, `ss_get target=<id>`); тест с двумя клиентами | M | цель этапа 2 ROADMAP |
| P0-9 | Проверка пути в `moveTo`: соседство, препятствия, занятость; `breakMv` при отказе | S | R5 |
| P0-10 | `Config` без захардкоженных путей; HTTP слушает `Config.http_host` | S | T11, R11 |
| P0-11 | Контент падает на старте при ошибке загрузки, а не молчит | S | R7 |

### P1 — фундамент для контента

| # | Задача | Размер |
|---|---|---|
| P1-1 | `Scheduler` + `World.run()` с виртуальными часами; перевод перелётов | M |
| P1-2 | Глобальная карта: интерес по `v_rad`, `userLost`, heartbeat ≤ 3 с | M |
| P1-3 | `content/` + `loader.py`: stocks, items (из `wiki_extract.py`), constants, start | M |
| P1-4 | `strings.py` + `strings.lock.json` + `build_texts.py`; удалить `STRING_ID_OFFSET` | M |
| P1-5 | Миграции БД; схема v2: `character_stats`, `items`, `character_quests`, `mail`, `map_marks`, `bank_accounts` | L |
| P1-6 | `accounts.role`; чат-команды только для gm/admin; `kickban`/`shutdown` | S |
| P1-7 | Структурированные логи с `sid/char`, DEBUG-провод по флагу, ротация | S |
| P1-8 | `/metrics` и `/status` | S |
| P1-9 | Dockerfile + compose + systemd-альтернатива; `run.sh` как обёртка | M |
| P1-10 | Бэкап по таймеру и при остановке; ротация | S |
| P1-11 | Перевод тестов на pytest с фикстурами (сервер в процессе, а не подпроцесс, где возможно) | M |
| P1-12 | Исследование: разрядность `uniq` в `oid` (`Item.as`, `ItemFactory`) и парсинг `H`-hex на клиенте — до реализации инвентаря | S |
| P1-13 | Проверить R9 на живом клиенте (дубль своего сообщения); зафиксировать в PROTOCOL.md | S |
| P1-14 | `ss_ack` с реальной экипировкой игрока (`ss_get` по маске слотов, `Master.requestInfo` → `firstRequest`, `PersEquip.as:101-110`) | M |

### P2 — игра

| # | Задача | Размер |
|---|---|---|
| P2-1 | Мобы: спавн из локации, респаун, маршруты, агро; `mobs.yaml` | L |
| P2-2 | Бой: ОД (600 мс тик, `c_ap`), выстрел/удар, `faAim/faShot/faHit/faWall/faMiss`, `caHit/caMiss`, смерть `lch;dead`, `resurrect`, `leave_combat_timeout` (res=39) | L |
| P2-3 | Инвентарь и экипировка: `ss_get/ss_move/ss_use/ss_heap_c/ss_upd`, `ss_di_*`, вес, прочность | L |
| P2-4 | Лут: `ss_loot`, мешки, `loot_tables.yaml` | M |
| P2-5 | Квесты трёх типов (`q_list/q_si/q_di/q_st/q_co/q_ca/q_status`), `quests.yaml` | L |
| P2-6 | Сессии NPC: торговля (`type_list` по индексу), ремонт, банк (`c_ga`, `updWeight`), лекарь, обучение, апгрейд | L |
| P2-7 | Почта с вложениями и тарифами (`chkml/getml/sndml/rmvml/uldml`, `ctml` только при res=0) | M |
| P2-8 | Группа (`p_op`) и каналы чата (party, world, trade, private с `nick`) | M |
| P2-9 | Интерес в больших локациях (радиус, `lostUser` при удалении) | M |
| P2-10 | Прогресс: опыт, уровни, атрибуты/навыки/специализации (`rp_info` из БД) | M |

### P3 — социальное и прочее

| # | Задача | Размер |
|---|---|---|
| P3-1 | Кланы (`admit/apply/head/gg_info`, `gg_*`) | L |
| P3-2 | Аукцион (`ah_*`, очередь `ah_sresult`) | L |
| P3-3 | Поля боя (`bg_op`, `bg_*`) | L |
| P3-4 | Эффекты/бафы (`e_*`) | M |
| P3-5 | Транспорт/аренда (`ts_get_si`, лессор) | M |
| P3-6 | Метки карты (`insMark/updMark/rmMark`, порядок = индекс) | S |
| P3-7 | Перехват игрока на карте (`moveTo;trg=`) | S |
| P3-8 | Граф переходов между интерьерами (outzones → цель) — данные, не код | L |

---

## 7. Что не менять

* `protocol.py` — целиком. Переименование в `net/codec.py` — единственная правка.
* Тексты комментариев в `server.py`, объясняющие поведение клиента: они
  переезжают вместе с обработчиками.
* Разрешение id локаций, `entry_cell()`, `settlements()` — как есть.
* Принцип тестов: последовательности из AS-исходников, а не из головы.
