import io
BS = chr(92)
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/run.sh"
lines = io.open(p, encoding="utf-8").read().split("\n")
out, skip = [], 0
for i, ln in enumerate(lines):
    if skip:
        skip -= 1
        continue
    if ln.startswith("ZOOM="):
        out.append("# ZOOM is in tenths of the stage. 10 keeps the window at exactly the")
        out.append("# stage size, which is the only setting guaranteed to line up: the")
        out.append("# client lays the game scene out from Stage.width, so any mismatch")
        out.append("# between the reported stage and the real window leaves the scene")
        out.append("# sitting in a corner. Anything above 10 forces show-all, which pins")
        out.append("# the stage to 950x650 and lets Ruffle scale the picture instead.")
        out.append("ZOOM=${LAVA_ZOOM:-10}")
        continue
    if "--scale show-all --force-scale --letterbox on" in ln:
        out.append('    $SCALE_FLAGS ' + BS)
        continue
    if ln.strip().startswith("local w=$(( STAGE_W"):
        out.append("  local w=$(( STAGE_W * ZOOM / 10 ))")
        out.append("  local h=$(( STAGE_H * ZOOM / 10 ))")
        out.append("  local SCALE_FLAGS=")
        out.append("  local mode='native 1:1'")
        out.append("  if [ $ZOOM -ne 10 ]; then")
        out.append("    SCALE_FLAGS='--scale show-all --force-scale --letterbox on'")
        out.append("    mode='scaled'")
        out.append("  fi")
        skip = 2   # drop the old local h= and echo lines
        out.append('  echo "window      : ${w}x${h}  stage ${STAGE_W}x${STAGE_H}  ($mode)"')
        continue
    out.append(ln)
io.open(p, "w", encoding="utf-8").write("\n".join(out))
print("patched")
