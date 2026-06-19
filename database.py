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
