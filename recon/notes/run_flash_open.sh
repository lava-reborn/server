R=/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server
URL='http://127.0.0.1:8080/res/main.swf?logged=1&session=dev&vversion=1&var_host=127.0.0.1&var_port=9775&var_login=dev'
"$R/tools/flash/fp32_sa.exe" "$URL" > "$R/logs/flash.log" 2>&1
