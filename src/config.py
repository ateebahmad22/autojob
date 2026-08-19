import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GMAIL_USER = os.getenv("GMAIL_USER")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
    RESUME_PATH = os.getenv("RESUME_PATH", "resume.docx")
    DEFAULT_JOB_TITLE = os.getenv("DEFAULT_JOB_TITLE", "Software Engineer")
    DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "Remote")
    DB_PATH = os.getenv("DB_PATH", "applications.db")
