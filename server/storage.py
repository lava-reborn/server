# -*- coding: utf-8 -*-
"""Где живут данные: файл SQLite или общий Postgres.

Выбор делает окружение: есть `LAVA_DB_URL` — работаем с Postgres, нет —
открываем файл, как всю дорогу до сих пор. Вся разница между базами
спрятана здесь; `accounts.py` пишет один и тот же SQL с вопросительными
знаками и не знает, куда он поедет.

Что именно пришлось развести по диалектам, и почему:

* **Плейсхолдеры.** В sqlite3 это «?», в psycopg «%s». Курсор Postgres
  подменяет их сам, поэтому запросы в коде остались прежними.
* **Новый идентификатор.** `cur.lastrowid` в Postgres не существует;
  вместо него `INSERT ... RETURNING`, и колонку ключа приходится назвать
  явно — она у таблиц разная (`id`, `uniq`, `q_id`).
* **`INSERT OR REPLACE`** — это SQLite. В Postgres то же самое пишется
  как `ON CONFLICT (...) DO UPDATE`, и список ключей конфликта нужно
  назвать руками.
* **Схема.** Единственный источник — `SCHEMA` в accounts.py, написанная
  на диалекте SQLite. Для Postgres она не переписывается второй раз, а
  переводится: DDL прогоняется через SQLite в памяти, оттуда читается
  состав таблиц и из него собирается CREATE TABLE для Postgres.
  Второй экземпляр схемы разошёлся бы с первым в первый же вечер.
* **Состав таблицы.** `PRAGMA table_info` против `information_schema`.

Из кода игры сюда ходят только `connect()` и методы соединения; ничего
специфичного для драйвера наружу не торчит.
"""
import os
import re
import sqlite3

DB_URL = os.environ.get("LAVA_DB_URL", "").strip()


class IntegrityError(Exception):
    """Нарушение уникальности — одинаково для обеих баз."""


def using_postgres():
    return bool(DB_URL)


# --- SQLite ---------------------------------------------------------------

class SqliteDB:
    """Тонкая обёртка: соединение sqlite3 плюс общие методы."""

    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        # Два процесса держат этот файл: сервер игры и страница
        # регистрации. Под обычным журналом писатель запирает читателей на
        # всю транзакцию, и регистрация, пришедшая посреди сохранения,
        # ждала его и иногда сдавалась. WAL пропускает их мимо друг друга.
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")

    # --- общий интерфейс -------------------------------------------------
    def execute(self, sql, args=()):
        try:
            return self._db.execute(sql, args)
        except sqlite3.IntegrityError as exc:
            raise IntegrityError(str(exc))

    def executemany(self, sql, rows):
        return self._db.executemany(sql, rows)

    def insert(self, sql, args=(), returning="id"):
        """Выполнить INSERT и вернуть новый идентификатор."""
        return self.execute(sql, args).lastrowid

    def replace(self, table, columns, rows, conflict):
        self._db.executemany(
            "INSERT OR REPLACE INTO %s (%s) VALUES (%s)"
            % (table, ", ".join(columns), ", ".join("?" * len(columns))), rows)

    def columns(self, table):
        return {r["name"] for r in self._db.execute("PRAGMA table_info(%s)" % table)}

    def create_function(self, *args, **kwargs):
        self._db.create_function(*args, **kwargs)

    # sqlite3-соединение само по себе транзакция: `with db:` фиксирует её
    # на выходе и откатывает на исключении. Код на это рассчитывает, и
    # обёртка обязана вести себя так же.
    def __enter__(self):
        self._db.__enter__()
        return self

    def __exit__(self, *exc):
        return self._db.__exit__(*exc)

    def create_schema(self, schema_sql):
        self._db.executescript(schema_sql)

    def commit(self):
        self._db.commit()

    def close(self):
        self._db.close()

    @property
    def raw(self):
        return self._db


# --- Postgres -------------------------------------------------------------

def _qmarks_to_pg(sql):
    """«?» → «%s», не трогая вопросительные знаки внутри строковых литералов."""
    out, in_str = [], False
    for ch in sql:
        if ch == "'":
            in_str = not in_str
        if ch == "?" and not in_str:
            out.append("%s")
        else:
            out.append(ch)
    return "".join(out)


class PgCursor:
    """Курсор с «?» и строками, у которых есть доступ по имени столбца."""

    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None

    def execute(self, sql, args=()):
        self._cur.execute(_qmarks_to_pg(sql), tuple(args))
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur.fetchall())


