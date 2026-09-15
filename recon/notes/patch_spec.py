import io
p="/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/PROTOCOL.md"
s=io.open(p,encoding="utf-8").read()
a=s.index("### Клиент → сервер")
b=s.index("### Сервер → клиент")
new = u"""### Клиент → сервер: 55 классов, 53 уникальные команды

Классы в `recon/as-src/lol/server/mess/CSM_*.as`. Имя на проводе — поле `_name`,
и оно НЕ совпадает с именем класса. Параметры — вызовы `addProp()` в конструкторе.
Полная таблица «команда → параметры»: `recon/notes/cs_commands.txt`. Группы:

- сессия: `hello`, `login`, `logout`, `actPlayer`, `selPers`, `newPers`, `resurrect`
- локация и движение: `lenter`, `moveTo` (3 формы: dx/dy, path, trg), `chWorld`
- метки карты: `insMark`, `updMark`, `rmMark`
- предметы: `ss_create`, `ss_get`, `ss_move`, `ss_use`, `ss_upd`, `ss_heap_c`, `ss_get_di`, `ss_get_si`, `ss_get_s_si`
- квесты: `q_list`, `q_st`, `q_ca`, `q_co`, `q_di`, `q_si`, `q_status`
- кланы: `admit`, `apply`, `head`, `gg_info`, `c_ga`
- почта: `chkml`, `getml`, `sndml`, `rmvml`, `uldml`
- аукцион: `ah_create`, `ah_op`, `ah_search`
- поля боя: `bg_op`
- прочее: `userMsg`, `on_conv`, `getInfo`, `p_op`, `rp_get_info`, `e_get_di`, `e_get_si`, `ts_get_si`

"""
s = s[:a] + new + s[b:]
s = s.replace(u"### Сервер → клиент: ~120 команд",
              u"### Сервер → клиент: 239 подписок")
io.open(p,"w",encoding="utf-8").write(s)
print("patched ok")
