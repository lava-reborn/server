"""Letters to players' own mailboxes: an address to confirm, a link for a new
password (email_flow.py). Not the game's mail between characters -- that is
the mail table and mail.py's business.

Configuration (docker-compose.yml passes it to the http service from .env):

  LAVA_SMTP_HOST      the server to hand letters to (smtp.mail.ru); empty
                      means none leave, and the page says mail is not set up
  LAVA_SMTP_PORT      465, TLS from the first byte (the default), or 587 with
                      STARTTLS
  LAVA_SMTP_USER      the mailbox that sends (support@lava-reborn.ru)
  LAVA_SMTP_PASSWORD  its password for outside programs: Mail.ru takes no
                      account password over SMTP, only one made under
                      «Безопасность → Пароли для внешних приложений»
  LAVA_MAIL_FROM      the From line, "Lava Reborn <LAVA_SMTP_USER>" by default
  LAVA_MAIL_OUTBOX    a folder: every letter is written there as a .eml file
                      instead of sent -- the suites read their links from it

A letter goes from a queue, on a thread of its own: the page that asked for
it answers at once, and an SMTP server that is slow or down holds no
request. Three tries, 10 and 60 seconds apart. The log names a letter by its
subject and a masked address, never by its link: the link opens the account.
"""
import email.message
import email.utils
import itertools
import os
import queue
import smtplib
import ssl
import threading
import time

import errlog

HOST = os.environ.get("LAVA_SMTP_HOST", "").strip()
PORT = int(os.environ.get("LAVA_SMTP_PORT", "465") or 465)
USER = os.environ.get("LAVA_SMTP_USER", "").strip()
PASSWORD = os.environ.get("LAVA_SMTP_PASSWORD", "")
FROM = os.environ.get("LAVA_MAIL_FROM", "").strip() or (
    "Lava Reborn <%s>" % USER if USER else "Lava Reborn <noreply@localhost>")
OUTBOX = os.environ.get("LAVA_MAIL_OUTBOX", "").strip()
PAUSES = (10, 60)
TIMEOUT = 30

_queue = queue.Queue(maxsize=500)
_lock = threading.Lock()
_worker = None
_seq = itertools.count(1)


def enabled():
    """Whether a letter can leave at all: a server to hand it to, or the
    suites' folder."""
    return bool(OUTBOX or (HOST and USER and PASSWORD))


def masked(address):
    """g.mkrtchyan.m@gmail.com -> g***@gmail.com, for the log."""
    local, _, domain = (address or "").partition("@")
    return "%s***@%s" % (local[:1], domain) if domain else "***"


def build(to, subject, text, html=None):
    msg = email.message.EmailMessage()
    msg["From"] = FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=False, usegmt=True)
    domain = email.utils.parseaddr(FROM)[1].rpartition("@")[2] or "localhost"
    msg["Message-ID"] = email.utils.make_msgid(domain=domain)
    # A robot's letter: an out-of-office reply has nobody to answer.
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _deliver(msg):
    if OUTBOX:
        os.makedirs(OUTBOX, exist_ok=True)
        path = os.path.join(OUTBOX, "%06d-%d.eml" % (next(_seq), os.getpid()))
        with open(path + ".tmp", "wb") as fh:
            fh.write(bytes(msg))
        os.replace(path + ".tmp", path)
        return
    context = ssl.create_default_context()
    if PORT == 465:
        with smtplib.SMTP_SSL(HOST, PORT, timeout=TIMEOUT, context=context) as smtp:
            smtp.login(USER, PASSWORD)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(HOST, PORT, timeout=TIMEOUT) as smtp:
            smtp.starttls(context=context)
            smtp.login(USER, PASSWORD)
            smtp.send_message(msg)


def _run():
    while True:
        msg = _queue.get()
        name = "%s to %s" % (msg["Subject"], masked(msg["To"]))
        for attempt, pause in enumerate((0,) + PAUSES, 1):
            if pause:
                time.sleep(pause)
            try:
                _deliver(msg)
                print("  MAIL sent: %s" % name, flush=True)
                break
            except Exception as exc:  # anything the SMTP side throws is worth a retry
                print("  MAIL try %d of %d failed: %s: %s: %s"
                      % (attempt, len(PAUSES) + 1, name, type(exc).__name__, exc), flush=True)
                # A failure is for the admin panel's error log as well
                # (errlog), from a logger that writes only there: the line
                # above stays as it was.
                errlog.only("lava.mail").warning(
                    "try %d of %d failed: %s: %s: %s",
                    attempt, len(PAUSES) + 1, name, type(exc).__name__, exc)
        else:
            print("  MAIL gave up: %s" % name, flush=True)
            errlog.only("lava.mail").error("gave up: %s", name)
        _queue.task_done()


def send(to, subject, text, html=None):
    """Queue a letter. False when mail is not set up or the queue is full --
    the caller tells the person so; True is no promise it arrives."""
    global _worker
    if not enabled():
        print("  MAIL off (no LAVA_SMTP_*): not sent: %s to %s" % (subject, masked(to)), flush=True)
        return False
    try:
        _queue.put_nowait(build(to, subject, text, html))
    except queue.Full:
        print("  MAIL queue full: not sent: %s to %s" % (subject, masked(to)), flush=True)
        errlog.only("lava.mail").warning("queue full: not sent: %s to %s",
                                         subject, masked(to))
        return False
    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="emailer", daemon=True)
            _worker.start()
    return True
