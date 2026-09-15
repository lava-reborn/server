#!/usr/bin/env bash
# Launch the whole stack: game server, HTTP bootstrap, and the Ruffle player.
#
#   ./run.sh              start everything and open the client
#   ./run.sh servers      start only the servers
#   ./run.sh stop         stop the servers
#   ./run.sh log          follow the game server log
#
# Works from either Git Bash on Windows or a WSL shell; it detects which one
# it is in. The Python servers always run inside WSL, because the Windows
# "python" is the Microsoft Store stub. WSL mirrored networking makes them
# reachable from Windows on 127.0.0.1, so Ruffle can talk to them.
set -u

REPO_WIN="C:/Users/gmkrt/OneDrive/Desktop/claude/lava-server"
REPO_WSL="/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server"
RUFFLE_WSL="$REPO_WSL/tools/ruffle/ruffle.exe"
RES_WSL="/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"
GAME_PORT=9775
HTTP_PORT=8080

if grep -qi microsoft /proc/version 2>/dev/null; then IN_WSL=1; else IN_WSL=0; fi

# Run a command inside WSL, whichever side we were started from.
in_wsl() {
  if [ "$IN_WSL" = 1 ]; then bash -lc "$1"; else wsl.exe -e bash -lc "$1"; fi
}

# The servers are launched by absolute path so that this pattern matches their
# argv exactly; a bare "python3 server.py" would be both unmatchable here and
# dangerously broad to pkill.
PATTERN="$REPO_WSL/server/(server|bootstrap_http).py"

port_free() {  # $1 = port; true when nothing is listening
  ! in_wsl "ss -ltn 2>/dev/null | grep -q ':$1 '"
}

stop_servers() {
  in_wsl "pkill -f '$PATTERN'; true" >/dev/null 2>&1
  for _ in $(seq 1 20); do
    if port_free "$GAME_PORT" && port_free "$HTTP_PORT"; then
      echo "servers stopped"
      return 0
    fi
    sleep 0.25
  done
  in_wsl "pkill -9 -f '$PATTERN'; true" >/dev/null 2>&1
  sleep 1
  if port_free "$GAME_PORT" && port_free "$HTTP_PORT"; then
    echo "servers stopped"
  else
    echo "WARNING: ports $GAME_PORT/$HTTP_PORT still busy; something else holds them"
    in_wsl "ss -ltnp 2>/dev/null | grep -E ':$GAME_PORT |:$HTTP_PORT '" || true
    return 1
  fi
}

start_servers() {
  stop_servers || return 1
  in_wsl "mkdir -p '$REPO_WSL/logs'
    LAVA_HOST=0.0.0.0 LAVA_PORT=$GAME_PORT       nohup python3 '$REPO_WSL/server/server.py'         > '$REPO_WSL/logs/game.log' 2>&1 &
    LAVA_RES='$RES_WSL' LAVA_HTTP_PORT=$HTTP_PORT     LAVA_GAME_HOST=127.0.0.1 LAVA_GAME_PORT=$GAME_PORT       nohup python3 '$REPO_WSL/server/bootstrap_http.py' > '$REPO_WSL/logs/http.log' 2>&1 &
    sleep 1" >/dev/null 2>&1

  # Both ports must be listening AND both processes still alive. Checking only
  # that the HTTP port answers would pass against a leftover server.
  local ok=1
  for _ in $(seq 1 20); do
    if ! port_free "$GAME_PORT" && ! port_free "$HTTP_PORT"        && [ "$(in_wsl "pgrep -c -f '$PATTERN'" 2>/dev/null | tr -d '')" = "2" ]; then
      ok=0; break
    fi
    sleep 0.5
  done
  if [ $ok -ne 0 ]; then
    echo "servers failed to start:"
    in_wsl "tail -n 3 '$REPO_WSL/logs/game.log' '$REPO_WSL/logs/http.log'" 2>&1 | sed 's/^/  /'
    return 1
  fi
  echo "game server : 127.0.0.1:$GAME_PORT"
  echo "http        : http://127.0.0.1:$HTTP_PORT/"
  echo "logs        : logs/game.log   (./run.sh log)"
}

start_player() {
  # Windows path when launched from Git Bash, /mnt/c path when from WSL.
  local exe="$REPO_WIN/tools/ruffle/ruffle.exe"
  [ "$IN_WSL" = 1 ] && exe="$RUFFLE_WSL"
  if [ ! -x "$exe" ] && [ ! -f "$exe" ]; then
    echo "Ruffle not found at $exe"
    return 1
  fi
  echo "starting Ruffle..."
  # logged=1 is what sends the client down the loaduser path, where it takes
  # our host, port and hash, instead of the official domain that is now dead.
  "$exe" \
    --tcp-connections allow \
    --socket-allow "127.0.0.1:$GAME_PORT" \
    --base "http://127.0.0.1:$HTTP_PORT/res/" \
    --width 1024 --height 700 \
    -Plogged=1 -Psession=dev -Pvversion=1 \
    -Pvar_host=127.0.0.1 -Pvar_port=$GAME_PORT -Pvar_login=dev \
    "http://127.0.0.1:$HTTP_PORT/res/main.swf"
}

case "${1:-all}" in
  stop)    stop_servers ;;
  servers) start_servers ;;
  log)     in_wsl "tail -f '$REPO_WSL/logs/game.log'" ;;
  all)     start_servers && start_player ;;
  *)       echo "usage: $0 [all|servers|stop|log]"; exit 2 ;;
esac
