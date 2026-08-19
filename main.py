import asyncio
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.config import Config
from src.resume_parser import extract_resume_text
from src.db import init_db
from src.browser_agent import JobAutomationAgent

async def main():
    print("==================================================")
    print("AI Auto Job Application & HR Cold Mailer Agent")
    print("==================================================")

    init_db()

    resume_path = Config.RESUME_PATH
    if not os.path.exists(resume_path):
        for alt in ["resume.docx", "resume.pdf", "Resume.docx", "Resume.pdf"]:
            if os.path.exists(alt):
                resume_path = alt
                break

    if not os.path.exists(resume_path):
        print(f"\n[ERROR] Resume file not found at {os.getcwd()}")
        return

    print(f"\n[INFO] Reading Resume from: {resume_path}")
    try:
        resume_text = extract_resume_text(resume_path)
        print(f"[SUCCESS] Resume parsed successfully ({len(resume_text)} characters read).")
    except Exception as e:
        print(f"[ERROR] Failed to parse resume: {e}")
        return

    job_title = Config.DEFAULT_JOB_TITLE
    location = Config.DEFAULT_LOCATION
    max_jobs = 5

    if len(sys.argv) > 1:
        job_title = sys.argv[1]
    if len(sys.argv) > 2:
        location = sys.argv[2]
    if len(sys.argv) > 3:
        try:
            max_jobs = int(sys.argv[3])
        except ValueError:
            max_jobs = 5

    print(f"\n[START] Searching for '{job_title}' in '{location}' (Max jobs: {max_jobs})...\n")
    agent = JobAutomationAgent(resume_text=resume_text)
    await agent.run(job_title=job_title, location=location, max_jobs=max_jobs)

    print("\n[COMPLETE] Process Finished! Check 'applications.db' for records.")

if __name__ == "__main__":
    asyncio.run(main())
