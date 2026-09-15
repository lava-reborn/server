# Квесты, диалоги с НПС, сервисы НПС, тексты

Разбор клиента (AS2, `recon/as-src/lol/`) под задачу «взять первый квест у НПС,
выполнить, сдать». Ссылки вида `файл:строка` — на декомпилированные исходники.
Серверные заглушки: `server/server.py`, строки: `server/names.py`,
HTTP-стаб текстов: `server/bootstrap_http.py`.

Главные выводы, если читать только их:

- Диалога как дерева реплик в клиенте **нет**. «Диалог» с НПС — это окно
  `questInterface` со списком «Доступные / Незавершённые / Завершённые задания»
  плюс вкладки сервисов (торговля, ремонт, банк…). Ветвлений и выбора реплик
  нет; `m_hello` клиент принимает, но нигде не показывает.
- Квест = статика по типу (`q_si_*`, приходит один раз на тип) + динамика по
  экземпляру (`q_di_*`, приходит по запросу и по инициативе сервера) +
  статус доступности по типу (`q_status`). Три вида целей: убить мобов,
  принести предметы (до 6 позиций), доставить предмет.
- Взять квест: `q_st;mob=<id НПС>;q_idx=<индекс в give_quests>;` → `cmdAck;res=0;`
  → сервер **обязан сам** прислать `q_di_<вид>;q_id=…;` — иначе квест не
  попадёт в журнал и останется «доступным».
- Сдать: `q_co;obj_idx=<выбор награды>;mob=<id НПС>;q_id=<экземпляр>;` →
  `cmdAck;res=0;`. Любой `res≠0` клиент показывает как «сдали максимум
  ежедневных» (`ErrorReport 44`).
- Все имена и тексты (название + 3 описания на тип квеста) — числовые id строк,
  и все они должны попасть в `?all=1` до входа (PROTOCOL.md §9). Предлагаемая
  схема: `2 000 000 + 4·type + {0,1,2,3}`.

---

## 1. Модель квеста на клиенте

### 1.1 Классы

| Класс | Роль | Файл |
|---|---|---|
| `Quest` | статика типа квеста (одна на `typeID`) | `core/quests/Quest.as` |
| `QuestTask` | экземпляр у игрока: `qID`, `typeID`, `complete`, ссылка на `Quest` | `core/quests/QuestTask.as` |
| `KillMobQuest` / `BringObjQuest` / `DeliverObjQuest` | цель (`missionStatus`) | `core/quests/*Quest.as` |
| `QuestInspector` | синглтон-менеджер: сеть, коллекции, очередь запросов | `core/quests/QuestInspector.as` |
| `QuestInterface` | окно квестов у НПС (то самое «окно диалога») | `gpui/QuestInterface.as` |
| `QuestInfoInterface` | журнал (вкладка в окне персонажа) | `gpui/QuestInfoInterface.as` |

### 1.2 Поля `Quest` и откуда берутся (`Quest.as:40-59`, `85-93`)

Все приходят в кадре `q_si_<вид>` (см. 1.4), ключи `obj.param.*`:

| Поле клиента | Ключ кадра | Тип | Где показывается |
|---|---|---|---|
| `typeID` | `type` | число | ключ коллекции |
| `nameStrID` | `name` | **id строки** | заголовок, список, маркеры карты |
| `start_descStrID` | `start_desc` | id строки или `""` | описание при выдаче (`QuestInterface.as:277`), журнал (`QuestInfoInterface.as:111`), подсказка метки на глобальной карте |
| `notfinish_descStrID` | `notfinish_desc` | id строки или `""` | у принимающего НПС, пока `complete=0` (`QuestInterface.as:287`) |
| `finish_descStrID` | `finish_desc` | id строки или `""` | у принимающего НПС при `complete=1` (`QuestInterface.as:281`) |
| `repeatable` | `repeatable` | 0/1 | «Задание является повторяемым» |
| `party_size` | `party_size` | число | «Количество человек…» если ≠0 |
| `level` | `level` | число | «Необходимый уровень…» показывается, если **ни один** навык игрока не ≥ level (`QuestInterface.as:310-323`) |
| `loc` | `loc` | geoID (`x<<13\|y`) или 0 | метка незавершённого квеста на глобальной карте (`GlobalMapInterface.as:661-666`) |
| `finish_loc` | `finish_loc` | geoID или -1 | метка «сдать» на карте, когда `complete` (`GlobalMapInterface.as:654-660`) |
| `rew_obj` | `rew_obj` | список type_id предметов | иконки наград; >1 — выбор одной (`buildRewardItems`) |
| `num_rew_obj` | `num_rew_obj` | список чисел | количество каждой награды |
| `rew_afro`, `rew_gold` | те же | число; **gold делится на 100** при показе (`QuestInterface.as:342`) | «За это задание вы также получите…» |
| `rew_loc` | `rew_loc` | 0/1 | «после выполнения Вас переместят в другое место» |
| `needQuest` | `need_quest` | число | не используется в UI (только хранится) |
| `q_type` | `q_type` | число | приоритет/категория, см. 1.6 |

Для каждого `rew_obj` клиент строит прототип предмета через `ItemFactory.createPrototype` (`Quest.as:129-140`) — это тянет `ss_get_si;type=…;` на каждый тип награды (окно 5, PROTOCOL §7). Значит все типы наград должны быть известны `items.static_info`.

