import sqlite3
import os

def get_db_path() -> str:
    """Returns the writable database path. On Vercel/Linux, uses /tmp."""
    if os.environ.get("VERCEL") or os.name != "nt" or os.path.exists("/tmp"):
        return "/tmp/applications.db"
    return "applications.db"

def init_db(db_path=None):
    """Initializes SQLite DB to track applied jobs and HR cold emails."""
    db_path = db_path or get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title TEXT,
                company TEXT,
                url TEXT UNIQUE,
                hr_email TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email_sent INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] init_db failed: {e}")

def is_already_applied(url: str, db_path=None) -> bool:
    """Checks if job URL has already been processed."""
    db_path = db_path or get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM applications WHERE url = ?", (url,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception:
        return False

def get_all_applications(db_path=None) -> list:
    """Fetches all applications and stats from database."""
    db_path = db_path or get_db_path()
    init_db(db_path)
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM applications ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB ERROR] get_all_applications failed: {e}")
        return []

def log_application(job_title: str, company: str, url: str, hr_email: str = None, email_sent: bool = False, db_path=None):
    """Logs applied job and cold email status."""
    db_path = db_path or get_db_path()
    init_db(db_path)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO applications (job_title, company, url, hr_email, email_sent)
            VALUES (?, ?, ?, ?, ?)
        """, (job_title, company, url, hr_email, 1 if email_sent else 0))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] log_application failed: {e}")
