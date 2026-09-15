# Прогрессия персонажа: атрибуты, навыки, специализации, опыт, репутация, премиум, создание

Разбор клиента `recon/as-src/lol/` (AS2, декомпилят) плюс фанатская вики
`lava-online.fandom.com` (статьи «Игромеханика», «Атрибут», «Навык»,
«Специализация», «Таблица опыта», «Обучение специализаций», «Интерфейс» —
«Игромеханика» это, судя по ссылкам на GSDL и `PlayerTtaits`, перепечатка
внутреннего дизайн-документа разработчиков). Ссылки вида `файл:строка`
относятся к `recon/as-src/lol/`, если не сказано иное.

Главные выводы вперёд:

1. **Свободного распределения очков в игре нет.** Ни одной команды для этого
   в клиенте не существует. Атрибуты растут только через специализации
   (+1 за уровень спеца), телосложение — от максимального навыка. Навыки и
   специализации растут только опытом за действия. Единственный «выбор»
   игрока — какие специализации купить у учителя.
2. Клиент запрашивает `rp_get_info` **один раз за сессию**
   (`PersAttributes.firstLoad`, `core/player/PersAttributes.as:128-137`).
   Все дальнейшие изменения статов сервер обязан **пушить** свежим `rp_info`
   (можно частичным, по маске). Иначе карточка и сообщения «+N опыта» никогда
   не обновятся.
3. `usrUp` несёт **только** `hcur/hmax/scur/smax`. Ни опыта, ни уровня, ни
   денег в нём нет (`core/player/Entity.as:102-111`).
4. Деньги после любой покупки клиент узнаёт только из повторного
   `userInfo_Player;id=0;...afro=;gold=;` — единственный другой путь
   (`Gamer.setMoney`) вызывается лишь почтой (`core/mail/MailInspector.as:519`).
5. **Ошибка в текущем `server/server.py`:** `ss_upd` с `s_status=0`
   (закрытие сессии) шлётся **без** регистрации cmdAck всеми семью
   отправителями (Training, Trade, Bank, Barter, Loot, Upgrade,
   TrophyManager — см. §2.4), а `EXPECTS_ACK` включает `ss_upd` целиком.
   После закрытия любого окна NPC в FIFO лежит лишний `cmdAck`, и следующая
   команда получает чужой ответ. Ack нужен только для `s_status ≠ 0`.
6. Формулы карточки (`gpui/CharInterface.as`) **не совпадают** с формулами
   вики: коэффициенты крита у клиента в ~2–8 раз крупнее. Игрок видит
   клиентские цифры, поэтому серверный бой должен опираться на них (§5).

---

## 1. Модель персонажа глазами клиента

### 1.1 Атрибуты (5) — `core/player/PersAttributes.as:64-70`, `AttribObject.as`

Имена в коде не заданы (подписи `attribTitle0..4` живут в SWF-ресурсе),
восстановлены по описаниям `CharInterface.showAttribDesc`
(`gpui/CharInterface.as:813-837`) и формулам:

| idx | Атрибут      | Что даёт (по описанию клиента)                                   | Растёт от специализаций          |
|-----|--------------|-------------------------------------------------------------------|----------------------------------|
| 0   | Сила         | урон в рукопашной/холодным, переносимый вес, HP, крит дробовик/пулемёт | Рукопашный бой, Дробовики, Пулемёты |
| 1   | Ловкость     | уворот в ближнем, крит и антикрит (ближний, пистолет, ПП, автомат, винтовка), броня, выносливость | Режущее, Автоматы, ПП, Первая помощь (+Переработка по spec.xml) |
| 2   | Телосложение | HP, выносливость, регенерация                                     | «с максимально прокачанным навыком» |
| 3   | Восприятие   | броня, уворот в ближнем, крит из всего огнестрела, антикрит      | Пистолеты, Винтовки (+Добыча по spec.xml) |
| 4   | Интеллект    | урон из огнестрела                                                | Хирургия                          |

`AttribObject` (`core/player/AttribObject.as`): `value` — базовое (из
`a_attribs`), `value_bonus` — с бонусами экипировки/эффектов (из
`f_attribs`); `level` возвращает `value_bonus`; `bonus = value_bonus - value`.
Карточка показывает `value + bonus`, т.е. просто `f_attribs`
(`gpui/CharInterface.as:608-610`). Все формулы карточки используют `.level`,
т.е. значения **с бонусами**.

### 1.2 Навыки (5) — `PersAttributes.as:72-85`, `SkillObject.as`

| idx | Название (клиент)  | Видим в UI | Специализации (specMatrix) |
|-----|--------------------|------------|----------------------------|
| 0   | Ближнего боя       | да         | 0, 1                       |
| 1   | Стрельбы           | да         | 2..7                       |
| 2   | Медицины           | да         | 8, 9                       |
| 3   | Промышленность     | да         | 10, 11                     |
| 4   | Производство       | **нет**    | 12, 13, 14                 |

Карточка и окно учителя строят ровно 4 слайда (`while(_loc2_ < 4)`,
`gpui/CharInterface.as:639`, `gpui/TrainingInterface.as:159`); пятый слайд
карточки — «Навык бойца» (репутация, §1.5). Навык 4 и спецы 12–14
недостижимы через интерфейс — сервер может их не выдавать.

