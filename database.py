import sqlite3
from datetime import datetime, timedelta

BONUS_COOLDOWN_HOURS = 24


class Database:
    def __init__(self, db_path="bot.db"):
        self.db_path = db_path
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id     INTEGER PRIMARY KEY,
                    name        TEXT,
                    username    TEXT,
                    balance     REAL DEFAULT 0,
                    referrer_id INTEGER,
                    joined_date TEXT,
                    last_bonus  TEXT
                );

                CREATE TABLE IF NOT EXISTS withdrawals (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER,
                    amount       REAL,
                    method       TEXT,
                    account_no   TEXT,
                    status       TEXT DEFAULT 'pending',
                    requested_at TEXT,
                    handled_at   TEXT
                );
            """)
            # যদি পুরনো DB-তে last_bonus কলাম না থাকে, যুক্ত করে দেয়
            cols = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
            if "last_bonus" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN last_bonus TEXT")

    def register_user(self, user_id, name, username, referrer_id=None):
        with self._conn() as conn:
            existing = conn.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
            if existing:
                return False
            conn.execute(
                "INSERT INTO users (user_id, name, username, referrer_id, joined_date) VALUES (?,?,?,?,?)",
                (user_id, name, username, referrer_id, datetime.now().strftime("%d/%m/%Y"))
            )
            return True

    def get_user(self, user_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def add_balance(self, user_id, amount):
        with self._conn() as conn:
            conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))

    def get_referral_count(self, user_id):
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM users WHERE referrer_id=?", (user_id,)).fetchone()
            return row["cnt"]

    def claim_daily_bonus(self, user_id, amount):
        """
        Daily bonus claim করার চেষ্টা করে।
        Returns: (success: bool, info)
            - success=True হলে info = নতুন balance (float)
            - success=False হলে info = পরবর্তী claim পর্যন্ত বাকি সময় (timedelta)
        """
        with self._conn() as conn:
            row = conn.execute("SELECT last_bonus FROM users WHERE user_id=?", (user_id,)).fetchone()
            if row is None:
                return False, None

            now = datetime.now()
            if row["last_bonus"]:
                last_claim = datetime.fromisoformat(row["last_bonus"])
                elapsed = now - last_claim
                cooldown = timedelta(hours=BONUS_COOLDOWN_HOURS)
                if elapsed < cooldown:
                    remaining = cooldown - elapsed
                    return False, remaining

            conn.execute(
                "UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id=?",
                (amount, now.isoformat(), user_id)
            )
            new_balance = conn.execute(
                "SELECT balance FROM users WHERE user_id=?", (user_id,)
            ).fetchone()["balance"]
            return True, new_balance

    # ---------------- Withdrawal ----------------

    def has_pending_withdrawal(self, user_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM withdrawals WHERE user_id=? AND status='pending'", (user_id,)
            ).fetchone()
            return row is not None

    def request_withdrawal(self, user_id, amount, method, account_no, min_amount):
        """
        উইথড্র রিকোয়েস্ট তৈরি করে। ব্যালেন্স যাচাই করে সাথে সাথে আটকে রাখে (deduct করে)
        যাতে ইউজার একসাথে একাধিক রিকোয়েস্ট করে ব্যালেন্সের বেশি তুলে নিতে না পারে।

        Returns: (success: bool, message: str, withdrawal_id or None)
        """
        with self._conn() as conn:
            user = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
            if user is None:
                return False, "account_not_found", None

            if self.has_pending_withdrawal(user_id):
                return False, "already_pending", None

            if amount < min_amount:
                return False, "below_minimum", None

            if user["balance"] < amount:
                return False, "insufficient_balance", None

            # ব্যালেন্স থেকে কেটে নেয়া (reject হলে ফেরত দেওয়া হবে)
            conn.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
            cur = conn.execute(
                "INSERT INTO withdrawals (user_id, amount, method, account_no, status, requested_at) "
                "VALUES (?,?,?,?, 'pending', ?)",
                (user_id, amount, method, account_no, datetime.now().isoformat())
            )
            return True, "ok", cur.lastrowid

    def get_withdrawal(self, withdrawal_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM withdrawals WHERE id=?", (withdrawal_id,)).fetchone()
            return dict(row) if row else None

    def get_pending_withdrawals(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM withdrawals WHERE status='pending' ORDER BY requested_at ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def approve_withdrawal(self, withdrawal_id):
        """এডমিন এপ্রুভ করলে স্ট্যাটাস আপডেট হয় (ব্যালেন্স আগেই কাটা হয়েছিল)।"""
        with self._conn() as conn:
            row = conn.execute("SELECT status FROM withdrawals WHERE id=?", (withdrawal_id,)).fetchone()
            if row is None or row["status"] != "pending":
                return False
            conn.execute(
                "UPDATE withdrawals SET status='approved', handled_at=? WHERE id=?",
                (datetime.now().isoformat(), withdrawal_id)
            )
            return True

    def reject_withdrawal(self, withdrawal_id):
        """এডমিন রিজেক্ট করলে টাকা ইউজারের ব্যালেন্সে ফেরত যায়।"""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM withdrawals WHERE id=?", (withdrawal_id,)).fetchone()
            if row is None or row["status"] != "pending":
                return False
            conn.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id=?",
                (row["amount"], row["user_id"])
            )
            conn.execute(
                "UPDATE withdrawals SET status='rejected', handled_at=? WHERE id=?",
                (datetime.now().isoformat(), withdrawal_id)
            )
            return True

    def get_user_withdrawals(self, user_id, limit=5):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM withdrawals WHERE user_id=? ORDER BY requested_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]
