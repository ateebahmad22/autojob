import os
import sys
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.resume_parser import extract_resume_text
from src.browser_agent import JobAutomationAgent
from src.db import init_db

app = FastAPI(title="AI Auto Job Application Agent API")

class JobRequest(BaseModel):
    job_title: str = "Full Stack Developer"
    location: str = "Remote"
    max_jobs: int = 3

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "AI Auto Job Application & HR Cold Mailer Agent API",
        "deployment": "Vercel Serverless"
    }

@app.post("/api/run")
async def run_agent(req: JobRequest):
    init_db()
    resume_path = os.getenv("RESUME_PATH", "resume.docx")
    
    if not os.path.exists(resume_path):
        return {"status": "error", "message": f"Resume file not found at {resume_path}"}
    
    try:
        resume_text = extract_resume_text(resume_path)
        agent = JobAutomationAgent(resume_text=resume_text)
        await agent.run(job_title=req.job_title, location=req.location, max_jobs=req.max_jobs)
        return {
            "status": "success",
            "message": f"Successfully processed job search for '{req.job_title}' in '{req.location}'",
            "max_jobs_processed": req.max_jobs
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