Поля `SkillObject`: `value` (из `a_skills`), `value_bonus` (из `f_skills`;
`level` = `value_bonus`), `xp_skills`, `xp_max_skills`;
`currentValue = round(xp*100/xp_max)` (`SkillObject.as:27-30`).
Ранг по уровню (`SkillObject.as:55-80`): 0–4 «Новичок», 5–9 «Ученик»,
10–14 «Любитель», 15–19 «Профи», 20+ «Гуру»; строка вида
`"12 ( Любитель ), 350 из 409600 ( 0% )"`.

События (важно для сообщений на экране):
- сеттер `value_bonus` шлёт `INCREASE_LEVEL`, если значение изменилось,
  старое определено и `(старое != 0 || новое - старое < 2)`
  (`SkillObject.as:15-22`). Прыжок с 0 сразу на 2+ сообщения не даёт.
- сеттер `xp_skills` шлёт `INCREASE_SKILL` с дельтой только при росте и
  когда старое значение определено (`SkillObject.as:32-41`) — первый
  `rp_info` тихий, сброс xp после level-up тоже тихий.

### 1.3 Специализации (15) — `PersAttributes.as:87-125`, `SpecObject.as`

`specMatrix = [0,0,1,1,1,1,1,1,2,2,3,3,4,4,4]` (`PersAttributes.as:62`) —
спец → навык.

| idx | Название (клиент)   | Навык | min_skill_level (клиент, `PersAttributes.as:111-125`) | Вики «Обучение специализаций» | Атрибут (spec.xml/вики) |
|-----|---------------------|-------|-----|------|-------------|
| 0   | Рукопашный бой      | 0     | 0   | 0    | Сила        |
| 1   | Режущее оружие      | 0     | 0   | 0    | Ловкость    |
| 2   | Пистолеты           | 1     | 0   | 0    | Восприятие  |
| 3   | Дробовики           | 1     | 4   | 4    | Сила        |
| 4   | Автоматы            | 1     | 12  | 12   | Ловкость    |
| 5   | Винтовки            | 1     | 6   | —    | Восприятие  |
| 6   | Ручные пулеметы     | 1     | 16  | 16   | Сила        |
| 7   | Пистолет-пулеметы   | 1     | 8   | 8    | Ловкость    |
| 8   | Хирургия            | 2     | 0   | 0    | Интеллект   |
| 9   | Первая помощь       | 2     | 0   | 0    | Ловкость    |
| 10  | Добыча              | 3     | 0   | 0    | Восприятие  |
| 11  | Переработка         | 3     | 0   | 20   | Ловкость    |
| 12  | Мастер свинца       | 4     | 0   | —    | — (spec.xml: взрывчатка) |
| 13  | Мастер селитры      | 4     | 0   | —    | — (spec.xml: миномёт)    |
| 14  | Мастер меди         | 4     | 0   | —    | — (spec.xml: отмычки)    |

**Таблица `min_skill_level` в клиенте нигде не проверяется.** Окно учителя
берёт `minSkill` из `res/xmldocs/spec.xml` (`gpui/TrainingInterface.as:274-303`),
а там у всех 15 записей `minSkill='0'`. Требование навыка — обязанность
сервера. Атрибут `prise` в spec.xml клиент не читает.

`SpecObject`: `value` (из `a_specs`; **< 0 = не изучена**, `available =
value >= 0`), `value_bonus` (из `f_specs`; `level` = `value_bonus` если
изучена, иначе `value`, т.е. **−1**), `xp_specs`, `xp_max_specs`;
`currentValue` = `undefined` для неизученной (`SpecObject.as:23-32,59-74`).
Квирк: неизученная спец даёт `level = -1`, и формулы карточки (§5) честно
вычитают единицу.

### 1.4 HP / выносливость / ОД / вес / уровень / деньги

`PersAttributes` хранит из `rp_info`: `hp, hp_max, sp, sp_max, ap_max,
max_weight (граммы), armor, lvl, max_specs` (`PersAttributes.as:138-190`).
Условия `if(obj.param.hp)` и т.п. — **ноль игнорируется**, а `armor`
присваивается безусловно. Порядок присваивания `hp` → `hp_max`, при этом
сеттер `health` режет по **старому** `maxHealth` (`PersAttributes.as:248-259`):
при level-up с ростом hp_max текущее hp в `rp_info` обрежется. Вывод: HP/SP
слать через `usrUp` (там сначала `hmax`, потом `hcur`,
`core/player/Entity.as:106-109`), а в `rp_info` `hp/hp_max` опускать.

- `usrUp;id=<id>;hcur=;hmax=;scur=;smax=;` — `Master.usrUp` /
  `PlayerRegister.usrUp` маршрутизируют по `id` (`core/Master.as:132-137`,
  `core/player/PlayerRegister.as:147-151`); `hmax/smax` необязательны.
- Уровень: `attributes.level` берётся из `userInfo*` `lvl`
  (`core/player/Entity.as:61`, сеттер принимает 0) и из `rp_info` `lvl`
  (0 игнорируется). `PersAttributes.getLevel()` = максимум уровней навыков
  (`PersAttributes.as:232-243`) — совпадает с определением вики
  («уровня как такового нет, уровень = максимальный навык»). Отображение:
  `[lvl] Имя` в чате/над головой/на карте (`core/location/CharInfo.as:190-193`,
  `core/globmap/DisplayMapObject.as:123`, `services/ChatPan.as:1289`),
  «Уровень N» в экипировке (`gpui/OutfitInterface.as:67`), число под
  аватаром (`gpui/UserAvatarPan.as:31`). `level == 0` подсвечивает кнопку
  квестов новичку (`gpui/QuestInterface.as:65`).
