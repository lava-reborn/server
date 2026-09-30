# Предметы, инвентарь, торговля — анализ клиента

Разбор клиента LAVA Online по теме «предметы»: контейнеры, экипировка, торговля,
банк, ремонт, улучшение, аукцион, трофеи, сеты, деньги, вес. Все ссылки вида
`Файл.as:строки` относятся к `recon/as-src/lol/`, серверные — к `server/`.

Коротко о главном:

- Предмет на проводе — hex-строка `oid = <uniq><type_id:4 hex><root:2 hex>`
  (`ItemFactory.as:167-173`, `MDString.as:50-68`); в списках `|x<oid>|`, в
  командах `obj=x<oid>;`.
- Инвентарь приходит одним `ss_ack;o_list=|...|;` на `ss_get;target=;slot=<маска>;`,
  порядок в списке жёсткий: 6 слотов одежды, 2 руки, рюкзак; пустой слот = `x0`
  (`PersEquip.as:181-240`).
- На каждый новый тип клиент шлёт `ss_get_si`, на каждый экземпляр —
  `ss_get_di`; оба идут через одно окно в 5 запросов (`ItemFactory.as:30-64`).
  Сервер сейчас **не отвечает на `ss_get_di` вообще** — с шестого реального
  предмета конвейер встаёт.
- Все сделки (купить, продать, ремонт, банк, лут, бартер, апгрейд, трофеи) —
  одна команда `ss_upd;s_status=<код>;obj=x..;[param=..;]` внутри сессии,
  открытой `ss_create;s_type=<тип>;target=<id>;`. Коды `s_status` **зависят от
  типа сессии**, и часть из них **не ждёт `cmdAck`** (раздел 2.13) — текущий
  `cmd_ss_upd`, который всегда отвечает `cmdAck`, ломает очередь.
- Клиент после успешной сделки **не добавляет и не убирает предметы сам** (кроме
  перемещений внутри своих слотов): сервер обязан пушить
  `ss_obj_status;obj=x..;status=1|0;` и повторно слать `userInfo_Player` с
  новыми `afro`/`gold`.
- Вики повторяет игровой тултип построчно (названия строк = подписи из
  `Annotation.as`), так что перенос в схему `ss_si_*` механический; проблема
  только в связи русских названий с внутренними именами, и для массового
  оружия она **не решается по имени** (внутренние имена вида
  `pistols_1_lvl_18_mod_agility_pm`), решается по хешам иконок.

---

## 1. Модель инвентаря на клиенте

### 1.1. Идентификатор экземпляра

`Item.set id` (`Item.as:83-87`) хранит `oID` строкой. `ItemFactory.create`
(`ItemFactory.as:155-182`) разбирает её `MDString.parseBigUINT(oid,4,2)`:
последние 2 hex-символа — `rootID`, предыдущие 4 — `typeID`, остаток — уникальный
номер. По `rootID` выбирается класс (`ItemFactory.getClass:190-220`), по
`typeID` — прототип (`createPrototype:221-237`). Пример: uniq=42, type=4380
(0x111C), root=0 → `2a111c00`.

На проводе: в `ss_ack` список big-uint `o_list=|x2a111c00|x...|;` — парсер
режет первый символ `x` (`SCDataParser.as:186-198`); клиент отправляет
`obj=x2a111c00;` (`BigUINT.toString`, `BigUINT.as:59-74`). Ответы `ss_di_*`
несут `obj=x<oid>;` — `getBigUINTData` возвращает строку без `x`
(`SCDataParser.as:140-144`), и она совпадает с ключом `itemStore`.

Заглушка `0` (`x0` в списке) — «пустой слот»: `StuffManager.createItem`
(`StuffManager.as:61-70`) пропускает `oid == "0"` и строки короче 2 символов.

### 1.2. Корневые классы и что в них лежит

| root | класс (`ItemFactory.as:190-220`) | SI-кадр | DI-кадр | поля экземпляра (DI) |
|---|---|---|---|---|
| 0 | `FireArm` | `ss_si_firearm` | `ss_di_firearm` | `break`, `max_break_cur`, `ammo_count`, `ammo_type`, `cur_mode` |
| 1 | `Wear` | `ss_si_wear` | `ss_di_wear` | `break`, `max_break_cur` |
| 2 | `HealItem` | `ss_si_heal` | `ss_di_heal` | `use_count` |
| 3 | `Ammo` (Heapable) | `ss_si_ammo` | `ss_di_heap` | `size` |
| 4 | `Trash` (Heapable) | `ss_si_simple_obj` | `ss_di_heap` | `size` |
| 5 | `MeleeWeapon` | `ss_si_coldarm` | `ss_di_coldarm` | `break`, `max_break_cur` |
| 6 | `Trophy` | `ss_si_trophy` | `ss_di_trophy` | `count`, `k_id`, `k_name`, `k_lvl`, `v_id`, `v_name`, `v_lvl`, `v_clan`, `time` |

DI применяется как есть: `updateProperties` (`Item.as:271-287`) пишет каждый
ключ в `this[key]`, только `break` уходит в `__break`. Значит в DI можно
положить любое поле; обязательный минимум — из таблицы. У огнестрела `cur_mode`
обязателен: без него `getAP` берёт `fire_costs[undefined]` и в боевой локации
`canUse` вернёт `false` (`FireArm.as:182-199`, `ItemActivator.as:275-290`).

Трофейные поля `k_*`/`v_*` читаются в `Trophy.initialize` из SI
(`Trophy.as:21-33`), но типов трофеев всего 9 (`objects.xml`, root 6) — поэтому
индивидуальные данные убийства надо отдавать в `ss_di_trophy`, `getProp`
их найдёт (`Item.getProp:293-307`).

Общие SI-поля (`Item.initialize`, `Item.as:92-109`): `name` (числовой id строки),
`desc` (id или `@@`), `vis`, `weight` (граммы), `tech_dif`, `exchang`, `cost`
(афро), `g_cost` (золото в сотых унции), `bg_p_cost` (ПвП-баллы), `repair_mod`,
`sell_mod`, `premium` (0/1/2), `action_map` (битмаска действий), `quest`,
`need_pvp_rep`. Требования и бонусы — маска + плотный список
(`parseNeedBonus`, `Item.as:110-221`): `need_attribs_m`/`need_attribs` (5 бит),
`need_skills_m`/`need_skills` (5), `need_specs_m`/`need_specs` (15), те же для
`bonus_*`, плюс скаляры `bonus_hp`, `bonus_st`, `bonus_od`, `bonus_cp`, `bonus_ce`.

Классовые SI-поля:

- FireArm (`FireArm.as:51-76`): массивы по 3 режимам `h_damage_min/max`,
  `st_damage_min/max`, `max_range`, `opt_range`, `end_opt_range`, `target_size`,
  `fire_costs`, `fire_mods` (длина очереди, 0 = режим выключен), `fire_times`
  (мс), `piercing`; скаляры `reload_time`, `reload_cost`, `clip_size`,
  `max_break_abs`, `weapon_type` (0 пистолет, 1 дробовик, 2 автомат, 3 винтовка,
  4 пулемёт, 5 ПП), `comp_array` (список type_id патронов), `ammo_count`.
  Клиент делит: `accuracy = round(1000·target_size/max_range)/10`
  (`FireArm.as:77-88`).
