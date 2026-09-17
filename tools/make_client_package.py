#!/usr/bin/env python3
"""Build the folder a friend is handed, which holds no part of the game.

Three files: the string table the shipped client is missing, a launcher with
the server's address baked in, and instructions. The client itself -- res/, the
SWFs, the artwork -- is the player's own copy and never travels with this.

    python3 tools/make_client_package.py --host lava.example.org [--port 9775]

Writes dist/ by default. Everything in it is text; if this script ever produces
a file that is not, something has gone wrong with what is being handed out.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import export_texts  # noqa: E402

PROJECTOR_URL = ("https://fpdownload.macromedia.com/pub/flashplayer/updaters/"
                 "32/flashplayer_32_sa.exe")

# cmd reads a .bat in the console's OEM codepage, which is 866 on a Russian
# Windows and 437 on an English one. The same bytes cannot be right in both,
# so everything this file prints is ASCII and the Russian lives in README.txt.
LAUNCHER = """@echo off
rem LAVA Online -- start the client against {host}:{port}
rem
rem Put this file and texts.xml next to your LAVA folder, so that res\\ is in
rem the same directory as lava.bat, and put fp32_sa.exe here as well.
rem If your files live somewhere else, edit PLAYER and RES below.

setlocal
set "HOST={host}"
set "PORT={port}"
set "PLAYER=%~dp0fp32_sa.exe"
set "RES=%~dp0res"

if not exist "%PLAYER%" (
  echo Flash projector not found: %PLAYER%
  echo Download it from:
  echo   {projector}
  echo and save it next to this file as fp32_sa.exe
  pause
  exit /b 1
)
if not exist "%RES%\\main.swf" (
  echo Game files not found: %RES%\\main.swf
  echo Edit RES in this file so it points at your own res folder.
  pause
  exit /b 1
)
rem The string table is the one file the shipped client does not have. Copy it
rem into place once; the game shows the login screen again without it.
if not exist "%RES%\\database\\texts.xml" (
  if exist "%~dp0texts.xml" (
    echo Installing texts.xml into %RES%\\database\\
    copy /y "%~dp0texts.xml" "%RES%\\database\\texts.xml" >nul
  ) else (
    echo texts.xml is missing from both %RES%\\database\\ and this folder.
    pause
    exit /b 1
  )
)

rem No command line switch carries flashvars into the projector; they ride in
rem the query string of the movie's own path, and Flash unpacks them into
rem _root the same way it would from a web page. var_host and var_port are
rem where the client reads the server's address in local mode.
rem
rem If the projector says it cannot find the file, it took the query string
rem for part of the name. Comment out the line below, uncomment the two after
rem it, and it gets the same thing as a file:/// URL instead. Either way the
rem login window has address and port fields you can type into.
"%PLAYER%" "%RES%\\main.swf?vversion=1&var_host=%HOST%&var_port=%PORT%"
rem set "RESURL=%RES:\\=/%"
rem "%PLAYER%" "file:///%RESURL%/main.swf?vversion=1&var_host=%HOST%&var_port=%PORT%"
endlocal
"""

README = """LAVA Online — как подключиться
==============================

Сервер: {host}, порт {port}
Регистрация: http://{host}:{http_port}/

В этой папке нет ни одного файла игры. Клиент — ваша собственная копия;
здесь только то, чего в ней нет, и запускалка.

Что нужно
---------

1. Папка с игрой — та, внутри которой лежит res\\ (в ней main.swf,
   locations, mobs и прочее).

2. Flash Player projector 32 — отдельный .exe, браузер для этого не нужен
   и уже не годится. Скачать:

   {projector}

   Сохраните его рядом с lava.bat под именем fp32_sa.exe.

3. texts.xml из этой папки — таблица всех названий: предметов, существ,
   квестов, машин. В выпущенном клиенте её нет (файл был на сервере), и
   без неё игра выкидывает на экран входа, как только ей понадобится
   название, которого она не знает. Никогда не заменяйте её файлом из
   другой сборки и не редактируйте: сервер и эта таблица должны совпадать.

Установка
---------

1. Положите lava.bat и texts.xml в папку с игрой — туда, где лежит res\\.
   Рядом же положите fp32_sa.exe.

