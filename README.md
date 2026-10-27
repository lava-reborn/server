# LAVA Online — сервер

Сервер для MMO **LAVA Online** (VR-Ocean, 2008–2018), восстановленный по
оригинальному клиенту и фанатской вики: бой, квесты, торговля, кланы,
транспорт, аукцион, банк, глобальная карта. Клиент — оригинальный, на Flash.
Игрок получает лаунчер, который ставит игру с сервера и обновляет её
([client/README.md](client/README.md)).

## Что нужно

- Python 3.12 и Docker с compose.
- Оригинальный клиент игры — папка `res/`, около 2 ГБ. Серверу из неё нужен
  срез примерно в 35 МБ: `locations/{static,deadloc,desert}/*.xml`,
  `database/mobs.xml`, `database/objects.xml`, `avatars/list.xml`. Тестам
  нужен тот же срез.
- Для игры на своей машине — Flash Player projector 32
  (`flashplayer_32_sa.exe`) в `tools/flash/`.

## Запуск на своей машине

```bash
./run.sh            # серверы и клиент
./run.sh servers    # только серверы
./run.sh stop
./run.sh log        # хвост logs/game.log
```

Путь к папке `res/` задаётся переменной `RES_WSL` в начале `run.sh`.
Серверы работают под Python из WSL. Регистрация — `http://127.0.0.1:8080/`.

## Развёртывание в Docker

```bash
cp .env.example .env            # указать LAVA_RES_DIR и LAVA_PUBLIC_HOST
docker compose up -d --build
docker compose logs -f game
docker compose down             # сервер сохраняет всех, кто в игре
```

Два сервиса из одного образа: `game` — игровой сокет (9775) и политика Flash
(843), `http` — страница регистрации, админ-панель `/admin` и `/status`.

| Переменная | По умолчанию | Что задаёт |
|---|---|---|
| `LAVA_RES_DIR` | — | папка `res/`, монтируется только для чтения |
| `LAVA_PUBLIC_HOST` | `127.0.0.1` | адрес сервера, который видят игроки |
| `LAVA_GAME_PORT`, `LAVA_HTTP_PORT` | `9775`, `8080` | опубликованные порты |
| `LAVA_BIND` | `0.0.0.0` | интерфейс публикации портов |
| `LAVA_POLICY_PORT`, `LAVA_POLICY_PUBLIC_PORT` | `8430`, `843` | порт политики Flash в контейнере и снаружи |
| `LAVA_DB_URL` | пусто | адрес Postgres; пусто — SQLite в томе `lava-db` |
| `LAVA_ADMINS` | пусто | игровые логины через запятую с доступом к `/admin`; пусто — панели нет |
| `LAVA_ADMIN_HOURS` | `12` | сколько часов держится вход в панель |
| `LAVA_LOG_LEVEL` | `INFO` | `DEBUG` пишет в лог весь протокол |
| `LAVA_HTTP_RES` | `0` | раздавать ли `res/` по HTTP; держите `0` |
| `LAVA_SERVER_CHAT` | `0` | `1` — сервер пишет в чат причины отказов |
| `LAVA_BOSS_HOURS`, `LAVA_BOSS_TZ`, `LAVA_BOSS_STAY` | см. `.env.example` | часы появления боссов, часовой пояс, сколько минут босс стоит |
| `LAVA_WAREHOUSE_HOURS` | `20` | час прихода хозяина складов |
| `LAVA_NOOB_VALLEY_SAFE` | `0` | `1` — в Нубийской долине нет ПвП вне арены |
| `LAVA_SMTP_*`, `LAVA_MAIL_FROM`, `LAVA_SITE_URL` | пусто | почта игрокам: подтверждение адреса и сброс пароля |
| `LAVA_REGISTER_EMAIL` | `0` | `1` — без почты регистрация не проходит |

## База данных

По умолчанию — файл SQLite в томе `lava-db`. С `LAVA_DB_URL` сервер работает
с Postgres. Схема одна на обе базы (`SCHEMA` в `server/accounts.py`),
недостающие таблицы и колонки создаются при старте. Проверка на Postgres —
`server/test_storage_pg.py` с заданным `LAVA_DB_URL`; базе нужна своя,
одноразовая.

## Выкладка на сервер

```bash
LAVA_DEPLOY_HOST=user@host LAVA_RES_SRC=/path/to/res bash deploy/deploy.sh --with-data   # первый раз
LAVA_DEPLOY_HOST=user@host bash deploy/deploy.sh             # дальше: код, пересборка, рестарт
```