### 1.3 Цели (`missionStatus`)

**KillMobQuest** (`KillMobQuest.as`): статика `mobs_kill` (список type_id мобов), `num_kill` (список нужных количеств); динамика `kill_num` (список текущих). Журнал: «Убито N целей из M» на каждую позицию.

**BringObjQuest** (`BringObjQuest.as:23-37`): до **6** позиций, статика плоскими ключами `obj_1..obj_6` (type_id), `obj_num_1..obj_num_6` (нужно), `mobs_1..mobs_6` (кто дропает; в UI не используется); динамика `obj_num` — **список** текущих количеств в порядке позиций. Журнал: «Найдено N <имя>».

**DeliverObjQuest** (`DeliverObjQuest.as`): статика `obj` (type_id предмета, может быть 0/пусто — тогда предмет не создаётся и статус пустой); динамика `obj` — флаг «найден» (0/1). Журнал: «предмет X найден, но не доставлен / не найден».

Вид цели определяется **именем кадра**, а не полем: `q_si_kill_mobs` / `q_si_bring_l_obj` / `q_si_del_obj` и парные `q_di_*` (`QuestInspector.as:52-59`).

### 1.4 Кадры сервера

```
q_list;q_id=|<инст1>|<инст2>|;q_types=|<тип1>|<тип2>|;          (QuestInspector.as:383-410)
q_status;type=<тип>;status=0|1;name=<id строки>;q_type=<n>;      (:114-145)
q_si_kill_mobs;type=;name=;start_desc=;notfinish_desc=;finish_desc=;
    repeatable=;party_size=;loc=;finish_loc=;level=;rew_obj=|..|;num_rew_obj=|..|;
    rew_afro=;rew_gold=;rew_loc=;need_quest=;q_type=;mobs_kill=|..|;num_kill=|..|;
q_si_bring_l_obj;<общие>;obj_1=;obj_num_1=;mobs_1=|..|;… obj_6…;
q_si_del_obj;<общие>;obj=<type_id>;
q_di_kill_mobs;q_id=;q_type=<тип квеста>;complete=0|1;kill_num=|..|;   (:613-635)
q_di_bring_l_obj;q_id=;q_type=;complete=;obj_num=|..|;                  (:636-658)
q_di_del_obj;q_id=;q_type=;complete=;obj=0|1;                            (:659-681)
q_sys;daily_available=<n>;                                              (:358-373)
```

Внимание: в `q_di_*` ключ `q_type` несёт **type_id квеста** (не категорию),
а в `q_si_*`/`q_status` ключ `q_type` — категорию. Одноимённые ключи с разным смыслом.

Пустое описание: клиент сравнивает `start_desc == ""` (`Quest.as:89-91`).
Если ключ **отсутствует**, `Number(undefined)=NaN`, `getString(NaN)` вернёт
null и `stringUpdate` никогда не завершится — имя квеста не появится. Поэтому
слать все четыре id всегда; проще всего завести общую строку-пустышку.

### 1.5 Кадры клиента (`server/mess/CSM_Q*.as`, `recon/notes/cs_commands.txt`)

| Команда | Параметры | Когда | Ответ |
|---|---|---|---|
| `q_list;` | — | вход в локацию / `Master.requestInfo` (`Master.as:201,305`) | `q_list` (без cmdAck) |
| `q_status;q_type=T;` | тип | на каждый тип из `give_quests`/`take_quests` каждого НПС при `userInfo_*` (`NPC.as:31-40` → `checkQStatus`), дедуп по типу; заново для всех НПС локации после сдачи/отмены (`requestAllNPC`, :687-743, по одному НПС в 300 мс) | `q_status` (без cmdAck) |
| `q_si;q_type=T;` | тип | неизвестная статика (из `q_list` или при открытии описания) | `q_si_<вид>` |
| `q_di;q_id=Q;` | экземпляр | из `q_list` для известных типов, после `q_si` для `cqList` | `q_di_<вид>` |
| `q_st;mob=N;q_idx=I;` | id НПС, **индекс в его `give_quests`** (`NPC.as:57-68`) | кнопка «взять» | `cmdAck` |
| `q_co;obj_idx=K;mob=N;q_id=Q;` | выбор награды, id НПС, экземпляр | кнопка «сдать» | `cmdAck` |
| `q_ca;q_id=Q;` | экземпляр | журнал → «Отказаться» | `cmdAck` |

Окно конвейера = 1 для `q_status`/`q_si`/`q_di` (`packageLength = 1`,
`QuestInspector.as:26,69-94`): следующий запрос уходит только после ответа.
`q_list`, `q_st`, `q_co`, `q_ca` идут мимо этой очереди.
Ответ на неизвестный тип/экземпляр всё равно обязателен (любой `q_si_*`/`q_di_*`).

`obj_idx`: `QuestInterface.as:381` присваивает иконкам наград `id = n-1-i`
(i — индекс в `rew_obj`), при одной награде всегда 0. Значит сервер выбирает
`rew_obj[n-1-obj_idx]`. Проверить вживую при первом квесте с выбором.

### 1.6 Состояния и что делает клиент сам

