cd /tmp && echo "wsl-reachable" > probe.txt
python3 -m http.server 18099 --bind 0.0.0.0 >/dev/null 2>&1 &
SRV=$!
sleep 2
echo "started pid $SRV"
