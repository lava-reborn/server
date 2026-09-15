# Инвентаризация протокола LAVA Online: клиент против сервера

Дата: 2026-09-16. Источники: `recon/as-src/lol/**` (395 классов AS2),
`server/server.py` (722 строки), `server/items.py`, `server/protocol.py`, `PROTOCOL.md`.

Как проверялось. Три механических прохода по исходникам клиента, а не по заметкам:

1. Все 56 конструкторов `lol/server/mess/CSM_*.as` (имя `_name`, вызовы `addProp`).
2. Все `this.XMC.addEventListener("…")` (единственное имя переменной соединения во всех
   44 классах-подписчиках, проверено) плюс динамические `XMLCCallStack.addCall("…")`.
3. Все `new lol.server.mess.CSM_*(…)` с охватывающей функцией и наличием в ней
   `XMLCCallStack.addCall("cmdAck", …)`, то есть ждёт ли команда подтверждения.

Поля `obj.param.*` сняты с тел обработчиков, включая передачу `obj.param` в `initialize()`
классов предметов, квестов, эффектов, кланов.

---

## 0. Цифры

| Направление | Всего | Сервер реализует | Заглушка | Нет |
|---|---|---|---|---|
| Клиент → сервер, уникальных имён | **53** (56 классов) | **10** | **10** | **33** |
| Сервер → клиент, сетевых команд | **90** (89 живых + `fireAck`) | **36** | — | **54** |

`recon/notes/cs_commands.txt` **точен**: 56 классов, 53 имени, параметры совпадают
с конструкторами один в один. Три коллизии имён: `admit` (2 класса), `moveTo` (3),
`on_conv` (2). Единственное, чего таблица не показывает: `sndml` шлёт ключ `item` и
`rmvml` ключ `id` **повторно** (см. §1.1).

`recon/notes/sc_commands.txt` (239 имён) — это все `addEventListener` клиента, сетевых
среди них 86 статических подписок. Плюс 4 динамических (через `XMLCCallStack`):
`cmdAck`, `ss_ack`, `ctml`, `ah_sresult`. Итого 90. Остальные ~150 имён — внутренние
события `LEventDispatcher`, сервер их слать не должен. Полный сетевой список в §3.

---

## 1. Кодек: три вещи, которые матрица не покажет

### 1.1. Повторяющиеся ключи в кадре

`CSMessage.addProp(name, value, duplicateName)` пишет в кадр **исходное имя**, а
`duplicateName` служит только ключом в `propList`. Поэтому:

    sndml;item=x…;item=x…;item=x…;body=@…@;type=0;subj=@…@;to=@…@;
    rmvml;id=x…;id=x…;

`protocol.decode()` складывает пары в `dict`, то есть **останется только последний**
`item`/`id`. При реализации почты декодер надо расширить (список для повторов).
Больше нигде повторов нет.

### 1.2. Идентификатор предмета (oid)

`ItemFactory.create` разбирает oid через `MDString.parseBigUINT(oid, 4, 2)`:

    <серийный hex><type_id, ровно 4 hex><root_type, ровно 2 hex>

Пример: `x1a` + `111c` + `00` → серийник 0x1a, тип 0x111c = 4380, root 0 (FireArm).
На проводе всегда `x`-префикс: `obj=x1a111c00;`, в списках `o_list=|x1a111c00|x…|;`.
Класс предмета клиент берёт **из oid**, а не из имени команды `ss_di_*`. Пустой слот
в `o_list` — строка `0` (`createItem` отбрасывает `"0"` и строки короче 2 символов).

### 1.3. Цель выстрела/удара/лечения

`MDString.createBigUINT([targetType,1],[target,8])` → `target=x` + 1 hex тип +
8 hex id. `targetType` 1 = сущность (id игрока/моба), 0 = номер гекса.
Пример выстрела по мобу 100: `ss_use;type=16;obj=x1a111c00;target=x100000064;`.

---

## 2. Клиент → сервер: 56 классов / 53 команды

Обозначения в колонке «Сервер»: **Р** реализовано в объёме, достаточном для клиента;
**Ч** частично или заглушка (отвечает, чтобы клиент не завис, но содержания нет);
**Н** нет обработчика (падает в `handle()`: лог + `cmdAck;res=3;` если имя в `EXPECTS_ACK`).

«Ack» — регистрирует ли отправитель обработчик `cmdAck` (строго по `XMLCCallStack.addCall`
в той же функции). Это и есть истина для FIFO-очереди; расхождения с `EXPECTS_ACK`
сервера собраны в §2.1.

### 2.1. Сессия и персонаж

| Команда | Параметры | Откуда (класс.метод → действие игрока) | Ack | Ждёт в ответ | Сервер |
|---|---|---|---|---|---|
| `hello` | `minor=2, major=0` | `Session.sendHello` — сразу после connect; таймер 20 с | нет | `hello` (любые поля) | **Р** |
| `login` | `hash=@…@` | `Session.login` — по приходу `hello` | да | `cmdAck res=0`, затем клиент сам ничего не шлёт, ждёт `persInfo`/`accountInfo` | **Р** |
| `logout` | — | `Session.finish` — выход | нет | — (сервер рвёт сокет) | **Р** |
| `selPers` | `num` | `PersGenerator.selectDefaultPers`/`selectPers` — выбор персонажа | **нет** | `lcall` | **Р** |
| `newPers` | `name=@…@, sex, res=@…@` | `PersGenerator.___generatePers` — кнопка «создать» | да | `cmdAck` (0 ок; 5 плохое имя; 6 занято) | **Р** |
| `actPlayer` | — | `PersGenerator.activatePlayer` — после интро/видеоурока | да | `cmdAck`, затем `lcall` | **Р** |
| `resurrect` | `res_type` (0 бесплатно, 1 gold, 2 afro — `RegenerationInterface.RESURECT_*`) | `Resurrector.resurrect` — окно возрождения после `lch;dead=0` | да | `cmdAck res=0` → клиент сам закрывает окно, ставит `LOCAL_STATE`; дальше ждёт `usrUp`/`lch` | **Н** |
| `getInfo` | `type` (0 игрок, 1 NPC/моб), `id`, `lvl=0` | `Player.requestInfo`/`Entity.requestInfo` — автоматически из конструктора каждой сущности с `id≠0`; для себя из `Master.requestInfo` после `lenter`/`gmap` | нет | `userInfo_*` по классу сущности (+ `usrUp`) | **Р** |
| `rp_get_info` | — | `PersAttributes.requestAttributes` — один раз после `lenter` (`Master.requestInfo`), и из окон персонажа/экипировки/обучения | нет | `rp_info` | **Ч** (константы) |
| `chWorld` | `to` (undefined = кнопка «на карту»/«в локацию»; **1** = выход из локации в соседнюю через `exitLoc` «loc») | `Master.changeWorld` из `GlobalMapInterface`, `LocationInterface`, `DisplayMapObject`, `Location.exitLoc` | да | `cmdAck` (0 ок; 39 «нельзя выйти в бою»), затем `gmap` или `lcall` | **Ч** (`to=1` игнорируется, интерьер-граф утрачен) |
| `lenter` | `accept=1` | `Master.locLoaded` — когда XML/арт локации загружены и `lcall.ie≠1` | да, **но** `lenter` снимает его (`skipCall`) | `lenter` (успех) **или** `cmdAck res≠0` (отказ), не оба | **Р** |

