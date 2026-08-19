import os
import sys
import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.resume_parser import extract_resume_text
from src.browser_agent import JobAutomationAgent
from src.db import init_db

app = FastAPI(title="AI Auto Job Application Agent")

class JobRequest(BaseModel):
    job_title: str = "Full Stack Developer"
    location: str = "Remote"
    max_jobs: int = 3

@app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Auto Job Application & HR Cold Mailer Agent</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #0f172a; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }
            .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
            .btn-primary { background: #6366f1; border: none; font-weight: 600; padding: 12px; }
            .btn-primary:hover { background: #4f46e5; }
            .form-control { background: #0f172a; border: 1px solid #475569; color: #fff; }
            .form-control:focus { background: #0f172a; color: #fff; border-color: #818cf8; box-shadow: none; }
            .badge-live { background: #10b981; color: #fff; }
        </style>
    </head>
    <body class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card p-4 shadow-lg">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h2 class="m-0 fw-bold">🤖 AI Auto Job Application & HR Cold Mailer Agent</h2>
                        <span class="badge badge-live px-3 py-2 rounded-pill">System Live</span>
                    </div>

                    <p class="text-secondary">Enter your target job requirements below. The AI Agent will parse your resume, crawl job portals, extract recruiter emails, generate tailored cold emails via Gemini AI, and dispatch them from your Gmail.</p>

                    <form id="jobForm" class="mt-3">
                        <div class="mb-3">
                            <label class="form-label text-slate-300 fw-semibold">Target Job Title</label>
                            <input type="text" id="job_title" class="form-control form-control-lg" value="Full Stack Developer" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label text-slate-300 fw-semibold">Target Location</label>
                            <input type="text" id="location" class="form-control form-control-lg" value="Remote" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label text-slate-300 fw-semibold">Maximum Jobs to Process</label>
                            <input type="number" id="max_jobs" class="form-control form-control-lg" value="3" min="1" max="10" required>
                        </div>
                        <button type="submit" id="submitBtn" class="btn btn-primary btn-lg w-100 mt-2">
                            🚀 Run AI Job Application Agent
                        </button>
                    </form>

                    <div id="outputBox" class="mt-4 p-3 rounded d-none" style="background: #090d16; border: 1px solid #1e293b;">
                        <h5 class="fw-bold mb-2">Agent Status & Logs:</h5>
                        <pre id="logOutput" class="m-0 text-success" style="white-space: pre-wrap; font-family: monospace;"></pre>
                    </div>
                </div>
            </div>
        </div>

        <script>
            document.getElementById('jobForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = document.getElementById('submitBtn');
                const outputBox = document.getElementById('outputBox');
                const logOutput = document.getElementById('logOutput');

                btn.disabled = true;
                btn.innerHTML = '⏳ AI Agent Working... Please wait';
                outputBox.classList.remove('d-none');
                logOutput.innerText = '🔍 Starting search & AI email generation engine...\n';

                try {
                    const res = await fetch('/api/run', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            job_title: document.getElementById('job_title').value,
                            location: document.getElementById('location').value,
                            max_jobs: parseInt(document.getElementById('max_jobs').value)
                        })
                    });
                    const data = await res.json();
                    if (data.status === 'success') {
                        logOutput.innerText += `\n✅ ${data.message}\nMax jobs processed: ${data.max_jobs_processed}\n\nCheck your Gmail Sent folder!`;
                    } else {
                        logOutput.innerText += `\n❌ Error: ${data.message}`;
                    }
                } catch (err) {
                    logOutput.innerText += `\n❌ Network Error: ${err.message}`;
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '🚀 Run AI Job Application Agent';
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

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
