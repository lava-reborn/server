# Клиент: релизы и обновления

Лаунчер ставит игру целиком с сервера и держит её ровно такой, какой её
описывает подписанный релиз. Релиз собирается и публикуется шлюзом при
каждой выкатке сервера, поэтому клиент и сервер меняются вместе. Новый
лаунчер шлюз собирает и подписывает сам, когда выкатка меняет его код.
Формат файлов — [FORMAT.md](FORMAT.md).

Цепочка: слитый в `main` PR → CI → шлюз на сервере собирает релиз
(`client/build.py`: оригинал + правки), при изменённом коде лаунчера
собирает его (`launcher/build.sh` в контейнере Mono), выкатывает сервер,
публикует релиз и лаунчер в `/download/client/` → лаунчер игрока при запуске
проверяет подписи, докачивает изменённые файлы и при необходимости заменяет
себя.

## Что здесь лежит

| Файл | Что это |
|---|---|
| `FORMAT.md` | формат указателя, списка, заявления, подписи, хранилища |
| `base.txt` | оригинальная игра пофайлово: хэш, размер, путь |
| `remove.txt` | файлы оригинала, которые игрокам не нужны |
| `extra.txt` | крупные свои файлы, которые лежат только в хранилище сервера |
| `files/` | небольшие свои файлы, в git как есть |
| `objects/` | свои объекты локаций ([objects/README.md](objects/README.md)) |
| `keys/` | открытые ключи, которые вшиваются в лаунчер |
| `build.py` | сборщик релиза |
| `publish.py` | публикатор; на сервере держит ключ подписи |
| `lavasig.py` | подпись RSA: ключи, подпись, проверка |
| `devserve.py` | стенд разработчика: весь конвейер на одной машине |
| `test_client.py` | тесты сборщика, публикатора и подписи |

Слитый PR становится программой, которую запустят у себя все игроки.
Право слияния в `main` давайте только тем, кому это доверяете.

## Выпустить правку клиента

1. Правка: патч в `tools/widescreen.py`, подпись карты в
   `data/map_labels.json`, клетка карты в `data/map_cells.json` или файл в
   `client/files/<путь под res>`.
2. Проверка: `python3 client/test_client.py` и тесты патча
   (`tools/test_widescreen.py`).
3. PR. Правку, которой нужен и новый сервер, и новый клиент, делайте одним
   PR: шлюз выкатит их вместе.
4. После слияния CI выкатит сервер и опубликует релиз; игроки получат его
   при следующем запуске лаунчера.

## Добавить, заменить или убрать файл игры

- **Небольшой файл** — в `client/files/` по его пути под `res/`; файл
  оригинала с тем же путём будет заменён.
- **Крупный файл** кладётся в хранилище на сервере:
  `python3 /opt/lava-ci/client/publish.py add --root /opt/lava-site/download/client FILE`.
  Команда печатает хэш и размер; строку `хэш TAB размер TAB путь` добавляют
  в `extra.txt` обычным PR.
- **Убрать файл оригинала** — вписать путь в `remove.txt`.

## Новый лаунчер

Отдельного шага нет: поменяйте код в `launcher/` обычным PR (проверка на
Windows — `launcher\test\run.ps1`). При выкатке шлюз считает хэш всего, из
чего сделан exe; если он изменился, собирает лаунчер с номером на единицу
больше опубликованного и публикует его, прежний остаётся как
`LavaReborn.exe.prev`. Если сборка не удалась, выкатка останавливается
целиком.

Аварийный выпуск в обход шлюза — ключом владельца:

```
powershell -ExecutionPolicy Bypass -File launcher\build.ps1 -Build <N> -SignKey <путь к launcher.pem>
bash deploy/client/publish_launcher.sh dist/LavaReborn.exe dist/<N>.txt
```

## Ключи

| Ключ | Закрытая часть | Открытая часть |
|---|---|---|
| ресурсов | на сервере, `/opt/lava-ci/client/resource.pem` | `keys/resource.keys` |
| лаунчера (шлюза) | на сервере, `/opt/lava-ci/client/launcher.pem` | `keys/launcher.keys` |
| лаунчера (запасной) | у владельца, вне репозитория | `keys/launcher.keys` |

- Ключи сервера делает `deploy/remote/install.sh`, запасной —
  `python3 client/lavasig.py genkey <путь>`. Закрытые ключи в репозиторий не
  кладутся.
