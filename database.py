import sqlite3
from datetime import datetime, timedelta

BONUS_COOLDOWN_HOURS = 24


class Database:
    def __init__(self, db_path="bot.db"):
        self.db_path = db_path
        self._init_db()
        self._init_task_db()

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
            cols = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
            if "last_bonus" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN last_bonus TEXT")

    def _init_task_db(self):
        """টাস্ক এবং সাবমিশনের জন্য টেবিল তৈরি করে"""
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    title        TEXT,
                    desc         TEXT,
                    reward       REAL,
                    url          TEXT,
                    created_at   TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_submissions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER,
                    task_id      INTEGER,
                    photo_file_id TEXT,
                    status       TEXT DEFAULT 'pending',
                    reward       REAL,
                    submitted_at TEXT
                );
            """)

    def add_new_task(self, title, desc, reward, url):
        """চ্যানেল থেকে নতুন টাস্ক যোগ করার ফাংশন"""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO tasks (title, desc, reward, url, created_at) VALUES (?, ?, ?, ?, ?)",
                (title, desc, reward, url, datetime.now().isoformat())
            )

    def get_all_tasks(self):
        """সবগুলো একটিভ টাস্ক লিস্ট নিয়ে আসার ফাংশন"""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY task_id DESC").fetchall()
            return [dict(r) for r in rows]

    def get_task(self, task_id):
        """নির্দিষ্ট একটি টাস্কের ডিটেইলস জানা"""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            return dict(row) if row else None

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

    def has_pending_task(self, user_id, task_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM task_submissions WHERE user_id=? AND task_id=? AND status='pending'",
                (user_id, task_id)
            ).fetchone()
            return row is not None

    def submit_task_proof(self, user_id, task_id, photo_file_id, reward):
        with self._conn() as conn:
            already_done = conn.execute(
                "SELECT status FROM task_submissions WHERE user_id=? AND task_id=?", 
                (user_id, task_id)
            ).fetchone()
            
            if already_done and already_done["status"] in ["pending", "approved"]:
                return False, already_done["status"]

            cur = conn.execute(
                "INSERT INTO task_submissions (user_id, task_id, photo_file_id, status, reward, submitted_at) "
                "VALUES (?, ?, ?, 'pending', ?, ?)",
                (user_id, task_id, photo_file_id, reward, datetime.now().isoformat())
            )
            return True, cur.lastrowid

    def get_submission(self, sub_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM task_submissions WHERE id=?", (sub_id,)).fetchone()
            return dict(row) if row else None

    def approve_task_submission(self, sub_id):
        with self._conn() as conn:
            sub = conn.execute("SELECT * FROM task_submissions WHERE id=? AND status='pending'", (sub_id,)).fetchone()
            if not sub:
                return False
            
            conn.execute("UPDATE task_submissions SET status='approved' WHERE id=?", (sub_id,))
            conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (sub["reward"], sub["user_id"]))
            return sub["user_id"], sub["reward"], sub["task_id"]

    def reject_task_submission(self, sub_id):
        with self._conn() as conn:
            sub = conn.execute("SELECT * FROM task_submissions WHERE id=? AND status='pending'", (sub_id,)).fetchone()
            if not sub:
                return False
            conn.execute("UPDATE task_submissions SET status='rejected' WHERE id=?", (sub_id,))
            return sub["user_id"], sub["task_id"]

    def has_pending_withdrawal(self, user_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM withdrawals WHERE user_id=? AND status='pending'", (user_id,)
            ).fetchone()
            return row is not None

    def request_withdrawal(self, user_id, amount, method, account_no, min_amount):
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

    def approve_withdrawal(self, withdrawal_id):
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