- `PersAttributes.compareLevels(a,b)` = clamp(a−b, −4..4)
  (`PersAttributes.as:335-376`) → кадр `mobLevel_mc` над мобом
  (`core/location/CharInfo.as:294-307`). Та же нормализация ±4 у вики в
  формуле опыта (§2.1).
- ОД: из `lenter;pos=;aspd=;amax=;` — `APManager.setAP(aspd, amax)`
  (`core/Master.as:272-279`): +`aspd` каждые 600 мс (`APManager.as:11,46-58`),
  шаг −1 ОД (`moveAP = 1`), `c_ap;ap=N;` — принудительная синхронизация
  (`APManager.as:17-22`). `ap_max` из `rp_info` нужен только карточке (§5 OD),
  причём карточка сама добавляет `bonus_od` предметов/сетов/эффектов — в
  `rp_info.ap_max` их включать **нельзя** (задвоится).
- Вес: `max_weight` в граммах, панель делит на 1000
  (`gpui/WeightPan.as:130-152`); значение **уже включает** премиум-бонус (§1.6).
- Деньги: `afro`, `gold` только из `userInfo_Player`
  (`core/player/Gamer.as:54-63`), клампятся ≥ 0. Обновление — повторный
  `userInfo_Player` (см. вывод 4 вверху). Курс: вики «1 голд = 40000 афро»,
  сервер сейчас шлёт `gold_to_afro_rate=100`.
- Смерть: `persInfo.death`, `lch;dead=<id>;` → окно воскрешения
  (`core/player/Resurrector.as:46-58`); `resurrect;res_type=` 0 бесплатно,
  1 за 5 голда, 2 за 500 афро (`gpui/RegenerationInterface.as:13-18,72-107`).

### 1.5 Репутация — `core/player/Reputation/*`

- Фракция **одна**: `factionMaxCount = 1`, титул «Навык бойца»
  (`PersReputations.as:7,17`). `userInfo_Player` несёт `rep=|N|` (список,
  читается индекс 0), `bg_rep`, `bg_pen` (`Entity.as:62-64`); последние два
  показываются в окне арены как «Репутация за арену» / «Штрафы за арену»
  (`gpui/BattleGroundInterface.as:35-36`).
- Ранги (`ReputationObject.as:16-24`): [0,100) Странник, [100,200)
  Следопыт, [200,400) Охотник, [400,800) Преследователь, [800,1600)
  Налетчик, [1600,3200) Стрелок, [3200,6400) Пустынный рейнджер,
  [6400,12800) Мститель, [12800,25600) Ассасин. При `rep ≥ 25600` ни один
  диапазон не совпадает и `repString` даёт мусор — сервер должен капать
  25599. Индекс ранга = кадр «черепа» рядом с уровнем
  (`core/location/CharInfo.as:314-326`).
- События роста (`ReputationObject.as:26-33,43-61`) → сообщения «Навык
  бойца повышен на N / до уровня N» (`services/SpecSkillMessages.as:326-362`).
- Предметы: `need_pvp_rep` показывается как «Необходимый навык бойца»
  (`gpui/Annotation.as:408,640,702,1001,1033`) и **не проверяется**
  клиентом; торговец арены — `bg_objects` + `bg_obj_rep_req`
  (`core/player/Trader.as:23-24`), цена `bg_p_cost` предмета.

### 1.6 Премиум — «вид на жительство» (1) и «гражданство» (2)

- `userInfo_Player` `pr` = 0/1/2 (`core/player/Player.as:28`); звезда над
  персонажем (`core/location/CharInfo.as:75-77`).
- `constants`: `premium_weight_bonus_{1,2}`, `premium_break_bonus_{1,2}`,
  `premium_xp_bonus_{1,2}`, `daily_max`, `daily_reset_time` (минуты от
  полуночи, `core/quests/QuestInspector.as:364-376`), `gold_to_afro_rate`,
  `quest_log_capacity`, `leave_combat_timeout`, `gold_repair_price_mod`,
  `gold_repair_mod` (`core/GConstatns.as:23-45`).
- Опыт: клиент получает **итоговую** дельту `v` и раскладывает её как
  `бонус = round(v·b/(1+b))`, `база = v − бонус` (`SpecSkillMessages.as:173-203`).
  То есть сервер должен считать `v = база·(1+b)`; `b` — доля (0.25 = +25%).
  Текущие серверные 1 и 2 означают +100%/+200%.
- Вес: та же раскладка `bonus_kg = round(max_weight·b·0.001/(1+b))`
  (`gpui/WeightPan.as:130-152`) → `max_weight` в `rp_info` = база·(1+b).
- Предметы с `premium` > `gamer.premium` нельзя надеть/зарядить, коды
  ошибок 1002/1003 (`gpui/EquipInterface.as:258-275`,
  `core/player/PersEquip.as:456-465`, `gpui/TransRentInterface.as:294`).
- `premium_break_bonus` клиентом не используется (только хранится) —
  серверная скидка на износ.

### 1.7 Кодирование «маска + плотный список» — `PersAttributes.updateParam` (`:191-208`)

```
for i in 0..N-1:            # N = 5 (attribs/skills) или 15 (specs)
    if (mask >> i) & 1:
        obj[i][param] = list[k]; k += 1
```
Список содержит значения **только** для выставленных бит, по возрастанию
индекса. Пары в `rp_info` (`PersAttributes.as:142-151`):

