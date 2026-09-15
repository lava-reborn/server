import io
raw = open("/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/names_check.txt", "rb").read()
print("  как cp1251:", raw.decode("cp1251"))
try:
    raw.decode("utf-8")
    print("  ВНИМАНИЕ: также валидный utf-8, кодировка неоднозначна")
except UnicodeDecodeError:
    print("  не utf-8, значит это именно cp1251 — то, что ждёт клиент")
