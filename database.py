import sqlite3
from datetime import datetime, timedelta

class Database:
    def __init__(self, db_name="gram_earn.db"):
        self.db_name = db_name
        self.init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # ইউজার টেবিল
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                username TEXT,
                balance REAL DEFAULT 0.0,
                referrer_id INTEGER,
                joined_date TEXT,
                last_daily_bonus TEXT,
                is_banned INTEGER DEFAULT 0
            )
        """)
        
        # টাস্ক টেবিল
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                desc TEXT,
                reward REAL,
                url TEXT
            )
        """)
        
        # টাস্ক সাবমিশন বা প্রুফ টেবিল
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
        
        # উইথড্র রিকোয়েস্ট টেবিল
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                wd_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                method TEXT,
                account_no TEXT,
                photo_id TEXT,
                status TEXT DEFAULT 'pending',
                date TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    # --- USER MANAGEMENT ---
    
    def register_user(self, user_id, name, username, referrer_id=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if user:
            conn.close()
            return False  # পুরাতন ইউজার
            
        joined_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO users (user_id, name, username, referrer_id, joined_date) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, username, referrer_id, joined_date)
        )
        conn.commit()
        conn.close()
        return True  # নতুন ইউজার

    def get_user(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name, username, balance, referrer_id, joined_date FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "user_id": row[0], "name": row[1], "username": row[2],
                "balance": row[3], "referrer_id": row[4], "joined_date": row[5]
            }
        return None

    def get_all_users(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
        conn.close()
        return [{"user_id": r[0]} for r in rows]

    def add_balance(self, user_id, amount):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()

    def get_referral_count(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(user_id) FROM users WHERE referrer_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def claim_daily_bonus(self, user_id, bonus_amount):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT last_daily_bonus, balance FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return False, None
            
        last_bonus_str, current_balance = row
        now = datetime.now()
        
        if last_bonus_str:
            last_bonus = datetime.strptime(last_bonus_str, "%Y-%m-%d %H:%M:%S")
            time_passed = now - last_bonus
            if time_passed < timedelta(hours=24):
                time_left = timedelta(hours=24) - time_passed
                conn.close()
                return False, time_left
                
        new_balance = current_balance + bonus_amount
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE users SET balance = ?, last_daily_bonus = ? WHERE user_id = ?", (new_balance, now_str, user_id))
        conn.commit()
        conn.close()
        return True, new_balance

    def ban_user(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    def unban_user(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    def is_user_banned(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] == 1 if row else False


    # --- TASK SYSTEM ---
    
    def add_new_task(self, title, desc, reward, url):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks (title, desc, reward, url) VALUES (?, ?, ?, ?)", (title, desc, reward, url))
        conn.commit()
        conn.close()

    def get_all_tasks(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT task_id, title, desc, reward, url FROM tasks")
        rows = cursor.fetchall()
        conn.close()
        return [{"task_id": r[0], "title": r[1], "desc": r[2], "reward": r[3], "url": r[4]} for r in rows]

    def get_task(self, task_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT task_id, title, desc, reward, url FROM tasks WHERE task_id = ?", (task_id,))
        r = cursor.fetchone()
        conn.close()
        if r:
            return {"task_id": r[0], "title": r[1], "desc": r[2], "reward": r[3], "url": r[4]}
        return None

    def delete_task(self, task_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted > 0

    def update_task(self, task_id, title, desc, reward, url):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET title = ?, desc = ?, reward = ?, url = ? WHERE task_id = ?",
            (title, desc, reward, url, task_id)
        )
        updated = cursor.rowcount
        conn.commit()
        conn.close()
        return updated > 0

    def has_pending_task(self, user_id, task_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT sub_id FROM task_submissions WHERE user_id = ? AND task_id = ? AND status = 'pending'", (user_id, task_id))
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def submit_task_proof(self, user_id, task_id, photo_id, reward):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # ইতিমধ্যে এপ্রুভ বা পেন্ডিং আছে কিনা চেক
        cursor.execute("SELECT status FROM task_submissions WHERE user_id = ? AND task_id = ?", (user_id, task_id))
        row = cursor.fetchone()
        if row:
            if row[0] == "approved":
                conn.close()
                return False, "approved"
            elif row[0] == "pending":
                conn.close()
                return False, "pending"
                
        cursor.execute(
            "INSERT INTO task_submissions (user_id, task_id, photo_id, reward) VALUES (?, ?, ?, ?)",
            (user_id, task_id, photo_id, reward)
        )
        sub_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return True, sub_id

    def approve_task_submission(self, sub_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, reward, task_id, status FROM task_submissions WHERE sub_id = ?", (sub_id,))
        row = cursor.fetchone()
        
        if not row or row[3] != "pending":
            conn.close()
            return None
            
        user_id, reward, task_id, _ = row
        cursor.execute("UPDATE task_submissions SET status = 'approved' WHERE sub_id = ?", (sub_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
        conn.commit()
        conn.close()
        return user_id, reward, task_id

    def reject_task_submission(self, sub_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, task_id, status FROM task_submissions WHERE sub_id = ?", (sub_id,))
        row = cursor.fetchone()
        
        if not row or row[2] != "pending":
            conn.close()
            return None
            
        user_id, task_id, _ = row
        cursor.execute("UPDATE task_submissions SET status = 'rejected' WHERE sub_id = ?", (sub_id,))
        conn.commit()
        conn.close()
        return user_id, task_id


    # --- WITHDRAW SYSTEM ---
    
    def has_pending_withdrawal(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT wd_id FROM withdrawals WHERE user_id = ? AND status = 'pending'", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def request_withdrawal(self, user_id, amount, method, account_no, photo_id, min_withdraw):
        if amount < min_withdraw:
            return False, "less_than_min", None
            
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "account_not_found", None
            
        balance = row[0]
        if balance < amount:
            conn.close()
            return False, "insufficient_balance", None
            
        # অলরেডি পেন্ডিং চেক
        cursor.execute("SELECT wd_id FROM withdrawals WHERE user_id = ? AND status = 'pending'", (user_id,))
        if cursor.fetchone():
            conn.close()
            return False, "already_pending", None
            
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # ইউজার ব্যালেন্স ইনস্ট্যান্ট কেটে নেওয়া
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        
        cursor.execute(
            "INSERT INTO withdrawals (user_id, amount, method, account_no, photo_id, date) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, amount, method, account_no, photo_id, date_str)
        )
        wd_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return True, "success", wd_id

    def get_withdrawal(self, wd_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount, method, account_no, status FROM withdrawals WHERE wd_id = ?", (wd_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"user_id": row[0], "amount": row[1], "method": row[2], "account_no": row[3], "status": row[4]}
        return None

    def approve_withdrawal(self, wd_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE withdrawals SET status = 'approved' WHERE wd_id = ?", (wd_id,))
        conn.commit()
        conn.close()

    def reject_withdrawal(self, wd_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount, status FROM withdrawals WHERE wd_id = ?", (wd_id,))
        row = cursor.fetchone()
        if row and row[2] == "pending":
            user_id, amount, _ = row
            # রিজেক্ট হলে টাকা মেইন ব্যালেন্সে ফেরত দেওয়া হচ্ছে
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            cursor.execute("UPDATE withdrawals SET status = 'rejected' WHERE wd_id = ?", (wd_id,))
            conn.commit()
        conn.close()


    # --- LEADERBOARD SYSTEM ---
    
    def get_top_earners(self, limit=10):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, balance FROM users WHERE is_banned = 0 ORDER BY balance DESC LIMIT ?", 
            (limit,)
        )
        result = cursor.fetchall()
        conn.close()
        return [{"name": r[0], "balance": r[1]} for r in result]

    def get_top_referrers(self, limit=10):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT u.name, COUNT(r.user_id) as ref_count 
            FROM users u
            LEFT JOIN users r ON u.user_id = r.referrer_id
            WHERE u.is_banned = 0
            GROUP BY u.user_id
            ORDER BY ref_count DESC
            LIMIT ?
            """, 
            (limit,)
        )
        result = cursor.fetchall()
        conn.close()
        return [{"name": r[0], "ref_count": r[1]} for r in result]


    # --- SYSTEM STATISTICS ---
    
    def get_system_stats(self):
        """বটের সামগ্রিক পরিসংখ্যান (ইউজার, টাস্ক ও উইথড্র) গণনা করে নিয়ে আসবে"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # মোট ইউজার সংখ্যা
        cursor.execute("SELECT COUNT(user_id) FROM users")
        total_users = cursor.fetchone()[0]
        
        # মোট ব্যানড ইউজার সংখ্যা
        cursor.execute("SELECT COUNT(user_id) FROM users WHERE is_banned = 1")
        banned_users = cursor.fetchone()[0]
        
        # মোট টাস্ক সংখ্যা
        cursor.execute("SELECT COUNT(task_id) FROM tasks")
        total_tasks = cursor.fetchone()[0]
        
        # মোট পেন্ডিং উইথড্র রিকোয়েস্ট সংখ্যা
        cursor.execute("SELECT COUNT(wd_id) FROM withdrawals WHERE status = 'pending'")
        pending_withdraws = cursor.fetchone()[0]
        
        conn.close()
        return {
            "total_users": total_users,
            "banned_users": banned_users,
            "total_tasks": total_tasks,
            "pending_withdraws": pending_withdraws
        }
