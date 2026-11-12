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

_SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
  account TEXT NOT NULL, ref TEXT NOT NULL, first_ts REAL NOT NULL, ts REAL NOT NULL, count INTEGER NOT NULL,
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
        try:
            path.chmod(0o600)
        except OSError:
            pass
        self._lock = threading.Lock()
        self._codes: dict[str, tuple[str, str | None, str, float]] = {}
        self._sessions: dict[str, tuple[str, str | None, str, float]] = {}

    # ---------------------------------------------------------------- identifiers
    def _mac(self, *parts: str) -> str:
        return hmac.new(self._key, "|".join(parts).encode(), hashlib.sha256).hexdigest()[:32]

    def account_id(self, account_key: str) -> str:
        return self._mac("account", account_key)

    def message_ref(self, account: str, message_id: str) -> str:
        return self._mac("message", account, message_id)

    # ---------------------------------------------------------------- recording
    def record(self, account_key: str, message_id: str, subject: str, sender: str, result: dict) -> None:
        acct, now = self.account_id(account_key), time.time()
        ref = self.message_ref(acct, message_id)
        with self._lock:
            self._db.execute(
                "INSERT INTO emails VALUES (?,?,?,?,1,?,?,?,?,?) ON CONFLICT(account, ref) DO UPDATE SET "
                "ts=excluded.ts, count=count+1, verdict=excluded.verdict, score=excluded.score, "
                "subject=excluded.subject, sender=excluded.sender, result=excluded.result",
                (acct, ref, now, now, result["verdict"], result.get("score"), subject[:300], sender[:300], json.dumps(result)))
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

    def mint_code(self, account_key: str, message_id: str | None, label: str) -> str:
        acct, now = self.account_id(account_key), time.time()
        ref = self.message_ref(acct, message_id) if message_id else None
        code = secrets.token_urlsafe(32)
        with self._lock:
            self._prune(self._codes, now)
            self._codes[code] = (acct, ref, label, now + CODE_TTL_S)
        return code

    def redeem(self, code: str) -> tuple[str, dict] | None:
        now = time.time()
        with self._lock:
            entry = self._codes.pop(code, None)  # single use
            if not entry or entry[3] < now:
                return None
            acct, ref, label, _ = entry
            self._prune(self._sessions, now)
            token = secrets.token_urlsafe(32)
            self._sessions[token] = (acct, ref, label, now + SESSION_TTL_S)
        context = ref if ref and self.get(acct, ref) else None
        return token, {"context": context, "account_label": label, "expires_in": SESSION_TTL_S}

    def session(self, token: str) -> tuple[str, str | None, str] | None:
        with self._lock:
            s = self._sessions.get(token or "")
            if not s or s[3] < time.time():
                return None
            return s[0], s[1], s[2]

    # ---------------------------------------------------------------- reads (always scoped to one account)
    def list(self, acct: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT ref, first_ts, ts, count, verdict, score, subject, sender, result FROM emails "
                                    "WHERE account=? AND ts>=? ORDER BY ts DESC", (acct, time.time() - RETENTION_S)).fetchall()
        out = []
        for ref, first_ts, ts, count, verdict, score, subject, sender, result in rows:
            r = json.loads(result)
            out.append({"id": ref, "first_analyzed": first_ts, "analyzed_at": ts, "times_analyzed": count, "verdict": verdict,
                        "score": score, "subject": subject, "sender": sender, "category": r.get("category", ""),
                        "headline": r.get("headline", "")})
        return out

    def get(self, acct: str, ref: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT first_ts, ts, count, subject, sender, result FROM emails WHERE account=? AND ref=?",
                                   (acct, ref)).fetchone()
        if not row:
            return None
        first_ts, ts, count, subject, sender, result = row
        return {"id": ref, "first_analyzed": first_ts, "analyzed_at": ts, "times_analyzed": count,
                "subject": subject, "sender": sender, "result": json.loads(result)}

    def clear(self, acct: str) -> int:
        with self._lock:
            n = self._db.execute("DELETE FROM emails WHERE account=?", (acct,)).rowcount
            self._db.commit()
        return n
