import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/run.sh"
s = io.open(p, encoding="utf-8").read()

start = s.index("stop_servers() {")
end = s.index("start_player() {")
new = '''# The servers are launched by absolute path so that this pattern matches their
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
    LAVA_HOST=0.0.0.0 LAVA_PORT=$GAME_PORT \
      nohup python3 '$REPO_WSL/server/server.py'         > '$REPO_WSL/logs/game.log' 2>&1 &
    LAVA_RES='$RES_WSL' LAVA_HTTP_PORT=$HTTP_PORT \
    LAVA_GAME_HOST=127.0.0.1 LAVA_GAME_PORT=$GAME_PORT \
      nohup python3 '$REPO_WSL/server/bootstrap_http.py' > '$REPO_WSL/logs/http.log' 2>&1 &
    sleep 1" >/dev/null 2>&1

  # Both ports must be listening AND both processes still alive. Checking only
  # that the HTTP port answers would pass against a leftover server.
  local ok=1
  for _ in $(seq 1 20); do
    if ! port_free "$GAME_PORT" && ! port_free "$HTTP_PORT" \
       && [ "$(in_wsl "pgrep -c -f '$PATTERN'" 2>/dev/null | tr -d '\r')" = "2" ]; then
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

'''
io.open(p, "w", encoding="utf-8").write(s[:start] + new + s[end:])
print("run.sh patched")
