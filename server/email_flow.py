"""An account's e-mail: the address confirmed by a link, a forgotten password
replaced by one. The site's forms post here through bootstrap_http.py (the
/account/ paths); the letters leave through emailer.py.

  registration    an address given with the account is written as waiting
                  (accounts.email, email_ok 0) and a confirm link goes to it
  /account/email  the cabinet: login, the current password and an address.
                  It is checked like the game checks a login (the digest),
                  and a confirm link goes to the address. A confirmed
                  address stays the account's until the new one is
                  confirmed; the same form sends the link again
  /account/confirm  the link's token: the address becomes the account's own
  /account/forgot  a login or an address: a reset link to every account
                  that has it as its confirmed address. The answer is the
                  same whether there was one or not -- the form is no way
                  to learn who plays here or under which address
  /account/reset  the link's token and a new password

Both links are the site's own page with the token after a #
(https://lava-reborn.ru/#confirm=..., #reset=...): a browser never sends what
follows the # to a server, so no access log -- Caddy's, nginx's, this
process's -- ever holds a token, and a mail service that opens every link of
a letter to check it spends nothing, since only the page's script posts the
token here.

A link is good once: confirm for CONFIRM_TTL, reset for RESET_TTL. Only its
sha256 is kept (accounts.email_tokens). Letters are paced, each kind on its
own: one per account a minute and ACCOUNT_HOUR an hour, counted in the
database; IP_HOUR requests that may send one from an address an hour,
counted here. A reset link only ever goes to a confirmed address -- an
unconfirmed one may be anybody's typo.
"""
import collections
import os
import re
import threading
import time

import accounts
import emailer

SITE = os.environ.get("LAVA_SITE_URL", "https://lava-reborn.ru").strip().rstrip("/")
SUPPORT = os.environ.get("LAVA_SUPPORT_MAIL", "").strip() or emailer.USER or "support@lava-reborn.ru"
CONFIRM_TTL = 3 * 24 * 3600
RESET_TTL = 3600
ACCOUNT_GAP = 60
ACCOUNT_HOUR = 5
IP_HOUR = 10

# Pragmatic: one @, no spaces or the characters a header would choke on, a
# dot in the domain and a TLD of two or more. Letters of any script are let
# through (.рф); what the server cannot reach, the confirm link tells.
_EMAIL = re.compile(r"^[^@\s<>()\[\]\\,;:\"']{1,64}@[^@\s<>()\[\]\\,;:\"']{1,190}\.[^@\s<>()\[\]\\,;:\"'.]{2,63}$")

TOO_SOON = "Письмо уже отправлено, следующее можно запросить через минуту"
TOO_MANY = "Слишком много писем подряд, попробуйте через час"
NO_MAIL = "Почта на сервере ещё не настроена"


def clean_email(text):
    """(address in lower case, None) or (None, a message for the person)."""
    address = (text or "").strip().lower()
    if not address:
        return None, "Укажите электронную почту"
    if len(address) > 254 or not _EMAIL.match(address):
        return None, "Это не похоже на адрес электронной почты"
    return address, None


class _IpPace:
    """Requests that may send a letter, per address of the asker, in the
    last hour. The process's own memory: a restart forgets it, and the
    per-account pace in the database still holds."""

    def __init__(self):
        self._lock = threading.Lock()
        self._seen = collections.defaultdict(collections.deque)

    def allow(self, ip, now=None):
        now = now if now is not None else time.time()
        with self._lock:
            q = self._seen[ip]
            while q and q[0] < now - 3600:
                q.popleft()
            if len(q) >= IP_HOUR:
                return False
            q.append(now)
            if len(self._seen) > 10000:
                for key in [k for k, v in self._seen.items() if not v]:
                    del self._seen[key]
            return True


ip_pace = _IpPace()


def _account_pace(store, account_id, kind, now):
    """Counted by kind: a reset asked for right after registering is not
    held back by the confirm letter that registering sent."""
    if store.email_tokens_since(account_id, now - ACCOUNT_GAP, kind):
        return TOO_SOON
    if store.email_tokens_since(account_id, now - 3600, kind) >= ACCOUNT_HOUR:
        return TOO_MANY
    return None


# --- the letters ----------------------------------------------------------