- Wear (`Wear.as:44-56`): `armor_class`, `slot_type` (0 голова, 1 камуфляж/грудь,
  2 броня, 3 пояс, 4 ноги, 5 ступни — по `PersEquip.as:116-133` и
  `AuctionInterface.as:163-170`), `max_break_abs`, `set_type` (0 = без сета).
- Ammo (`Ammo.as:30-41`, `Heapable.as:16-20`): `max_count`, `range_mod`,
  `st_mod`, `dam_mod`, `acc_mod`, `piercing` (множители, 1 = без бонуса),
  `sell_num` — размер пачки: клиент делит `cost` и `g_cost` на него, то есть
  `cost` в SI — цена пачки.
- HealItem (`HealItem.as:33-55`): `heal_time`, `heal_cost` (ОД), `min/max_h_rest`,
  `min/max_st_rest`, `use_count` (→ `max_use_count`), `bonus_prob`,
  `bonus_act_time`, `can_rest_br`, `str/dex/sta/per/int_bonus`, `effects`
  (список type_id эффектов → отдельный конвейер `e_get_si`), `effects_prob`.
- MeleeWeapon (`MeleeWeapon.as:29-43`): скаляры `h_damage_min/max`,
  `st_damage_min/max`, `max_range`, `can_aimed`, `max_break_abs`, `strike_cost`,
  `strike_mod`, `strike_time`.
- Trash (`Trash.as:34-40`): `max_count`, `range_mod`, `st_mod`, `dam_mod`.

`action_map` (`Item.as:312-333`, `items.py:33-36`): бит 1 зарядить, 2
использовать на себя, 4 на цель, 8 на предмет, 16 стрельба, 32 разрядить, 64
смена режима. Двойной клик в рюкзаке работает только если `actions[1].enable`
(`PersEquip.onDoubleClick:701-731`).

### 1.3. Контейнеры и коды слотов

`PersEquip` (`PersEquip.as:98-142`): рюкзак `bag` (maskIndex 8), руки
`primary`/`secondary` (maskIndex 2, index 0/1), одежда `head, camouflage, armor,
belt, legs, boots` (maskIndex 1, index 0..5). Код слота в `ss_move`:
`maskIndex << 8 | index` (`PersEquip.requestTranfer:389-410`):

| слот | код | | слот | код |
|---|---|---|---|---|
| head | 256 | | boots | 261 |
| camouflage | 257 | | primary | 512 |
| armor | 258 | | secondary | 513 |
| belt | 259 | | bag | 2048 |
| legs | 260 | | | |

Рюкзак без ограничения по числу ячеек — только вес (раздел 4). Хранилище
банка, куча лута, бартерные списки, лоты — не слоты: адресуются кодами
`s_status` в `ss_upd`, а в `ss_get` — битом 16. Бит 32 — публичные трофеи.

### 1.4. `ss_get` / `ss_ack`

`ss_get;target=<id>;slot=<маска>;` (`CSM_SSGet.as`, `StuffManager.getStuff:18-25`).
`target` = 0 для себя (`Gamer.ID`), id игрока для чужой экипировки; при вызове
без цели свойство опускается (`CSMessage.toString:21-44` пропускает
`undefined`) — так делают торговля, бартер, банк, лут, апгрейд.

Кто и что запрашивает:

| кто | кадр | когда |
|---|---|---|
| `PersEquip.firstRequest:167-176` | `ss_get;target=0;slot=11;` | вход в локацию: одежда+руки+рюкзак |
| `Player` (чужой) `Player.as:14-17` | `ss_get;target=<id>;slot=3;` | появление игрока: одежда+руки для отрисовки |
| `Trade/Barter/Upgrade.requestSession` | `ss_get;slot=8;` | открытие окна: свой рюкзак заново |
| `Bank/Loot.requestSession` | `ss_get;slot=24;` | рюкзак + содержимое хранилища/кучи |
| `TrophyManager.requestTrophy:100-108` | `ss_get;target=0;slot=16;` | список зарегистрированных трофеев |
| `PersEquip.requestPublicTrophy:1344-1352` | `ss_get;target=<id>;slot=32;` | витрина трофеев |

Ответ `ss_ack;o_list=|x..|x..|;[set_res=<res>;]`. Маску клиент берёт **не из
кадра**, а из своей очереди (`XMLCCallStack.addCall(..., n)`,
`XMLCCallStack.as:14-25, 49-58`), поэтому порядок `ss_ack` строго FIFO по
порядку `ss_get`, отдельно от `cmdAck`. Разбор `PersEquip.ss_ack:181-240`:

1. бит 1 → `splice(0,6)` → шесть слотов одежды **ровно шесть элементов**, пустой
   = `x0`;
2. бит 2 → `splice(0,2)` → primary, secondary;
3. бит 8 → всё остальное → рюкзак;
4. биты 4 и 16 в `PersEquip` не обрабатываются (ветки пустые);
5. `set_res` — id ресурса внешности полного сета (раздел 5).

Для маски 24 (`Bank.ss_ack:42-74`, `Loot.ss_ack:62-103`): элементы до первого
`x0` — рюкзак, после — хранилище/куча. Лут с пустым хвостом даёт «На этом месте
нет предметов» и закрывает окно.

Особый случай витрины трофеев (`PersEquip.as:1344-1383`): регистрируются оба
обработчика — `ss_ack` и `cmdAck`, и первый пришедший снимает второй. Отвечать
надо **либо** `ss_ack`, **либо** `cmdAck` (отказ), никогда обоими.

Чужие предметы создаются с `notRequestDI=true` (`parseWear/parseAction`,
`PersEquip.as:241-271`) — DI на них не запрашивается, кроме публичных трофеев
(`createItem(oid,false,id)` → `ss_get_di;target=<id>;obj=x..;`).

### 1.5. Конвейер SI/DI

`ItemFactory` (`ItemFactory.as:30-64`): `ss_get_si;type=N;` и
`ss_get_di;obj=x<oid>;[target=<id>;]` делят одну очередь и один счётчик
`callCount` с окном `packageLength = 5`; освобождение только по приходу любого
`ss_si_*`/`ss_di_*`. Ответ на неизвестный тип обязателен. Запросы уходят только
в состоянии `Master.LOCAL_STATE` (`ItemFactory.as:42`) — на глобальной карте
копятся; сервер должен выдавать инвентарь после `lenter`.

Сеты — отдельная такая же очередь (`SetManager.as:16-50`, окно 5,
`ss_get_s_si;type=N;` → `ss_si_set`). Эффекты лечилок — третья
(`EffectsFactory`, `e_get_si`).

Предмет попадает в UI только после события `itemUpdate`, которое ждёт строки
имени из `texts.xml` (`Item.stringUpdate:229-245`, PROTOCOL.md §9).

### 1.6. Имена и `$`-суффиксы