- Рядом со своим ключом держите `pinned.txt` со строками `resource <id>` и
  `launcher <id>`: `build.ps1` сверяет с ним ключи репозитория и не собирает
  при расхождении (`-AcceptKeys` — осознанная смена).
- **Смена ключа ресурсов:** новый ключ рядом со старым → его строка второй
  в `keys/resource.keys`, слить → после обновления игроков переименовать
  новый в `resource.pem` и убрать старую строку.
- **Пропал ключ лаунчера шлюза:** новый ключ через `install.sh`,
  `CLIENT_LAUNCHER=0` в `gate.conf`, строку ключа в `keys/launcher.keys`,
  аварийный лаунчер ключом владельца, затем `CLIENT_LAUNCHER=1`.
- **Пропали оба ключа лаунчера:** самообновление остановится, игрокам
  придётся один раз скачать новый лаунчер вручную.

## Первая установка на сервере

1. Скопировать `deploy/` и `client/` в `/root/lava-ci-src` и запустить
   `bash /root/lava-ci-src/deploy/remote/install.sh --pubkey '<ключ CI>'`.
   Он сделает ключи ресурсов и шлюза и напечатает их строки: первую — в
   `keys/resource.keys`, вторую — в `keys/launcher.keys`.
2. Положить проектор Flash для сборки лаунчера:
   `scp tools/flash/fp32_sa.exe <сервер>:/opt/lava-ci/client/fp32_sa.exe`.
   Папка `/opt/lava-site/download` должна принадлежать root
   (`chown root:root`, `chmod 755`).
3. Залить оригинальную игру в хранилище:

   ```
   python3 /opt/lava-ci/client/publish.py import-base --root /opt/lava-site/download/client \
       --base /root/lava-ci-src/client/base.txt --zip /root/LAVA.zip --prefix LAVA/res/
   ```

   Все файлы должны сойтись с `base.txt`.
4. В `/opt/lava-ci/gate.conf` добавить `CLIENT_RELEASE=1` и
   `CLIENT_LAUNCHER=1`. Первая выкатка опубликует первый релиз и лаунчер.

## Откат

- **Сервер и клиент вместе** — выкатить прежний коммит.
- **Только клиент**:
  `python3 /opt/lava-ci/client/publish.py rollback --root /opt/lava-site/download/client --key /opt/lava-ci/client/resource.pem [--to <номер>]`.
- **Лаунчер** — откатить код в `launcher/` обычным PR: номер версии только
  растёт.

## Стенд разработчика

Весь конвейер на одной машине, с тестовыми ключами в `client/dev/`:

```
python3 client/devserve.py --zip "LAVA.zip" --prefix LAVA/res/ --res /путь/к/res
```

`--own-base` берёт эталоном вашу копию игры. Лаунчер для стенда:

```
powershell -ExecutionPolicy Bypass -File launcher\build.ps1 -Site http://127.0.0.1:8098 `
    -ResourceKeys client\dev\keys\resource.keys -LauncherKeys client\dev\keys\launcher.keys `
    -SignKey client\dev\keys\launcher.pem -Out dist\dev\LavaReborn.exe
```

## Тесты

- `client/test_client.py`, `tools/test_swfgen.py` — в общем прогоне CI.
- `launcher\test\run.ps1` — лаунчер на Windows: ставит, обновляет, чинит,
  заменяет себя.
- `launcher\test\check_netfx.ps1 <exe>` — exe из шлюза работает на .NET
  Framework этой машины.
- `bash deploy/remote/test_gate.sh` — шлюз целиком (Linux с docker).
- `bash tools/flash_headless/run.sh <локация.xml>` — настоящий Flash Player
  рисует локацию без окон ([README](../tools/flash_headless/README.md)).

## Обслуживание

```
python3 /opt/lava-ci/client/publish.py status --root /opt/lava-site/download/client
python3 /opt/lava-ci/client/publish.py gc --root /opt/lava-site/download/client \
    --base /root/lava-ci-src/client/base.txt --extra /root/lava-ci-src/client/extra.txt [--dry-run]
```

`gc` удаляет из хранилища файлы, которые не нужны ни одному из последних
списков (`CLIENT_KEEP`, по умолчанию восемь) и не входят в оригинал.
