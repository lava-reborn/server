# client/files

Небольшие свои файлы, которые игроки получают как есть, по тому же пути под
`res/`: `client/files/xmldocs/x.xml` становится `res/xmldocs/x.xml` и
заменяет файл оригинала с этим путём. Крупные файлы кладутся в хранилище и
`client/extra.txt` (client/README.md).

Пути, которые сборка релиза генерирует сама (`main.swf`,
`database/texts.xml`, `database/locations.xml`, `hints/hints.xml`, тайлы
карты, спрайты своих объектов, `xml/loc_defs.xml`, свои локации), здесь
запрещены — правится их генератор. Локация, которую должен читать и сервер,
кладётся в `data/locations/static/<id>.xml`.

Что здесь сейчас:

- `locations/static/262.xml` — «Тотем» у Абри: оригинал с другим
  заголовком окна. Файл входит в срез `res/`, который читает сервер, поэтому
  `deploy/deploy.sh --with-data` и `--data-only` требуют в `LAVA_RES_SRC`
  оригинальную версию (`tools/test_deploy_slice.py`).
- `classes/SimpleObject/qSilverReal_one/ico.swf` — иконка «Серебристой
  монеты»: копия оригинальной `qSilverReal/ico.swf` под тем именем, по
  которому её ищет клиент.
