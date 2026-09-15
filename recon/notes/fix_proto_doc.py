import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/PROTOCOL.md"
s = io.open(p, encoding="utf-8").read()
old = "Кодировка кириллицы: CP1251 (`convertToCP1251` в клиенте)."
new = ("Кодировка: **UTF-8**. Flash разбирает трафик `XMLSocket` как UTF-8, если не\n"
       "включён `System.useCodepage`, а клиент выставляет его лишь в одной редко\n"
       "достижимой ветке экрана входа. Функция `convertToCP1251` относится к\n"
       "`MD5rus` и описывает только то, что подаётся на вход хешу пароля, а не то,\n"
       "что едет по проводу.\n"
       "\n"
       "Ошибка здесь не даёт внятного сбоя: разборщик клиента после каждой строки\n"
       "двигает курсор на её длину **в символах**, поэтому значение, раскодированное\n"
       "в другую длину, сдвигает все последующие поля кадра.")
assert old in s, "anchor missing"
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")