Перед рестартом игроки получают отсчёт (`--warn=SECONDS`, `--now` — без
него). `--data-only` обновляет только срез `res/`. Каталог на сервере —
`LAVA_DEPLOY_DIR`, по умолчанию `/opt/lava`. Файл `.env` на сервере
создаётся из `deploy/env.example` при первой выкладке и дальше не
перезаписывается. База лежит в томе docker, выкладка её не трогает.

## Админ-панель

`/admin` на HTTP-сервисе, вход игровым логином и паролем. Доступ — логинам
из `LAVA_ADMINS`. Учётки администраторов:

```bash
python3 tools/admin_account.py list
python3 tools/admin_account.py create NAME     # спросит пароль
python3 tools/admin_account.py delete NAME --yes
```

## Клиент и лаунчер

Релиз клиента собирается из оригинального `res/` и наших правок и
подписывается; лаунчер ставит его и проверяет по хэшам. Порядок выпуска,
ключи и сборка лаунчера — в [client/README.md](client/README.md), формат
файлов — в [client/FORMAT.md](client/FORMAT.md).

Новому серверу нужны свои ключи подписи и свой лаунчер с его адресом
(`launcher/build.ps1 -ServerHost ... -Site ...`): уже установленные
лаунчеры доверяют только тем ключам, с которыми собраны.

## Тесты

```bash
bash tools/run_suite.sh . /tmp/lava_suite 8                      # все наборы по 8 разом
bash tools/run_suite.sh . /tmp/lava_suite 8 --only test_combat   # выбранные
bash tools/run_suite.sh . /tmp/lava_suite 8 --affected           # затронутые правкой
```

Под Windows — `tools\run_suite.ps1 -Out D:\lava_suite -Jobs 8`. Итог — в
`summary.txt` и `report.html` папки результатов. Набор, зависящий от
времени, под нагрузкой может упасть; перед тем как считать падение
настоящим, его гоняют отдельно. `test_bootstrap` сверяет размер `main.swf`
и падает на другой копии клиента. Как устроены наборы — в
[TESTING.md](TESTING.md).

## CI/CD

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) гоняет тесты на push
в `main` и на pull request, а после зелёных тестов на `main` выкладывает
код на сервер через шлюз из `deploy/ci/`. Нужны self-hosted раннер с меткой
`lava` и секреты `DEPLOY_SSH_KEY` и `DEPLOY_KNOWN_HOSTS`. Push в `main` —
это выкладка, поэтому работа идёт в ветках. Push, который меняет только
`README.md`, `TASKS.md`, `UNDONE.md`, `ROADMAP.md`, `PROTOCOL.md` или
`recon/`, прогона не запускает.

## Что где лежит

| Папка | Что там |
|---|---|
| `server/` | игровой сервер, HTTP-сервис, тесты |
| `data/` | таблицы игры в JSON и сборщики, которые их строят |
| `client/` | сборка, подпись и публикация релизов клиента |
| `launcher/` | лаунчер игрока (C#) |
| `tools/` | редактор локаций, экспорт строк, запуск тестов и прочее |
| `deploy/` | выкладка, compose, шлюз CI |
| `recon/` | разбор оригинального клиента |

Протокол клиент–сервер — [PROTOCOL.md](PROTOCOL.md).

## Правовая рамка

Восстановление сервера для мёртвой игры ради совместимости и сохранения —
обычная практика (MaNGOS, rAthena, L2J). Здесь только серверный код и
результаты анализа. Ассеты остаются у правообладателя. Данные с вики —
CC-BY-SA, при использовании указывать источник.

### Лицензия

Код из этого репозитория распространяется под лицензией MIT, полный текст —
в [`LICENSE`](LICENSE). Его можно использовать, менять и распространять, в
том числе в закрытых сборках, при одном условии: сохранять уведомление об
авторстве и текст лицензии.

Лицензия касается только кода. Под неё не подпадают:

- ресурсы и файлы оригинального клиента и всё, что извлечено из них
  дословно (тексты `texts.xml` в `data/orig_*.json`, таблицы клиента) —
  они принадлежат правообладателю игры;
- данные с фан-вики (`data/wiki*`, `data/*_wiki.json`) — они остаются
  под CC BY-SA и требуют указания источника.