| Маска              | Список          | Куда                         |
|--------------------|-----------------|------------------------------|
| `a_attribs_mask`   | `a_attribs`     | attrib.value (база)          |
| `f_attribs_mask`   | `f_attribs`     | attrib.value_bonus (с бонусами) |
| `a_skills_mask`    | `a_skills`      | skill.value                  |
| `f_skills_mask`    | `f_skills`      | skill.value_bonus (= level)  |
| `xp_skills_mask`   | `xp_skills`     | skill.xp_skills              |
| `xp_max_skills_mask` | `xp_max_skills` | skill.xp_max_skills        |
| `a_specs_mask`     | `a_specs`       | spec.value (−1 = не изучена) |
| `f_specs_mask`     | `f_specs`       | spec.value_bonus (= level)   |
| `xp_specs_mask`    | `xp_specs`      | spec.xp_specs                |
| `xp_max_specs_mask` | `xp_max_specs` | spec.xp_max_specs            |

Плюс скаляры `max_specs, hp, hp_max, sp, sp_max, ap_max, max_weight, armor,
lvl`. Частичный пуш легален: `rp_info;xp_skills_mask=2;xp_skills=|150|;`
обновит только опыт стрельбы. Полный кадр — см. `server/server.py:571-586`.
Та же схема у предметов (`need_attribs_m/need_skills_m/need_specs_m`,
`bonus_*_m`, `core/objects/Item.as:110-215`) и эффектов
(`attribs_mask/skills_mask/specs_mask`, `core/effects/Effect.as:262-310`).

---

## 2. Как растут

### 2.1 Опыт, пороги, производные (вики «Игромеханика» + клиент)

Клиент ничего не считает: он лишь показывает дельты из очередного `rp_info`
(«Стрельба: +N опыта», «Навык Стрельба повышен до N», «Специализация X
повышена до N», при премиуме — «Бонус от гражданства: +M опыта»;
`services/SpecSkillMessages.as`). В боевой локации (`ws=1`) сообщения
копятся и выдаются при выходе из боя (`changeWarState`, `:54-134`).

Правила оригинала (вики, с пометкой «GSDL» — серверный конфиг):

- Навык: целое 0..20, старт 0, `xp_max` старт 100, при переполнении
  уровень+1 и `xp_max *= 2` (0→100, 1→200, …, 19→52 428 800, 20→104 857 600).
- Специализация: 0..5, старт −1 (выключена), после покупки 0; `xp_max` =
  `1250·8^уровень` (1250, 10 000, 80 000, 640 000, 5 120 000, 40 960 000).
- За урон по мобу: `k = clamp(lvl_моба − lvl_игрока, −4, 4) + 4`;
  `xp = floor(k · урон)` «пропорционально пулу моба»; половина в навык,
  половина в соответствующую спец; остаток при повышении переносится.
- За лечение: `MO = min(2, hp_max пациента / heal_max предмета)`;
  `xp = floor(вылечено · MO)`, так же пополам навык/спец.
- Атрибут: +1 за каждый уровень спеца (вики §Атрибуты п.5); ограничение
  «атрибут без шмота ≤ 20 и ≤ уровня игрока» (вики §Специализации п.4).
  При сбросе спеца атрибут уменьшается на её уровень.
- Телосложение = `floor(5 + 0.75·maxSkill)`.
- HP = `4·Сила + 20·Телосложение`, SP = `4·Ловкость + 20·Телосложение`
  (сходится с «Таблицей опыта»: старт 120/120 при силе 5, тело 5; навык 20 →
  тело 20 → 420).
- ОД max = `50 + 5·maxSkill`; вес = `30 + 2·Сила` кг; регенерация: +тело HP
  в минуту (или +1 при HP < 30%), каждое HP стоит 1 SP, SP +1 в минуту.
- Базовая броня по вики `(Ловк·3 + Воспр)/2`, по клиенту `/4` (§5) — верить
  клиенту.
- Уровень мобов: в `res/database/mobs.xml` 881 записей с суффиксом `_lvlN`
  в `name` (диапазон 0..33) — готовый источник `lvl` для `userInfo` моба и
  множителя опыта.
- Эффекты (бафы) несут множители `mob_exp/pl_exp/mob_drop/pl_drop`
  (`core/effects/Effect.as:62-79`; подписи «Бонус к опыту с мобов» в
  `gpui/Annotation.as`) — серверные множители опыта.
- Квесты-тренировки (вики, категория «Повышение опыта»): «Навык стрельбы
  1..5» дают 100 000 … 1 600 000 опыта навыку за 20…800 G, «Специализация
  X 1..5» — опыт спецу («требуется открытая специализация»), «экзамены» на
  военной базе Вади-Хальфы — +20 000 навыку и спецу за 25 000 афро при
  наличии самоучителя. Примечание вики: накопленный опыт «реализуется в
  уровень» только при следующем боевом получении хотя бы 1 опыта — т.е.
  проверка level-up у оригинала происходила в момент начисления, не при
  выдаче квестовой награды.

### 2.2 Распределение очков

Отсутствует как механика. Карточка (`gpui/CharInterface.as`) — только
просмотр: слайды навыков, список спецов с «xp из xp_max», подсказки.
Единственная точка выбора — обучение спецов (§2.3).

### 2.3 Обучение у учителя (SpecTrainer) — `core/player/Training.as`, `gpui/TrainingInterface.as`

NPC с `root_type_id=2` (`Entity.TEACHER`, `userInfo_SpecTrainer`,
`server/world.py:32-41`); в `mobs.xml` 16 таких типов (`Simple_SpecTrainer`
type_id 4, `Npc_SpecTrainer000001` 5204 и т.д.). У NPC должен быть
`ally` truthy (`core/player/Gamer.as:222`).