2. Скопируйте texts.xml в res\\database\\texts.xml.
   lava.bat сделает это сам при первом запуске, если файла там ещё нет.

Должно получиться так:

    LAVA\\
      lava.bat
      texts.xml
      fp32_sa.exe
      res\\
        main.swf
        database\\
          texts.xml   <- скопированный
          locations.xml
          mobs.xml
          objects.xml
        locations\\ ...

Если res\\ лежит в другом месте, откройте lava.bat блокнотом и поправьте
строку с RES — там нужен путь к вашей папке res.

Как играть
----------

1. Зарегистрируйтесь в браузере: http://{host}:{http_port}/
   Логин от трёх символов, пароль любой. Пароль никуда не уходит: клиент
   считает от него хеш и посылает только его.

2. Запустите lava.bat.

3. В окне входа введите тот же логин и пароль. Персонаж создаётся при
   первом входе.

   В этом же окне есть поля адреса и порта. Обычно они уже заполнены —
   их подставляет lava.bat. Если пусто или написано другое, впишите
   руками:

       адрес  {host}
       порт   {port}

   Игра соединяется именно с тем, что стоит в этих полях, так что ими
   можно поправить что угодно.

Всё, что игра рисует и проигрывает, она берёт с вашего диска. По сети идёт
только сама игра — один сокет на {host}:{port}. Ни одного файла с сервера
не скачивается.

Если не запускается
-------------------

* Окно открылось и сразу закрылось, или пусто — путь к res\\ в lava.bat
  неверный. Проверьте, что "%RES%\\main.swf" существует.

* Projector пишет, что не может открыть файл, хотя main.swf на месте —
  он принял строку запроса за часть имени. В конце lava.bat есть
  запасной вариант через file:/// — закомментируйте рабочую строку и
  раскомментируйте две следующие.

* Дошло до экрана входа, но поля адреса пустые — projector не передал
  игре строку запроса. Ничего страшного: впишите адрес и порт руками
  (см. выше), остальное работает как обычно.

* Игра доходит до экрана входа, но после входа возвращает туда же —
  texts.xml не на месте или не тот. Он должен лежать в res\\database\\ и
  быть из этой же раздачи.

* «Соединение с сервером потеряно» — сервер выключен или порт {port}
  закрыт. Проверьте страницу регистрации: если она открывается, сервер жив.

* Flash отказывается открывать сокет (окно входа есть, но соединения нет).
  Разрешите папке с игрой выход в сеть: создайте текстовый файл

      %APPDATA%\\Macromedia\\Flash Player\\#Security\\FlashPlayerTrust\\lava.cfg

  и напишите в нём одну строку — полный путь к папке с игрой, например

      C:\\Games\\LAVA

  После этого запустите lava.bat снова.
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", required=True,
                    help="address friends connect to: a name or an IP")
    ap.add_argument("--port", default="9775", help="game socket port")
    ap.add_argument("--http-port", default="8080",
                    help="port of the registration page")
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "dist"),
                    help="where to build (default: dist/)")
    args = ap.parse_args(argv)

    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    blob = export_texts.document_bytes()
    missing, stray = export_texts.verify(blob)
    if missing or stray:
        print("таблица строк не сходится: %d не хватает, %d лишних"
              % (len(missing), len(stray)), file=sys.stderr)
        return 1
    with open(os.path.join(out, "texts.xml"), "wb") as fh:
        fh.write(blob)

    fields = dict(host=args.host, port=args.port, http_port=args.http_port,
                  projector=PROJECTOR_URL)
    # CRLF throughout: these are read by cmd.exe and by Notepad.
    with open(os.path.join(out, "lava.bat"), "w", encoding="ascii",
              newline="\r\n") as fh:
        fh.write(LAUNCHER.format(**fields))
    # A byte order mark, or Notepad reads the Russian as the system codepage.
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8-sig",
              newline="\r\n") as fh:
        fh.write(README.format(**fields))

    for name in sorted(os.listdir(out)):
        print("  %-12s %8d B" % (name, os.path.getsize(os.path.join(out, name))))
    print("%s: сервер %s:%s" % (out, args.host, args.port))
    return 0


if __name__ == "__main__":
    sys.exit(main())
