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
* **Сколько строк задето.** `cursor.rowcount` есть у обоих курсоров.
* **Неудачный оператор.** В SQLite он соседей не трогает, в Postgres
  обрывает транзакцию целиком; поэтому соединение Postgres после ошибки
  откатывается само и остаётся годным.
* **Две перестройки схемы разом.** Файл SQLite запирает себя на запись
  сам, а в Postgres create_schema и migrate двух процессов сталкиваются;
  их разводит `schema_lock()`.

Из кода игры сюда ходят только `connect()` и методы соединения; ничего
специфичного для драйвера наружу не торчит.
"""
import contextlib
import os
import re
import sqlite3

DB_URL = os.environ.get("LAVA_DB_URL", "").strip()


class IntegrityError(Exception):
    """Нарушение уникальности — одинаково для обеих баз."""


class CommitError(Exception):
    """The driver failed to confirm COMMIT; its outcome may be unknown."""


@contextlib.contextmanager
def atomic(db):
    """Defer Store commits until the complete operation succeeds.

    SQLite reserves the writer before validation; PostgreSQL's caller locks
    the character. A caught inner failure still makes the unit rollback-only.
    """
    depth = getattr(db, "_atomic_depth", 0)
    if not depth:
        db.commit()
        db._atomic_failed = False
        db.execute("BEGIN IMMEDIATE" if isinstance(db, SqliteDB) else "BEGIN")
    db._atomic_depth = depth + 1
    try:
        yield db
        if not depth:
            if db._atomic_failed:
                raise RuntimeError("transaction was aborted by a nested operation")
            try:
                db.raw.commit()
            except Exception as exc:
                raise CommitError("could not confirm transaction commit") from exc
    except BaseException:
        db._atomic_failed = True
        if not depth:
            with contextlib.suppress(Exception):
                db.raw.rollback()
        raise
    finally:
        db._atomic_depth = depth
        if not depth:
            db._atomic_failed = False


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
        # REFERENCES в схеме — документация, а не ограничение, и так было
        # всегда (в SQLite это умолчание); здесь это сказано вслух, чтобы
        # никто не включил проверку «для порядка». Персонаж 0 — это «никто»,
        # и на нём держатся две вещи: вещи в мешке на земле
        # (items.char_id = combat.LOOT_OWNER) и письма аукциона
        # (mail.from_char = mail.SYSTEM_SENDER). С foreign_keys=ON каждое
        # такое письмо падало бы, а вместе с ним откатывалась бы вся
        # сделка: выкуп, ставка, возврат лота. test_auction.py это
        # проверяет.
        self._db.execute("PRAGMA foreign_keys=OFF")

    # --- общий интерфейс -------------------------------------------------
    def execute(self, sql, args=()):
        try:
            return self._db.execute(sql, args)
        except sqlite3.IntegrityError as exc:
            raise IntegrityError(str(exc))

    def executemany(self, sql, rows):
        try:
            return self._db.executemany(sql, rows)
        except sqlite3.IntegrityError as exc:
            raise IntegrityError(str(exc))

    def insert(self, sql, args=(), returning="id"):
        """Выполнить INSERT и вернуть новый идентификатор."""
        return self.execute(sql, args).lastrowid

    @contextlib.contextmanager
    def schema_lock(self):
        # Файл запирает себя сам на каждую запись; см. PostgresDB.
        yield self

    def add_column(self, table, column, decl):
        self._db.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, decl))

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
        if getattr(self, "_atomic_depth", 0):
            if exc[0] is not None:
                self._atomic_failed = True
            return False
        return self._db.__exit__(*exc)

    def create_schema(self, schema_sql):
        self._db.executescript(schema_sql)

    def commit(self):
        if not getattr(self, "_atomic_depth", 0):
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

    @property
    def rowcount(self):
        # Сколько строк задел последний UPDATE/DELETE — как у курсора
        # sqlite3. Без него update_mark падал на AttributeError, и
        # правка метки на карте не доходила до базы.
        return self._cur.rowcount

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

    def _abort(self):
        # Любая ошибка оператора в Postgres обрывает всю транзакцию, и до
        # отката соединение отвечает на всё «current transaction is
        # aborted». У сервера игры соединение одно на всех: один неудачный
        # запрос оставил бы без базы каждого игрока. В SQLite неудачный
        # оператор соседей не трогает, и здесь так же. Соединение, которого
        # уже нет, откатывать нечем: наверх уходит исходная ошибка.
        if getattr(self, "_atomic_depth", 0):
            self._atomic_failed = True
        try:
            self._conn.rollback()
        except self._psycopg.Error:
            pass

    def execute(self, sql, args=()):
        try:
            return self._cursor().execute(sql, args)
        except self._psycopg.errors.UniqueViolation as exc:
            self._abort()
            raise IntegrityError(str(exc))
        except self._psycopg.Error:
            self._abort()
            raise

    def executemany(self, sql, rows):
        cur = self._conn.cursor()
        try:
            cur.executemany(_qmarks_to_pg(sql), [tuple(r) for r in rows])
        except self._psycopg.errors.UniqueViolation as exc:
            self._abort()
            raise IntegrityError(str(exc))
        except self._psycopg.Error:
            self._abort()
            raise
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

    def add_column(self, table, column, decl):
        """ALTER TABLE ADD COLUMN с типом, переведённым так же, как в
        pg_schema. Объявление пишется на диалекте SQLite, а там INTEGER —
        64 бита; в Postgres INTEGER — 32, и досоздаваемые колонки
        (accounts.CHARACTER_COLUMNS) выходили бы уже остальных: деньги
        свежей базы упирались в 2 147 483 647, а в SQLite и в перенесённой
        sqlite_to_pg базе — нет."""
        kind, _, rest = decl.strip().partition(" ")
        self.execute("ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s %s %s"
                     % (table, column, _pg_type(kind), rest))

    # Ключ pg_advisory_lock: любое число, лишь бы одно у всех процессов.
    SCHEMA_LOCK = int.from_bytes(b"lavaschm", "big")

    @contextlib.contextmanager
    def schema_lock(self):
        """Схему и миграции проходит один процесс за раз на всю базу.

        Сервер игры и страница регистрации открывают базу одновременно
        (docker compose поднимает оба), и каждый делает CREATE TABLE IF NOT
        EXISTS, ALTER TABLE ADD COLUMN и run_once. В Postgres два таких
        прохода по новой схеме сталкиваются: второй CREATE TABLE падает на
        pg_type_typname_nsp_index, второй ALTER — на «column already
        exists», и процесс не поднимается. Замок сессии, а не транзакции:
        create_schema и migrate фиксируют свои транзакции сами, а
        отпускается он только здесь.
        """
        self._conn.execute("SELECT pg_advisory_lock(%s)", (self.SCHEMA_LOCK,))
        try:
            yield self
        except BaseException:
            # Наверх уходит та ошибка, из-за которой мы здесь. Если умерло
            # само соединение, снять замок тоже не выйдет — и не нужно:
            # замок сессии Postgres снимает сам, когда сессия кончается. А
            # исключение из снятия заняло бы место исходного, и в журнале
            # вместо причины осталось бы «the connection is closed».
            try:
                self._schema_unlock()
            except self._psycopg.Error:
                pass
            raise
        self._schema_unlock()

    def _schema_unlock(self):
        if self._conn.info.transaction_status == \
                self._psycopg.pq.TransactionStatus.INERROR:
            self._conn.rollback()
        self._conn.execute("SELECT pg_advisory_unlock(%s)", (self.SCHEMA_LOCK,))
        self._conn.commit()

    def create_function(self, *args, **kwargs):
        # В Postgres LOWER знает кириллицу сам, и свою функцию заводить
        # не нужно; запрос выбирает форму через storage.lower().
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if getattr(self, "_atomic_depth", 0):
            if exc_type is not None:
                self._atomic_failed = True
            return False
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        return False

    def commit(self):
        if not getattr(self, "_atomic_depth", 0):
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

    REFERENCES не переносятся, и это намеренно, а не недосмотр: персонаж 0
    — «никто» (мешок на земле, письма аукциона), и внешний ключ в Postgres
    отверг бы каждую такую строку. См. SqliteDB.__init__.
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
