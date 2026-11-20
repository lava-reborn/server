#!/usr/bin/env python3
"""Queue an Eden assignment or early release for the game server.

    python tools/eden_sentence.py assign Tester16 --reason "Test" --yes --db TEST.db
    python tools/eden_sentence.py status Tester16 --db TEST.db
    python tools/eden_sentence.py release Tester16 --reason "Test finished" --yes --db TEST.db

Only the game applies assignments: an online character must change through
its owning session. Without --yes the tool only previews the proposed action.
Database access is the administrator's authority; there is no player command.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))

import accounts  # noqa: E402
import storage  # noqa: E402


def character(db, target):
    if str(target).isdigit():
        rows = db.execute("SELECT id, account_id, name FROM characters WHERE id = ?",
                           (int(target),)).fetchall()
    else:
        rows = db.execute("SELECT id, account_id, name FROM characters WHERE name = ?",
                           (str(target),)).fetchall()
    if len(rows) != 1:
        raise ValueError("character not found or name is ambiguous; use the character id")
    return dict(rows[0])


def queue(db, target, admin, reason, release=False):
    """Write only a queued command, never a character's sentence or position."""
    admin, reason = admin.strip(), reason.strip()
    if not admin or len(admin) > 100 or not reason or len(reason) > 1000:
        raise ValueError("admin (1..100 characters) and reason (1..1000) are required")
    row = character(db, target)
    kind = "eden_release" if release else "eden"
    action_id = db.insert(
        "INSERT INTO admin_actions (made_at, admin, kind, char_id, account_id, args_json)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (int(time.time()), admin, kind, row["id"], row["account_id"],
         json.dumps({"reason": reason}, ensure_ascii=False)), returning="id")
    db.commit()
    return action_id


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("assign", "release", "status"))
    parser.add_argument("character", help="exact character name or numeric id")
    parser.add_argument("--db", help="existing SQLite file; LAVA_DB_URL selects Postgres")
    parser.add_argument("--admin", default="console")
    parser.add_argument("--reason")
    parser.add_argument("--yes", action="store_true", help="enqueue the proposed action")
    args = parser.parse_args(argv)
    if args.db and storage.using_postgres():
        parser.error("--db is for local SQLite; clear LAVA_DB_URL before targeting a test file")
    path = args.db or accounts.DB_PATH
    if not storage.using_postgres() and not os.path.isfile(path):
        parser.error("database file does not exist; specify the running server's --db")
    if args.action != "status" and not args.reason:
        parser.error("--reason is required for assignment and release")
    db = storage.connect(path)
    try:
        row = character(db, args.character)
        if args.action == "status":
            rec = db.execute("SELECT * FROM char_eden WHERE char_id = ?",
                              (row["id"],)).fetchone()
            print(json.dumps(dict(rec) if rec is not None else None, ensure_ascii=False))
            return 0
        print("%s: %s (id %d); reason: %s" % (
            args.action, row["name"], row["id"], args.reason))
        if not args.yes:
            print("Preview only; add --yes to queue this action.")
            return 0
        action_id = queue(db, row["id"], args.admin, args.reason,
                          release=args.action == "release")
        print("Queued admin action %d; the game server applies it and records the result."
              % action_id)
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