- `available` (по типу) — из `q_status.status`. Только доступные типы попадают в
  списки (`getGQs` :201-231, `getTQs` :232-257) и в проверку `hasAvailableQuests`.
- «Доступный» = в `give_quests` НПС, `available`, **нет** в `currentQuests`.
- «Незавершённый» = в `take_quests` НПС, есть в `currentQuests`, `complete=0`;
  «Завершённый» = то же с `complete=1` (кнопка «сдать» только здесь).
- Лимит журнала: `constants.quest_log_capacity` (`GConstatns.as:26`), при
  превышении алерт `MAX_NUMBER_OF_QUESTS` (`QuestInterface.as:461-465`).
- Ежедневные: `q_sys.daily_available`, сброс по `constants.daily_reset_time`
  (минуты UTC) до `daily_max` — только для надписи в журнале (`QuestInfoInterface.as:74`).
- Маркер над НПС (`core/location/CharInfo.as:385-448`): есть доступные → кадр
  `3+q_type` (если `q_type>0`), есть незавершённый → 3, есть завершённый → 2,
  первая игра → 16. `q_type` также ищет подсказку `quest_type` в hints.xml
  (`Char.as:471-475`), которого нет.
- Что клиент **не** делает: не добавляет квест в журнал после `q_st` (ждёт
  `q_di_*`), не считает прогресс, не убирает предметы, не даёт награду.

### 1.7 Последовательность «взять — выполнить — сдать» (что обязан прислать сервер)

1. Вход: `lch` с НПС → клиент `getInfo;type=1;id=N;` → `userInfo_<Класс>` с
   `give_quests`/`take_quests` → клиент шлёт `q_status` на каждый тип →
   сервер отвечает `status=1;name=<id>;q_type=…` (или 0). Маркер над НПС.
2. `q_list` → `q_id=|…|;q_types=|…|` (пусто у нового персонажа).
3. Клик по НПС → подход → `proposeContact` (`Gamer.as:169-256`): для
   Commoner без банка и Medic окно открывается сразу; для Trader/Teacher/
   Upgrader/Auctioner/банка — сначала `ss_create` и `cmdAck;res=0` (см. §3).
   Окно `questInterface` показывает список или сразу описание, если квест один.
4. Описание: если тип не инициализирован → `q_si;q_type=T;` → `q_si_<вид>`
   (плюс `ss_get_si` на награды). Кнопка «взять» → `q_st;mob=N;q_idx=I;`.
5. Сервер: `cmdAck;res=0;` и **сразу** `q_di_<вид>;q_id=Q;q_type=T;complete=0;…`.
   Клиент показывает «Получено новое задание <имя>», перестраивает список
   (квест уходит из «доступных», появляется в «незавершённых», если НПС его принимает).
6. Прогресс: сервер по своей инициативе шлёт `q_di_<вид>` с новыми счётчиками;
   `complete=1` даёт событие `COMPLETE` и маркер «сдать» (кадр 2), метку
   `finish_loc` на глобальной карте.
7. Сдача: `q_co;obj_idx=K;mob=N;q_id=Q;`. Сервер: выдать награды **до**
   `cmdAck` (клиент между отправкой и ack слушает `addItem` на экипировке, чтобы
   показать «Вы получили: …», `QuestInspector.as:438-521`), обновить деньги
   (`userInfo_Player`/`usrUp`), затем `cmdAck;res=0;`. После этого клиент шлёт
   `q_status` заново по всем НПС локации — отвечать на каждый.
8. Отмена: `q_ca;q_id=Q;` → `cmdAck;res=0;` → тот же шторм `q_status`.

Побочный эффект незапрошенного `q_di_*`: `updateCall()` уменьшает `callCount`
ниже нуля, после чего клиент может держать два квестовых запроса в полёте.
Сервер, отвечающий на всё по порядку, от этого не страдает.

---

## 2. Диалог с НПС

### 2.1 Что происходит при клике

`SpriteFocusManager.spriteClick` (`display/SpriteFocusManager.as:166-186`):
обычный клик по спрайту → `onSpriteClick` → сцена ведёт игрока
(`Gamer.gotoWalker(id,"contact")`, `Gamer.as:125-168`) на соседнюю клетку; по
приходу — `proposeContact` (`Gamer.as:169-256`). Длинный клик/Shift — контекстное
меню (бартер/приват/осмотр/в отряд), «actionBarter» = тот же `contact`.
Клик по маркеру «!» над головой — тоже `gotoWalker(id,"contact")` (`CharInfo.as:459-462`).

В `proposeContact` (по классу НПС и только при `playerInfo.ally` истинном):

| Класс (rtype) | Действие клиента | Сетевой запрос |
|---|---|---|
| `Trader` (1) c `can_trade\|can_repair\|can_trophy` | `Trade.ss_propose` | `ss_create;target=N;s_type=1;` → cmdAck |
| `Teacher` (2, `userInfo_SpecTrainer`) | `Training.ss_propose` | `ss_create;target=N;s_type=4;` → cmdAck |
| `Upgrader` (3) | `Upgrade.ss_propose` | `ss_create;target=N;s_type=5;` → cmdAck, затем `ss_get` своего рюкзака |
| `Commoner` (4) с `can_banking` | `Bank.ss_propose` | `ss_create;target=N;s_type=3;` → cmdAck, затем `ss_get;slot=maskIndex+16;` |
| `Commoner` (4) без банка | `NPCService.openService` | **ничего** — окно сразу |
| `Healer` (5, `userInfo_Medic`) | `NPCService.openService` | ничего — окно сразу |
| `Lessor` (6) | `Rent.ss_propose` | ничего — окно сразу |
| `Auctioner` (7, `userInfo_Auctioneer`) | `Auction.ss_propose` | окно сразу; поиск — `ah_search` |
| `Player` | `Barter.ss_propose` | `ss_create;s_type=2` (игрок↔игрок) |

