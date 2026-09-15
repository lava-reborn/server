#!/usr/bin/env bash
# Launch the whole stack: game server, HTTP bootstrap, and a Flash player.
#
#   ./run.sh              start everything and open the client
#   ./run.sh servers      start only the servers
#   ./run.sh stop         stop the servers
#   ./run.sh log          follow the game server log
#
# Works from either Git Bash on Windows or a WSL shell; it detects which one it
# is in. The Python servers always run inside WSL, because the Windows "python"
# is the Microsoft Store stub. WSL mirrored networking makes them reachable
# from Windows on 127.0.0.1, so the player can talk to them.
#
# LAVA_PLAYER=ruffle switches to Ruffle. It gets as far as walking around, but
# draws the whole interface into roughly 313x107 stage units regardless of
# window size: it logs ~172 AVM1 stack underflows while main.swf loads, and the
# layout assignments in SceneShifter.setMCSize do not survive that. The 0.7.0
# nightly behaves the same. The original projector renders correctly.
set -u

REPO_WIN="C:/Users/gmkrt/OneDrive/Desktop/claude/lava-server"
REPO_WSL="/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server"
RES_WSL="/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"
GAME_PORT=9775
HTTP_PORT=8080
PLAYER=${LAVA_PLAYER:-flash}

if grep -qi microsoft /proc/version 2>/dev/null; then IN_WSL=1; else IN_WSL=0; fi
if [ "$IN_WSL" = 1 ]; then ROOT="$REPO_WSL"; else ROOT="$REPO_WIN"; fi

# Launched by absolute path so this pattern matches their argv exactly; a bare
# "python3 server.py" would be both unmatchable here and far too broad to pkill.
PATTERN="$REPO_WSL/server/(server|bootstrap_http).py"

# Run a command inside WSL, whichever side we were started from.
in_wsl() {
  if [ "$IN_WSL" = 1 ]; then bash -lc "$1"; else wsl.exe -e bash -lc "$1"; fi
}

port_free() {  # $1 = port; true when nothing is listening
  ! in_wsl "ss -ltn 2>/dev/null | grep -q ':$1 '"
}

stop_servers() {
  in_wsl "pkill -f '$PATTERN'; true" >/dev/null 2>&1
  for _ in $(seq 1 20); do
    if port_free "$GAME_PORT" && port_free "$HTTP_PORT"; then
      echo "servers stopped"; return 0
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
    LAVA_HOST=0.0.0.0 LAVA_PORT=$GAME_PORT \
      nohup python3 '$REPO_WSL/server/server.py'         > '$REPO_WSL/logs/game.log' 2>&1 &
    LAVA_RES='$RES_WSL' LAVA_HTTP_PORT=$HTTP_PORT \
    LAVA_GAME_HOST=127.0.0.1 LAVA_GAME_PORT=$GAME_PORT \
      nohup python3 '$REPO_WSL/server/bootstrap_http.py' > '$REPO_WSL/logs/http.log' 2>&1 &
    sleep 1" >/dev/null 2>&1

  # Both ports listening AND both processes alive. Checking only that the HTTP
  # port answers would pass against a leftover server from a previous run.
  for _ in $(seq 1 20); do
    if ! port_free "$GAME_PORT" && ! port_free "$HTTP_PORT" \
       && [ "$(in_wsl "pgrep -c -f '$PATTERN'" 2>/dev/null | tr -d '\r')" = "2" ]; then
      echo "game server : 127.0.0.1:$GAME_PORT"
      echo "http        : http://127.0.0.1:$HTTP_PORT/"
      echo "logs        : logs/game.log   (./run.sh log)"
      return 0
    fi
    sleep 0.5
  done
  echo "servers failed to start:"
  in_wsl "tail -n 3 '$REPO_WSL/logs/game.log' '$REPO_WSL/logs/http.log'" 2>&1 | sed 's/^/  /'
  return 1
}

start_player() {
  # logged=1 is what sends the client down the loaduser path, where it takes
  # our host, port and login hash, instead of the official domain that is now
  # dead. The projector takes no flashvars on the command line, so they ride
  # in the SWF's query string, which Flash unpacks into _root exactly the same.
  local vars="logged=1&session=dev&vversion=1&var_host=127.0.0.1&var_port=$GAME_PORT&var_login=dev"
  local url="http://127.0.0.1:$HTTP_PORT/res/main.swf?$vars"

  if [ "$PLAYER" = "ruffle" ]; then
    local exe="$ROOT/tools/ruffle/ruffle.exe"
    [ -f "$exe" ] || { echo "Ruffle not found at $exe"; return 1; }
    echo "player      : Ruffle (interface will render undersized)"
    "$exe" --tcp-connections allow --socket-allow "127.0.0.1:$GAME_PORT" \
      --base "http://127.0.0.1:$HTTP_PORT/res/" --width 950 --height 650 \
      -Plogged=1 -Psession=dev -Pvversion=1 \
      -Pvar_host=127.0.0.1 -Pvar_port=$GAME_PORT -Pvar_login=dev \
      "http://127.0.0.1:$HTTP_PORT/res/main.swf"
    return
  fi

  local exe="$ROOT/tools/flash/fp32_sa.exe"
  if [ ! -f "$exe" ]; then
    echo "Flash projector not found at $exe"
    echo "fetch it with:"
    echo "  curl -L -o tools/flash/fp32_sa.exe \\"
    echo "    https://fpdownload.macromedia.com/pub/flashplayer/updaters/32/flashplayer_32_sa.exe"
    return 1
  fi
  echo "player      : Flash projector 32.0.0.465"
  "$exe" "$url"
}

case "${1:-all}" in
  stop)    stop_servers ;;
  servers) start_servers ;;
  log)     in_wsl "tail -f '$REPO_WSL/logs/game.log'" ;;
  all)     start_servers && start_player ;;
  *)       echo "usage: $0 [all|servers|stop|log]"; exit 2 ;;
esac
