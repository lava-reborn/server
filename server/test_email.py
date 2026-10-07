"""An account's e-mail through the game's HTTP, as the site's forms use it
(server/email_flow.py, server/emailer.py): registration with an address, the
confirm link, «forgot password», the reset link, a changed address, the pace
of letters, and mail that is not set up. Letters go to a folder
(LAVA_MAIL_OUTBOX) and the links are read out of them. On SQLite in a folder
of its own, or on the database LAVA_DB_URL names (deploy/ci/pg_suites.sh).
"""
import email
import email.policy
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = tempfile.mkdtemp(prefix="lava_email_")
OUTBOX = os.path.join(WORK, "outbox")
SITE = "https://site.example"
os.environ.setdefault("LAVA_DB", os.path.join(WORK, "lava.db"))
sys.path.insert(0, HERE)

import accounts  # noqa: E402
import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(**extra):
    port = free_port()
    env = dict(os.environ, LAVA_HTTP_PORT=str(port), LAVA_SITE_URL=SITE,
               LAVA_SMTP_HOST="", LAVA_SMTP_USER="", LAVA_SMTP_PASSWORD="")
    env.update(extra)
    proc = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = []
    threading.Thread(target=lambda: log.extend(proc.stdout), daemon=True).start()
    base = "http://127.0.0.1:%d" % port
    end = time.time() + testkit.START_WAIT
    while time.time() < end:
        try:
            urllib.request.urlopen(base + "/status", timeout=1).read()
            break
        except Exception:
            if proc.poll() is not None:
                raise SystemExit("bootstrap http exited:\n" + "".join(log)[-2000:])
            time.sleep(0.1)
    else:
        raise SystemExit("bootstrap http did not start")
    return proc, base, log


def post(base, path, ip="203.0.113.1", **fields):
    """(status, decoded JSON or the page text) for a form posted as the site
    posts it, from the visitor ip as Caddy forwards it."""
    req = urllib.request.Request(
        base + path, data=urllib.parse.urlencode(fields).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "X-Forwarded-For": ip})
    try:
        r = urllib.request.urlopen(req, timeout=10)
        code, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        code, body = e.code, e.read()
    text = body.decode("utf-8", "replace")
    try:
        return code, json.loads(text)
    except ValueError:
        return code, text


def letters():
    out = []
    for path in sorted(glob.glob(os.path.join(OUTBOX, "*.eml"))):
        with open(path, "rb") as fh:
            msg = email.message_from_binary_file(fh, policy=email.policy.default)
        out.append(msg)
    return out


