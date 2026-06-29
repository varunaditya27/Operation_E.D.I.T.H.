"""
Operation E.D.I.T.H. v5 — Database Layer
Document Ref: SPEC-ACT5-OPSDEPLOY §2.2

SQLite database for nonce tracking, session management, and rate limiting.
"""
import sqlite3
import time
import os
import threading

DB_PATH = os.environ.get("DB_PATH", "./data/edith.db")
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local database connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db():
    """Initialize database tables per SPEC-ACT5-OPSDEPLOY §2.2."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS issued_nonces (
            nonce TEXT PRIMARY KEY,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            used BOOLEAN DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS wrc_sessions (
            session_id TEXT PRIMARY KEY,
            blink_sequence TEXT NOT NULL,
            resolved BOOLEAN DEFAULT 0,
            timestamp INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS auth_sessions (
            session_token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            dashboard_accessed BOOLEAN DEFAULT 0,
            pcap_released BOOLEAN DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS challenges (
            challenge_id TEXT PRIMARY KEY,
            challenge TEXT NOT NULL,
            username TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            used BOOLEAN DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS rate_limits (
            ip TEXT PRIMARY KEY,
            request_count INTEGER DEFAULT 0,
            window_start INTEGER NOT NULL,
            blocked_until INTEGER DEFAULT 0
        );
    """)
    conn.commit()


# ──────────────────────────────────────────
# Nonce Management (Acts II/IV)
# ──────────────────────────────────────────

def create_nonce(nonce: str, ttl: int = 90):
    """Insert a fresh nonce with a TTL."""
    conn = _get_conn()
    now = int(time.time())
    conn.execute(
        "INSERT INTO issued_nonces (nonce, created_at, expires_at, used) VALUES (?, ?, ?, 0)",
        (nonce, now, now + ttl)
    )
    conn.commit()


def validate_and_consume_nonce(nonce: str) -> bool:
    """Check if a nonce is valid (exists, not used, not expired) and mark it used.
    Returns True if valid, False otherwise."""
    conn = _get_conn()
    now = int(time.time())
    row = conn.execute(
        "SELECT * FROM issued_nonces WHERE nonce = ?", (nonce,)
    ).fetchone()
    if not row:
        return False
    if row["used"] or row["expires_at"] < now:
        return False
    conn.execute("UPDATE issued_nonces SET used = 1 WHERE nonce = ?", (nonce,))
    conn.commit()
    return True


# ──────────────────────────────────────────
# Challenge Management (Act II SCRP)
# ──────────────────────────────────────────

def store_challenge(challenge_id: str, challenge: str, username: str):
    """Store a SCRP challenge."""
    conn = _get_conn()
    now = int(time.time())
    conn.execute(
        "INSERT OR REPLACE INTO challenges (challenge_id, challenge, username, created_at, used) "
        "VALUES (?, ?, ?, ?, 0)",
        (challenge_id, challenge, username, now)
    )
    conn.commit()


def get_and_consume_challenge(challenge_id: str) -> dict | None:
    """Retrieve and consume a challenge."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM challenges WHERE challenge_id = ? AND used = 0", (challenge_id,)
    ).fetchone()
    if not row:
        return None
    now = int(time.time())
    if now - row["created_at"] > 60:  # challenges expire after 60s
        return None
    conn.execute("UPDATE challenges SET used = 1 WHERE challenge_id = ?", (challenge_id,))
    conn.commit()
    return dict(row)


# ──────────────────────────────────────────
# Session Management (Act II)
# ──────────────────────────────────────────

def create_session(session_token: str, username: str, ttl: int = 90):
    """Create an authenticated session."""
    conn = _get_conn()
    now = int(time.time())
    conn.execute(
        "INSERT OR REPLACE INTO auth_sessions "
        "(session_token, username, created_at, expires_at, dashboard_accessed, pcap_released) "
        "VALUES (?, ?, ?, ?, 0, 0)",
        (session_token, username, now, now + ttl)
    )
    conn.commit()


def validate_session(session_token: str) -> dict | None:
    """Check if a session is valid."""
    conn = _get_conn()
    now = int(time.time())
    row = conn.execute(
        "SELECT * FROM auth_sessions WHERE session_token = ? AND expires_at > ?",
        (session_token, now)
    ).fetchone()
    return dict(row) if row else None


def mark_dashboard_accessed(session_token: str):
    """Mark that a session has accessed the employee dashboard (triggers PCAP release)."""
    conn = _get_conn()
    conn.execute(
        "UPDATE auth_sessions SET dashboard_accessed = 1, pcap_released = 1 WHERE session_token = ?",
        (session_token,)
    )
    conn.commit()


def is_pcap_released(session_token: str) -> bool:
    """Check if the PCAP has been released for this session."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT pcap_released FROM auth_sessions WHERE session_token = ?",
        (session_token,)
    ).fetchone()
    return bool(row and row["pcap_released"])


# ──────────────────────────────────────────
# Rate Limiting (SPEC-ACT5-OPSDEPLOY §3.1)
# ──────────────────────────────────────────

def check_rate_limit(ip: str, max_requests: int = 12, window: int = 60, block: int = 180) -> bool:
    """Returns True if the request is allowed, False if rate-limited."""
    conn = _get_conn()
    now = int(time.time())
    row = conn.execute("SELECT * FROM rate_limits WHERE ip = ?", (ip,)).fetchone()

    if row:
        if row["blocked_until"] > now:
            return False
        if now - row["window_start"] > window:
            # Reset window
            conn.execute(
                "UPDATE rate_limits SET request_count = 1, window_start = ?, blocked_until = 0 WHERE ip = ?",
                (now, ip)
            )
        else:
            new_count = row["request_count"] + 1
            if new_count > max_requests:
                conn.execute(
                    "UPDATE rate_limits SET blocked_until = ? WHERE ip = ?",
                    (now + block, ip)
                )
                conn.commit()
                return False
            conn.execute(
                "UPDATE rate_limits SET request_count = ? WHERE ip = ?",
                (new_count, ip)
            )
    else:
        conn.execute(
            "INSERT INTO rate_limits (ip, request_count, window_start, blocked_until) VALUES (?, 1, ?, 0)",
            (ip, now)
        )
    conn.commit()
    return True