Строка имени может нести суффикс после `$`:

- FireArm/Wear/Heal/Melee: `Name$SUB` → `name`, `sub_name`
  (`FireArm.as:126-138`); показывается второй строкой в контейнере
  (`ItemContainer.itemUpdate:540-560`).
- Ammo: `Name $KS` → `mod_type` = `KS`, имя обрезается на **один символ** до `$`
  (пробел) (`Ammo.as:42-51`). Коды: ББ, ЭК, СБ, ШК, ОТ, СТ, КС (`Ammo.as:18-24`);
  папки иконок `Ammo_9mmNato_KS` и т.п. им соответствуют.
- Trash: `Name$2F` → `sub_name` = «Обычная» по таблице `Trash.MOD_ARR`
  (`Trash.as:16-33`: 0..4 = Кустарное/Старое/Обычное/Заводское/Идеальное, суффикс
  M/F — род, `BP` = Чертёж).

### 1.7. Push-кадры сервера по предметам

Все подписки клиента на `ss_*` (grep по `addEventListener("ss_`):
`ss_ack` (динамически), `ss_si_{firearm,wear,heal,ammo,simple_obj,coldarm,trophy,set}`,
`ss_di_{firearm,wear,heal,heap,coldarm,trophy}`, `ss_obj_status`, `ss_obj_move`,
`ss_loot`, `ss_upd`, `ss_create`.

- `ss_obj_status;obj=x<oid>;status=1|0;` (`PersEquip.ss_obj_status:322-357`):
  1 = создать/положить в рюкзак (создаёт предмет, запросит SI/DI), 0 = убрать
  откуда угодно (рюкзак, руки, одежда). Если убран расходник из руки, клиент
  сам перекладывает такой же из рюкзака в руку (`ss_move`). Это единственный
  способ сообщить о новом предмете и о списании.
- `ss_obj_move;id=<игрок>;from=<код>;to=<код>;obj=x<oid>;`
  (`PlayerRegister.ss_obj_move:225-233`, `PersEquip.ss_obj_move:846-884`):
  экипировка чужого игрока; для `id` = свой игнорируется.
- `ss_loot;s_status=1|0;hex=|<клетка>|...|;` (`Location.ss_loot:501-530`): показать
  / убрать мешки лута на клетках.
- `ss_upd;s_status=..;obj=..;` от сервера: закрытие сессии (0) для всех
  менеджеров, вес банка (3/4), релей бартера, счётчик витрины трофеев (2).
- `ss_create;target=<id>;` от сервера: предложение бартера
  (`Gamer.ss_create:257-264`, `Barter.ss_create:198-210`).

---

## 2. Операции

### 2.1. Надеть / снять / переложить — `ss_move`

`ss_move;obj=x<oid>;to=<код>;from=<код>;` (`PersEquip.requestTranfer:389-410`).
Ответ `cmdAck;res=N;`. При `res=0` клиент сам переносит предмет; если целевой
слот занят — вытесненный уходит в `from` (обмен, `PersEquip.applyTransfer:411-433`).
При ошибке всё откатывается. Клиентские проверки до отправки
(`EquipInterface.sendTransferToServer:460-492`): премиум предмета выше своего →
отказ без запроса; несоответствие `need_*` — только предупреждение «будет
ломаться быстрее», отправка идёт. Проверять на сервере: `slot_type` одежды,
класс для рук (FireArm, MeleeWeapon, HealItem — лечилку в руку клиент кладёт
сам, `PersEquip.as:339-349`), вес. После успеха — `ss_obj_move` всем в локации
и пересчёт брони/бонусов (`rp_info`).

### 2.2. Разделить и объединить стопку — `ss_heap_c`

`StuffManager.as:154-191`, `CSM_SSHeap.as`:

- разделить: `ss_heap_c;num=<N>;obj=x<oid>;` — из `obj` выделить **новую
  стопку из N штук**, `obj` остаётся с `size−N`. Сценарии: ctrl-перетаскивание
  (`ItemContainer.startDragNDrop:172-183` → окно «Сколько отделить?»), выброс
  части (`EquipInterface.as:398-402, 601-608, 619-623`: после `separate` клиент
  выбрасывает **исходный** `obj`, то есть в нём остаётся то, что выбрано), банк
  и аукцион (`BankInterface.exchangeDropAck:486-501`). Ответ `cmdAck`; затем
  сервер обязан прислать `ss_obj_status;status=1;` для новой стопки и
  `ss_di_heap;obj=x<oid>;size=..;` для старой — клиент размер сам не меняет.
- объединить: `ss_heap_c;num=<N>;trg=x<oidB>;obj=x<oidA>;` — N штук из A в B,
  `N = min(A.size, B.max_count − B.size)` считает клиент. Ответ `cmdAck` (обработчик
  пустой); сервер пушит `ss_di_heap` для B и либо `ss_di_heap`, либо
  `ss_obj_status;status=0;` для A. В UI клиент возвращает A на место до ответа
  (`PersEquip.checkUse:434-458`), убрать её может только сервер.
  Лут после «взять всё» сам объединяет однотипные стопки серией `ss_heap_c`
  (`Loot.joinHeapStack:234-317`).

### 2.3. Использовать — `ss_use`

`ss_use;type=<acID>;obj=x<oid>;[target=x<..>;]` (`ItemActivator.useItem:171-205`).
`type` — бит из `action_map`:

| type | действие | `target` | клиент после `res=0` |
|---|---|---|---|
| 1 | зарядить (`loadObject:47-52`) | `x<oid патронов>` | ждёт `ss_di_firearm` (`ammo_count`, `ammo_type`) и `ss_di_heap`/`ss_obj_status 0` для патронов; списывает `reload_cost` ОД |
| 2 | на себя (лечилка) | нет | ждёт `usrUp`, `ss_di_heal;use_count=` или `ss_obj_status 0`; списывает `heal_cost` ОД |
| 4 | на цель | `x` + `<тип цели:1 hex><id:8 hex>` (`MDString.createBigUINT`, `Gamer.heal:265-291`) | то же |
| 16 | выстрел / удар | тот же формат; тип 1 = существо, 0 = клетка; для кулака `obj=x0` (`ItemActivator.strike:113-149`) | бой, не эта тема; ОД списывает по `faShot`/`caHit` |
| 32 | разрядить | нет | ждёт `ss_di_firearm` и новую стопку патронов через `ss_obj_status 1` |
| 64 | сменить режим | `x<номер режима hex>` | **сам** ставит `cur_mode` (`PersEquip.applyChangeFireMode:687-700`); клиент уже проверил `fire_mods[m] ≠ 0` |
| 0 | удалить (`deleteObject:25-46`) | нет | ждёт `ss_obj_status;status=0;` — иначе предмет остаётся в рюкзаке |

Кулдаун: до `cmdAck` или 3 с второй `ss_use` не уходит (`coolDownBlock`).
Автоперезарядка выбирает патроны из `comp_array`, предпочитая уже заряженный
тип (`PersEquip.reloadloadFireArm:509-578`), с проверкой премиума патронов.