### 2.2. Движение и карта

| Команда | Параметры | Откуда | Ack | Ждёт | Сервер |
|---|---|---|---|---|---|
| `moveTo` (loc) | `path=\|c0\|c1\|…\|` (c0 = текущая клетка) | `Location.movePlayer` — клик по гексу / подход к NPC (`Gamer.gotoWalker`) | да, `moveCmdAck` (пустой) | `cmdAck` + `userMove;id=0;path=…` **или** `breakMv`/`cor_pos` (они делают `skipCall` — тогда `cmdAck` слать нельзя) | **Р** (эхо; без валидации пути) |
| `moveTo` (map) | `dy, dx` (сотые клетки) | `GlobalMap.playerMove` — клик по карте; `dy=1,dx=0` = отмена перехвата | нет | `moveAck;vx;vy;t`, затем `userMove;id=0;…;vx=0;vy=0` по прибытии | **Р** |
| `moveTo` (trg) | `trg=<id>` | `GlobalMap.interceptPlayer` — контекстное меню «перехватить» | нет | `moveAck`/`userMove` | **Н** (`return`) |
| `insMark` | `dx, dy` (целые клетки от игрока), `title=@@`, `info=@@` | `GlobalMap.addMark` — окно метки | да | `cmdAck res=0` → клиент сам добавляет метку | **Н** |
| `updMark` | `id` (индекс в клиентском массиве), `title`, `info` | `GlobalMap.editMark` | **нет** | ничего | **Н** |
| `rmMark` | `id` (индекс) | `GlobalMap.removeMark` | да | `cmdAck res=0` | **Н** |

### 2.3. Предметы, сессии с NPC, торговля

`ss_create;s_type` — тип сессии (`StuffManager`): 0 лут (target = **номер гекса**),
1 торговля, 2 бартер (target = id игрока), 3 банк, 4 обучение, 5 апгрейд, 6 трофеи
(target = 0, свой id). Все семь вызовов регистрируют `cmdAck`.

`ss_upd;s_status;obj;param` — операция внутри открытой сессии. Коды по сессиям:

| Сессия | `s_status` | Ack? |
|---|---|---|
| Торговля (`Trade`) | 0 close | **нет** |
| | 1 buy, 4 buy_gold, 8 bgpoints_buy (`obj` = x`tradeID` — индекс в `type_list`, `param` = кол-во) | да |
| | 2 sell (`param` = размер стопки) | да |
| | 3 repair, 5 repair_gold, 7 restore | да (`repAck` → событие `repAck`) |
| | 6 reg_trophy | да (`regAck`) |
| Бартер (`Barter`) | 0 close, 2 deny, 5 apply, 6 break | **нет** |
| | 1 agree, 3 to_buffer, 4 to_bag, 7 add_afro, 8 add_gold (`obj` = x сумма) | да |
| Банк (`Bank`) | 0 close | **нет** |
| | 1 put, 2 get, 6 increase_weight (без `obj`) | да |
| Лут (`Loot`) | 0 close | **нет** |
| | 1 to_bag, 2 to_buffer, 3 get_all | да |
| Обучение (`Training`) | 0 close | **нет** |
| | 1 forget, 2 learn (`obj` = x номер спецухи) | да (пустой) |
| Апгрейд (`Upgrade`) | 0 close | **нет** |
| | 1 upgrade (`obj` = x oid, `param` = out type) | да (`upgrAck`) |
| Трофеи (`TrophyManager`) | 0 close | **нет** |
| | 1 set_public (`param` = слот), 3 by_public (без `obj`), 4 delete | да |