def _letter(title, lines, link, button):
    """The same letter as text and as HTML: a greeting, a few lines, the
    link, a word on what to do if it was not you."""
    text = "\n\n".join(lines[:-1] + [link, lines[-1], "— Lava Reborn, %s" % SITE])
    esc = lambda s: (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    paras = "".join('<p style="margin:0 0 14px">%s</p>' % esc(p) for p in lines[:-1])
    html = (
        '<!doctype html><html><body style="margin:0;padding:24px;background:#16130f;'
        'font-family:Segoe UI,Arial,sans-serif;color:#e9e0d2">'
        '<div style="max-width:520px;margin:0 auto;background:#221d17;border-radius:12px;'
        'padding:28px 28px 20px">'
        '<h1 style="margin:0 0 18px;font-size:20px;color:#ff8a3d">%s</h1>%s'
        '<p style="margin:22px 0"><a href="%s" style="background:#ff7a1a;color:#16130f;'
        'text-decoration:none;font-weight:600;padding:12px 20px;border-radius:8px;'
        'display:inline-block">%s</a></p>'
        '<p style="margin:0 0 14px;font-size:13px;color:#a89c8b">Если кнопка не нажимается, '
        'скопируйте ссылку в браузер:<br><span style="word-break:break-all">%s</span></p>'
        '<p style="margin:0 0 14px;font-size:13px;color:#a89c8b">%s</p>'
        '<p style="margin:18px 0 0;font-size:12px;color:#7d7264">Lava Reborn · '
        '<a href="%s" style="color:#a89c8b">%s</a></p></div></body></html>'
        % (esc(title), paras, esc(link), esc(button), esc(link), esc(lines[-1]),
           esc(SITE), esc(SITE.split("//", 1)[-1])))
    return text, html


def _send_confirm(store, account, address, now):
    token = store.issue_email_token(account["id"], "confirm", address, CONFIRM_TTL, now)
    link = "%s/#confirm=%s" % (SITE, token)
    title = "Подтвердите почту"
    text, html = _letter(title, [
        "Здравствуйте, %s!" % account["login"],
        "Этот адрес указан для аккаунта %s в Lava Reborn. Подтвердите его — "
        "через него восстанавливается пароль." % account["login"],
        "Ссылка действует три дня. Если вы не регистрировались у нас, просто "
        "удалите письмо: без подтверждения адрес к аккаунту не привяжется.",
    ], link, "Подтвердить почту")
    return emailer.send(address, "%s — Lava Reborn" % title, text, html)


def _send_reset(store, account, now):
    token = store.issue_email_token(account["id"], "reset", account["email"], RESET_TTL, now)
    link = "%s/#reset=%s" % (SITE, token)
    title = "Новый пароль"
    text, html = _letter(title, [
        "Здравствуйте, %s!" % account["login"],
        "Для аккаунта %s попросили сменить пароль. Задать новый можно по "
        "ссылке ниже." % account["login"],
        "Ссылка действует час и сработает один раз. Если вы ничего не просили, "
        "просто удалите письмо: пароль останется прежним.",
    ], link, "Задать новый пароль")
    return emailer.send(account["email"], "%s — Lava Reborn" % title, text, html)


# --- what the forms do ------------------------------------------------------

def on_register(store, account_id, address, now=None):
    """After registration with an address: written as waiting, a confirm
    link sent. Returns a line for the person."""
    now = int(now if now is not None else time.time())
    store.set_email_unconfirmed(account_id, address)
    if not emailer.enabled():
        return "Почту запомнили, но письма сейчас не уходят: подтвердите её позже в кабинете."
    if _send_confirm(store, store.account_by_id(account_id), address, now):
        return "На %s отправлено письмо: подтвердите почту по ссылке из него." % address
    return "Письмо для подтверждения отправить не удалось — попробуйте позже из кабинета."


def change_email(store, login, password, text, ip, now=None):
    """The cabinet's form. Returns (message, error)."""
    now = int(now if now is not None else time.time())
    address, err = clean_email(text)
    if err:
        return None, err
    login = (login or "").strip()
    account = store.by_credential(accounts.credential(login, password or ""))
    if not account or account["login"] != login:
        return None, "Неверный пароль"
    if account["banned"]:
        return None, "Аккаунт заблокирован"
    if account["email_ok"] and account["email"] == address:
        return None, "Этот адрес уже подтверждён"
    if not emailer.enabled():
        return None, NO_MAIL
    if not ip_pace.allow(ip, now):
        return None, TOO_MANY
    err = _account_pace(store, account["id"], "confirm", now)
    if err:
        return None, err
    store.set_email_unconfirmed(account["id"], address)
    if not _send_confirm(store, account, address, now):
        return None, "Письмо отправить не удалось, попробуйте позже"
    if account["email_ok"]:
        return ("Письмо отправлено на %s. Пока новый адрес не подтверждён, "
                "действует прежний." % address), None
    return "Письмо отправлено на %s: подтвердите почту по ссылке из него." % address, None


def confirm(store, token, now=None):
    """The confirm link. Returns 'confirmed', 'used', 'expired' or 'unknown'."""
    row, why = store.take_email_token(token, "confirm", now)
    if not row:
        return why
    if not store.account_by_id(row["account_id"]):
        return "unknown"
    store.confirm_email(row["account_id"], row["email"])
    return "confirmed"


def forgot(store, who, ip, now=None):
    """The «forgot password» form. Returns (message, error): the message is
    the same whether a letter went or not."""
    now = int(now if now is not None else time.time())
    who = (who or "").strip()
    if not who:
        return None, "Укажите логин или почту"
    if not emailer.enabled():
        return None, NO_MAIL
    if not ip_pace.allow(ip, now):
        return None, TOO_MANY
    if "@" in who:
        address, err = clean_email(who)
        if err:
            return None, err
        found = store.accounts_by_email(address)
    else:
        account = store.account_by_login_loose(who)
        found = [account] if account and account["email_ok"] and account["email"] else []
    for account in found:
        if account["banned"] or _account_pace(store, account["id"], "reset", now):
            continue
        _send_reset(store, account, now)
    return ("Если у аккаунта есть подтверждённая почта, письмо со ссылкой уже "
            "в пути — проверьте и папку «Спам». Почты не было — напишите на %s "
            "с адреса, который поможет нам вас узнать." % SUPPORT), None


def reset(store, token, password, now=None):
    """The reset link's form. Returns (login, error)."""
    if not password:
        return None, "Введите пароль"
    if len(password) < 4:
        return None, "Пароль короче четырёх символов"
    row, why = store.take_email_token(token, "reset", now)
    if not row:
        return None, {"used": "Ссылка уже использована — запросите новое письмо",
                      "expired": "Ссылка устарела — запросите новое письмо"}.get(
                          why, "Ссылка не подходит — запросите новое письмо")
    account = store.account_by_id(row["account_id"])
    if not account:
        return None, "Аккаунта больше нет"
    err = store.set_password(account["id"], password)
    if err:
        return None, err
    return account["login"], None