1. Подход вплотную/соседний гекс → клиент → `ss_create;target=<npc>;s_type=4;`
   (`StuffManager.SESSION_TRAINING = 4`, `Training.as:18-29`), ждёт cmdAck:
   `res=0` → открывает окно `spec` (`NPCService.openService`,
   `TrainingInterface`); иначе алерт «Невозможно начать обучение у <res>».
2. Окно вызывает `requestAttributes()` — но `firstLoad` уже стоит, повторного
   `rp_get_info` не будет. Показывает 4 слайда навыков со всеми их спецами
   (`TrainingInterface.as:153-227`); по клику — описание из spec.xml,
   строка «Требует навык "X" не ниже minSkill» (всегда 0), «Изучено на N»
   для купленных, цена (`price_mc` кадр 1 = афро, 2 = голд).
3. **Купить**: `ss_upd;obj=x<hex id>;s_status=2;` (`UPD_LEARN = 2`,
   `Training.as:52-58`; `obj` = BigUINT → `"x" + id.toString(16)` без
   дополнения, спец 10 → `obj=xa`; `param` не передаётся — `CSMessage.toString`
   пропускает undefined, `server/mess/CSMessage.as:30`). Регистрирует cmdAck,
   обработчик пустой (`trainingAck`). Сервер после успеха обязан:
   `cmdAck;res=0;` → `rp_info` (минимум `a_specs/f_specs/xp_specs/xp_max_specs`
   по маске спеца, `a_attribs/f_attribs` если атрибут вырос, `max_specs`) →
   `userInfo_Player` с новыми `afro/gold`. При отказе `cmdAck;res=N;` — окно
   ничего не покажет, стоит продублировать чат-сообщением.
4. **Сбросить**: подтверждение «Сбросить специализацию?» →
   `ss_upd;obj=x<hex id>;s_status=1;` (`UPD_FORGET = 1`, `Training.as:60-66`,
   `TrainingInterface.as:90-109`), ack + `rp_info` (спец −1, xp 0, xp_max 1250,
   атрибут −уровень, счётчик −1).
5. **Закрыть**: `ss_upd;obj=x0;s_status=0;` (`UPD_CLOSE = 0`,
   `Training.as:128-140`) — **без cmdAck-обработчика**. То же у
   `Trade.as:295-307`, `Bank.as:291-303`, `Barter.as:301-313`, `Loot.as:49-54`,
   `Upgrade.as:194-206`, `TrophyManager.as:69-73`. `XMLConnection.Send` сам
   ничего не регистрирует (`server/XMLConnection.as:107-127`). Сервер **не
   должен** отвечать на закрытие. Серверный `ss_upd;s_status=0;` принудительно
   закрывает Trade/Bank/Barter/Upgrade/Trophy, но Training его не слушает.
6. Стоимость (`Training.getCost`, `Training.as:71-127`): считает изученные
   спецы `n`; если `n < max_specs` — бесплатно; иначе по `n`: 0 → 0 афро,
   1 → 1000 афро, 2 → 10 G, 3 → 30 G, 4 → 55 G, ≥5 → 75 G. Вики «Обучение
   специализаций»: 0/1000 A/10 G/30 G/45 G/75 G; старая «Игромеханика»:
   0/1000 A/10 G/50 G/100 G/200 G. `max_specs` = число бесплатных слотов;
   по вики первая бесплатна → `max_specs=1` (сервер сейчас шлёт 3).
   Клиент денег **не проверяет**.
7. Требование навыка сервер проверяет сам по таблице §1.3 (клиент видит
   нули из spec.xml). Вики добавляет «специализации берутся с 4-го уровня»
   (старое правило, в клиенте следов нет).

### 2.4 Прочие команды из ТЗ

- `head;reg=;soc=;` — клановая (CSM_C_Head), не смена портрета. Смена
  портрета/скина в протоколе отсутствует: `res` фиксируется при создании,
  кнопка «скины» открывает URL профиля (`gpui/EquipInterface.as:938-942`).
- `p_op;op=;id=;` — операции отряда (`core/party/PartyManager.as`).
- `getInfo;lvl=0;id=;type=;` — `lvl` всегда 0 (`CSM_P_GetInfo`, вызовы в
  `Player.as:22`, `Entity.as:46`), к уровню персонажа отношения не имеет.

---

## 3. Влияние на бой, вес, торговлю

- **Бой**: клиент бой не считает (ROADMAP §1); сервер должен выдавать
  `faHit;dmg=;sdmg=;crit=;` так, чтобы частоты сходились с цифрами карточки
  (§5). Правила урона/брони по вики: некрит — `компенсация = max(0,
  класс_брони − Armor_LochProbe патрона)` уходит в выносливость, остаток в HP;
  крит игнорирует броню; крит возможен только на оптимальной дистанции;
  разброс `МР = (1 + (0.7 − 0.65/20·Стрельба) + (0.8 − 0.75/5·Спец)) ·
  TargetSize · Precision_Mod`.
- **Требования предметов** `need_attribs/need_skills/need_specs` (маска +
  список): клиент лишь предупреждает «Не выполняются условия: … Поэтому этот
  предмет будет ломаться быстрее. Применить?» и **пропускает** экипировку
  (`gpui/EquipInterface.as:483-528,882-936`); фильтр рюкзака №9 прячет
  недоступные (`gpui/BagInterface.as:660-740`). Ошибка 45 «У вас не хватает
  навыков для использования этого предмета» (`utils/ErrorReport.as:78`) —
  ответ сервера на `ss_use`. Итог: сервер решает — ускоренный износ при
  экипировке и/или отказ при использовании.