| Команда | Параметры | Откуда | Ack | Ждёт | Сервер |
|---|---|---|---|---|---|
| `ss_create` | `s_type, target` | `Trade/Bank/Barter/Training/Upgrade.ss_propose` (подход к NPC, `Gamer.proposeContact`), `Loot.createSession` (клик по мешку), `TrophyManager.createSession` (окно трофеев) | да | `cmdAck res=0` → клиент открывает окно и шлёт `ss_get` за содержимым | **Ч** (только ack, сессия не создаётся) |
| `ss_get` | `slot` (маска), `target` (id владельца) | `PersEquip.firstRequest` (**slot=11** = 8 рюкзак + 2 руки + 1 одежда, свой id, после `lenter`); `Player`/`Mob` конструктор (**slot=3**, чужой id — чтобы нарисовать экипировку); `Trade/Barter/Upgrade.requestSession` (8); `Bank/Loot.requestSession` (24 = 8 + 16 сессия); `TrophyManager.requestTrophy` (16); `PersEquip.requestPublicTrophy` (32) | нет; очередь `ss_ack` (FIFO) — для slot=32 регистрирует **и** `ss_ack`, **и** `cmdAck`, первый пришедший снимает второй | `ss_ack;o_list=\|…\|;set_res=` — порядок: [6 одежда][2 руки][рюкзак…]; для 16/24 после рюкзака идёт `0`-разделитель, дальше содержимое сессии | **Ч** (всегда пусто) |
| `ss_get_si` | `type` | `ItemFactory.requestSI` — при первом появлении type_id (окно **5**, только в `LOCAL_STATE`) | нет | `ss_si_<класс>` | **Ч** (`items.static_info`: 30 позиций STOCK детально, остальные по шаблону root-типа) |
| `ss_get_di` | `obj=x…`, `target` (опц.) | `ItemFactory.requestSD` — при первом появлении **каждого** oid (окно **5**, общее с `ss_get_si`) | нет | `ss_di_<класс>;obj=…` + динамика | **Н** — как только появится первый настоящий oid, окно засорится |
| `ss_get_s_si` | `type` | `SetManager.requestSI` — когда у `ss_si_wear` пришёл `set_type≠0` (окно 5) | нет | `ss_si_set` | **Ч** |
| `ss_move` | `from, to` (`maskIndex<<8 \| index`), `obj=x…` | `PersEquip.requestTranfer` — drag&drop рюкзак↔слоты. Маски: 1 одежда (index 0..5 = head, camouflage, armor, belt, legs, boots), 2 руки (0 primary, 1 secondary), 8 рюкзак | да | `cmdAck` (0 → клиент сам переносит; иначе откат) | **Н** |
| `ss_use` | `type` (бит действия), `obj=x…`, `target` | `ItemActivator.useItem`. `type`: 0 delete, 1 load (`target`=x oid патронов), 2 use_idle, 4 use_target (`target` = x1+id), 8 use_item, 16 fire/strike (`target` = §1.3; для кулаков `obj=x0`), 32 unload, 64 usemode (`target` = x режим) | да | `cmdAck` (0 ок; 11 нет ОД, 13 нет патронов, 14 не те патроны, 15 уже заряжено, 16 сломан, 17 не готов, 45 не хватает навыков) + для 16: `faAim/faShot/faHit/faWall/faMiss` или `caHit/caMiss`; для 2/4: `heal`, `usrUp`, `ss_obj_status`; для 1/32/64: `ss_di_firearm` | **Н** |
| `ss_heap_c` | `obj=x…` (стопка-приёмник), `num`, `trg=x…` (стопка-донор, только при слиянии) | `StuffManager.joinHeap`/`separateHeap`, `MailInspector.separateHeap` | да | `cmdAck` + `ss_obj_status`/`ss_di_heap` | **Н** |
| `e_get_si` | `type` | `EffectsFactory.requestSI` — при первом эффекте из `ss_si_heal.effects` или `e_list` (окно 5) | нет | `e_si` | **Н** (не срабатывает, пока `effects=[]`) |
| `e_get_di` | `type, mobi_id` | `EffectsFactory.requestDI` — только для `mobi_id=0` (свои эффекты) | нет | `e_di` | **Н** |
| `ts_get_si` | `type` | `TransportFactory.requestSI` — из `userInfo_Player.tr≠0` или списка `give_transport` арендодателя (окно 5) | нет | `ts_si` | **Н** (не срабатывает при `tr=0`) |

### 2.4. Квесты

Окно конвейера `QuestInspector` = **1** для `q_status`, `q_si`, `q_di` (общий счётчик).
`q_list` вне окна.

| Команда | Параметры | Откуда | Ack | Ждёт | Сервер |
|---|---|---|---|---|---|
| `q_list` | — | `requestCurrentQuests` — после `lenter` и `gmap` (один раз, флаг `requested`) | нет | `q_list;q_id=\|…\|;q_types=\|…\|` → по каждому: `q_si` (если тип неизвестен) или `q_di` | **Ч** (пусто) |
| `q_status` | `q_type` | `checkQStatus` — по каждому id из `give_quests`/`take_quests` NPC | нет | `q_status;type;status;name;q_type` | **Ч** (`status=0`) |
| `q_si` | `q_type` | `requestSI` — из `q_list`, `loadUnknownQuest` | нет | `q_si_kill_mobs` / `q_si_bring_l_obj` / `q_si_del_obj` | **Н** |
| `q_di` | `q_id` | `requestDI` — из `q_list`/после `q_si` | нет | `q_di_*` | **Н** |
| `q_st` | `q_idx` (индекс в `give_quests` NPC), `mob` | `getQuest` — «взять квест» | да | `cmdAck` + `q_di_*` (новое задание) | **Н** |
| `q_co` | `q_id, mob, obj_idx` | `takeQuest` — «сдать» (obj_idx = выбранная награда) | да | `cmdAck` (44 = лимит ежедневных) + `ss_obj_status` награды | **Н** |
| `q_ca` | `q_id` | `cancelQuest` | да | `cmdAck` | **Н** |

### 2.5. Чат, отряд, кланы, банк валют

| Команда | Параметры | Откуда | Ack | Ждёт | Сервер |
|---|---|---|---|---|---|
| `userMsg` | `entry=@@`, `group` (0 локация, 1 отряд, 2 клан, 3 события, 4 торговля, 5 помощь, 6 мир), `to=@ник@` (приват; тогда `group` отсутствует) | `Chat.sendMessage` | да | `cmdAck` (0 → печатает своё; 9 → как «сервер»; 1001 приват без адреса) — и **эхо `userMsg` не нужно**: своё сообщение клиент печатает по ack | **Р** (ack + эхо; эхо даёт дубль — проверить) |
| `p_op` | `op, id` | 0 invite (`Gamer.sendInviteToParty`, id гостя), 1 kick (id; 0 = выйти), 2 say_yes / 3 say_no (`PartyManager.sendInviteAnswer`), 4 change_leader, 5 party_list | да для 0,1,2,3,4; **нет для 5** и для авто-отказа (`DeclineInvite`) | `cmdAck` (31 = нельзя пригласить); на 5 → `p_m` | **Н** |
| `head` | `soc=@имя@, reg=@описание@` | `ClanInspector.createClan` | да | `cmdAck` (5, 6, 21 нет денег) + `fellow` | **Н** |
| `admit` | `post=@@, perm, char` (`@имя@` при приглашении, число при смене прав) | `inviteToClan` / `changeRights` | да | `cmdAck` (22 не найден, 28 в другом клане, 30 оффлайн, 23 длинно) + `invite` адресату | **Н** |
| `apply` | `action, number` | `action`: 0 переключить приём приглашений; 1 выйти (number=0) / выгнать (number=char); 1/2 ответ на приглашение (number=0, action 1 = нет, 2 = да); 3 afro / 4 gold в казну (number<0 = снять); 5/6 установить отношение (number = clanID); 7 запросить отношение | да | `cmdAck` (21 нет денег) + `gg_list`/`gg_struct`/`fellow` | **Н** |
| `gg_info` | `det` | 1 список членов, 3 afro казны, 4 gold казны, 5 отношения, 6 стоимости | да | `cmdAck` (9 = повторить через 5 с) + `gg_list;res=<det>` | **Н** |
| `c_ga` | `gold` | `BankAccount.convertGoldToAfro` — окно обмена | да | `cmdAck` + `userInfo_Player` (обновить деньги) | **Н** |