class PostgresDB:
    def __init__(self, dsn):
        import psycopg
        from psycopg.rows import dict_row
        self._psycopg = psycopg
        self._conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=False)

    def _cursor(self):
        return PgCursor(self._conn.cursor())

    def execute(self, sql, args=()):
        try:
            return self._cursor().execute(sql, args)
        except self._psycopg.errors.UniqueViolation as exc:
            self._conn.rollback()
            raise IntegrityError(str(exc))

    def executemany(self, sql, rows):
        cur = self._conn.cursor()
        cur.executemany(_qmarks_to_pg(sql), [tuple(r) for r in rows])
        return cur

    def insert(self, sql, args=(), returning="id"):
        cur = self.execute("%s RETURNING %s" % (sql.rstrip().rstrip(";"), returning),
                           args)
        row = cur.fetchone()
        return row[returning] if row else None

    def replace(self, table, columns, rows, conflict):
        """ON CONFLICT DO UPDATE — то же, что INSERT OR REPLACE в SQLite."""
        sets = ", ".join('%s = EXCLUDED.%s' % (c, c)
                         for c in columns if c not in conflict)
        sql = ("INSERT INTO %s (%s) VALUES (%s) ON CONFLICT (%s) DO UPDATE SET %s"
               % (table, ", ".join(columns), ", ".join("?" * len(columns)),
                  ", ".join(conflict), sets))
        self.executemany(sql, rows)

    def columns(self, table):
        cur = self.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = ?", (table,))
        return {r["column_name"] for r in cur.fetchall()}

    def create_schema(self, schema_sql):
        for statement in pg_schema(schema_sql):
            self.execute(statement)
        self.commit()

    def create_function(self, *args, **kwargs):
        # В Postgres LOWER знает кириллицу сам, и свою функцию заводить
        # не нужно; запрос выбирает форму через storage.lower().
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        return False

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    @property
    def raw(self):
        return self._conn


# --- перевод схемы --------------------------------------------------------

def _pg_type(decl):
    decl = (decl or "").upper()
    if "INT" in decl:
        return "BIGINT"
    if "REAL" in decl or "FLOA" in decl or "DOUB" in decl:
        return "DOUBLE PRECISION"
    if "BLOB" in decl:
        return "BYTEA"
    return "TEXT"


def pg_schema(schema_sql):
    """CREATE TABLE для Postgres, собранные из той же схемы SQLite.

    DDL исполняется в базе в памяти, и состав таблиц читается уже оттуда:
    так перевод не зависит от того, как именно написан текст схемы —
    комментарии, переносы, CHECK и прочее разбирает сам SQLite.
    """
    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    mem.executescript(schema_sql)
    out = []
    tables = [r["name"] for r in mem.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for table in tables:
        info = list(mem.execute("PRAGMA table_info(%s)" % table))
        sql = mem.execute("SELECT sql FROM sqlite_master WHERE name = ?",
                          (table,)).fetchone()["sql"] or ""
        serial = "AUTOINCREMENT" in sql.upper()
        pk = [(c["pk"], c["name"]) for c in info if c["pk"]]
        cols = []
        for c in info:
            piece = '%s %s' % (c["name"], _pg_type(c["type"]))
            if c["pk"] and len(pk) == 1 and "INT" in (c["type"] or "").upper():
                # Ключ-счётчик: значения бывают и свои (перенос), поэтому
                # BY DEFAULT, а не ALWAYS.
                piece += " GENERATED BY DEFAULT AS IDENTITY"
            if c["notnull"]:
                piece += " NOT NULL"
            if c["dflt_value"] is not None and not c["pk"]:
                piece += " DEFAULT %s" % c["dflt_value"]
            cols.append(piece)
        if pk:
            cols.append("PRIMARY KEY (%s)" % ", ".join(n for _, n in sorted(pk)))
        # UNIQUE в SQLite живёт не в table_info, а в служебных индексах, и
        # без этого шага уникальность логина просто не переехала бы: второй
        # такой же аккаунт создавался бы молча.
        for idx in mem.execute("PRAGMA index_list(%s)" % table):
            if idx["unique"] and idx["origin"] in ("u", "pk"):
                names = [r["name"] for r in
                         mem.execute("PRAGMA index_info(%s)" % idx["name"])]
                if names and names != [n for _, n in sorted(pk)]:
                    cols.append("UNIQUE (%s)" % ", ".join(names))
        out.append("CREATE TABLE IF NOT EXISTS %s (\n  %s\n)"
                   % (table, ",\n  ".join(cols)))
    # Индексы переносим как есть: их синтаксис в обеих базах одинаков.
    for row in mem.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"):
        out.append(re.sub(r"(?i)^CREATE INDEX", "CREATE INDEX IF NOT EXISTS",
                          row["sql"]))
    mem.close()
    return out


# --- вход -----------------------------------------------------------------

def lower(column):
    """Нижний регистр, одинаково понятный обеим базам.

    LOWER в SQLite folds только латиницу, поэтому там подставляется своя
    функция pylower; в Postgres LOWER справляется с кириллицей сам.
    """
    return "LOWER(%s)" % column if DB_URL else "pylower(%s)" % column


def connect(path=None):
    """Соединение с базой: Postgres, если задан LAVA_DB_URL, иначе файл."""
    if DB_URL:
        return PostgresDB(DB_URL)
    return SqliteDB(path)