Если `ss_create` вернул `res≠0` — алерт «Невозможно…» и окно не открывается
(`Trade.as:270-285` и т.п.). Квесты у торговца/учителя/апгрейдера, таким
образом, **зависят от `cmdAck;res=0` на `ss_create`** — заглушка это уже делает
(`server.py:606`).

### 2.2 Как строится «меню диалога» (`core/player/NPCService.as:51-132`)

`openService` собирает список вкладок и открывает `SceneShifter.openNewWindow(первая, undefined, список)`:

- Trader: `trade` (если `can_trade`), `repair` (`can_repair`), `regTrophy` (`can_trophy`);
- Upgrader: `upgrade`; Lessor: `transRent`; Teacher: `spec`;
- любой с `haveSupport()`: `support` (Прописка/Лечение, см. §3.5); Auctioner: `auction`, `auctionMyLots`;
- `can_banking` у любого класса: `bank`;
- `hasAvailableQuests()`: `quests` — и она становится **активной первой**.

Окна: `SceneShifter.as:354-398` (`quests`→`questInterface`, `support`→`supportInterface`, `spec`→`specInterface`, `transRent`→`transRentInterface`, `bank`→`bankInterface`, `regeneration`→`regenerationInterface`…).

Ветвления реплик нет. Единственная «реплика» — тексты квеста (start/notfinish/finish).

### 2.3 `on_conv` — это не разговор, а сервисы (`CSM_Conv.as`, `CSM_TS_on_conv.as`)

```
on_conv;mob=<id НПС>;op=0;                    прописка   (Attendance.SET_HOME, Attendance.as:7,38-45)
on_conv;mob=<id НПС>;op=1;                    лечение    (Attendance.HEAL)
on_conv;p2=<дней>;p1=<type_id транспорта>;mob=<id>;op=2;   аренда транспорта (Rent.as:19-38)
```
Все три ждут `cmdAck`. `res=0` — успех; для аренды `res≠0` → событие
`GET_TRANSPORT_FAIL`. Обработчики прописки/лечения пустые: эффект (смена точки
возрождения, восстановление HP через `usrUp`, списание денег через `userInfo_Player`)
целиком на сервере. `Attendance.BANK=2` объявлен, но не используется.

### 2.4 `m_hello`, `give_quests`, `take_quests` в `userInfo_*` (`NPC.as:26-57`)

- `give_quests=|T1|T2|;` — типы, которые НПС выдаёт; порядок важен: `q_st.q_idx` — индекс в этом списке.
- `take_quests=|T|;` — типы, которые принимает (для сдачи и для списка «незавершённых»).
- `m_hello=|id|id|;` — id строк приветствий; клиент подписывается на строки,
  но декомпилят `createHelloStrings` (`NPC.as:142-152`) не присваивает
  `helloStrArr`, и `getHello` никто не вызывает. **Мёртвое поле**, слать `|;`.
- Прочие: `can_set_home`, `can_banking`, `can_trophy`, `can_repair`, `can_trade`
  (0/1), `res` (type_id → `persType`, графика), `name` (id строки),
  `ally` (обязателен ≠0, иначе все сервисы игнорируются), `lvl`, `rep`,
  `bg_rep`, `bg_pen`, `sex`.

`userMsg` от НПС: реплики над головой рисуются из лога чата
(`DisplayLocScene.as:68-84`, `fromID` → `showPhrase`), т.е. НПС может «говорить»
серверным чат-кадром с его id. Фразы мобов `m_idle/m_detect/m_attack/m_run/m_death`
(`Mob.as:23-32`) клиент принимает, но геттеры никто не вызывает — мёртвые.

---

## 3. Сервисы по типам НПС: точные команды

Константы сессий `StuffManager.as:6-11`: TRADE=1, BARTER=2, BANK=3, TRAINING=4,
UPGRADE=5, TROPHY=6. Все операции внутри сессии — `ss_upd;s_status=<op>;obj=<hex id>;param=<n>;`
(`cs_commands.txt`: `ss_upd param,obj,s_status`), каждая ждёт `cmdAck`. Закрытие
окна — `ss_upd;s_status=0;obj=0;` **без** ожидания ack (`Trade.as:295-307`).

### 3.1 Торговец (`Trader`, rtype 1) — `core/player/Trade.as`

`userInfo_Trader`: `type_list=|type_id…|` (прилавок, индекс = `tradeID`),
`bg_objects`, `bg_obj_rep_req`, `pmod`, `smod`, `rmod` (`Trader.as:19-28`).