### 2.6. Почта, аукцион, поля боя, услуги NPC

| Команда | Параметры | Откуда | Ack | Ждёт | Сервер |
|---|---|---|---|---|---|
| `chkml` | `mode` (0 входящие, 1 исходящие, 255 тарифы) | `MailInspector.getInbox/getOutbox/getMailParam` — открытие окна почты (первый раз) | да | `cmdAck` затем `lsml` или `svml` | **Ч** (пусто + тарифы) |
| `getml` | `id=x…` | `getFullLetter` — открыть письмо | да | `cmdAck` (35 не найдено) + `rcml` | **Н** |
| `sndml` | `to=@@, subj=@@, type, body=@@, item=x…×N, afro, gold` (`afro`/`gold` только если ≠0) | `sendLetter` | да + очередь `ctml` | `cmdAck` (34 адресат не найден, 37 не в клане) и **только при 0** — `ctml` | **Н** |
| `rmvml` | `id=x…×N` | `removeLetters` | да | `cmdAck` | **Н** |
| `uldml` | `id=x…` | `getObjectsFromLetter` — забрать вложения | да + `ctml` | `cmdAck` (35, 36 нет вложений); при 0 — `ctml` | **Н** |
| `ah_search` | `target, page, name=@@, cat, subcat, min_lvl, max_lvl, min_a, max_a, min_g, max_g, sort, s_mode` | `Auction.sendSearchRequest` (антиспам 1 с) | **нет** — очередь `ah_sresult` | `ah_sresult;page;count;next` + N × `ah_lot` | **Н** |
| `ah_op` | `target, type` (0 bid, 1 buyout, 2 takeoff, 3 sell), `obj=x…`, `amount` (bid) | `rateLot/buyoutLot/cancelLot/sellsLot` | да | `cmdAck` (0 или 40 → клиент повторяет поиск) | **Н** |
| `ah_create` | `target, obj=x…, time, a_bid, a_buyout, g_bid, g_buyout` | `createLot` | да | `cmdAck` | **Н** |
| `bg_op` | `type, ts, op` | 0 в очередь (`goToBattleGround`), 2 из очереди, 3 да / 4 нет на приглашение, 5/7 покинуть незавершённое/завершённое, 6 запрос инфо (через 1.5 с после входа в BG-локацию) | **да только для 0 и 2** | `cmdAck`; далее `bg_op` (S→C), `bg_res` | **Н** |
| `on_conv` | `mob, op` (0 прописка, 1 лечение у медика); форма `TS_on_conv`: `op=2, p1=typeID, p2=дней, mob` (аренда транспорта) | `Attendance.activate`, `Rent.getTransport` | да | `cmdAck` (+ `usrUp` при лечении, `userInfo_Player.tr` при аренде) | **Н** |

### 2.7. Расхождения `EXPECTS_ACK` сервера с клиентом

Это важнее любой недостающей команды: лишний `cmdAck` сдвигает FIFO, и все дальнейшие
подтверждения достаются чужим обработчикам, молча.

| Команда | Сервер сейчас | Клиент на самом деле | Где стреляет |
|---|---|---|---|
| `ss_upd` s_status=0 (close) во **всех** сессиях | `cmd_ss_upd` всегда `cmdAck` | не регистрирует | **Достижимо сейчас**: открыть лавку, закрыть — очередь съехала на 1 |
| `ss_upd` бартер 2 deny, 5 apply, 6 break | ack | нет | бартер |
| `ah_search` | в `EXPECTS_ACK` | нет, только `ah_sresult` | аукцион |
| `updMark` | в `EXPECTS_ACK` | нет | метки карты |
| `bg_op` op 3,4,5,6,7 | fallback ack (res=3) | нет (только 0 и 2) | поля боя; PROTOCOL.md §7 это знает, код — нет |
| `p_op` op=5 | в `EXPECTS_ACK` | нет | отряд (после каждого ответа на приглашение клиент шлёт op=5) |
| `moveTo` path, отвергнутый | — | `breakMv`/`cor_pos` делают `skipCall(moveCmdAck)` → отказ надо слать **вместо** `cmdAck`, не после | движение |
| `ss_get` slot=32 | — | ждёт `ss_ack` **или** `cmdAck`, второй снимается | трофеи: слать только `ss_ack` |
| `lenter` | верно (ack только при отказе) | | |

---

## 3. Сервер → клиент: 90 команд по подсистемам

«Шлёт» — есть ли `self.send("…")` в `server.py`. Поля даны в порядке чтения
обработчиком; `\|…\|` — список, `@@` — строка, `x` — BigUINT.

### 3.1. Вход и аккаунт

| Команда | Поля | Клиент | Шлёт |
|---|---|---|---|
| `hello` | любые | `Session.hello` → снимает таймер, шлёт `login` | ✓ |
| `cmdAck` | `res` | `XMLCCallStack` → первый ожидающий обработчик; `ErrorReport` показывает текст по коду (1 логин, 2 бан, 3 сервер не отвечает, 4 аккаунт занят, 5/6 имя, 7/18 нельзя в локацию, 8 нельзя пройти, 11 ОД, 12 объект не найден, 13–17 оружие, 19 нет предмета, 27 перегруз, 44 дневной лимит, 45 навыки, 1001–1003 чат/гражданство) | ✓ |
| `constants` | `gold_to_afro_rate, quest_log_capacity, leave_combat_timeout, premium_weight_bonus_1/2, premium_break_bonus_1/2, premium_xp_bonus_1/2, gold_repair_price_mod, gold_repair_mod, daily_max, daily_reset_time` | `GConstatns` | ✓ |
| `persInfo` | `num, name=@@, sex, death, res=@@` | `PersGenerator.persInfo` — по одному на персонажа | ✓ |
| `accountInfo` | `nPers, can_create` | `PersGenerator.accountInfo` — **обрабатывается только при `can_create≠0`** | ✓ |
| `kickban` | `admin=@@, seconds, reason=@@` | окно-alert | ✗ |
| `shutdown` | `seconds` | окно-alert | ✗ |