def wait_letters(n, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        got = letters()
        if len(got) >= n:
            return got
        time.sleep(0.05)
    return letters()


def link_of(msg, kind):
    text = msg.get_body(preferencelist=("plain",)).get_content()
    m = re.search(r"%s/#%s=([A-Za-z0-9_-]+)" % (re.escape(SITE), kind), text)
    return m.group(1) if m else None


def msg_of(page):
    m = re.search(r'class="msg (ok|err)">(.*?)</p>', page if isinstance(page, str) else "", re.S)
    return (m.group(1), re.sub("<[^>]+>", "", m.group(2))) if m else (None, page)


def store():
    return accounts.Store()


proc, BASE, LOG = start(LAVA_MAIL_OUTBOX=OUTBOX, LAVA_REGISTER_EMAIL="1")
tokens_seen = []
try:
    # --- registration -----------------------------------------------------
    code, page = post(BASE, "/register", login="Mailer", password="secret1")
    check("registration without an address is refused when one is required",
          msg_of(page)[0], "err")
    code, page = post(BASE, "/register", login="Mailer", password="secret1", email="not-an-address")
    check("a malformed address is refused", msg_of(page), ("err", "Это не похоже на адрес электронной почты"))
    s = store()
    check("and no account was made for either", s.account_by_login("Mailer"), None)
    s.close()

    code, page = post(BASE, "/register", login="Mailer", password="secret1", email=" Mailer@Example.COM ")
    state, text = msg_of(page)
    check("registration with an address goes through", state, "ok")
    check("and says a letter went", "mailer@example.com" in text, True)
    got = wait_letters(1)
    check("one letter in the outbox", len(got), 1)
    first = got[0]
    check("to the address, lower case", first["To"], "mailer@example.com")
    check("its subject", first["Subject"], "Подтвердите почту — Lava Reborn")
    check("a robot's letter", first["Auto-Submitted"], "auto-generated")
    check("text and HTML", sorted(p.get_content_type() for p in first.iter_parts()),
          ["text/html", "text/plain"])
    token = link_of(first, "confirm")
    tokens_seen.append(token)
    check("the link is the site's page with the token after #", bool(token), True)
    s = store()
    acc = s.account_by_login("Mailer")
    check("the address waits on the account, unconfirmed",
          (acc["email"], acc["email_ok"]), ("mailer@example.com", 0))
    check("only the token's digest is kept",
          s.db.execute("SELECT COUNT(*) c FROM email_tokens WHERE digest = ?", (token,)).fetchone()["c"], 0)
    s.close()

    # --- the confirm link --------------------------------------------------
    code, reply = post(BASE, "/account/confirm", t="nonsense")
    check("an unknown token", (code, reply), (200, {"ok": False, "state": "unknown"}))
    code, reply = post(BASE, "/account/confirm", t=token)
    check("the confirm link confirms", (code, reply), (200, {"ok": True, "state": "confirmed"}))
    code, reply = post(BASE, "/account/confirm", t=token)
    check("and is good once", reply, {"ok": False, "state": "used"})
    s = store()
    check("the account's address is confirmed", s.account_by_login("Mailer")["email_ok"], 1)
    s.close()
    req = urllib.request.Request(BASE + "/account/confirm?t=" + token)
    try:
        urllib.request.urlopen(req, timeout=5)
        status = 200
    except urllib.error.HTTPError as e:
        status = e.code
    check("a GET spends nothing: the link is a page's, not this server's", status, 404)

    # --- forgot ------------------------------------------------------------
    code, reply = post(BASE, "/account/forgot", who="mailer", ip="203.0.113.2")
    check("forgot by login, in another case", (code, reply["ok"]), (200, True))
    got = wait_letters(2)
    check("a reset letter went", len(got), 2)
    reset_letter = got[1]
    check("its subject", reset_letter["Subject"], "Новый пароль — Lava Reborn")
    rtoken = link_of(reset_letter, "reset")
    tokens_seen.append(rtoken)
    check("with a reset link", bool(rtoken), True)

    code, reply2 = post(BASE, "/account/forgot", who="nobody-here", ip="203.0.113.2")
    check("an unknown login gets the very same answer", reply2, reply)
    code, reply3 = post(BASE, "/account/forgot", who="mailer@example.com", ip="203.0.113.2")
    check("a second letter inside a minute is not sent, and the answer is the same",
          (reply3, len(wait_letters(3, timeout=1))), (reply, 2))

    # --- reset ---------------------------------------------------------------
    code, reply = post(BASE, "/account/reset", t=rtoken, password="abc")
    check("a short password is refused", (code, reply["ok"]), (400, False))
    code, reply = post(BASE, "/account/reset", t=rtoken, password="newsecret")
    check("and the link was not spent by it: the new password is set",
          (code, reply), (200, {"ok": True, "login": "Mailer"}))
    s = store()
    check("the new password is the account's",
          bool(s.by_credential(accounts.credential("Mailer", "newsecret"))), True)
    check("the old one no longer is",
          s.by_credential(accounts.credential("Mailer", "secret1")), None)
    kicks = s.db.execute("SELECT admin, account_id, args_json FROM admin_actions"
                         " WHERE kind = 'kick'").fetchall()
    check("whoever plays on the account is put out, through the admin queue",
          [(r["admin"], r["account_id"]) for r in kicks],
          [("Lava Reborn", s.account_by_login("Mailer")["id"])])
    check("  ..and told why", "Пароль аккаунта сменён" in kicks[0]["args_json"], True)
    s.close()
    code, reply = post(BASE, "/account/reset", t=rtoken, password="another1")
    check("a reset link is good once", (code, reply["ok"]), (400, False))

    # --- an account with no confirmed address -------------------------------
    code, page = post(BASE, "/register", login="Unsure", password="pass99", email="unsure@example.com")
    check("a second account", msg_of(page)[0], "ok")
    n = len(wait_letters(3))
    post(BASE, "/account/forgot", who="Unsure", ip="203.0.113.3")
    check("no reset goes to an address never confirmed", len(wait_letters(n + 1, timeout=1)), n)

    # --- the cabinet's form ----------------------------------------------------
    code, reply = post(BASE, "/account/email", login="Mailer", password="wrong", email="new@example.com",
                       ip="203.0.113.4")
    check("a wrong password changes nothing", (code, reply), (400, {"ok": False, "error": "Неверный пароль"}))
    code, reply = post(BASE, "/account/email", login="Mailer", password="newsecret", email="mailer@example.com",
                       ip="203.0.113.4")
    check("the confirmed address again", reply["error"], "Этот адрес уже подтверждён")
    s = store()
    # The reset above was a letter less than a minute ago: let it be older.
    s.db.execute("UPDATE email_tokens SET created = created - 120")
    s.db.commit()
    s.close()
    n = len(letters())
    code, reply = post(BASE, "/account/email", login="Mailer", password="newsecret", email="new@example.com",
                       ip="203.0.113.4")
    check("a new address: a letter to it", (code, reply["ok"]), (200, True))
    got = wait_letters(n + 1)
    check("to the new address", got[-1]["To"], "new@example.com")
    ctoken = link_of(got[-1], "confirm")
    tokens_seen.append(ctoken)
    s = store()
    check("the confirmed address stays until the new one is confirmed",
          (s.account_by_login("Mailer")["email"], s.account_by_login("Mailer")["email_ok"]),
          ("mailer@example.com", 1))
    s.close()
    code, reply = post(BASE, "/account/email", login="Mailer", password="newsecret", email="other@example.com",
                       ip="203.0.113.4")
    check("a second letter inside a minute is refused here, and said so",
          (code, reply["error"]), (429, "Письмо уже отправлено, следующее можно запросить через минуту"))
    post(BASE, "/account/confirm", t=ctoken)
    s = store()
    check("confirmed, the new address is the account's",
          (s.account_by_login("Mailer")["email"], s.account_by_login("Mailer")["email_ok"]),
          ("new@example.com", 1))
    check("and a reset by the old address finds nothing",
          s.accounts_by_email("mailer@example.com"), [])
    s.close()

    # --- expiry --------------------------------------------------------------
    s = store()
    acc = s.account_by_login("Mailer")
    old = s.issue_email_token(acc["id"], "reset", acc["email"], 3600, now=1000)
    check("a link past its hour is refused", s.take_email_token(old, "reset")[1], "expired")
    check("a confirm token is not a reset token",
          s.take_email_token(s.issue_email_token(acc["id"], "confirm", "x@example.com", 60), "reset")[1],
          "unknown")
    s.close()

    # --- the pace by asker --------------------------------------------------------
    codes = [post(BASE, "/account/forgot", who="nobody%d" % i, ip="198.51.100.9")[0] for i in range(11)]
    check("ten requests an hour from one address, the eleventh refused",
          (codes[:10].count(200), codes[10]), (10, 429))
    check("another address is not held by it",
          post(BASE, "/account/forgot", who="nobody", ip="198.51.100.10")[0], 200)

    # --- the log ---------------------------------------------------------------
    time.sleep(0.3)
    joined = "".join(LOG)
    check("letters are logged", joined.count("MAIL sent:") >= 4, True)
    check("no token in the log", [t for t in tokens_seen if t and t in joined], [])
    check("no full address in the log", "mailer@example.com" in joined, False)
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

# --- mail not set up -----------------------------------------------------------
proc, BASE, LOG = start(LAVA_MAIL_OUTBOX="", LAVA_REGISTER_EMAIL="0")
try:
    code, page = post(BASE, "/register", login="Plain", password="plain1")
    check("without the requirement, an account is made with no address", msg_of(page)[0], "ok")
    code, page = post(BASE, "/register", login="Later", password="later1", email="later@example.com")
    state, text = msg_of(page)
    check("an address given with mail off is kept, and the page says the letter waits",
          (state, "в кабинете" in text), ("ok", True))
    s = store()
    check("as waiting", (s.account_by_login("Later")["email"], s.account_by_login("Later")["email_ok"]),
          ("later@example.com", 0))
    s.close()
    code, reply = post(BASE, "/account/forgot", who="Later")
    check("forgot says mail is not set up", (code, reply["error"]), (503, "Почта на сервере ещё не настроена"))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("email OK")
