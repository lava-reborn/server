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

stop_servers() {
  in_wsl "pkill -f 'lava-server/server/server.py'
          pkill -f 'lava-server/server/bootstrap_http.py'
          true" >/dev/null 2>&1
  echo "servers stopped"
}

start_servers() {
  stop_servers
  in_wsl "mkdir -p '$REPO_WSL/logs'
    cd '$REPO_WSL/server'
    LAVA_HOST=0.0.0.0 LAVA_PORT=$GAME_PORT \
      nohup python3 server.py         > '$REPO_WSL/logs/game.log' 2>&1 &
    LAVA_RES='$RES_WSL' LAVA_HTTP_PORT=$HTTP_PORT \
    LAVA_GAME_HOST=127.0.0.1 LAVA_GAME_PORT=$GAME_PORT \
      nohup python3 bootstrap_http.py > '$REPO_WSL/logs/http.log' 2>&1 &
    sleep 1" >/dev/null 2>&1

  for _ in $(seq 1 20); do
    if curl -s -o /dev/null -m 2 "http://127.0.0.1:$HTTP_PORT/"; then
      echo "game server : 127.0.0.1:$GAME_PORT"
      echo "http        : http://127.0.0.1:$HTTP_PORT/"
      echo "logs        : logs/game.log"
      return 0
    fi
    sleep 0.5
  done
  echo "HTTP bootstrap did not come up; see logs/http.log"
  return 1
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
