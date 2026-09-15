#!/usr/bin/env bash
# Launch the whole stack: game server, HTTP bootstrap, and the Ruffle player.
#
# Run from Git Bash on Windows. The two Python servers run inside WSL, because
# the Windows "python" is the Microsoft Store stub; WSL's mirrored networking
# makes them reachable from Windows on 127.0.0.1.
#
#   ./run.sh              start everything and open the client
#   ./run.sh servers      start only the servers (no player)
#   ./run.sh stop         stop the servers
set -u

REPO_WIN="C:/Users/gmkrt/OneDrive/Desktop/claude/lava-server"
REPO_WSL="/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server"
RES_WSL="/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"
GAME_PORT=9775
HTTP_PORT=8080
LOGDIR="$REPO_WSL/logs"

stop_servers() {
  wsl.exe -e bash -lc "pkill -f 'lava-server/server/server.py'; pkill -f 'lava-server/server/bootstrap_http.py'; true" >/dev/null 2>&1
  echo "servers stopped"
}

start_servers() {
  stop_servers
  wsl.exe -e bash -lc "mkdir -p '$LOGDIR'
    cd '$REPO_WSL/server'
    LAVA_HOST=0.0.0.0 LAVA_PORT=$GAME_PORT \
      nohup python3 server.py          > '$LOGDIR/game.log' 2>&1 &
    LAVA_RES='$RES_WSL' LAVA_HTTP_PORT=$HTTP_PORT \
    LAVA_GAME_HOST=127.0.0.1 LAVA_GAME_PORT=$GAME_PORT \
      nohup python3 bootstrap_http.py  > '$LOGDIR/http.log' 2>&1 &
    sleep 2" >/dev/null 2>&1

  local ok=1
  for _ in $(seq 1 20); do
    if curl -s -o /dev/null -m 2 "http://127.0.0.1:$HTTP_PORT/"; then ok=0; break; fi
    sleep 0.5
  done
  if [ $ok -ne 0 ]; then
    echo "HTTP bootstrap did not come up; see logs/http.log"
    return 1
  fi
  echo "game server : 127.0.0.1:$GAME_PORT"
  echo "http        : http://127.0.0.1:$HTTP_PORT/"
  echo "logs        : logs/game.log, logs/http.log"
}

case "${1:-all}" in
  stop)    stop_servers ;;
  servers) start_servers ;;
  all)
    start_servers || exit 1
    echo "starting Ruffle..."
    # -P sets flashvars; logged=1 is what makes the client fetch host, port and
    # hash from /exe/lavaclient/loaduser/ instead of the dead official domain.
    "$REPO_WIN/tools/ruffle/ruffle.exe" \
      --tcp-connections allow \
      --socket-allow "127.0.0.1:$GAME_PORT" \
      --base "http://127.0.0.1:$HTTP_PORT/res/" \
      --width 1024 --height 700 \
      -Plogged=1 -Psession=dev -Pvversion=1 \
      -Pvar_host=127.0.0.1 -Pvar_port=$GAME_PORT -Pvar_login=dev \
      "http://127.0.0.1:$HTTP_PORT/res/main.swf"
    ;;
  *) echo "usage: $0 [all|servers|stop]"; exit 2 ;;
esac