### 2.4. Выбросить и подобрать — сессия лута (`s_type=0`)

- Выброс (`PersEquip.dropItem:740-763`): если лут-сессии нет →
  `ss_create;target=<клетка>;s_type=0;` (`Loot.createSession:24-32`, UI скрыт) →
  `cmdAck 0` → на каждый предмет `ss_upd;s_status=2;obj=x<oid>;` (UPD_TO_BUFFER)
  → `cmdAck`. Клиент сам убирает предмет из рюкзака. Сервер должен разослать
  `ss_loot;s_status=1;hex=|<клетка>|;`. Сессия висит до закрытия окна
  экипировки: `ss_upd;s_status=0;obj=x0;` (без `cmdAck`!).
- Подбор (`Gamer.gotoLoot:70-99` → `Loot.createSession(pos)` с UI): тот же
  `ss_create`, затем `ss_get;slot=24;`; взять один — `ss_upd;s_status=1;obj=x<oid>;`
  (UPD_TO_BAG), взять всё — `ss_upd;s_status=3;obj=x0;` (после `res=0` клиент
  переносит всё сам, `Loot.allTranferAck:200-233`); закрыть — `s_status=0`.
  Когда куча опустела — `ss_loot;s_status=0;hex=|..|;`.

### 2.5. Купить / продать — торговая сессия (`s_type=1`)

Открытие (`Gamer.proposeContact:207-215`): у NPC-торговца должно быть
`ally` истинно и хотя бы один из `can_trade/can_repair/can_trophy`
(`NPC.userInfo:26-56`); `ss_create;target=<npc>;s_type=1;` → `cmdAck 0` →
окно услуг (`NPCService.openService:51-133`: trade / repair / regTrophy) →
`ss_get;slot=8;`.

Прилавок — из `userInfo_Trader` (`Trader.as:19-28`): `type_list` (type_id по
порядку), `bg_objects`, `bg_obj_rep_req`, `pmod` (множитель покупки), `smod`
(продажи), `rmod` (ремонта). На каждый элемент клиент делает `TradeItem`
(`TradeItem.as`) с `tradeID` = индекс; размер стопки прилавка = `max_count`.

- Покупка (`Trade.buy:80-111`): `ss_upd;s_status=1;obj=x<индекс hex>;param=<кол-во>;`;
  `s_status=4` если у типа есть `g_cost` (за золото), `8` если `bg_p_cost`
  (ПвП-баллы). `param` = 1, для патронов — выбранное число (окно «Сколько штук
  купить?», максимум `max_count`). Цена на клиенте: `ceil(cost·n·pmod)`
  (`ExchangePan.countMoney:156-175`), для патронов `cost` уже поделен на
  `sell_num`. Перед отправкой клиент предупреждает о перегрузе
  (`TradeInterface.tryToSendTransferToServer:586-630`). После `res=0` клиент
  **ничего не добавляет** — нужен `ss_obj_status;status=1;` с новым oid (и
  `ss_di_*`) плюс `userInfo_Player` с деньгами. `res≠0` → «У вас недостаточно
  средств» (`TradeInterface.moveItemError:661-674`).
- Продажа (`Trade.sell:112-138`): `ss_upd;s_status=2;obj=x<oid>;param=<кол-во>;`.
  Клиент отказывает сам: `cost = 0`, `__break = 0` (полностью сломан), трофеи
  (`checkSellItem:637-655`); предметы с `g_cost` требуют ввести «ПРОДАТЬ».
  Цена: `floor(cost·smod·sell_mod·curQuality·n)` (`ItemContainer.showCost:391-475`,
  для лечилок ещё `·use_count/max_use_count`). После `res=0` клиент предмет
  **не убирает** (`Trade.applyTransfer:206-241` только шлёт событие `sell`) —
  нужен `ss_obj_status;status=0;` или `ss_di_heap` при частичной продаже.
- Закрытие: `ss_upd;s_status=0;obj=x0;` без `cmdAck`; сервер может закрыть
  сессию сам кадром `ss_upd;s_status=0;` (`Trade.ss_upd:286-295`).

Одна сессия может держать только одного контрагента: `gamer.trade` создаётся
заново на каждый контакт.

### 2.6. Ремонт (`Trader.can_repair`, та же сессия `s_type=1`)

Окно показывает `getBreakedItems` — всё, у чего `__break/max_break_cur < 1`
(`PersEquip.as:790-845`). Команды (`Trade.repairItem:157-171`, `restoreItem:172-184`):

- `ss_upd;s_status=3;obj=x<oid>;` — за афро;
- `ss_upd;s_status=5;obj=x<oid>;` — за золото;
- `ss_upd;s_status=7;obj=x<oid>;` — «восстановить» (возврат `max_break_cur` к
  `max_break_abs`, только у предметов с `g_cost`).

Цена на клиенте (`RepairInterface.repairCostCount:527-580`):
`афро = floor(cost·rmod·repair_mod·(1−curQuality))`, минимум 1;
`золото = floor(афро/gold_repair_mod·100)/100` унций, минимум 0.01;
восстановление = `round(g_cost·gold_repair_price_mod)/100` унций. После `res=0`
клиент только анимирует полоску — нужен `ss_di_*;obj=;break=;max_break_cur=;`
и `userInfo_Player`. Модель износа: `break` текущая прочность, `max_break_cur`
текущий максимум (снижается ремонтом), `max_break_abs` заводской
(`ItemContainer.showBreak:493-513`).

### 2.7. Трофеи

Регистрация у торговца с `can_trophy`: `ss_upd;s_status=6;obj=x<oid>;` за
`cost` афро (`Trade.regTrophy:189-201`, `RegTrophyInterface`). Личная витрина
(`TrophyManager.as`, окно `TrophyInterface` без NPC):
`ss_create;target=0;s_type=6;` → `cmdAck 0` → `ss_get;target=0;slot=16;` (все
трофеи) и `ss_get;target=0;slot=32;` (витрина: список длиной в число слотов, `x0`
= пусто). Операции: поставить/снять `ss_upd;s_status=1;obj=x<oid|0>;param=<слот>;`,
купить слот `ss_upd;s_status=3;` (без `obj`), удалить `ss_upd;s_status=4;obj=x<oid>;`,
закрыть `s_status=0`. Сервер может прислать `ss_upd;s_status=2;obj=<число>;` —
число слотов витрины (`TrophyManager.ss_upd:31-44`, парсится `Number("0"+obj)`).

### 2.8. Улучшение (`Upgrader`, `s_type=5`)

`userInfo_Upgrader` (`Upgrader.as:13-19`): три параллельных списка `in_types`,
`out_types`, `costs` (золото в сотых, отображается `cost·0.01 G`,
`UpgradeItem.as:19-20`). Клиент составляет прилавок из тех `out_types`, для
которых в рюкзаке есть `in_types[i]` (`Upgrader.createAllUpgradeItems:32-61`).
`ss_create;target=<npc>;s_type=5;` → `ss_get;slot=8;`. Улучшить:
`ss_upd;s_status=1;obj=x<oid>;param=<out type_id>;` (`Upgrade._upgradeItem:95-103`);
для патронов перед этим отделяется остаток `ss_heap_c;num=<size−n>;obj=..;`
(`Upgrade.upgradeItem:80-94`). После `res=0` — анимация; предметы меняет сервер
через `ss_obj_status` (0 старый, 1 новый) и `userInfo_Player`.

