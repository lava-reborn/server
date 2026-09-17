# Режим LOCAL: что клиент берёт с диска, а что по сети

Разбор по исходникам `recon/as-src/lol/**`. Нужен для раздачи игры друзьям:
владелец поднимает сервер, игрок приносит свою копию клиента и запускает её
с диска. Вопрос, на который отвечает этот документ, один — **что при этом
уходит в сеть**.

Короткий ответ: только игровой сокет. Один XMLSocket на `var_host:var_port`.
Ни одного HTTP-запроса к нашему серверу клиент в этом режиме не делает.

---

## 1. Как выбирается режим

`SSettings.start()` (`lol/core/SSettings.as:39-50`) шлёт единственный запрос —
`CSETTINGS_URL`, то есть **относительный** путь `xmldocs/csettings_v1.xml`
(`SSettings.as:27`). Относительный: для локального `main.swf` он разрешается в
соседний каталог, то есть в `res/xmldocs/csettings_v1.xml`.

| исход | что происходит |
|---|---|
| загрузился | `SSEmulator.PATHTYPE = WEB` (`SSettings.as:53`), дальше всё от `base` из этого файла |
| не загрузился | `SSEmulator.PATHTYPE = LOCAL` (`SSettings.as:60`), `host = _root.var_host`, `port = _root.var_port` (`SSettings.as:61-62`) |

В выпущенном клиенте `res/xmldocs/csettings_v1.xml` **нет** — проверено на
диске, в `res/xmldocs/` лежат только `battlegrounds.xml`, `help.xml`,
`spec.xml`. Значит запуск с диска сам по себе даёт LOCAL, и специально ничего
выключать не надо. Обратное тоже верно и важно: стоит нашему HTTP отдать этот
файл — и клиент уйдёт в WEB, то есть начнёт тянуть с сервера всё
подряд. Поэтому `LAVA_HTTP_RES` закрывает весь `/res/`, включая
`csettings_v1.xml`, а не одни только ассеты.

`localPath` — пустая строка (`SSEmulator.as:4`) и нигде не переприсваивается
(проверено по всему дереву). То есть в LOCAL все пути относительные, от
каталога, где лежит `main.swf`. Для игрока это значит: `main.swf` должен
остаться внутри своего `res/`.

## 2. Что берётся с диска

Все пути ниже — относительно `res/`. Каждый выведен из ветки
`PATHTYPE == LOCAL` в `lol/services/SSEmulator.as`.

| строка | что | путь в LOCAL |
|---|---|---|
| 19 | тайлы глобальной карты | `globalmap/full/<n>.jpg`, `globalmap/client/<n>.jpg` |
| 45 | описание локации (геометрия, спавны) | `locations/static/<id>.xml`, `locations/deadloc/<n>.xml`, `locations/desert/<nnnn>.xml` |
| 81 | графика локации | `locations/libs/<id>.swf` |
| 94 | спрайты | `locations/libs/<type>/<id>.swf` |
| 107 | газета на экране входа | `lib/newspaper/issue.jpg` |
| 120 | видеосправка | `lib/help/videohelp.swf` |
| 133 | тексты справки | `xmldocs/help.xml` |
| 146 | названия локаций | `database/locations.xml` |
| 159 | заставка | `lib/intro/intro.swf` |
| 172 | таблица специализаций | `xmldocs/spec.xml` |
| **185** | **таблица строк** | **`database/texts.xml`** |
| 203 | звук | `sounds/<type>/<name>.swf` |
| 216 | фигура по умолчанию | `personages/default/ghost_0_0.swf` |
| 228 | описание персонажа | `personages/<name>.xml` |
| 241 | анимация персонажа | `personages/<name>/<name>_<action>.swf` |
| 254 | описание моба | `mobs/<res>.xml` |
| 268 | анимация моба | `mobs/<res>/<res>_<action>.swf` |
| 282 | анимация предмета в руках | `classes/...` |
| 297 | иконка предмета | `classes/<папка>/<имя>/ico.swf` |
| 314 | иконка транспорта | `transport/<typeID>.swf` |
| 329 | иконка эффекта | `effects/<typeID>.swf` |
| 343 | описание полей боя | `xmldocs/battlegrounds.xml` |
| 357 | подсказки | `hints/hints.xml` |
| 370 | картинка подсказки | `hints/<typeID>.swf` |
| 384 | список аватаров | `avatars/list.xml` |
| 397 | аватар | `avatars/<id>_<variant>.png` |

Плюс стартовая цепочка `SBase` (`lol/local/SBase.as:44-71`), тоже целиком с
диска: `database/objects.xml` → `database/mobs.xml` → `xml/loc_defs.xml` →
таблица строк.

Из всего этого в выпущенном клиенте **нет двух файлов**: `database/texts.xml`
и `hints/hints.xml`. Всё остальное на диске есть — проверено.

## 3. Что уходит в сеть

**Игровой сокет и больше ничего.** `XMLConnection.connect()`
(`lol/server/XMLConnection.as:52-58`) — обычный `XMLSocket.connect(host, port)`.
Во всём дереве нет ни одного `System.security.loadPolicyFile`, ни
`allowDomain`, ни какой-либо работы с `crossdomain.xml`: клиент про политику не
знает, её запрашивает сам Flash Player. Наш сервер отвечает на неё и на
отдельном порту 843 (`server.py:1762`), и прямо в игровом сокете на
`<policy-file-request/>` (`server.py:1737`) — второго достаточно, и порт 843
поэтому необязателен.

Разобранные поимённо места, где клиент **мог бы** сходить по HTTP, и почему не
ходит:

* `Session.loadSBase` (`Session.as:82-98`) — POST на
  `/exe/lavaclient/loaduser/?ajax` под условием
  `_root.logged == 1 && PATHTYPE == WEB`. В LOCAL второе условие ложно, и ветка
  `else` — просто `SceneShifter.enterScene()`, то есть обычный экран входа.
  Автовхода в LOCAL нет.
* `Session.getHashAndLogin` (`Session.as:101-108`) — запрос к зашитому
  `http://www.lava-online.ru/client/game_session.php` (`SSEmulator.as:412`).
  **Не вызывается ниоткуда**, мёртвый код.
* `EnterGameInterface.getServerNum` (`EnterGameInterface.as:78-86`) — ещё один
  POST на `loaduser`. Тоже **не вызывается ниоткуда**.
* `PersGenerator.sendSmsCode` (`PersGenerator.as:262-272`) — отправка на
  неинициализированную переменную; код вырезан, ветка недостижима.
* `EnterGameInterface.as:251` — единственный живой посторонний запрос:
  `LoadVars.sendAndLoad("http://www.lava-online.ru/res/stats.php")` со временем
  загрузки, **после** успешного соединения и только при
  `timeLoading > 1000 && speedLoading`. Домен мёртв, ответ никуда не идёт,
  игре не мешает. Если игрок сидит за DNS, который на мёртвые домены отвечает
  своей заглушкой, это всё равно один POST в никуда.
* Кнопки «регистрация», «забыл пароль», «форум», «поддержка»
  (`EnterGameInterface.as:305-317`, `HelpDropList.as`, `GlobalMapInterface.as`)
  — `getURL(..., "_blank")`, то есть открывают браузер по клику. Не запросы
  клиента, и ведут на мёртвый сайт. Регистрация у нас идёт мимо них, на нашей
  HTTP-странице.
* `DebugPanel.as:557` — `loadClip("http://res.lava-online.ru/...")`, отладочная
  панель разработчиков.

## 4. Три ловушки

**`texts.xml` и `?all=1`.** `SBase` в обеих цепочках, и LOCAL, и WEB, приходит
в `initializeStringCollector()` (`SBase.as:94-100`), а тот зовёт
`StringCollector.requestAll()` (`StringCollector.as:98-105`), который строит
URL как `getStringURL() + "?all=1"` — в LOCAL это
`database/texts.xml?all=1`. Строка запроса приписывается к пути на диске.
Flash при чтении локального файла строку запроса отбрасывает, так что читается
файл целиком, а `parse()` (`StringCollector.as:74-92`) кладёт в кэш **все**
`<s id>` из документа разом. То есть локальный файл ведёт себя ровно как ответ
нашего `?all=1`, и именно поэтому экспорт обязан быть полным: инвариант
PROTOCOL §9 в LOCAL никуда не девается. Если id, который сервер прислал, в
файле нет — `getString` (`StringCollector.as:30-45`) поставит его в очередь,
`request()` сходит за ним ещё раз, `parse()` разошлёт `update`, а `SBase`
отвечает на это своим `onLoad`, который Session превращает в
`SceneShifter.enterScene()` — экран входа. Одна недостающая строка стоит
сессии.

**`hints/hints.xml`.** `GameHelpMessageManager.loadDescription()`
(`GameHelpMessageManager.as:40-46`) подписывается только на `onXML` и **не**
подписывается на `failed`. Файла в клиенте нет, запрос не удаётся, обработчик
не зовётся, `xmlInfoLoaded` остаётся `false` — подсказок не будет, и больше
ничего. Не фатально, класть в пакет нечего.

**`index.xml`.** `SBase.init()` (`SBase.as:22-26`) читает
`localPath + "index.xml"`, которого в клиенте тоже нет. Но `init()` — не та
функция, с которой начинается игра: Session зовёт `createDB()`
(`Session.as:31-35`), а он идёт по цепочке `initializeLocalItemDB` и до
`index.xml` не доходит. Счётчик `count` остаётся нулём, и на этом всё.

## 5. Откуда клиент берёт адрес сервера

Два пути, и второй важнее, чем кажется:

1. Флешвары. `SSettings.failed()` (`SSettings.as:61-62`) читает
   `_root.var_host` и `_root.var_port`. Своего ключа командной строки у
   projector нет; переменные едут в строке запроса самого фильма, и Flash
   раскладывает их в `_root` так же, как сделал бы из HTML. Это то, что делает
   `lava.bat`, и тем же способом уже работает `run.sh` (там через HTTP).
2. **Поля ввода на экране входа.** `EnterGameInterface.as:162-163` заполняет
   `host_txt` и `port_txt` значениями из `SSettings`, а соединение берёт то,
   что в полях **на момент нажатия кнопки** (`EnterGameInterface.as:234-235`).
   То есть адрес и порт видны в окне входа и правятся руками. Если флешвары по
   какой-то причине не доехали, игрок просто впечатывает адрес — и играет.

Это и есть запасной путь, которого требовало задание: отдельный загрузчик не
нужен, клиент и так спрашивает адрес у игрока.

## 6. Что осталось непроверенным

* Запуск projector с локальным путём и строкой запроса
  (`fp32_sa.exe "...\main.swf?var_host=..."`) **на этой машине не
  проверялся** — клиент запускать было нельзя. По HTTP тот же способ работает
  (`run.sh`, `recon/notes/run_flash*.sh`). Если на локальном пути он окажется
  сломан, спасают поля ввода из §5, и в `README.txt` пакета про них сказано.
* Песочница Flash для локального фильма. Отдельного `loadPolicyFile` клиент не
  делает, так что всё зависит от того, в какую песочницу projector кладёт
  локальный SWF. Если окажется, что сокет из неё не открывается, лечится
  файлом доверия
  `%APPDATA%\Macromedia\Flash Player\#Security\FlashPlayerTrust\lava.cfg` с
  путём к папке игры — это тоже написано в `README.txt` пакета.