| Операция | `s_status` | `obj` | `param` | Строка |
|---|---|---|---|---|
| купить за афро | 1 | индекс в `type_list` (hex) | количество (патроны) | `Trade.as:80-111` |
| продать | 2 | id предмета | размер стопки | `:112-138` |
| ремонт афро / золото | 3 / 5 | id предмета | — | `:157-171` |
| восстановление | 7 | id предмета | — | `:172-184` |
| купить за золото | 4 | индекс | кол-во | `:85-87` |
| купить за BG-очки | 8 | индекс | кол-во | `:94-97` |
| регистрация трофея | 6 | id предмета | — | `:189-201` (окно `regTrophy`) |

### 3.2 Учитель (`Teacher`, rtype 2, кадр `userInfo_SpecTrainer`) — `Training.as`

`ss_create;s_type=4` → окно `spec` (`TrainingInterface.as`) тянет
`rp_get_info` → `rp_info` (специализации/навыки). Выучить: `ss_upd;s_status=2;obj=<id спец.>;`,
забыть: `s_status=1`. Стоимость считается на клиенте (`Training.as:71-127`:
бесплатно до `max_specs`, дальше 1000 афро / 10 / 30 / 55 / 75 золота) — сервер
должен списывать столько же.

### 3.3 Апгрейдер (`Upgrader`, rtype 3) — `Upgrade.as`, `Upgrader.as`

`userInfo_Upgrader`: `in_types=|…|` (что принимает), `out_types=|…|` (во что
превращает, тот же индекс), `costs=|…|` (`Upgrader.as:13-19`). Сессия
`s_type=5`; улучшение `ss_upd;s_status=1;obj=<id предмета>;param=<out type_id>;`
(`Upgrade.as:95-103`), ответ `cmdAck` → событие `upgrAck`.

### 3.4 Горожанин (`Commoner`, rtype 4)

Носитель флагов: `can_set_home=1` → пункт «Прописка» (`on_conv op=0`);
`can_banking=1` → банк: `ss_create;s_type=3`, затем `ss_get;slot=<maskIndex+16>;`,
ответ `ss_ack;o_list=|…|0|…|` — рюкзак, разделитель `0`, хранилище (`Bank.as:42-74`);
положить `ss_upd;s_status=1;obj=<id>`, взять `s_status=2`, расширить `6`;
сервер шлёт `ss_upd;s_status=3;obj=<hex макс.вес>` и `s_status=4` (текущий).
Квесты — у любого класса, но в стартовой локации именно горожане и апгрейдер
их дают (см. §5).

### 3.5 Лекарь (`Healer`, rtype 5, кадр `userInfo_Medic`) — `Healer.as`

`a_price=<афро>`; поле `g_price` клиент берёт **из того же `a_price`** (баг
`Healer.as:16-17`), так что цена в золоте не передаётся. Окно `support` →
«Лечение» → `on_conv;mob=N;op=1;` → `cmdAck`. Восстановление HP — `usrUp;id=0;hcur=…`.
Воскрешение после смерти — отдельно: `resurrect;res_type=0|1|2;` (бесплатно/5 голда/500 афро).

### 3.6 Арендодатель (`Lessor`, rtype 6) — `Lessor.as`, `Rent.as`, `TransRentInterface.as`

`userInfo_Lessor`: `give_transport=|type_id…|`; на каждый тип клиент тянет
`ts_get_si;type=T;` → `ts_si` (окно 5). Аренда: `on_conv;op=2;p1=<type_id>;p2=<дней>;mob=N;` → `cmdAck`.
Текущий транспорт игрока — `userInfo_Player.tr`, `tr_hours`.

### 3.7 Аукционер (`Auctioner`, rtype 7, кадр `userInfo_Auctioneer`) — `Auction.as`

`ah_search;target=N;page;name;cat;subcat;min_lvl…;sort;s_mode` → `ah_sresult` +
`ah_lot`×n (своя очередь); `ah_op;target;type=BID|BUYOUT|SELL|TAKEOFF;obj;amount` → cmdAck;
`ah_create;target;obj;time;a_bid;a_buyout;g_bid;g_buyout` → cmdAck.

### 3.8 Что уже отдаёт заглушка (`server/server.py:520-562`)

`send_npc_info` шлёт правильный кадр по `root_type_id`, `ally=1`, пустые
`give_quests/take_quests/m_hello`, флаги 0; торговцу — прилавок, лекарю
`a_price=10`, горожанину `can_set_home=1`. `cmd_q_list` → пусто, `cmd_q_status`
→ `status=0`. `q_si/q_di/q_st/q_co/q_ca/on_conv` — только `cmdAck;res=3` через
`EXPECTS_ACK` (`q_si`/`q_di` там нет — они и не ждут ack, но ждут ответа-кадра,
которого пока нет: открыть описание любого квеста сейчас невозможно).

---

## 4. Тексты

### 4.1 Формат и разбор (`utils/StringCollector.as`)

- Догрузка: `POST <base>/database/texts.xml` тело `<data>1,2,3</data>` (`:55-66`);
  всё разом: `GET …/texts.xml?all=1` (`:98-105`).