- **Бонусы предметов** `bonus_attribs/skills/specs` (маска+список),
  `bonus_hp/bonus_st/bonus_od/bonus_cp/bonus_ce` (`Item.as:206-210`);
  комплекты `bonus_<n>_od/_cp/_ce` за n=2..6 надетых
  (`CharInterface.getBonusFromSet`, `:396-417`). `f_*` в `rp_info` = `a_*` +
  бонусы предметов + бонусы эффектов; `bonus_cp/ce/od` карточка добавляет
  сама — в `rp_info` их не включать.
- **Эффекты**: `armor, max_hp, max_sp, max_od, critical_probability,
  critical_evade, bonusAttribs/Skills/Specs, mob_exp, pl_exp, mob_drop,
  pl_drop, immobilize, stun` (`core/effects/Effect.as:50-108`).
- **Вес**: `max_weight` (граммы, с премиумом), перегруз — ошибка 27.
- **`tech_dif`**: приходит в статике предмета и хранится (`Item.as:98,406-413`),
  **нигде не отображается и не используется** клиентом — серверная
  «техническая сложность» (вероятно, для апгрейда/ремонта). Можно
  игнорировать до этапа апгрейда.
- **Торговец** `pmod/smod/rmod` (`userInfo_Trader`, `core/player/Trader.as:25-27`):
  `pmod` — множитель цены покупки у NPC (`gpui/TradeInterface.as:119,342`),
  `smod` — множитель при продаже NPC (`:116,328`), `rmod` — ремонт
  (`gpui/RepairInterface.as:117`). Это свойства NPC, от прогрессии игрока не
  зависят; клиент лишь показывает цену, сервер обязан умножать сам.
- **`need_pvp_rep`** и `bg_obj_rep_req` — только серверная проверка (§1.5).
- **Уровень как гейт**: квест `level` (`core/quests/Quest.as:47`) сравнивается
  с уровнями навыков — требование выполнено, если **любой** навык ≥ level
  (`gpui/QuestInfoInterface.as:121-134`); аукцион фильтрует `min_lvl/max_lvl`.

---

## 4. Создание персонажа

Последовательность (`core/player/PersGenerator.as`, `gpui/PersGeneratorPan.as`):

1. `login` → `cmdAck;res=0;` → `persGen.loadDescription()` грузит
   `res/avatars/list.xml` (`core/Session.as:184-192`, `PersGenerator.as:33-64`).
   Файл: 8 аватаров, все `buy='free'`: мужские `id` 45676/7483/0/3 с
   `sex` 0/1/2/3, женские 49327/49328/131/133 с `sex` 128/129/131/133, плюс
   заглушки `dummy1/dummy2`. `sex` = id тела (`personages/<persType>`),
   `res` = id портрета; `PersInfo.boolSex = sex < 128`
   (`core/player/PersInfo.as`). Обе величины берутся из одной строки.
2. Сервер шлёт `constants`, `persInfo;num=;name=@@;sex=;death=;res=@@;` на
   каждого, затем `accountInfo;nPers=;can_create=;`.
3. `checkFullInfo` (`PersGenerator.as:133-151`): XML загружен **и**
   `accInfoReceived` (ставится только при truthy `can_create`) → окно
   создания; иначе при полученных `persInfo` → `createAvatars` +
   `selPers;num=0;` (без ack). Известная поломка кнопки выбора
   (`PersGeneratorPan.as:97-104` передаёт метод вместо объекта) → правило
   «есть персонаж → `can_create=0`».
4. Экран: две карусели (муж/жен, разделение `sex < 128 || sex == "man"`),
   случайный стартовый аватар, поле ника с плейсхолдером «Введите ник».
   Кнопка «Далее» активна при выбранном аватаре и `name.length > 1`
   (`PersGeneratorPan.as:406-418`) — **вся клиентская валидация**. Платные
   аватары (`buy != 'free'`) открывают мёртвое поле SMS-кода. Кнопка «Урок»
   создаёт персонажа и включает видеоуроки (`startLesson`).
5. `newPers;res=<avatar id>;sex=<avatar sex>;name=@..@;`
   (`CSM_CreatePers`) → ждёт cmdAck: 0 → интро → `actPlayer` (ack) →
   `lcall`; 5 «Имя содержит некорректные символы», 6 «Имя уже используется
   другим аккаунтом» (`utils/ErrorReport.as:63-64`); любой ≠ 0 → `failed`.
6. **Стартовые статы задаёт только сервер** (вики: «GSDL, экземпляр
   Player_Trait»). Реконструкция по «Таблице опыта» (строка «Уровень 1»
   = навыки 0): атрибуты 5/5/5/5/5, навыки 0 (0/100), спецы −1 (0/1250),
   `max_specs=1`, HP=SP=120, ОД 50 (+`aspd` неизвестен), вес 40 кг
   (`max_weight=40000`), броня 5, `lvl=0`, репутация 0, премиум 0. Текущий
   `server.py` шлёт `lvl=1`, `hp=100`, `ap_max=20`, `max_weight=50000`,
   `max_specs=3`, `a_specs=-1` при `f_specs=1` (несогласованно).

---

## 5. Формулы `gpui/CharInterface.as` — дословно