### 2.9. Банк (`Commoner.can_banking`, `s_type=3`)

`ss_create;target=<npc>;s_type=3;` → `ss_get;slot=24;`. Положить
`ss_upd;s_status=1;obj=x<oid>;`, взять `s_status=2`, расширить хранилище
`ss_upd;s_status=6;` (без `obj`, клиент требует `gold ≥ 1` сотую), закрыть
`s_status=0`. Клиент на `res=0` (`Bank.applyTransfer:188-224`): при «положить»
добавляет копию в список хранилища, но из рюкзака **не убирает**; при «взять»
убирает из хранилища, но в рюкзак **не кладёт**. Значит сервер шлёт
`ss_obj_status;status=0;` после PUT и `status=1` после GET. Вес хранилища:
`ss_upd;s_status=3;obj=x<hex граммы>;` (максимум) и `s_status=4` (занято) —
парсятся как `Number("0x"+obj)` (`Bank.ss_upd:270-291`), поэтому **только
hex через `x`**; UI делит на 1000 (`BankInterface.updWeight:203-208`). Это и
есть событие `updWeight` (PROTOCOL.md §8 прав). Перед «взять» клиент
предупреждает о перегрузе рюкзака.

Цена расширения зашита в само окно: `main.swf`, спрайт 723 (экспорт
`bankInterface`), DefineText 716 — «Вы можете увеличить размер хранилища на
50 кг за 1 унцию», то есть 100 сотых золота за 50 000 г. Базовой вместимости
нет ни в клиенте, ни в texts.xml, ни на вики; сервер берёт 50 кг
(`LAVA_BANK_BASE`). Реализация — `server/inventory.py` (строки `items` со
`slot=4096`, `bank_*`), банками считаются типы 5228, 2424, 729, 1170.

### 2.10. Бартер игрок–игрок (`s_type=2`)

`Barter.as`. Инициатор: `ss_create;target=<id игрока>;s_type=2;` (ждёт
`cmdAck`, `res≠0` → «Невозможно совершить бартер»). Сервер ретранслирует
второму `ss_create;target=<id инициатора>;`. Тот отвечает
`ss_upd;s_status=1;obj=x0;` (согласие, ждёт `cmdAck`) или `s_status=2` (отказ,
**без** `cmdAck`); сервер ретранслирует инициатору `ss_upd;s_status=1|2;`.
Оба шлют `ss_get;slot=8;`. Далее коды (`Barter.as:18-26`), каждый релеится
контрагенту тем же `ss_upd`: 3 положить в обмен (`obj=x<oid>`, ждёт ack; у
получателя → `addToVAVList` + свой `ss_get_di`), 4 вернуть, 5 готов, 6 не готов
(оба без ack), 7 добавить афро / 8 золото (`obj=x<hex сумма>`, ждёт ack; у
контрагента парсится `Number("0x"+obj)`), 0 закрыть (без ack). Любое изменение
сбрасывает готовность у обоих. Когда обе стороны готовы, клиент **сам**
переносит чужой список в рюкзак (`Barter.applyBarter:364-371`) — сервер обязан
провести обмен и подтвердить содержимое через `ss_obj_status`.

### 2.11. Аукцион (`Auctioner`, без `ss_create`)

`Auction.as`. Поиск:
`ah_search;target=<npc>;page=N;name=@..@;cat=<root|-1|101>;subcat=<n|-1>;min_lvl;max_lvl;min_a;max_a;min_g;max_g;sort=<0..4>;s_mode=<0|1>;`
— `cat=101` = «мои лоты» (`AuctionMyLotsInterface.getSearchObject:926-941`);
подкатегории (`AuctionInterface.changedCategory:141-213`): оружие →
`weapon_type` 0..5 и 6 «остальное»; одежда → слоты 0,1,2,4,5; лечилки 0 hp / 1 sp;
патроны 0..8 по калибрам (5.56x45, 7.62x25, 7.62x39, 7.62x51, 7.62x54R, 9mm,
0.45, 12 cal, остальное); разное 1 детали / 2 чертежи / 3 квестовые / 0 прочее.
`sort`: 0 имя, 1 количество, 2 время, 3 владелец, 4 цена; `s_mode` 0 убыв /
1 возр. Ответ: шапка `ah_sresult;page=N;count=N;next=<0|1>;` в **своей** очереди
(`XMLCCallStack "ah_sresult"`), затем `count` кадров
`ah_lot;obj=x<oid>;owner=@..@;a_bid=;a_buyout=;g_bid=;g_buyout=;time_left=<часы>;bidder=@..@;`
(`Auction.addLot:99-117`). Лот создаётся с `notRequestDI=true`
(`Lot.setItem`, `Lot.as:14-18`), поэтому размер стопки (`Lot.count` →
`getProp("size")`) сервер должен пушить сам: `ss_di_heap` вслед за `ah_lot`.
Клиент душит поиск чаще 1 с. Операции `ah_op;target=<npc>;type=T;obj=x<oid>;[amount=N;]`:
0 ставка (`amount` афро или золото×100), 1 выкуп, 2 снять, 3 продать текущему
покупателю. Ответ `cmdAck`: 0 ок, 40 лот не найден, 9 ставка мала / нет денег,
прочее «недостаточно денег». Создание:
`ah_create;target=<npc>;obj=x<oid>;time=<24|72|168>;a_bid;a_buyout;g_bid;g_buyout;`
(кнопки «12/24/48» шлют 24/72/168 часов, `AuctionMyLotsInterface.createLot:654-681`);
клиент требует `exchang=1`, `cost>0`, износ не хуже 15%; комиссия афро 5/7/9 %
от `cost·size`, золото 2/3/4 % не менее 0.5/0.75/1 G. После `res=0` предмет
должен исчезнуть из рюкзака (`ss_obj_status 0`).

Как это сделано на сервере (`server/auction.py`): порядок полей `ah_lot`
выше — порядок чтения в `addLot`, но сервер шлёт
`ah_lot;obj;a_bid;a_buyout;time_left;owner;bidder;` — только пару полей
валюты лота (у афро-лота `g_bid=0` отключил бы клиентскую проверку «ставка
≥ текущая + 10 %», `AuctionInterface.rateLot:385`) и строки последними
(`SCDataParser.parse` перешагивает строку по её длине). Вслед за каждым
`ah_lot` — ровно один `ss_di_*` по корню предмета (не только `ss_di_heap`:
износ и патроны в магазине тоже приходят только так).

### 2.12. Прочие сессии

- Обучение (`Teacher`, `s_type=4`): `ss_upd;s_status=2;obj=x<spec>;` учить, `1`
  забыть (`Training.as`), цены за афро/золото захардкожены на клиенте
  (`Training.getCost:71-127`).
