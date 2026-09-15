R=/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server
LOG=$R/logs/ruffle.log
rm -f "$LOG"
RUST_LOG=warn timeout 40 "$R/tools/ruffle/ruffle.exe" \
  --tcp-connections allow \
  --socket-allow 127.0.0.1:9775 \
  --base http://127.0.0.1:8080/res/ \
  --width 950 --height 650 \
  -Plogged=1 -Psession=dev -Pvversion=1 \
  -Pvar_host=127.0.0.1 -Pvar_port=9775 -Pvar_login=dev \
  http://127.0.0.1:8080/res/main.swf > "$LOG" 2>&1
echo "ruffle завершился, строк в логе: $(wc -l < "$LOG")"