### 3.2. Персонаж (свой)

| Команда | Поля | Клиент | Шлёт |
|---|---|---|---|
| `userInfo_Player` | `id, name=@@` (пусто → «Солдат СА»), `sex, res=@@` (id аватара), `ail, ally, lvl, rep=\|…\|, bg_rep, bg_pen, hl, pr, clan`; для `id=0` ещё `afro, gold, tr, tr_hours` | `PlayerRegister` → `Player.userInfo`/`Gamer.userInfo`; `ClanInspector.userInfo` читает `clan`; `tr≠0` → `ts_get_si` | ✓ (только id=0) |
| `usrUp` | `id, hcur, scur, hmax, smax` (`hmax`/`smax` опц.) | `Entity.userUpdate` (два подписчика: `Master` и `PlayerRegister`) | ✓ (при `getInfo`) |
| `rp_info` | `a_attribs_mask, a_attribs, f_attribs_mask, f_attribs, a_skills_mask, a_skills, f_skills_mask, f_skills, xp_skills_mask, xp_skills, xp_max_skills_mask, xp_max_skills, a_specs_mask, a_specs, f_specs_mask, f_specs, xp_specs_mask, xp_specs, xp_max_specs_mask, xp_max_specs, max_specs, hp, hp_max, sp, sp_max, ap_max, max_weight, armor, lvl` (маска + плотный список; 5 атрибутов, 5 навыков, 15 спецух) | `PersAttributes.rp_info` — также ставит `gamer.health/maxHealth` | ✓ (константы) |
| `c_ap` | `ap` | `APManager.syncAPtoServer` — принудительная синхронизация ОД | ✗ |
| `e_list` | `mobi_id, effects=\|type…\|` | `EffectManager.e_list` — список активных эффектов сущности; неизвестные типы → `e_get_si` | ✗ |
| `prepare` | `id, time` | `Location.prepare` → `Player.prepare = time-2` (таймер подготовки) | ✗ |

### 3.3. NPC и мобы

Класс сущности клиент строит по `rtype` из `lch` (0 Mob, 1 Trader, 2 Teacher, 3 Upgrader,
4 Commoner, 5 Healer, 6 Lessor, 7 Auctioner, **любое другое, например -1 — Player**).
Имя команды `userInfo_*` должно соответствовать классу: `userInfo` для Mob,
`userInfo_Trader`, `userInfo_SpecTrainer`, `userInfo_Upgrader`, `userInfo_Commoner`,
`userInfo_Medic`, `userInfo_Lessor`, `userInfo_Auctioneer`.

| Команда | Поля | Клиент | Шлёт |
|---|---|---|---|
| `userInfo` (Mob) | `id, name` (**числовой id строки**), `sex, res` (type_id), `ail, ally, lvl, rep, bg_rep, bg_pen, m_idle=\|…\|, m_detect, m_attack, m_run, m_death` (id строк-реплик) | `Mob.userInfo`; `res` → `persType` → путь к арту | ✓ (без реплик) |
| `userInfo_<NPC>` | базовые + `give_quests=\|type…\|, take_quests=\|…\|, can_set_home, can_banking, can_trophy, can_repair, can_trade, m_hello=\|…\|`; Trader: `type_list=\|type…\|` (прайс, индекс = `tradeID` для `ss_upd buy`), `bg_objects, bg_obj_rep_req, pmod, smod, rmod`; Upgrader: `in_types, out_types, costs`; Medic: `a_price`; Lessor: `give_transport=\|type…\|` | `NPC.userInfo` → каждый id из `give_quests`/`take_quests` порождает `q_status` | ✓ |

### 3.4. Локация

| Команда | Поля | Клиент | Шлёт |
|---|---|---|---|
| `lcall` | `id, ws, ie, g_id` | `Master.lcall` → грузит локацию; `ie≠1` → клиент пришлёт `lenter;accept=1` | ✓ |
| `lenter` | `pos, aspd, amax` | `Master.lenter` → ставит игрока, снимает `lenterAck`, затем `requestInfo()` (= `getInfo`, `rp_get_info`, `ss_get slot=11`, `q_list`) | ✓ |
| `lch` | независимые поля, любое подмножество: `ws` (0/1 боевой режим); `newUser + pos + rtype` (все три обязательны; `refl` = зарегистрировать без фигуры); `lostUser`; `enemy` (id); `dead` (id; **0 = сам игрок** → окно возрождения); `friend` (игнорируется) | `Location.lch`, `AutoCommandManager`, `Resurrector`, `ItemActivator`, `SpecSkillMessages` | ✓ (только `newUser` для NPC при входе) |
| `userMove` (loc) | `id, path=\|c…\|` | `Location.userMove` → `LocWalker.createMove` (первая клетка = текущая) | ✓ (себе) |
| `breakMv` | `id, pos` | телепорт на `pos`, `skipCall(moveCmdAck)`, сброс `busy` | ✗ |
| `cor_pos` | `id, pos` | то же + для себя переотправляет `moveTo` к прежней цели | ✗ |
| `ss_loot` | `s_status` (1 появился / 0 исчез), `hex` | мешок лута на гексе; клик → `ss_create;s_type=0;target=hex` | ✗ |

### 3.5. Глобальная карта

| Команда | Поля | Клиент | Шлёт |
|---|---|---|---|
| `gmap` | `x, y, v_rad` | `Master.gmap` → `GlobalMap.addGamer`; потом `getInfo`, `q_list` | ✓ |
| `newUser` | `id, dx, dy` (**целые клетки относительно игрока**: `x_чужого = x_мой − dx`) | `GlobalMap.newUser` → объект с секундным таймером живучести | ✗ |
| `userLost` | `id` | `GlobalMap.userLost` | ✗ |
| `userMove` (map) | `id, dx, dy` (**абсолютные** координаты), `vx, vy` (клеток/с), `t` | `GlobalMap.userMove` — сбрасывает таймер; неизвестный `id` создаётся на лету; **3 с без кадра → объект гаснет, 6 с → удаляется** | ✓ (себе, id=0, только по прибытии) |
| `moveAck` | `vx, vy, t` | `GlobalMap.moveAck` → старт движения своего объекта | ✓ |
| `marks` | `dxdy=\|x1\|y1\|x2\|y2…\|, title=\|@@…\|, info=\|@@…\|` | `GlobalMap.marks` — порядок = индексы для `updMark`/`rmMark` | ✗ |