- Аренда транспорта (`Lessor`): список `give_transport` → `ts_get_si;type=` →
  `ts_si` (`speed_mod, aggro_mod, g_cost, cost, res, premium, name, desc`,
  `TransObject.as:26-35`); аренда `on_conv;op=2;mob=<npc>;p1=<type>;p2=<дни>;` →
  `cmdAck`.
- Конвертация золота: `c_ga;gold=<сотые>;` → `cmdAck` (`BankAccount.as`), курс
  `constants.gold_to_afro_rate`.

### 2.13. Какие команды ждут `cmdAck` (обязательная таблица)

`ss_move`, `ss_use`, `ss_heap_c` (оба варианта), `ss_create` (любой `s_type`),
`ah_create`, `ah_op`, `c_ga` — **всегда**. `ss_get` ждёт `ss_ack`, не `cmdAck`.
`ss_upd` — по коду и сессии:

| сессия | ждут `cmdAck` | **не ждут** |
|---|---|---|
| лут (0) | 1, 2, 3 | 0 |
| торговля/ремонт/трофеи у NPC (1) | 1, 2, 3, 4, 5, 6, 7, 8 | 0 |
| бартер (2) | 1, 3, 4, 7, 8 | 0, 2, 5, 6 |
| банк (3) | 1, 2, 6 | 0 |
| обучение (4) | 1, 2 | 0 |
| апгрейд (5) | 1 | 0 |
| витрина трофеев (6) | 1, 3, 4 | 0 |

Источники: `Loot.as:49-55,149-199`, `Trade.as:296-307`, `Barter.as:179-185,233-239,314-329,301-313`,
`Bank.as:292-303`, `Training.as:128-140`, `Upgrade.as:194-206`, `TrophyManager.as:69-73`.
Сервер, отвечающий `cmdAck` на закрытие, сдвигает очередь — это текущее
поведение `server.py:607-608`.

### 2.14. Коды `res` (`ErrorReport.as:58-81`)

11 не хватает ОД, 12 объект не найден, 13 кончились патроны, 14 патроны не
подходят, 15 оружие уже заряжено, 16 предмет сломан, 17 объект не готов, 19 нет
подходящего предмета, 27 перегружен (клиент дополнительно вызывает
`checkBagOverload`), 45 не хватает навыков, 1002/1003 нужен вид на жительство /
гражданство. Аукцион: 9, 40. Прочие ненулевые коды показываются как общие
ошибки окон («недостаточно средств» и т.п.).

---

## 3. Деньги

- Поля `afro` (целое) и `gold` (целое, **сотые унции**: `MoneyPan.as:63-67`
  показывает `floor(gold/100).gold%100`) приходят только в `userInfo_Player`
  и только для себя (`Gamer.userInfo:54-63`). Других кадров обновления денег
  нет (`grep afro`): после покупки/продажи/ремонта сервер повторно шлёт полный
  `userInfo_Player;id=0;...;afro=;gold=;` — все поля, потому что
  `Entity.userInfo:49-87` переприсваивает имя, пол, ресурс, уровень, репутацию, а
  пустое имя заменяется на «Солдат СА» (`PlayerRegister.as:163-171`).
- Три валюты предмета в SI: `cost` (афро), `g_cost` (сотые золота),
  `bg_p_cost` (ПвП-баллы); при `g_cost ≠ 0` покупка идёт за золото
  (`Trade.buy:83-88`), при `bg_p_cost` — за баллы.
- Константы (`GConstatns.as:23-45`, `server.py:186-197`): `gold_to_afro_rate`
  (G1 = A·rate, `GoldToAfroInterface`), `gold_repair_mod` (афро→золото при
  ремонте, по умолчанию 10000), `gold_repair_price_mod` (восстановление),
  `premium_weight_bonus_1/2`, `premium_break_bonus_1/2`, `premium_xp_bonus_1/2`.
- Множители торговца `pmod/smod/rmod` и предмета `sell_mod/repair_mod`
  (раздел 2.5–2.6); бартер передаёт суммы hex через `obj`; аукцион и апгрейд —
  золото в сотых.

## 4. Вес

- `weight` в SI — граммы за штуку; для стопки `size·_weight`
  (`Heapable.weight`, `Heapable.as:21-27`); тултип «Вес 1 шт.» у патронов.
- Текущий вес считает клиент: рюкзак + 8 слотов (`WeightPan.count:55-126`).
  Максимум — `rp_info.max_weight` (граммы; сервер шлёт 50000,
  `server.py:586`) плюс премиум-бонус `round(max·b·0.001/(b+1))` — в **кг**,
  который затем складывается с граммами (`WeightPan.calcMaxWeight:127-161`) —
  ошибка клиента, бонус практически не виден.
- Перегруз решает сервер: `cmdAck;res=27;`; клиент лишь предупреждает перед
  покупкой и взятием из банка. `updWeight` — внутреннее событие банка, а не
  переносимый вес (раздел 2.9).

## 5. Сеты (`core/sets/`)

Одежда с `set_type ≠ 0` вызывает `SetManager.getSet` → `ss_get_s_si;type=N;`
(окно 5). Ответ `ss_si_set;type=N;res=<ресурс внешности>;name=<id строки>;desc=;`
плюс для K = 2..6 надетых частей: `bonus_K_attribs_m`/`bonus_K_attribs`,
`bonus_K_skills_m`/`bonus_K_skills`, `bonus_K_specs_m`/`bonus_K_specs`,
`bonus_K_hp`, `bonus_K_st`, `bonus_K_od`, `bonus_K_cp`, `bonus_K_ce`
(`SetObject.initSet:17-124`) — 55 полей. Полный сет клиент определяет сам по
пяти слотам head/armor/camouflage/legs/boots (пояс не участвует,
`PersEquip.getFullSetID:1110-1181`), сломанные части не считаются
(`getNumOfSetItem:1085-1109`), и подменяет внешность на `res`
(`checkFullSet:1187-1229`, настройка `SHOW_OWN_WEAR_SET`); для чужих игроков
внешность приходит в `ss_ack;set_res=`. Бонусы клиент только показывает —
применять их к характеристикам должен сервер в `rp_info`.

---

## 6. Что уже есть в `server/` и чего не хватает для «купить пистолет, надеть, зарядить»

Есть:

- `items.py`: каталог из `objects.xml` (`catalogue`), `STOCK` шести торговцев
  (только оружие и одежда, **патронов нет**), `static_info` для всех семи
  корней с придуманными числами и правильной формой (ненулевые делители,
  `sell_num`, `action_map`).
- `server.py`: `cmd_ss_get_si` (588-601), `cmd_ss_get_s_si` (610-613, пустой
  сет), `cmd_ss_get` (615-618, всегда `o_list=|;`), `cmd_ss_create` (603-605,
  всегда `res=0`), `cmd_ss_upd` (607-608, всегда `cmdAck 0`), `send_npc_info`
  с `type_list`, `pmod=smod=rmod=1`, `can_trade=can_repair=1` (520-560);
  `EXPECTS_ACK` отвечает `res=3` на `ss_move/ss_use/ss_heap_c/ah_*/c_ga`;
  `getInfo` отдаёт `afro=1000, gold=0` (506-518); `rp_info` — `max_weight=50000`.
