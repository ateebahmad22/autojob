import sqlite3
import os

def init_db(db_path="applications.db"):
    """Initializes SQLite DB to track applied jobs and HR cold emails."""
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

def is_already_applied(url: str, db_path="applications.db") -> bool:
    """Checks if job URL has already been processed."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM applications WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_all_applications(db_path="applications.db") -> list:
    """Fetches all applications and stats from database."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM applications ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def log_application(job_title: str, company: str, url: str, hr_email: str = None, email_sent: bool = False, db_path="applications.db"):
    """Logs applied job and cold email status."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO applications (job_title, company, url, hr_email, email_sent)
        VALUES (?, ?, ?, ?, ?)
    """, (job_title, company, url, hr_email, 1 if email_sent else 0))
    conn.commit()
    conn.close()