- Ответ: `<любой корень><s id="N">текст</s>…</любой корень>`; читается только
  атрибут `id` и `childNodes.join("")`, затем `mx.utils.XMLString.unescape` —
  это таблица **XML-сущностей** `&lt; &gt; &amp; &quot; &apos;` (`mx/utils/XMLString.as:14-19`),
  а не процентная таблица `lol.server.XMLString` из PROTOCOL §10.
  Значит в texts.xml разметку внутри строки кодировать сущностями:
  `&lt;hint&gt;…&lt;/hint&gt;`, `&lt;br&gt;` — именно так уже делает
  `names._escape` (`server/names.py:75`). Сырой `<br>` сломает XML-разбор всего ответа.
- Кэш: `stringCollection[id]`; `getString(id)` при промахе ставит id в стек и
  через 50 мс шлёт POST-пачку (`:30-54`). Любая такая пачка после входа
  → экран логина поверх игры (PROTOCOL §9).

### 4.2 Макросы (где применяются)

| Макрос | Кто раскрывает | Значение |
|---|---|---|
| `%имя%` | `Quest.parseString` (`Quest.as:180`), окна квестов | имя персонажа |
| `%sex?муж:жен%` | `ParseString.replaceParametrically` (`ParseString.as:73-94`), вызов `Quest.as:109-113` | индекс `Number(!boolSex)`: 0 — мужской (sex<128), 1 — женский |
| `<hint>…</hint>` | `QuestInterface.parseString` (`:544-550`) | `<font color="#315d07">` — только в окне у НПС, в журнале не заменяется |
| `%startProfile%…%endProfile%`, `%startPutGold%…%endPutGold%` | `Quest.as:171-179` | ссылка на профиль/пополнение |
| `\` | везде удаляется (`replaceAll(str,"\\","")`) | — |
| HTML `<b>`, `<br>`, `<u>` | `htmlText` | обычный Flash-HTML |
| `quot;` | `ParseString.parse` | → `"` |

Описания предметов: `ss_si_*.desc` тоже id строки или `""` (`core/objects/Item.as:226`).

### 4.3 Кто тянет строки (все — числовые id из кадров сервера)

`Entity.userInfo.name` (НПС/мобы, `Entity.as:74-85`), `Quest` (4 id), `q_status.name`,
`Item.name/desc`, `ss_si_set.name`, `Effect`, `TransObject`, `NPC.m_hello` (мёртво).
Литеральных `getString` в SWF нет (PROTOCOL §9) — значит множество id полностью
контролируется сервером и его можно замкнуть заранее.

### 4.4 Текущая нумерация и предлагаемая схема

Сейчас (`server/names.py`, `server/items.py:100`): мобы/НПС — `type_id` как есть
(1…~7300, поверх — имена из вики `data/npc_names.json`), предметы —
`1 000 000 + type_id`. Таблица собирается один раз в `names.document()` и
целиком отдаётся на `?all=1`.

Предложение (все диапазоны непересекающиеся, числа < 2^31, AS2-массив
разреженный, как и с предметами):

| Диапазон | Содержимое | Формула |
|---|---|---|
| 1 … 999 999 | имена мобов/НПС | `type_id` (как есть) |
| 1 000 000 … 1 999 999 | имена предметов | `1 000 000 + type_id` (как есть) |
| **2 000 000 … 2 999 999** | **квесты** | `2 000 000 + 4·quest_type + k`, k: 0 name, 1 start_desc, 2 notfinish_desc, 3 finish_desc (до 250 000 типов) |
| 3 000 000 … 3 999 999 | описания предметов | `3 000 000 + type_id` |
| 4 000 000 … 4 099 999 | реплики НПС (`m_hello`, чат-фразы) | `4 000 000 + 8·npc_type + k` (резерв, поле мёртвое) |
| 5 000 000 … | наборы (`ss_si_set.name`), эффекты, служебные (id 5 000 000 = пустая строка для отсутствующих описаний) | по мере надобности |

Правила, без которых схема не работает:

1. Источник квестового контента (`data/quests.json`) импортируется в
   `names.ALL` при старте **обоих** процессов — HTTP-стаб и игровой сервер
   читают одну таблицу, `names.known()` — единственный пропуск на провод.
2. `q_status.name` и четыре id в `q_si_*` — всегда числа, никогда пусто:
   для отсутствующего описания слать id пустой строки (5 000 000), а не `""`.
3. Изменил тексты — перезапуск обоих процессов (кэш `?all=1` строится один раз),
   иначе новый id уедет мимо предзагрузки и выкинет игрока на логин.
4. Признак поломки прежний: второй запрос `database/locations.xml` в HTTP-логе
   и строка «HTTP строки мимо предзагрузки» в `bootstrap_http.py:179-181`.

### 4.5 hints/hints.xml — второй отсутствующий файл

`GameHelpMessageManager.loadDescription` тянет `<base>/hints/hints.xml`
(`gpui/gamehelp/GameHelpMessageManager.as:41-47`, `services/SSEmulator.as:357-368`);
папки `res/hints` в клиенте нет. Записи `<hint id quest="…" quest_type="…" window_name="…" npc="…">`
— обучающие подсказки по имени квеста/категории/окна. Без файла подсказок просто
нет, ничего не виснет. Восстановить содержание неоткуда; можно отдать пустой
`<data/>`, чтобы не плодить 404 в логе.

---

## 5. Вики как источник контента

Проверено живьём 2026-09-16 (`lava-online.fandom.com/ru`, MediaWiki API):
категория «Квесты» — **1191** статья, «НПС» — **317**, «Персонажи» — 364.