- `names.py`/`bootstrap_http.py`: имена предметов как строки
  `STRING_ID_OFFSET + type_id`, режим `?all=1`.
- Тест `test_world.py:174-200`: прилавок, открытие сессии, описание одного типа.

Не хватает (по шагам сценария):

1. **`cmd_ss_get_di`** — отсутствует совсем; каждый реальный предмет запрашивает
   DI, окно ItemFactory забивается на пятом (раздел 1.5).
2. Хранилище экземпляров: генератор `uniq`, oid, контейнер/слот, `size`,
   `break/max_break_cur`, `ammo_count/ammo_type/cur_mode`, `use_count`;
   персистентность (в `lava.db` таблиц предметов нет).
3. `ss_get` с масками, заглушками `x0`, разделителем для бита 16.
4. Состояние сессии (тип, контрагент) и **политика `cmdAck` по `s_status`**
   (раздел 2.13) вместо безусловного ответа.
5. Покупка: `ss_upd 1/4/8` → проверка денег и веса → экземпляр →
   `ss_obj_status 1` → `userInfo_Player`.
6. `ss_move` с валидацией слота и семантикой обмена; `ss_obj_move` соседям.
7. `ss_use 1/32/64` для огнестрела: проверка `comp_array`, `clip_size`,
   совпадения `ammo_type`, списание стопки, `ss_di_firearm`.
8. Патроны в `STOCK`; `comp_array` сейчас ссылается на типы 1/8/9/23 — это
   записи `_9mmNato`, `_762x39`, `_12mm`, `_762x51` (заглушки калибров с
   подчёркиванием, без иконок), а реальные патроны — `Ammo_9mmNato_KS` (6092),
   `_ST` (6104), `_OT` (6116) и т.д. (`logs/items.txt`).
9. Деньги/вес персонажа в БД; `max_weight` от силы.

## 7. Данные: вики ↔ схема, связь имён

### 7.1. Структура статьи вики

Проверено на «9А-91» через `data/wiki_extract.py` (WSL, вывод в scratchpad):
таблица с колонками `I | II | III`, секции «Первый/Второй режим стрельбы» со
строками «Урон по здоровью» (диапазон), «Разброс на 100 метров», «Максимальная
дистанция», «Оптимальная» (диапазон), «Длина очереди», «Время на изготовку» (с),
«Очки действия»; общие строки «Необходимые навыки», «Крит. попадание»,
«Избег. крит. попадания», «Премиумность», «Емкость магазина/обоймы», «Износ»,
«Допустимость обмена», «Допустимость продажи», «Вес», «Базовая цена». Это
дословно подписи игрового тултипа (`Annotation.as:480-586, 583, 917, 1090-1097`)
— вики списана с клиента, поэтому соответствие полям однозначное.

Две проблемы парсера: (а) первая таблица статьи — рейтинг игроков, мусор;
(б) общие строки с жирным ключом принимаются за заголовки секций и теряют
значения (`wiki_extract.py:93-101`) — все «общие» поля пришли пустыми.
Обе сняты в переписанном `data/wiki_extract.py` (офлайн по `data/wiki/`):
мусорные таблицы отбрасываются по числу известных подписей (< 2), секция
определяется по подписи режима, а не по жирности; общие строки, стоящие
после последнего режима, возвращаются в общий блок.

Смысл колонок установлен по 12 статьям с римскими колонками (`КС-12`,
`СВД (R)`, `ПММ`, `ПКМ`, `АК-103`, `9А-91`, `ГШ-18`, `ТП-82`…): **I/II/III
(…VI) — ступени одной именной модели, каждая — отдельный type_id** с
растущим требованием «Стрельба N» (N, N+1, N+2 или уровни линейки: `КС-12`
I…V ↔ `lamantin_shotgun_4…8` со «Стрельба 4…8», `СВД (R)` I…V ↔
`lamantin_rifle_13,15,16,18,19`), уроном, износом и ценой. У наградных
(9А-91, ГШ-18, ТП-82) отличается только требование. Это не `_mod_`-варианты:
модификации живут на отдельных статьях «… Mod IX» (таблица номер ↔ суффикс
в `data/wiki_links.py:MOD_SUFFIX`). Колонки **(A)/(P)/(G)** — обычный
(афро), премиум (`_pm`/`_P`) и золотой (`_gold`/`_G`) экземпляры; у
патронов колонки КС/КС(Р)/СТ/ОТ/ОТ(PS)/ЭК/ББ/СБ/ШК ↔ суффиксы
`_KS/_KS_P/_ST/_OT/_OT_PS/_EK_G/_BB_G/_SB_G/_shock`.

### 7.2. Сопоставление строк вики и полей `ss_si_*`

| строка вики | поле SI | преобразование |
|---|---|---|
| Урон по здоровью (по режиму) | `h_damage_min[i]`, `h_damage_max[i]` | диапазон |
| Урон по выносливости | `st_damage_min/max[i]` | диапазон |
| Разброс на 100 метров | `target_size[i]` | `= разброс·max_range/100` (клиент: `accuracy = 100·target_size/max_range`) |
| Максимальная дистанция | `max_range[i]` | |
| Оптимальная | `opt_range[i]`, `end_opt_range[i]` | диапазон |
| Бронебойность | `piercing[i]` | |
| Длина очереди | `fire_mods[i]` | 0 = режим выключен |
| Время на изготовку | `fire_times[i]` | с × 1000 |
| Очки действия | `fire_costs[i]` / `strike_cost` / `heal_cost` | |
| Емкость магазина/обоймы | `clip_size` | |
| Перезарядка (если есть) | `reload_time`, `reload_cost` | |
| Износ | `max_break_abs` | |
| Вес | `weight` | в граммы |
| Базовая цена | `cost` (A) / `g_cost` (G × 100) | |
| Допустимость обмена / продажи | `exchang` / `cost = 0` → непродаваемый | |
| Премиумность | `premium` | 0/1/2 |
| Необходимые атрибуты/навыки/специализации | `need_*_m` + плотные списки | порядок атрибутов: сила, ловкость, телосложение, восприятие, интеллект; навыков: ближний бой, стрельба, медицина, промышленность, производство; 15 специализаций — `PersAttributes.as:96-110` |
| Здоровье / Выносливость / Очки действия / Крит. попадание / Избег. крит. | `bonus_hp/st/od/cp/ce` | |
| Подходящие типы патронов | `comp_array` | калибр → список type_id патронов этого калибра |
| Уровень брони | `armor_class` | одежда; слот — из категории статьи |
| Дальнобойность / Точность / Урон / Урон по выносливости / Бронебойность, % | `range_mod`, `acc_mod`, `dam_mod`, `st_mod`, `piercing` | `1 + p/100`, для точности **`1 − p/100`** (`Annotation.as:1032-1060`) |
| Количество (патроны) | `sell_num`, `max_count` | |
| Восстанавливаемое здоровье / стамина | `min/max_h_rest`, `min/max_st_rest` | |
| Плюсы (к силе…) | `str/dex/sta/per/int_bonus` | |