### 3.6. Бой

Все поля — готовые числа; клиент ничего не считает (кроме зеркала формул в `CharInterface`).
Отсутствие `id`/`target` означает самого игрока (0).

| Команда | Поля | Клиент | Шлёт |
|---|---|---|---|
| `faAim` | `id, ang, num_shots` | поворот, число выстрелов в очереди | ✗ |
| `faShot` | `id, status` (1 начало, 0 конец очереди) | `Location`, `ItemActivator.useFirearmAck` (снимает кулдаун), `AutoCommandManager` | ✗ |
| `faHit` | `target, dmg, sdmg, crit` | урон цели, таймер выхода из боя | ✗ |
| `faWall` | `hex` | попадание в стену | ✗ |
| `faMiss` | `x, y` | промах | ✗ |
| `caHit` | `id, target, dmg, sdmg, crit` | удар ближним | ✗ |
| `caMiss` | `id, hex` | промах ближним | ✗ |
| `heal` | `id, target, hp, sp` | ставит `health/stamina` цели | ✗ |
| `fireAck` | — | подписка есть, обработчика нет: **мёртвая** | — |

### 3.7. Предметы

Сервер отвечает по `ss_get_si` командой, зависящей от root_type (0 `ss_si_firearm`,
1 `ss_si_wear`, 2 `ss_si_heal`, 3 `ss_si_ammo`, 4 `ss_si_simple_obj`, 5 `ss_si_coldarm`,
6 `ss_si_trophy`). Поля скопированы из `initialize()` каждого класса.

| Команда | Поля | Шлёт |
|---|---|---|
| общие для всех `ss_si_*` | `type, name` (id строки), `desc` (id строки или `""`), `vis, weight, tech_dif, exchang, cost, bg_p_cost, g_cost, repair_mod, sell_mod, premium, action_map, quest, need_pvp_rep`; требования/бонусы: `need_attribs_m + need_attribs`, `need_skills_m + need_skills`, `need_specs_m + need_specs`, `bonus_attribs_m + bonus_attribs`, `bonus_skills_m + …`, `bonus_specs_m + …`, `bonus_hp, bonus_st, bonus_od, bonus_cp, bonus_ce` (маска + плотный список) | ✓ (бонусы не шлёт) |
| `ss_si_firearm` | `h_damage_min/max, st_damage_min/max, max_range, opt_range, end_opt_range, target_size, fire_costs, fire_mods, fire_times, piercing` — по списку из 3 (режимы); `reload_time, reload_cost, max_break_abs, clip_size, comp_array, ammo_count, weapon_type` | ✓ |
| `ss_si_wear` | `armor_class, slot_type, max_break_abs, set_type` | ✓ |
| `ss_si_heal` | `heal_time, max_h_rest, max_st_rest, min_h_rest, min_st_rest, use_count, bonus_prob, bonus_act_time, can_rest_br, str_bonus, dex_bonus, sta_bonus, per_bonus, int_bonus, heal_cost, effects=\|…\|, effects_prob=\|…\|` | ✓ |
| `ss_si_ammo` | `max_count, range_mod, st_mod, dam_mod, acc_mod, piercing, sell_num` | ✓ |
| `ss_si_simple_obj` | `max_count, range_mod, st_mod, dam_mod` | ✓ |
| `ss_si_coldarm` | `h_damage_min/max, st_damage_min/max, max_range, can_aimed, max_break_abs, strike_cost, strike_mod, strike_time` | ✓ |
| `ss_si_trophy` | `count, k_id, k_name, k_lvl, v_id, v_name, v_lvl, v_clan, time` | ✓ |
| `ss_si_set` | `type, res, name, desc, bonus_{2..6}_attribs_m/_attribs/_skills_m/_skills/_specs_m/_specs/_hp/_st/_od/_cp/_ce` | ✓ (пусто) |
| `ss_ack` | `o_list=\|x…\|` (см. §2.3 про раскладку по маске), `set_res` (id ресурса сета) | ✓ (пусто) |
| `ss_di_firearm/coldarm/wear/heal/heap/trophy` | `obj=x…` + произвольные поля, копируются в объект как есть (`updateProperties`); ключ `break` → `__break`. По `getProp` в UI ожидаются: `break, max_break_cur, size, ammo_count, ammo_type, cur_mode, use_count, bonus_*, premium, count, time` | ✗ |
| `ss_obj_status` | `obj=x…, status` (1 — добавить в рюкзак, 0 — удалить откуда угодно) | ✗ |
| `ss_obj_move` | `id, from, to` (`mask<<8\|index`), `obj=x…` | ✗ — смена экипировки **чужого** игрока (свой игнорируется) |
| `ss_create` (S→C) | `target` | ✗ — «игрок N предлагает бартер» |
| `ss_upd` (S→C) | `s_status, obj` | ✗ — закрытие сессии (0), банк: 3 max_weight/4 cur_weight (`obj` = hex), бартер: 1..8, трофеи: число публичных слотов |
| `e_si` | `type, name, desc, work_time, update_delta, bonusAttribs, bonusSkills, bonusSpecs, max_hp, max_sp, max_od, critical_probability, critical_evade, armor, mob_exp, pl_exp` (или `player_exp`), `mob_drop, pl_drop, res_icon, immob` (или `immobilize`), `stun, time` (или `effect_time + register_time`) + массивы бонусов | ✗ |
| `e_di` | `type, mobi_id` + те же | ✗ |
| `ts_si` | `type, speed_mod, aggro_mod, g_cost, cost, res, premium, name, desc` | ✗ |

### 3.8. Квесты