Обозначения: `A0..A4` = `attrib0..4.level` (сила, ловкость, телосложение,
восприятие, интеллект; **с бонусами**), `S0/S1` = `skill0/skill1.level`
(ближний бой / стрельба), `SpN` = `specN.level` (−1 если не изучена).

**Уворот в ближнем бою** (`showMeleeEvade`, строки 61-69):
```
meleeEvade% = A1 + A3 + S0 + Sp1                         # :64
```
(вики: `Ловк + Воспр + Навык + Рукопашный·3` — клиент берёт Режущее ×1.)

**Класс брони** (`showArmorLevel`, 70-121):
```
armor = (A1*3 + A3)/4                                    # :73
      + Σ armor_class по слотам head, armor, camouflage, belt, legs, boots   # :74-103
      + Σ effect.armor                                   # :104-114
```
Без округления. `rp_info.armor` карточкой не используется.

**Очки действия** (`showOD`, 135-183; `Apply_OD_Bonus` 122-134):
```
OD = ap_max                                              # :138
   + bonus_od(primary) + bonus_od(secondary)             # :139-140
   + bonus_od(head, armor, camouflage, belt, legs, boots)  # :141-146
   + сет-бонус "_od" по каждому уникальному setTypeID среди 6 слотов   # :147-167
   + Σ effect.max_od                                     # :168-178
```

**Крит / антикрит** (`showKrit`, 184-395), по `primaryItem.weapon_type`
(`core/objects/FireArm.as:38-43`: PISTOL 0, SHOTGUN 1, ASSAULT 2, RIFLE 3,
MACHINEGUN 4, SMG 5). Показывается только если в руках `FireArm`
(`:383-394`); для холодного оружия крит не выводится.
```
PISTOL     cp = (A1*8 + A3*4)/4 + S1/4 + Sp2            # :200
SHOTGUN    cp = (A0*6 + A3*6)/4 + S1/4 + Sp3            # :206
ASSAULT    cp = (A1*6 + A3*6)/4 + S1/4 + Sp4            # :212
RIFLE      cp = (A1*6 + A3*6)/4 + S1/4 + Sp5            # :218
MACHINEGUN cp = (A0*8 + A3*4)/4 + S1/4 + Sp6            # :224
SMG        cp = (A1*6 + A3*4)/4 + S1/4 + Sp7            # :230
любой      ce = (A1 + A3)/2 + S1/2 + Sp<тот же>         # :201,207,213,219,225,231
далее:
cp += bonus_cp(primary, secondary, head, armor, camouflage, belt, legs, boots)   # :236-337
ce += bonus_ce(те же)                                                             # :236-337
cp/ce += сет-бонусы "_cp"/"_ce" по уникальным setTypeID                           # :338-364
cp += Σ effect.critical_probability                                               # :372-375
ce += Σ effect.critical_probability  (если effect.critical_evade)  — баг         # :376-379
crit_txt = cp + " %";  critDodge_txt = ce + " %"                                  # :391-392
```
Баги зеркала, которые стоит знать: ветка пояса (`:350-354`) проверяет
`_loc12_` (belt), но добавляет бонус `_loc7_` (legs) — сет-бонус пояса не
считается, ноги считаются дважды; при `critical_evade` эффекта добавляется
`critical_probability` (`:378`).

Сет-бонус (`getBonusFromSet`, 396-417): для `n` = 2..6, если надето ≥ n
предметов сета — `+ set.bonus_<n><suffix>`.

Сравнение с вики (`(A1+A2)/4 + Стрельба/4 + Спец·2`, антикрит
`(Ловк+Воспр)/2 + Стрельба/8 + Спец`, где для пистолета A1=Ловк·3, A2=Воспр):
у клиента атрибутные коэффициенты в 2–2.7 раза больше, спец ×1 вместо ×2,
антикрит навык /2 вместо /8. Для сервера отправная точка — клиентские
формулы: их видит игрок.

**Подсказки карточки** (`:797-856`) дословно повторяют вики «Навык»
(«Класс брони определяет количество повреждений, которые будут перенаправлены
на выносливость…», «Параметр [ОД] увеличивается вместе с максимально
прокачанным навыком»).

---

## 6. Что добавить в `server/accounts.py` и `server/server.py`

### 6.1 Схема (`accounts.py`)

Сейчас `characters` хранит только `name, sex, res, loc, pos, gx, gy, on_map`
(`server/accounts.py:31-44`). Нужно:

```sql
-- к таблице characters (миграция через PRAGMA table_info, т.к. SCHEMA
-- исполняется как CREATE TABLE IF NOT EXISTS)
hp INTEGER, sp INTEGER,                 -- текущие; NULL = полные
afro INTEGER NOT NULL DEFAULT 0, gold INTEGER NOT NULL DEFAULT 0,
premium INTEGER NOT NULL DEFAULT 0, premium_until INTEGER,
rep INTEGER NOT NULL DEFAULT 0, bg_rep INTEGER NOT NULL DEFAULT 0,
bg_pen INTEGER NOT NULL DEFAULT 0,
max_specs INTEGER NOT NULL DEFAULT 1,
dead INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS char_stats (
    char_id INTEGER NOT NULL REFERENCES characters(id),
    kind    TEXT    NOT NULL,      -- 'attrib' | 'skill' | 'spec'
    idx     INTEGER NOT NULL,      -- 0..4 / 0..4 / 0..14
    value   INTEGER NOT NULL,      -- база атрибута / уровень навыка / уровень спеца (-1 = не изучена)
    xp      INTEGER NOT NULL DEFAULT 0,
    xp_max  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (char_id, kind, idx)
);
```
Производные (`hp_max, sp_max, ap_max, max_weight, armor, lvl, телосложение`)
не хранить — считать из базы по §2.1. `create_character` заполняет
стартовые значения §4 п.6; `Store` получает `load_stats/save_stats`,
`add_money`, `save_vitals`.