### 7.3. Связь русских названий с `objects.xml`

Факты (скрипты в scratchpad, `objects.xml`, `item_icons.xml`):

- 29 483 типа; после отсечения суффиксов `_pm`, `_gold`, `_mob`, `_mod_*`,
  `_lvl_N` остаётся 21 319 «семейств», но у огнестрела — 1 209 из 9 339, и
  двенадцать из них (`pistols_0..2`, `sub_machine_guns_0..2`, `rifle_1..2`,
  `shotgun_1..2`, `machine_gun_1..2`, `assault_rifle_1..2`) держат ~6 000 id:
  массовое оружие названо **обобщённо** (`pistols_1_lvl_18_mod_agility_pm`),
  модели в имени нет. По имени сопоставимы только «именные» стволы (`MG3`,
  `PPSH`, `Mauser_712_Mk2`, `AK_47_victory`, `crossbow`, `HM_MachGun_3`…).
- Одежда (15 778) почти вся с уникальными именами (`hermit_mask`,
  `Gorilla_Ribs_Armor`, `zayac_hat`) — сопоставлять по иконкам/вручную.
- Иконки: 18 561 папка `classes/<Класс>/<внутреннее имя>/ico.swf`, 18 560 имён
  совпадают с папкой один в один; уникальных хешей SWF 10 059 (FireArm 2 629,
  WearItem 4 738, Ammo 190, Heal 370, ColdArm 453, SimpleObject 1 779, Trophy 9).
  У вики 2 265 изображений. Хеш — готовый ключ «визуальное семейство».

Предлагаемый способ:

1. Таблица семейств: `type_id → (base, tier, lvl, mods, pm/gold/mob)` из
   разбора имени; статистика по каждому корню.
2. Именные модели: нормализация латиницы (убрать не-буквенно-цифровые,
   регистр) ↔ заголовки вики; закроет реальные стволы и часть одежды.
3. Проверить имена файлов картинок в вики (`[[Файл:...]]`): если они
   совпадают с внутренними именами или папками иконок — задача решается
   дёшево. В парсер добавить сбор имён файлов.
4. Иначе — растеризовать 10 059 уникальных `ico.swf` (JPEXS CLI/ruffle),
   perceptual hash против картинок вики, ручная верификация спорных.
5. Все id с одним хешем иконки получают статистику статьи; суффиксы
   (`_lvl_N`, `_mod_*`, `_pm`, `_gold`) — детерминированные поправки.
6. Свои id строк (`STRING_ID_OFFSET + type_id`) остаются: русское имя из вики
   идёт в `texts.xml`-заглушку, `sub_name` через `$`.

---

## 8. Задачи

Приоритет: P0 — блокирует «купить пистолет, надеть, зарядить»; P1 — базовая
экономика и инвентарь; P2 — остальные сессии; P3 — периферия. Размер: S до
полудня, M 1–2 дня, L больше.

| # | P | S | задача |
|---|---|---|---|
| 1 | P0 | S | `cmd_ss_get_di` → `ss_di_<root>` c обязательными полями (1.2); без него конвейер встаёт |
| 2 | P0 | S | политика `cmdAck` для `ss_upd`/`ss_create` по сессии и `s_status` (2.13); тест на `s_status=0` без ответа |
| 3 | P0 | M | хранилище экземпляров + генератор oid; `ss_get` с масками, `x0`-заглушками, разделителем бита 16; таблицы в `lava.db` |
| 4 | P0 | M | сессии NPC: состояние (тип, контрагент), закрытие, `ss_upd;s_status=0` от сервера |
| 5 | P0 | M | покупка `ss_upd 1/4/8` → деньги/вес → экземпляр → `ss_obj_status 1` + `ss_di_*` + `userInfo_Player` |
| 6 | P0 | M | `ss_move`: валидация `slot_type`/класса, обмен, `cmdAck`; трансляция `ss_obj_move` |
| 7 | P0 | M | `ss_use` 1/32/64: зарядка, разрядка, режим; списание стопки, `ss_di_firearm` |
| 8 | P0 | S | патроны в `STOCK`, `comp_array` на реальные type_id (не 1/8/9/23), `sell_num`/`max_count` согласованы |
| 9 | P1 | S | `ss_get;slot=3` и `ss_get_di;target=` для чужих игроков |
| 10 | P1 | M | продажа `ss_upd 2` с частичной стопкой; `ss_obj_status 0` / `ss_di_heap`; `smod·sell_mod·quality` |
| 11 | P1 | M | `ss_heap_c` разделение/объединение с пушами (2.2) |
| 12 | P1 | M | лут: `ss_create s_type=0`, кучи по клеткам, `ss_upd 1/2/3`, `ss_loot` всем |
| 13 | P1 | S | удаление `ss_use type=0` → `ss_obj_status 0` |
| 14 | P1 | M | ремонт 3/5/7 и модель износа (`break/max_break_cur/max_break_abs`), `gold_repair_mod` |
| 15 | P1 | M | лечилки: `ss_use 2/4`, `use_count`, `usrUp` (пересекается с боем) |
| 16 | P1 | M | банк `s_type=3`: хранилище, `ss_obj_status`, вес hex-пушами, расширение |
| 17 | P1 | S | вес: `max_weight` от характеристик, `res=27` |
| 18 | P1 | S | `wiki_extract.py`: пропуск мусорных таблиц, жирные строки со значениями, отсутствующие страницы, сбор `[[Файл:]]` |
| 19 | P1 | M | выгрузка категорий вики (Огнестрел, Холодное, Амуниция, Боеприпасы, БАФы…) в JSON; смысл колонок I/II/III |
| 20 | P1 | M | связь имён: таблица семейств, латинская нормализация, проверка имён картинок вики |
| 21 | P1 | S | `ss_si_set` с данными и `set_res` в `ss_ack` (после появления реальной одежды) |
| 22 | P2 | L | растеризация `ico.swf` и pHash-сопоставление с картинками вики |
| 23 | P2 | M | бартер `s_type=2`: релей `ss_create`/`ss_upd`, обмен, пуши обоим |
| 24 | P2 | M | апгрейд `s_type=5`: `in/out/costs` у NPC, `ss_upd 1` с `param`, замена предмета |
| 25 | P2 | M | трофеи: регистрация `ss_upd 6`, витрина `s_type=6`, DI трофея |
| 26 | P2 | L | аукцион: `ah_search`/`ah_sresult`/`ah_lot` (+`ss_di_heap` для лотов), `ah_op`, `ah_create`, таймеры, комиссии |
| 27 | P2 | S | `c_ga` конвертация по `gold_to_afro_rate` |
| 28 | P3 | M | транспорт: `ts_get_si`/`ts_si`, аренда `on_conv op=2` |
| 29 | P3 | S | ПвП-прилавок `bg_objects`/`bg_p_cost`, `ss_upd 8` |
| 30 | P3 | S | премиум-ограничения (`premium` предметов, `res` 1002/1003) |
