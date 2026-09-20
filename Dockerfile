# The server, and nothing of the game.
#
# res/ is the player's own copy of the client. It is not in the repository and
# it is not in this image; it arrives as a read-only mount at run time, and the
# server only ever reads locations, mobs.xml and objects.xml out of it. Without
# that mount the process stops at start rather than coming up half-built.
#
# One dependency, and only for the shared database: with SQLite the server
# runs on the standard library alone, and psycopg is what it needs when
# LAVA_DB_URL points it at Postgres instead.
FROM python:3.12-slim

# Единственная зависимость, и та появилась вместе с общей базой: с
# SQLite сервер работает стандартной библиотекой, драйвер нужен только
# когда задан LAVA_DB_URL. Ставится всегда, чтобы переключение было
# переменной окружения, а не пересборкой в неудобную минуту.
RUN pip install --no-cache-dir "psycopg[binary]==3.2.3"

# Unbuffered, or a container's log stays empty until the process dies; and no
# .pyc next to the source, which is read-only to the runtime user anyway.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Defaults that only make sense inside a container, so compose does not have to
# repeat them. Addresses are 0.0.0.0 because a published port never reaches the
# container's own loopback. The database lives on a volume, never in the layer.
ENV LAVA_HOST=0.0.0.0 \
    LAVA_PORT=9775 \
    LAVA_HTTP_HOST=0.0.0.0 \
    LAVA_HTTP_PORT=8080 \
    LAVA_HTTP_RES=0 \
    LAVA_POLICY_PORT=0 \
    LAVA_RES=/res \
    LAVA_DB=/var/lib/lava/lava.db \
    LAVA_LOG_LEVEL=INFO

# An unprivileged account, and the database directory made before the volume is
# mounted over it: docker gives a fresh named volume the ownership of the path
# it covers in the image, so this is what lets the server write there at all.
# It is also why LAVA_POLICY_PORT is 0 by default -- 843 is privileged, and the
# policy is answered inline on the game port regardless (server.py:1737).
RUN useradd --system --create-home --home-dir /home/lava lava \
 && mkdir -p /var/lib/lava \
 && chown lava:lava /var/lib/lava

WORKDIR /app
COPY server/ /app/server/
COPY data/ /app/data/
USER lava

# The modules import each other by bare name, the way every script and test in
# this tree runs them.
WORKDIR /app/server

EXPOSE 9775 8080
# Exec form on purpose: this process has to be the one docker signals. It
# installs handlers for SIGTERM and SIGINT and answers them by warning every
# session, saving where each player stands and closing the sockets, which a
# shell in front of it would swallow.
CMD ["python3", "server.py"]
