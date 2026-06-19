import sqlite3
from datetime import datetime, timedelta


class Database:
    def __init__(self, db_name="bot_database.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            username TEXT,
            balance REAL DEFAULT 0.0,
            referred_by INTEGER,
            joined_date TEXT,
            last_daily_bonus TEXT,
            is_banned INTEGER DEFAULT 0
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            account_no TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            desc TEXT,
            reward REAL,
            url TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_submissions (
            sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            photo_id TEXT,
            reward REAL,
            status TEXT DEFAULT 'pending'
        )
        """)
        self.conn.commit()

        # সেফটি চেক: যদি আগে থেকে ডাটাবেজ ফাইল তৈরি থাকে, তবে যেন কলাম মিসিং এরর না আসে
        try:
            cursor.execute("SELECT is_banned FROM users LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
            self.conn.commit()

    # ---------------- USER ----------------
    def register_user(self, user_id, name, username, referrer_id=None):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            return False
        joined_date = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            "INSERT INTO users (user_id, name, username, referred_by, joined_date) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, username, referrer_id, joined_date)
        )
        self.conn.commit()
        return True

    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT user_id, name, username, balance, referred_by, joined_date, last_daily_bonus FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "user_id": row[0], "name": row[1], "username": row[2],
                "balance": row[3], "referred_by": row[4],
                "joined_date": row[5], "last_daily_bonus": row[6]
            }
        return None

    def get_all_users(self):
        """👑 অ্যাডমিন ব্রডকাস্টের জন্য সব ইউজারের আইডি পাওয়ার মেথড"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        return [{"user_id": r[0]} for r in cursor.fetchall()]

    def add_balance(self, user_id, amount):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        self.conn.commit()

    def get_referral_count(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        return cursor.fetchone()[0]

    def claim_daily_bonus(self, user_id, bonus_amount):
        user = self.get_user(user_id)
        if not user:
            return False, None
        now = datetime.now()
        if user["last_daily_bonus"]:
            last_bonus_time = datetime.strptime(user["last_daily_bonus"], "%Y-%m-%d %H:%M:%S")
            time_passed = now - last_bonus_time
            if time_passed < timedelta(hours=24):
                return False, timedelta(hours=24) - time_passed
        cursor = self.conn.cursor()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE users SET balance = balance + ?, last_daily_bonus = ? WHERE user_id = ?",
            (bonus_amount, now_str, user_id)
        )
        self.conn.commit()
        return True, user["balance"] + bonus_amount

    # ---------------- BAN / UNBAN SYSTEM ----------------
    def is_user_banned(self, user_id):
        """ইউজার ব্যান কিনা চেক করে"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] == 1 if row else False

    def ban_user(self, user_id):
        """ইউজারকে ব্যান করে"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def unban_user(self, user_id):
        """ইউজারকে আনব্যান করে"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        self.conn.commit()

    # ---------------- WITHDRAW ----------------
    def request_withdrawal(self, user_id, amount, method, account_no, min_withdraw):
        user = self.get_user(user_id)
        if not user:
            return False, "account_not_found", None
        if amount < min_withdraw:
            return False, "below_minimum", None
        if user["balance"] < amount:
            return False, "insufficient_balance", None
        if self.has_pending_withdrawal(user_id):
            return False, "already_pending", None
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
            cursor.execute(
                "INSERT INTO withdrawals (user_id, amount, method, account_no, status) VALUES (?, ?, ?, ?, 'pending')",
                (user_id, amount, method, account_no)
            )
            self.conn.commit()
            return True, "success", cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            print(f"Withdraw DB Error: {e}")
            return False, "db_error", None

    def has_pending_withdrawal(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM withdrawals WHERE user_id = ? AND status = 'pending'", (user_id,))
        return cursor.fetchone() is not None

    def get_withdrawal(self, wd_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, amount, method, account_no, status FROM withdrawals WHERE id = ?", (wd_id,))
        row = cursor.fetchone()
        if row:
            return {"user_id": row[0], "amount": row[1], "method": row[2], "account_no": row[3], "status": row[4]}
        return None

    def approve_withdrawal(self, wd_id):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE withdrawals SET status = 'approved' WHERE id = ?", (wd_id,))
        self.conn.commit()

    def reject_withdrawal(self, wd_id):
        wd = self.get_withdrawal(wd_id)
        if wd:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (wd["amount"], wd["user_id"]))
            cursor.execute("UPDATE withdrawals SET status = 'rejected' WHERE id = ?", (wd_id,))
            self.conn.commit()

    # ---------------- TASK ----------------
    def add_new_task(self, title, desc, reward, url):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO tasks (title, desc, reward, url) VALUES (?, ?, ?, ?)", (title, desc, reward, url))
        self.conn.commit()

    def get_all_tasks(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT task_id, title, desc, reward, url FROM tasks")
        return [{"task_id": r[0], "title": r[1], "desc": r[2], "reward": r[3], "url": r[4]} for r in cursor.fetchall()]

    def get_task(self, task_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT task_id, title, desc, reward, url FROM tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        if row:
            return {"task_id": row[0], "title": row[1], "desc": row[2], "reward": row[3], "url": row[4]}
        return None

    def has_pending_task(self, user_id, task_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM task_submissions WHERE user_id = ? AND task_id = ? AND status = 'pending'",
            (user_id, task_id)
        )
        return cursor.fetchone() is not None

    def submit_task_proof(self, user_id, task_id, photo_id, reward):
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM task_submissions WHERE user_id = ? AND task_id = ?", (user_id, task_id))
        row = cursor.fetchone()
        if row:
            return False, row[0]
        cursor.execute(
            "INSERT INTO task_submissions (user_id, task_id, photo_id, reward, status) VALUES (?, ?, ?, ?, 'pending')",
            (user_id, task_id, photo_id, reward)
        )
        self.conn.commit()
        return True, cursor.lastrowid

    def approve_task_submission(self, sub_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, reward, task_id, status FROM task_submissions WHERE sub_id = ?", (sub_id,))
        row = cursor.fetchone()
        if row and row[3] == 'pending':
            user_id, reward, task_id = row[0], row[1], row[2]
            cursor.execute("UPDATE task_submissions SET status = 'approved' WHERE sub_id = ?", (sub_id,))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
            self.conn.commit()
            return user_id, reward, task_id
        return None

    def reject_task_submission(self, sub_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, task_id, status FROM task_submissions WHERE sub_id = ?", (sub_id,))
        row = cursor.fetchone()
        if row and row[2] == 'pending':
            user_id, task_id = row[0], row[1]
            cursor.execute("UPDATE task_submissions SET status = 'rejected' WHERE sub_id = ?", (sub_id,))
            self.conn.commit()
            return user_id, task_id
        return None
