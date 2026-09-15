# LAVA Online — протокол клиент/сервер

Восстановлено из `res/main.swf` (ActionScript 2, SWF v9) декомпиляцией JPEXS FFDec.
Исходник классов: `recon/as-src/lol/`. Ключевые файлы:
`lol/server/XMLConnection.as`, `lol/server/SCDataParser.as`,
`lol/server/mess/CSMessage.as`, `lol/core/Session.as`.

## 1. Транспорт

Flash `XMLSocket` поверх сырого TCP. Кадр = строка, завершённая байтом `0x00`.
Несмотря на имя, XML **не используется**: клиент оборачивает строку в `new XML(str)`,
получая текстовый узел, а на приёме делает `xml.childNodes.join("")`.
То есть на проводе — plain text.

Кодировка кириллицы: CP1251 (`convertToCP1251` в клиенте).

Адрес по умолчанию из `settings.db`:

    host = game.lava-online.ru
    port = 9775

## 2. Формат кадра

    <имя_команды>;<ключ>=<значение>;<ключ>=<значение>;

Генерация — `CSMessage.toString()`. Разбор — `SCDataParser.parse()`.
Имя команды = всё до первой `;`.

## 3. Типы значений

Тип определяется **первым символом** значения (`SCDataParser.getData`):

| Префикс      | Тип              | Формат                        | Пример                |
|--------------|------------------|-------------------------------|-----------------------|
| цифра, `+`, `-` | число         | `key=123;`                    | `res=0;`              |
| `@`          | строка           | `key=@текст@;`                | `name=@Вася@;`        |
| `H` / `h`    | hex-число        | `key=Hxxxx;`                  | `color=HFF00AA;`      |
| `x`          | big unsigned int | `key=xNNNN;` (хранится строкой) | `id=x4294967296;`   |
| `\|`         | список           | см. ниже                      |                       |

Списки (`getListData`):

- пустой: `key=\|;`
- числовой: `key=\|1\|2\|3\|;`
- строковый: `key=\|@a@\|@b@\|;`  (разделитель `@\|@`, терминатор `@\|;`)
- big-uint: `key=\|xN\|xM\|;`

Строки проходят через `XMLString.unescape()` — см. `recon/as-src/lol/server/XMLString.as`.

## 4. Рукопожатие

Полная последовательность из `lol/core/Session.as`:

1. **HTTP**, вне сокета: `GET http://www.lava-online.ru/client/game_session.php?session=<S>`
   Ответ — строка-хеш. Ответ `0` или пусто = отказ.
   Сессия `S` берётся из `_root.session` (flashvars от лаунчера).
2. TCP connect на `host:port`.
3. Клиент → `hello;minor=2;major=0;`
4. Сервер → кадр с именем `hello` (параметры клиент игнорирует).
   Таймаут 20 с, иначе клиент рвёт соединение (`closeWithoutHelloResponse`).
5. Клиент → `login;hash=@<хеш>@;`
6. Сервер → `cmdAck;res=0;`
   `res=0` — успех, клиент вызывает `persGen.loadDescription()` и идёт дальше.
   Любое другое значение — отказ.

Прочие служебные команды сервера: `kickban;admin=@..@;seconds=N;reason=@..@;`,
`shutdown;seconds=N;`.

## 5. Словарь команд

### Клиент → сервер: 55 классов, 53 уникальные команды

Классы в `recon/as-src/lol/server/mess/CSM_*.as`. Имя на проводе — поле `_name`,
и оно НЕ совпадает с именем класса. Параметры — вызовы `addProp()` в конструкторе.
Полная таблица «команда → параметры»: `recon/notes/cs_commands.txt`. Группы:

- сессия: `hello`, `login`, `logout`, `actPlayer`, `selPers`, `newPers`, `resurrect`
- локация и движение: `lenter`, `moveTo` (3 формы: dx/dy, path, trg), `chWorld`
- метки карты: `insMark`, `updMark`, `rmMark`
- предметы: `ss_create`, `ss_get`, `ss_move`, `ss_use`, `ss_upd`, `ss_heap_c`, `ss_get_di`, `ss_get_si`, `ss_get_s_si`
- квесты: `q_list`, `q_st`, `q_ca`, `q_co`, `q_di`, `q_si`, `q_status`
- кланы: `admit`, `apply`, `head`, `gg_info`, `c_ga`
- почта: `chkml`, `getml`, `sndml`, `rmvml`, `uldml`
- аукцион: `ah_create`, `ah_op`, `ah_search`
- поля боя: `bg_op`
- прочее: `userMsg`, `on_conv`, `getInfo`, `p_op`, `rp_get_info`, `e_get_di`, `e_get_si`, `ts_get_si`

### Сервер → клиент: 239 подписок

Диспетчеризация по имени через `XMLConnection.sendNotification` → `dispatchEvent`.
Полный список подписок — в `recon/notes/sc_commands.txt`.
Ключевые: `hello`, `cmdAck`, `lenter`, `lcall`, `lch`, `userInfo*`, `persInfo`,
`addPlayer`, `removePlayer`, `userMove`, `moveAck`, `ss_*`, `q_*`, `gg_*`, `bg_*`,
`ah_lot`, `chatRes`, `accountInfo`, `actionPoints`, `regAck`, `useAck`, `upgrAck`, `repAck`.

## 6. Что уже есть на клиенте

В `res/` лежит статический контент, который сервер знать не обязан:

| Файл                      | Записей | Содержимое                       |
|---------------------------|---------|----------------------------------|
| `res/database/objects.xml`| 29 486  | `type_id` → имя предмета         |
| `res/database/mobs.xml`   |  5 990  | `type_id` → имя моба + ресурс    |
| `res/database/locations.xml` | 417  | точки глобальной карты + описания|
| `res/locations/*.xml`     |  1 399  | геометрия и проходимость локаций |

Важно: это **только идентификаторы и графика**. Числовой баланс (урон, HP, лут,
цены, опыт) жил на сервере и в клиенте отсутствует — его придётся задавать заново.