| Команда | Поля | Шлёт |
|---|---|---|
| `q_list` | `q_id=\|…\|, q_types=\|…\|` | ✓ (пусто) |
| `q_status` | `type, status, name, q_type` | ✓ (`status=0`) |
| `q_sys` | `daily_available` | ✗ |
| `q_si_kill_mobs` / `q_si_bring_l_obj` / `q_si_del_obj` | `type, repeatable, party_size, loc, finish_loc, level, rew_obj=\|…\|, rew_afro, rew_gold, rew_loc, num_rew_obj, need_quest, q_type, name, start_desc, notfinish_desc, finish_desc` (id строк); kill: `mobs_kill=\|…\|, num_kill=\|…\|`; bring: `obj_1..obj_6, obj_num_1..6, mobs_1..6`; del: `obj` | ✗ |
| `q_di_kill_mobs` / `q_di_bring_l_obj` / `q_di_del_obj` | `q_id, q_type, complete` + `kill_num=\|…\|` / `obj_num=\|…\|` / `obj` | ✗ |

### 3.9. Чат, почта, кланы, отряд, аукцион, поля боя

| Команда | Поля | Шлёт |
|---|---|---|
| `userMsg` | `group, from` (id; отсутствует + есть `from` → приват), `entry=@@, nick=@@`, `player` (для клана — id вместо `from`) | ✓ |
| `lsml` | `id=\|x…\|, date=\|@@…\|, name=\|@@…\|, flag=\|…\|, subj=\|@@…\|`; `flag`: биты 0–3 тип, 4 возврат, 5 вложения, 6 непрочитано, 7 исходящее | ✓ (пусто) |
| `svml` | `data=\|8\|, time=\|8\|` | ✓ |
| `rcml` | `id, flag, date, from, to, body=@@` (внутри `=?HS:…?=`/`=?HC:…?=`/`=?BS:a/b?=` описания вложений), `items=\|x…\|, afro, gold` | ✗ |
| `ctml` | `id` (0 = отказ), `item=\|…\|` (5 предметов + afro + gold), `code=\|…\|` (-1 списан, 1 получен, -9/-11/9/11 ошибки) | ✗ |
| `fellow` | `id, reg, soc, post, stand, char, perm` (`id=0` — про себя; `reg=0` — выгнан; `reg=16777215` — свободен) | ✗ |
| `invite` | `rec, soc, pos` | ✗ |
| `gg_struct` | `id, act` (0 онлайн, 1 добавлен, 2 удалён, 3 права, 4 оффлайн), `name, post, date, perm` | ✗ |
| `gg_list` | `res` (эхо `det`), `data, names, posts, dates, perms, stats` | ✗ |
| `gg_code` | `res` (20 = не хватает прав) | ✗ |
| `p_op` | `op` (0 invite, 1 leave, 2 kicked, 3 leader, 4 join, 5 online, 6 disconnected, 7 exist, 8 refuse, 9 disband), `mob_id` | ✗ |
| `p_m` | `list=\|id…\|` (первый = лидер) | ✗ |
| `ah_sresult` | `page, count, next` | ✗ |
| `ah_lot` | `obj=x…, owner=@@, a_bid, a_buyout, g_bid, g_buyout, time_left, bidder` | ✗ |
| `bg_init` | `type_list=\|…\|, ts_list=\|…\|` | ✗ |
| `bg_op` | `type, ts, op` (0 приглашение, 1 осталось времени (`par`), 2 идёт бой), `par` | ✗ |
| `bg_res` | `team_win, players_0, kills_0, deaths_0, players_1, kills_1, deaths_1` | ✗ |

---

## 4. Особые случаи

### 4.1. Где клиент виснет без ответа

Ни одно из этих мест не показывает ошибку — просто перестаёт работать часть UI.

| Запрос | Механизм | Симптом |
|---|---|---|
| `ss_get_si`, `ss_get_di` | `ItemFactory.callCount`, окно 5, общее; декремент только по `ss_si_*`/`ss_di_*` | после 5 безответных — ни один новый предмет не описывается: лавка пустая, рюкзак «без имён» |
| `ss_get_s_si` | `SetManager`, окно 5 | описания сетов |
| `e_get_si`, `e_get_di` | `EffectsFactory`, окно 5 | эффекты |
| `ts_get_si` | `TransportFactory`, окно 5 | транспорт |
| `q_status`, `q_si`, `q_di` | `QuestInspector`, окно **1** | все квесты у всех NPC замирают после первого безответного |
| `ss_get` | очередь `ss_ack` FIFO | экипировка/лавка/банк/лут не заполняются; ответ чужому запросу |
| `chkml`, `getml`, `sndml`, `uldml` | `cmdAck` + для `sndml`/`uldml` вторая очередь `ctml` | окно почты |
| `ah_search` | очередь `ah_sresult` + флаг `resultFlag` | поиск блокируется навсегда |
| `hello` | таймер 20 с | обрыв соединения |
| `lenter` | флаг `lgetted` | сцена локации не открывается (`enterLocation` требует и `lloaded`, и `lgetted`) |
| `accountInfo` с `can_create=0` при нуле персонажей | `checkFullInfo` | экран выбора не открывается |

Плюс §2.7: любой лишний или пропущенный `cmdAck` — тихий сдвиг всей очереди.

### 4.2. Что нужно для мультиплеера

Сервер сейчас не хранит реестр сессий и не рассылает ничего никому, кроме отправителя.
Точные кадры, которые должны разойтись по всем в той же локации/зоне видимости:

**Локация.**
- Появление: `lch;newUser=<id>;pos=<cell>;rtype=-1;` (rtype вне 0..7 → класс `Player`;
  -1 дополнительно заставляет уже известного игрока перезапросить экипировку).
  Клиент нового игрока сам пришлёт `getInfo;type=0;id=<id>;lvl=0;` и
  `ss_get;slot=3;target=<id>;` — на них нужны `userInfo_Player;id=<id>;name=@…@;sex;res=@@;…`
  и `ss_ack;o_list=|6 одежды|2 руки|;` (пустые слоты — `0`).
- Уход: `lch;lostUser=<id>;` (клиент печатает событие «игрок покинул локацию» — нужно
  имя, то есть `userInfo_Player` должен был прийти раньше).
- Движение: `userMove;id=<id>;path=|c0|c1|…|;` каждому, включая отправителя (с `id=0`).
- Коррекция: `breakMv;id=<id>;pos=` / `cor_pos`.
- Смена экипировки: `ss_obj_move;id=<id>;from;to;obj=x…;`.
- Здоровье: `usrUp;id=<id>;hcur;scur;hmax;smax;`.
- Бой: `faAim/faShot/faHit/faWall/faMiss/caHit/caMiss/heal` с `id`/`target` стрелка и цели,
  `lch;dead=<id>;`, `lch;enemy=<id>;`, `lch;ws=1;` каждому участнику.
