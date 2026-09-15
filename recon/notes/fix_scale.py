import io
BS = chr(92)   # backslash, kept out of the source to survive the heredoc
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/run.sh"
lines = io.open(p, encoding="utf-8").read().split("\n")
out = []
for ln in lines:
    if ln.strip() == "HTTP_PORT=8080":
        out.append(ln)
        out += [
            "# main.swf declares a 950x650 stage and sets Stage.scaleMode to",
            '# "noScale" in its first frame. In a larger window it therefore draws',
            "# at that exact size in a corner while SceneShifter lays the UI out",
            "# against the window size, which pulls the interface apart. Forcing",
            "# show-all pins the reported stage to 950x650, where every centring",
            "# offset in SceneShifter.setMCSize works out to zero, and lets Ruffle",
            "# scale the whole picture up to the window.",
            "STAGE_W=950",
            "STAGE_H=650",
            "ZOOM=${LAVA_ZOOM:-15}   # tenths of the stage size; 15 means 1.5x",
        ]
        continue
    if "--width 1024 --height 700" in ln:
        out.append("    --scale show-all --force-scale --letterbox on " + BS)
        out.append('    --width "$w" --height "$h" ' + BS)
        continue
    if ln.strip().startswith('"$exe" ' + BS):
        out.append("  local w=$(( STAGE_W * ZOOM / 10 ))")
        out.append("  local h=$(( STAGE_H * ZOOM / 10 ))")
        out.append('  echo "window      : ${w}x${h}  (stage ${STAGE_W}x${STAGE_H})"')
        out.append(ln)
        continue
    out.append(ln)
io.open(p, "w", encoding="utf-8").write("\n".join(out))
print("run.sh patched")
