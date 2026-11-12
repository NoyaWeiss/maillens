"""Per-account analysis history for the Security Console (Phase 4).

Privacy and isolation design:
- No Gmail identity is needed. The add-on creates a random per-user account key (Apps Script user
  properties are private to each Google account) and sends it with each analysis. The backend never
  stores that key: rows are keyed by HMAC(server secret, key), so the stored id can't be reversed or
  forged without the server secret.
- Gmail message ids are stored only as HMAC(server secret, account id + message id).
- Stored per email: time, verdict, risk index, subject, sender, and the analysis result the add-on
  already showed. Never the message body. Retention: 30 days, at most MAX_PER_ACCOUNT emails.
- Dashboard access needs a one-time launch code minted by the add-on (API key + account key) at click
  time. The code is exchanged for a short-lived bearer session bound to that account only.
"""

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path

RETENTION_S = 30 * 24 * 3600
MAX_PER_ACCOUNT = 500
CODE_TTL_S = 120
SESSION_TTL_S = 8 * 3600
MAX_PENDING = 5000
SCAN_TTL_S = 15 * 60
SCAN_LIMIT = 50  # newest inbox messages per scan

_SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
  account TEXT NOT NULL, ref TEXT NOT NULL, first_ts REAL NOT NULL, ts REAL NOT NULL, count INTEGER NOT NULL,
  received REAL,
  verdict TEXT NOT NULL, score INTEGER, subject TEXT NOT NULL, sender TEXT NOT NULL, result TEXT NOT NULL,
  PRIMARY KEY (account, ref));