### 6.2 Логика (`server.py`, лучше отдельный `progression.py`)

Класс `Character` (память сессии, сериализация в `char_stats`):
- `attrib_base[5]`, `skill[5]{lvl,xp,xp_max}`, `spec[15]{lvl,xp,xp_max}`,
  `max_specs`, `premium`, `rep/bg_rep/bg_pen`, `afro/gold`, `hp/sp`.
- `derived()`: `level = max(skill.lvl)`; `constitution = floor(5+0.75·level)`
  (пишется в `attrib_base[2]`); `hp_max = 4·A0 + 20·A2`; `sp_max = 4·A1 +
  20·A2`; `ap_max = 50 + 5·level`; `max_weight = (30 + 2·A0)·1000·(1+wb)`;
  `armor = (3·A1 + A3)/4`.
- `effective()` = база + бонусы экипировки/эффектов → `f_*` (пока
  экипировки нет — равно базе).
- `rp_info(mask=None)` — полный или частичный кадр (§1.7); `hp/hp_max`
  не включать, слать `usrUp`.
- `gain_xp(skill_idx, spec_idx, amount)` с премиум-множителем, порогами
  `100·2^lvl` / `1250·8^lvl`, переносом остатка, +1 атрибут за уровень
  спеца (кап 20 и ≤ level), пересчёт телосложения/HP/SP/ОД, возврат набора
  изменённых индексов для маски.
- `learn_spec(idx)` / `forget_spec(idx)` / `spec_cost()` по §2.3 п.6-7 и
  таблице `min_skill_level` §1.3.
- `rank()` по таблице §1.5 с капом 25599.

Обработчики:
- `cmd_rp_get_info` → `Character.rp_info()`; `cmd_getInfo(id=0)` →
  `userInfo_Player` с реальными `lvl, rep=[rep], bg_rep, bg_pen, pr, afro,
  gold`; `usrUp` с реальными `hcur/hmax/scur/smax`; `cmd_lenter` → `amax =
  ap_max`, `aspd` из константы.
- `cmd_ss_create` с `s_type=4`: проверить, что `target` — NPC с
  `root == TEACHER`, соседняя клетка, открыть сессию → `cmdAck;res=0;`.
- `cmd_ss_upd`: **ack только при `s_status != 0`**; в сессии обучения
  `s_status=2` → `learn`, `1` → `forget`, `0` → закрыть без ответа; после
  успеха пуш `rp_info` (частичный) и `userInfo_Player` (деньги).
- Сохранение статов при `logout/close` и после каждого изменения xp/денег
  (дёшево — одна строка `char_stats`).
- `constants`: `gold_to_afro_rate=40000`, премиум-доли вида 0.25/0.5 вместо
  1/2, `daily_reset_time` в минутах.

### 6.3 Задачи

| Пр. | Задача | Размер | Зависимости |
|-----|--------|--------|-------------|
| P0 | Схема `char_stats` + новые колонки, миграция, стартовые статы при `newPers` (§4 п.6) | M | — |
| P0 | `Character` с производными и сборкой `rp_info`; `cmd_rp_get_info/getInfo/usrUp/lenter` из него; сохранение при выходе | M | схема |
| P0 | Не слать `cmdAck` на `ss_upd;s_status=0` (все сессии) | S | — |
| P1 | Обучение: `ss_create s_type=4`, `ss_upd` learn/forget, стоимость, `min_skill_level`, `max_specs=1`, пуш `rp_info` + `userInfo_Player` | M | P0 |
| P1 | Начисление опыта за урон/лечение, пороги, level-up, рост атрибутов, телосложение/HP/SP/ОД; уровень мобов из `_lvlN` | L | бой (этап 3) |
| P1 | Премиум: `pr`, доли бонусов, множитель опыта и веса, `premium_until` | S | P0 |
| P1 | Тесты в `test_world.py`: `rp_info` из БД, покупка/сброс спеца, персистентность после relogin | S | P0/P1 |
| P2 | Репутация «Навык бойца»: начисление за PvP, `rep/bg_rep/bg_pen`, кап 25599, `need_pvp_rep`/`bg_obj_rep_req` | M | PvP |
| P2 | Требования предметов `need_*`: ускоренный износ при экипировке, `res=45` при `ss_use`; `f_*` = база + бонусы экипировки | M | предметы (этап 3) |
| P2 | Квесты-тренировки и экзамены (опыт за голд/афро, самоучители) | L | квесты (этап 4) |
| P2 | Ремонт `spec.xml`: `minSkill` по таблице §1.3, чтобы окно учителя показывало требование честно (файл клиента, раздаётся нашим HTTP) | S | — |
| P3 | Эффекты `mob_exp/pl_exp`, сет-бонусы `bonus_<n>_*`, кривая `aspd` | M | эффекты |
| P3 | Скрытые навык 4 / спецы 12–14 — не выдавать (`a_specs=-1`, маска без них) | S | — |
| P3 | Обновить `PROTOCOL.md`: `usrUp` только HP/SP, `rp_info` пушится сервером, `ss_upd` close без ack, деньги через `userInfo_Player` | S | — |