### 5.1 Структура статьи квеста (машинно извлекаемо)

Шаблон устойчив (по 48 случайным статьям и полному проходу):

```
==Квест: <название>==
'''Начало квеста''' : ''<start_desc>''
'''Задача''': <что сделать>            (только в ~6%, обычно внутри start)
'''Незаконченный квест''': ''<notfinish_desc>''
'''Конец квеста''': ''<finish_desc>''
==Родительский квест== / ==Дочерний квест== / ==Сопутствующий квест==
==Требование к условиям выполнения квеста==  (уровень, «повторяемым», время суток)
==Локации связанные с квестом==  '''Начало квеста''': [[Город]] [[Локация]] 5968х1727
==Мобы связанные с квестом==  NPC дающий задание: [[Имя]]  /  NPC принимающий задание: [[Имя]]
==Предметы связанные с квестом==  [[…]]
==Награда за выполнение квеста==  [[предмет]] / '''250 афро''' / «одну из следующих наград»
```

Полный проход (результат — `recon/analysis/wiki_quests_all.json`: title, givers,
takers, start/notfinish/end, task, coords, reward, repeatable, kill/bring): из 1191 статей
регэкспами вытащены `start_desc` у 1100, `notfinish` у 1052, `finish` у 1057,
даватель у 963, координаты у 1151, награда у 1098. Остальное — вариации
разметки (`'''Начало квеста:'''` без курсива, `<span>`-заголовки), добираются
вручную или вторым проходом.

Что вики **не** даёт напрямую: `type_id` квеста и НПС (внутренние латинские
имена клиента), точные счётчики `num_kill`/`obj_num`, `q_type`, `level` в
числах (часто «от 8 уровня» текстом), `party_size`. Мост «имя на вики → type_id
в mobs.xml» уже есть для 16 НПС рынка (`data/npc_names.json`) и достраивается
по страницам локаций (у каждой статьи НПС есть `==Координаты==`, у каждой
локации — список жителей).

### 5.2 Кто и где даёт квесты

Топ давателей — «Мастера»/«Подмастерья» лагерей мастеров: Мастер Сэм 106,
Мастер Умар 96, Мастер Фахад 84, Подмастерье Басам 79, Мастер Самир 66… Это
серийные квесты улучшения оружия («<оружие> (G/P): урон»): принести оружие +
чертёж → получить `Mod`. Их ~700 из 1191; они однотипны (`bring_l_obj`,
`repeatable=1`) и генерируются таблицей. «Убить» упоминают всего 40 статей,
«принести» — 847, «повторяем» — 1053.

Клетки начала: 6183x1975 (Абу-Хамед) 182, 5969x1728 (Вади-Хальфа, жилой
квартал) 116, 5877x2012 (Донгола) 100, 6182x1977 80, 5876x2012 75,
5968x1726/1728 (Вади-Хальфа, рынки) 64+56, 5970x1730 (Чёрный рынок ВХ) 7.

### 5.3 Стартовая локация 102 «Чёрный рынок Вади-Хальфы» (21 спавн)

| type_id | класс | внутреннее имя | вики | квесты на вики |
|---|---|---|---|---|
| 5 | Upgrader | Simple_Upgrader | **Мастер Тиль** | Пистолетчик, Снайпер, Пулеметчик, Спецназовец, Автоматчик, Охотник, Броня «Красное Эхо», Золотая лихорадка II/VI, К шахте (12) |
| 2279 | Commoner | wh_modif_knifes | **Точильный камень** | Заточка/Эргономика Такоубы и др. (12, `bring`: нож + чертёж) |
| 2424 | Commoner | noobia_bank | Аарон | банк (`can_banking`) |
| 652 | Commoner | wh_technogeek | Техногик | — |
| 653 | Lessor | wh_Lessor | Шихаб | аренда: Ослик Панург, верблюды |
| 711, 636, 639, 893, 1152, 1200-1207 | Trader | wh_* | лотерея, Савин, Однопальцый, Пистолеты…, Ваккас, Хамис, Люций, Магдалена | торговля/ремонт |
| 7234-7236 | Commoner | Admin_Npc_Commoner00000x | — | — |

Соседние клетки (Старый рынок 5968x1727, Жилой квартал 5969x1727): Берт Гаммер
(«Квест: Тир Берта Гаммера» + Уроки 1-7), Кшиштоф = `wh_Kshishtoff` (47)
(«Местные предпочтения» → «Муж» → «Муж (часть 2)»), Назир = `wh_Nazir` (48),
Генри-мл = `wh_HenryJr` (46)/`wh_upg_Henry` (93), Барри («Курьер»).

Пример полностью восстановимого квеста (Мастер Тиль, «Пистолетчик»):
start «Решил начать учиться самостоятельно? Сертификат стрелка у Берта
получил?», notfinish «Показывай сертификат стрелка.», finish «- На базе Магриба…»,
`bring_l_obj` (Сертификат Берта Гаммера ×1), награда «Серебристая монета» +
выбор из 7 (журнал/учебники), `repeatable=1`, уровень любой. Но он требует
предмет из цепочки тира — для первого квеста не годится.

---

## 6. Задачи

Размер: S ≤ полдня, M ≤ 2 дня, L > 2 дней. Цель P0 — «взять квест у НПС на
рынке, сделать, сдать» без боя и без инвентаря (их ещё нет).