CREATE INDEX IF NOT EXISTS emails_by_time ON emails (account, ts);
"""


class History:
    def __init__(self, path: Path, secret: str) -> None:
        self._key = hashlib.sha256(b"maillens-history-v1|" + secret.encode()).digest()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.executescript(_SCHEMA)
        cols = {r[1] for r in self._db.execute("PRAGMA table_info(emails)")}
        if "received" not in cols:  # stores created before the received-time column
            self._db.execute("ALTER TABLE emails ADD COLUMN received REAL")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        self._lock = threading.Lock()
        self._codes: dict[str, tuple[str, str | None, str, float, str]] = {}
        self._sessions: dict[str, tuple[str, str | None, str, float, str]] = {}
        self._tickets: dict[str, tuple[str, int, str, float]] = {}  # ticket -> (account, range_s, unused, expiry)
        self._progress: dict[str, dict] = {}

    # ---------------------------------------------------------------- identifiers
    def _mac(self, *parts: str) -> str:
        return hmac.new(self._key, "|".join(parts).encode(), hashlib.sha256).hexdigest()[:32]

    def account_id(self, account_key: str) -> str:
        return self._mac("account", account_key)

    def message_ref(self, account: str, message_id: str) -> str:
        return self._mac("message", account, message_id)

    # ---------------------------------------------------------------- recording
    def record(self, account_key: str, message_id: str, subject: str, sender: str, result: dict,
               received: float | None = None) -> None:
        acct, now = self.account_id(account_key), time.time()
        ref = self.message_ref(acct, message_id)
        if not received or not 0 < received <= now + 300:
            received = None  # unknown or implausible: kept unknown, never replaced by the analysis time
        with self._lock:
            self._db.execute(
                "INSERT INTO emails (account, ref, first_ts, ts, count, received, verdict, score, subject, sender, result) "
                "VALUES (?,?,?,?,1,?,?,?,?,?,?) ON CONFLICT(account, ref) DO UPDATE SET "
                "ts=excluded.ts, count=count+1, received=COALESCE(excluded.received, received), verdict=excluded.verdict, score=excluded.score, "
                "subject=excluded.subject, sender=excluded.sender, result=excluded.result",
                (acct, ref, now, now, received, result["verdict"], result.get("score"), subject[:300], sender[:300], json.dumps(result)))
            self._db.execute("DELETE FROM emails WHERE ts < ?", (now - RETENTION_S,))
            self._db.execute("DELETE FROM emails WHERE account=? AND ref NOT IN (SELECT ref FROM emails WHERE account=? "
                             "ORDER BY ts DESC LIMIT ?)", (acct, acct, MAX_PER_ACCOUNT))
            self._db.commit()

    # ---------------------------------------------------------------- launch codes and sessions
    def _prune(self, table: dict, now: float) -> None:
        for k in [k for k, v in table.items() if v[3] < now]:
            del table[k]
        while len(table) >= MAX_PENDING:
            table.pop(next(iter(table)))

    def mint_code(self, account_key: str, message_id: str | None, label: str, scan_url: str = "") -> str:
        acct, now = self.account_id(account_key), time.time()
        ref = self.message_ref(acct, message_id) if message_id else None
        code = secrets.token_urlsafe(32)
        with self._lock:
            self._prune(self._codes, now)
            self._codes[code] = (acct, ref, label, now + CODE_TTL_S, scan_url)
        return code

    def redeem(self, code: str) -> tuple[str, dict] | None:
        now = time.time()
        with self._lock:
            entry = self._codes.pop(code, None)  # single use
            if not entry or entry[3] < now:
                return None
            acct, ref, label, _, scan_url = entry
            self._prune(self._sessions, now)
            token = secrets.token_urlsafe(32)
            self._sessions[token] = (acct, ref, label, now + SESSION_TTL_S, scan_url)
        context = ref if ref and self.get(acct, ref) else None
        return token, {"context": context, "account_label": label, "expires_in": SESSION_TTL_S, "scan_available": bool(scan_url)}

    def session(self, token: str) -> tuple[str, str | None, str, str] | None:
        with self._lock:
            s = self._sessions.get(token or "")
            if not s or s[3] < time.time():
                return None
            return s[0], s[1], s[2], s[4]

    # ---------------------------------------------------------------- inbox scan (Apps Script web app)
    def mint_ticket(self, acct: str, range_s: int) -> str:
        now = time.time()
        ticket = secrets.token_urlsafe(24)
        with self._lock:
            self._prune(self._tickets, now)
            self._tickets[ticket] = (acct, range_s, "", now + SCAN_TTL_S)
            self._progress[ticket] = {"state": "waiting", "total": 0, "done": 0, "skipped": 0, "failed": 0, "error": ""}
            for k in [k for k in self._progress if k not in self._tickets]:
                del self._progress[k]
        return ticket

    def ticket_for(self, ticket: str, account_key: str) -> tuple[str, int] | None:
        """The web app proves it runs as the same account: its private key must hash to the ticket's account."""
        with self._lock:
            t = self._tickets.get(ticket or "")
        if not t or t[3] < time.time() or not hmac.compare_digest(t[0], self.account_id(account_key)):
            return None
        return t[0], t[1]

    def update_progress(self, ticket: str, **fields) -> None:
        with self._lock:
            if ticket in self._progress:
                self._progress[ticket].update(fields)

    def progress(self, ticket: str, acct: str) -> dict | None:
        with self._lock:
            t = self._tickets.get(ticket or "")
            return dict(self._progress.get(ticket, {})) if t and t[0] == acct else None

    def known_refs(self, acct: str, message_ids: list[str]) -> list[str]:
        refs = {self.message_ref(acct, m): m for m in message_ids}
        if not refs:
            return []
        with self._lock:
            rows = self._db.execute(f"SELECT ref FROM emails WHERE account=? AND ref IN ({','.join('?' * len(refs))})",
                                    (acct, *refs)).fetchall()
        return [refs[r[0]] for r in rows]

    # ---------------------------------------------------------------- reads (always scoped to one account)
    def list(self, acct: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT ref, first_ts, ts, count, verdict, score, subject, sender, result, received FROM emails "
                                    "WHERE account=? AND ts>=? ORDER BY received IS NULL, received DESC, ts DESC", (acct, time.time() - RETENTION_S)).fetchall()
        out = []
        for ref, first_ts, ts, count, verdict, score, subject, sender, result, received in rows:
            r = json.loads(result)
            out.append({"id": ref, "first_analyzed": first_ts, "analyzed_at": ts, "received_at": received,
                        "times_analyzed": count, "verdict": verdict,
                        "score": score, "subject": subject, "sender": sender, "category": r.get("category", ""),
                        "headline": r.get("headline", "")})
        return out

    def get(self, acct: str, ref: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT first_ts, ts, count, subject, sender, result, received FROM emails WHERE account=? AND ref=?",
                                   (acct, ref)).fetchone()
        if not row:
            return None
        first_ts, ts, count, subject, sender, result, received = row
        return {"id": ref, "first_analyzed": first_ts, "analyzed_at": ts, "received_at": received, "times_analyzed": count,
                "subject": subject, "sender": sender, "result": json.loads(result)}

    def clear(self, acct: str) -> int:
        with self._lock:
            n = self._db.execute("DELETE FROM emails WHERE account=?", (acct,)).rowcount
            self._db.commit()
        return n
