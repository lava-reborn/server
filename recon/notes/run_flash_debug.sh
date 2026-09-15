R=/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server
URL='http://127.0.0.1:8080/res/main.swf?vversion=1&var_host=127.0.0.1&var_port=9775'
"$R/tools/flash/fp32_sa_debug.exe" "$URL" > "$R/logs/flash.log" 2>&1