### P0 — минимальный цикл

| # | Задача | Размер | Файлы |
|---|---|---|---|
| 1 | Таблица квестов `data/quests.json` (type, kind, name, 3 текста, give/take по type_id НПС, rew_afro/gold/obj, repeatable, level, q_type) + загрузчик; первый квест — «курьерский» `del_obj` с `obj=0` (принять у Техногика 652, сдать Аарону 2424 или ему же), награда `rew_afro` | S | `data/`, `server/quests.py` (новый) |
| 2 | Нумерация строк: `names.py` включает квестовые id `2 000 000+4·type+k` и пустую строку 5 000 000 в `ALL`/`document()`; тест, что каждый id из `quests.json` проходит `known()` | S | `server/names.py`, `server/test_*` |
| 3 | `send_npc_info`: `give_quests`/`take_quests` из таблицы по `type_id` | S | `server/server.py:520-562` |
| 4 | `cmd_q_status`: `status=1` если тип есть у НПС локации и (repeatable или не сдан) и уровень ок; `name`, `q_type` из таблицы | S | `server/server.py:642` |
| 5 | `cmd_q_si` → `q_si_<kind>` со всеми ключами (включая `obj_1..6`, пустые списки, все 4 id строк); неизвестный тип — ответ с заглушкой | M | `server/server.py` |
| 6 | Состояние: таблица `char_quests(q_id, char_id, type, progress_json, complete, taken_at)` в `lava.db`; `cmd_q_list` из неё; `cmd_q_di` → `q_di_<kind>` (неизвестный `q_id` — ответить `complete=0`) | M | `server/accounts.py`, `server/server.py:620` |
| 7 | `cmd_q_st`: проверить НПС в локации и `q_idx` → тип, лимит `quest_log_capacity`, создать экземпляр, `cmdAck;res=0`, затем `q_di_<kind>`; для `del_obj` с `obj=0` сразу `complete=1` | M | `server/server.py` |
| 8 | `cmd_q_co`: проверить `mob`∈take, `complete`; начислить `rew_afro/rew_gold` → `userInfo_Player`, `cmdAck;res=0`; пометить сдачу (для non-repeatable) | M | `server/server.py` |
| 9 | `cmd_q_ca`: удалить экземпляр, `cmdAck;res=0` | S | `server/server.py` |
| 10 | Ручной прогон в Ruffle по чек-листу §1.7 (маркер «!», окно, «Получено новое задание», «Задание завершено», ни одного POST texts.xml в HTTP-логе) | S | `run.sh`, `logs/` |

### P1 — настоящие цели и награды

| # | Задача | Размер |
|---|---|---|
| 11 | Инвентарь на сервере (сейчас `ss_get` → пусто): персистентные предметы, `ss_obj_move`/добавление в рюкзак; без этого нет `bring`/`del_obj` с предметом и наградных предметов | L |
| 12 | `bring_l_obj`: счёт по рюкзаку → `q_di_bring_l_obj` при изменениях; при сдаче изъять предметы; проверить формулу `obj_idx` (`rew_obj[n-1-obj_idx]`) на квесте с выбором | M |
| 13 | Наградные предметы: выдать до `cmdAck` на `q_co`, чтобы попало в «Вы получили» | S (после 11) |
| 14 | Импорт вики: `data/wiki_quests_all.json` → `quests.json` для НПС стартовых клеток; мост имя-на-вики → type_id через страницы локаций и `mobs.xml`; сначала Чёрный рынок ВХ + Старый рынок + Жилой квартал | M |
| 15 | `q_sys` при входе, `daily_max`/`daily_reset_time` в `constants` уже есть; счётчик ежедневных и `res≠0` на `q_co` (клиент покажет текст 44) | S |
| 16 | Сервисы без боя: прописка `on_conv op=0` (точка возрождения), лечение `op=1` (списать `a_price`, `usrUp`), аренда `op=2` + `ts_si` | M |

### P2 — то, что упирается в другие подсистемы

| # | Задача | Размер |
|---|---|---|
| 17 | `kill_mobs`: хук на смерть моба (боя пока нет) → `q_di_kill_mobs` | M (после боя) |
| 18 | `rew_loc`/`finish_loc`/`loc`: телепорт после сдачи (`lenter` в другую локацию), geoID в метках карты | M |
| 19 | Цепочки `need_quest`, `level`, `party_size`, неповторяемые с историей сдач | M |
| 20 | Обучение (`s_type=4`, `ss_upd 1/2` со списанием по `Training.getCost`), апгрейд (`s_type=5`), банк (`s_type=3`, разделитель `0` в `o_list`, `s_status 3/4`) | M каждый |
| 21 | Заглушка `res/hints/hints.xml` (пустой `<data/>`), чтобы не было 404 | S |

### P3 — косметика и мёртвые поля

| # | Задача | Размер |
|---|---|---|
| 22 | Реплики НПС через серверный чат-кадр (`fromID`=id НПС) — единственный способ «сказать» что-то вне окна квестов | S |
| 23 | `m_hello`, фразы мобов — не реализовывать (клиент не показывает); зарезервировать диапазон 4 000 000 | — |
| 24 | Аукцион `ah_*`, трофеи (`s_type=6`) | L |