- Лут: `ss_loot;s_status=1;hex=`.
- Чат: `userMsg;group=0;from=<id>;nick=@…@;entry=@…@;` всем в локации (отправителю
  эхо **не** нужно — он печатает своё по `cmdAck res=0`).

**Глобальная карта.**
- `newUser;id;dx;dy;` (относительные целые клетки) при входе в радиус `v_rad`.
- `userMove;id;dx;dy;vx;vy;t;` (абсолютные) **не реже раза в 3 с по каждому видимому**,
  иначе через 3 с объект гаснет, через 6 с удаляется (`MapObject.checkLive`).
- `userLost;id;` при выходе из радиуса.
- Перехват: `moveTo;trg=` → сервер ведёт к цели, отвечает `moveAck`/`userMove`.

**Бартер между игроками.** Инициатор: `ss_create;s_type=2;target=<id>` → `cmdAck`.
Адресату: `ss_create;target=<инициатор>;` (S→C) → он отвечает `ss_upd;s_status=1` (agree,
с ack) или `2` (deny, без ack). Дальше зеркалирование `ss_upd` 3/4/5/6/7/8 второй стороне.

---

## 5. Итог и приоритеты

Из 53 команд: **10 реализовано** (`hello, login, logout, selPers, newPers, actPlayer,
lenter, getInfo, moveTo`[path, dx/dy]`, userMsg`), **10 заглушки** (`chWorld`[без `to=1`],
`rp_get_info, ss_get_si, ss_get, ss_get_s_si, ss_create, ss_upd, q_list, q_status, chkml`),
**33 нет**. Из 90 ответов сервер шлёт 36.

Что «нет», по приоритету. P0 — без этого нельзя даже пройти текущий цикл
«зашёл → купил → надел»; P1 — основной игровой цикл; P2 — глубина; P3 — косметика.

**P0**
1. Исправить подтверждения (§2.7): `ss_upd` close/deny/apply/break без `cmdAck`; убрать из
   `EXPECTS_ACK` `ah_search`, `updMark`; `bg_op` только op 0/2; `p_op` не для op 5;
   отказ `moveTo` — `breakMv` вместо `cmdAck`. Закрытие лавки уже сейчас ломает очередь.
2. `ss_get` с содержимым: 6 одежда + 2 руки + рюкзак по маске; `0` для пустых; для
   slot=16/24 — `0`-разделитель и содержимое сессии. Без этого инвентаря нет вообще.
3. `ss_get_di` → `ss_di_<класс>;obj;break;max_break_cur;size;ammo_count;cur_mode;…`.
   Первый же настоящий oid засорит окно 5, и лавка перестанет описывать товары.
4. `ss_upd` buy/sell в торговой сессии по-настоящему: создать oid, списать деньги, послать
   `ss_obj_status;obj;status=1` + `userInfo_Player` (деньги). Сейчас ack «успех» без предмета.
5. `ss_move` (drag&drop рюкзак↔слоты) — экипировка.
6. Реестр сессий и рассылка (§4.2): `lch newUser/lostUser`, `userMove` соседям,
   `userInfo_Player`/`ss_ack` по чужому id, `newUser/userLost/userMove` на карте с
   heartbeat 3 с. Без этого «MMO» — одиночная песочница.

**P1**
7. `ss_use` все семь битов + `faAim/faShot/faHit/faWall/faMiss/caHit/caMiss/heal/c_ap/usrUp`,
   `lch ws/enemy/dead` — бой и лечение; клиент считает ноль формул, весь урон с сервера.
8. `resurrect` + `lch;dead=0` — цикл смерти (после `dead` клиент в `DEAD_STATE` и ждёт
   только `cmdAck` на `resurrect`).
9. Лут: `ss_create s_type=0` по гексу, `ss_loot`, `ss_ack` slot=24 c разделителем, `ss_upd`
   1/2/3, `ss_heap_c` (стопки).
10. Квесты: `q_si_*`/`q_di_*`/`q_st`/`q_co`/`q_ca`/`q_sys` + непустые `give_quests` у NPC
    (окно 1: каждая ошибка вешает всю подсистему).
11. `ss_heap_c` вне лута (объединить/разделить стопки патронов) и `ss_use type=0` (выбросить).
12. `chWorld;to=1` — выход из интерьера в соседнюю локацию (граф `outzones` утрачен, нужна
    своя таблица).

**P2**
13. Банк (`ss_create 3`, `ss_upd` 1/2/6, `ss_upd` S→C 3/4), обучение (4), апгрейд (5),
    трофеи (6 + `ss_get` 16/32), бартер (2 + `ss_create` S→C).
14. Отряд `p_op`/`p_m`; кланы `head/admit/apply/gg_info` + `fellow/invite/gg_struct/gg_list/gg_code`.
15. Почта `getml/sndml/rmvml/uldml` + `rcml/ctml`, и починка декодера под повторные ключи (§1.1).
16. Аукцион `ah_search/ah_op/ah_create` + `ah_sresult/ah_lot`; поля боя `bg_op` + `bg_init/bg_op/bg_res`.
17. Эффекты `e_get_si/e_get_di` + `e_si/e_di/e_list` (нужны, как только у аптечек появятся
    `effects`); транспорт `ts_get_si` + `ts_si` + `on_conv op=2`.

**P3**
18. Метки карты `insMark/updMark/rmMark` + `marks` (индексы = порядок в `marks`).
19. `moveTo;trg` перехват; `on_conv` op 0/1 (прописка, лечение у медика); `c_ga`;
    `kickban`/`shutdown`; `prepare`.

Мелкое, но заметное сейчас: `cmd_userMsg` шлёт эхо `userMsg` отправителю, а клиент печатает
своё сообщение сам по `cmdAck res=0` (`Chat.delivery` → `newMessage` → тот же `refreshChannel`,
что и у входящего `userMsg`) — строка в чате дублируется. Эхо отправителю убрать, рассылать
только остальным; ответы `/goto`/`/where` от «Сервера» при этом остаются как есть.
