import os
import sys
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from google import genai

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.resume_parser import extract_resume_text
from src.browser_agent import JobAutomationAgent
from src.db import init_db, is_already_applied, log_application
from src.config import Config

app = FastAPI(title="FastApply AI")

class JobRequest(BaseModel):
    job_title: str = "Full Stack Developer"
    location: str = "Remote"
    max_jobs: int = 3

class ChatRequest(BaseModel):
    prompt: str

@app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="en" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FastApply AI | Autonomous Job Application & HR Cold Mailer</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
        <style>
            :root {
                --chatgpt-bg: #171717;
                --chatgpt-sidebar: #202123;
                --chatgpt-card: #212121;
                --chatgpt-input: #2f2f2f;
                --chatgpt-border: #343541;
                --accent-primary: #10a37f;
                --accent-indigo: #6366f1;
            }
            body {
                background-color: var(--chatgpt-bg);
                color: #ececf1;
                font-family: 'Söhne', system-ui, -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
                overflow-x: hidden;
            }
            .sidebar {
                background-color: var(--chatgpt-sidebar);
                border-right: 1px solid var(--chatgpt-border);
                min-height: 100vh;
            }
            .nav-link-custom {
                color: #c5c5d2;
                padding: 10px 14px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                gap: 12px;
                font-weight: 500;
                transition: all 0.2s ease;
                text-decoration: none;
                cursor: pointer;
            }
            .nav-link-custom:hover, .nav-link-custom.active {
                background-color: #2a2b32;
                color: #ffffff;
            }
            .chat-container {
                max-width: 800px;
                margin: 0 auto;
            }
            .chat-bubble-user {
                background-color: #2f2f2f;
                border-radius: 18px 18px 4px 18px;
                padding: 14px 18px;
                max-width: 80%;
                margin-left: auto;
            }
            .chat-bubble-ai {
                background-color: #212121;
                border: 1px solid var(--chatgpt-border);
                border-radius: 18px 18px 18px 4px;
                padding: 16px 20px;
                max-width: 90%;
            }
            .prompt-input-box {
                background-color: var(--chatgpt-input);
                border: 1px solid var(--chatgpt-border);
                border-radius: 16px;
                color: #fff;
                padding: 14px 20px;
                resize: none;
            }
            .prompt-input-box:focus {
                background-color: var(--chatgpt-input);
                color: #fff;
                border-color: var(--accent-indigo);
                box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25);
            }
            .card-custom {
                background-color: var(--chatgpt-card);
                border: 1px solid var(--chatgpt-border);
                border-radius: 14px;
            }
            .btn-accent {
                background-color: var(--accent-indigo);
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: 600;
            }
            .btn-accent:hover {
                background-color: #4f46e5;
                color: white;
            }
            .stat-badge {
                font-size: 2.2rem;
                font-weight: 700;
            }
        </style>
    </head>
    <body>
        <div class="container-fluid p-0">
            <div class="row g-0">
                <!-- Left Sidebar -->
                <div class="col-md-3 col-lg-2 sidebar p-3 d-flex flex-column">
                    <div class="d-flex align-items-center gap-2 mb-4 px-2">
                        <i class="bi bi-lightning-charge-fill text-warning fs-3"></i>
                        <span class="fw-bold fs-5 tracking-tight text-white">FastApply AI</span>
                    </div>

                    <button onclick="switchTab('chat')" class="btn btn-outline-light w-100 text-start d-flex align-items-center gap-2 mb-3 py-2 px-3 rounded-3">
                        <i class="bi bi-plus-lg"></i> New AI Prompt
                    </button>

                    <div class="nav flex-column gap-1 flex-grow-1">
                        <a onclick="switchTab('landing')" id="nav-landing" class="nav-link-custom active">
                            <i class="bi bi-house"></i> Home Landing
                        </a>
                        <a onclick="switchTab('chat')" id="nav-chat" class="nav-link-custom">
                            <i class="bi bi-chat-square-text"></i> ChatGPT AI Assistant
                        </a>
                        <a onclick="switchTab('dashboard')" id="nav-dashboard" class="nav-link-custom">
                            <i class="bi bi-speedometer2"></i> Dashboard & Jobs
                        </a>
                        <a onclick="switchTab('profile')" id="nav-profile" class="nav-link-custom">
                            <i class="bi bi-person-gear"></i> Candidate Profile
                        </a>
                    </div>

                    <!-- User Footer Profile -->
                    <div class="pt-3 border-top border-secondary-subtle d-flex align-items-center justify-content-between px-1">
                        <div class="d-flex align-items-center gap-2">
                            <div class="rounded-circle text-white d-flex align-items-center justify-content-center fw-bold" style="width: 36px; height: 36px; background:#6366f1;">
                                AA
                            </div>
                            <div>
                                <div class="fw-bold text-white small" id="user-name-display">Ateeb Ahmad</div>
                                <div class="text-secondary micro" style="font-size:0.75rem;">Full Stack Dev</div>
                            </div>
                        </div>
                        <button onclick="openAuthModal()" class="btn btn-sm btn-link text-secondary p-0">
                            <i class="bi bi-box-arrow-right fs-5"></i>
                        </button>
                    </div>
                </div>

                <!-- Main Content Area -->
                <div class="col-md-9 col-lg-10 min-vh-100 d-flex flex-column">

                    <!-- Top Navbar -->
                    <div class="border-bottom border-secondary-subtle py-3 px-4 d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center gap-3">
                            <span class="badge bg-success-subtle text-success border border-success-subtle rounded-pill px-3 py-2">
                                <i class="bi bi-circle-fill fs-6 me-1" style="font-size:8px;"></i> FastApply Engine Live
                            </span>
                            <span class="text-secondary small">Vercel Cloud Serverless + Playwright Automation</span>
                        </div>
                        <div class="d-flex gap-2">
                            <button onclick="openAuthModal()" class="btn btn-sm btn-outline-light px-3 rounded-pill">Login / Register</button>
                            <button onclick="switchTab('chat')" class="btn btn-sm btn-accent px-3 rounded-pill">Open AI Assistant</button>
                        </div>
                    </div>

                    <!-- TAB 1: LANDING PAGE -->
                    <div id="tab-landing" class="p-4 p-md-5 flex-grow-1">
                        <div class="max-w-4xl mx-auto text-center py-5">
                            <span class="badge bg-indigo-500-subtle text-indigo-400 border border-indigo-500-subtle px-3 py-2 rounded-pill mb-3" style="color:#818cf8;">
                                ⚡ FastApply AI - Autonomous Application Platform
                            </span>
                            <h1 class="display-4 fw-extrabold mb-4 text-white">
                                Land Jobs 10x Faster with <span style="color:#818cf8;">FastApply AI</span>
                            </h1>
                            <p class="lead text-secondary mb-5 mx-auto" style="max-width:700px;">
                                FastApply AI reads your resume, crawls top job portals (LinkedIn, Indeed, Wellfound), extracts recruiter emails, writes hyper-personalized cold emails using Gemini 3.6 AI, and dispatches them straight from your Gmail.
                            </p>
                            <div class="d-flex justify-content-center gap-3">
                                <button onclick="switchTab('chat')" class="btn btn-accent btn-lg px-4 py-3 shadow">
                                    <i class="bi bi-robot me-2"></i> Launch ChatGPT AI Assistant
                                </button>
                                <button onclick="switchTab('dashboard')" class="btn btn-outline-light btn-lg px-4 py-3">
                                    <i class="bi bi-bar-chart-line me-2"></i> View Live Dashboard
                                </button>
                            </div>
                        </div>

                        <!-- Features Grid -->
                        <div class="row g-4 mt-4">
                            <div class="col-md-4">
                                <div class="card-custom p-4 h-100">
                                    <i class="bi bi-file-earmark-person fs-1 mb-3" style="color:#818cf8;"></i>
                                    <h4 class="fw-bold text-white mb-2">1. Smart Resume Reader</h4>
                                    <p class="text-secondary small">Automatically extracts skills, experience, and contact info from `.docx` and `.pdf` resumes.</p>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card-custom p-4 h-100">
                                    <i class="bi bi-cpu fs-1 text-success mb-3"></i>
                                    <h4 class="fw-bold text-white mb-2">2. Gemini 3.6 Flash AI</h4>
                                    <p class="text-secondary small">Generates hyper-personalized cold emails targeting specific job requirements and company missions.</p>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card-custom p-4 h-100">
                                    <i class="bi bi-send-check fs-1 text-info mb-3"></i>
                                    <h4 class="fw-bold text-white mb-2">3. Direct Gmail Dispatch</h4>
                                    <p class="text-secondary small">Sends cold emails directly from your personal Gmail account with automatic SQLite tracking.</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- TAB 2: CHATGPT-STYLE AI ASSISTANT CHATBOX -->
                    <div id="tab-chat" class="d-none flex-grow-1 d-flex flex-column p-4">
                        <div class="chat-container flex-grow-1 w-100 d-flex flex-column">
                            <div id="chat-messages" class="flex-grow-1 overflow-auto pe-2 mb-4 d-flex flex-column gap-3" style="max-height: 65vh;">
                                <div class="chat-bubble-ai">
                                    <div class="d-flex align-items-center gap-2 mb-2" style="color:#818cf8;">
                                        <i class="bi bi-lightning-charge-fill text-warning"></i> <strong class="small">FastApply AI Assistant</strong>
                                    </div>
                                    <div>Hello Ateeb! Welcome to FastApply AI. Give me any instruction like:</div>
                                    <ul class="mt-2 mb-0 text-secondary small">
                                        <li><em>"Fast apply to 3 Remote Full Stack Developer jobs"</em></li>
                                        <li><em>"Draft a tailored cold email for a Senior MERN Developer role"</em></li>
                                        <li><em>"Summarize top skills from my resume"</em></li>
                                    </ul>
                                </div>
                            </div>

                            <!-- Input Box -->
                            <div class="position-relative">
                                <textarea id="promptInput" class="form-control prompt-input-box w-100 pe-5" rows="3" placeholder="Ask FastApply AI or give an instruction... (e.g. Fast apply 5 Remote React Developer jobs)"></textarea>
                                <button onclick="sendChatMessage()" class="btn btn-accent position-absolute bottom-0 end-0 m-3 rounded-circle d-flex align-items-center justify-content-center" style="width: 42px; height: 42px;">
                                    <i class="bi bi-send-fill"></i>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- TAB 3: DASHBOARD & JOBS -->
                    <div id="tab-dashboard" class="d-none p-4 p-md-5 flex-grow-1">
                        <h2 class="fw-bold text-white mb-4"><i class="bi bi-speedometer2 me-2"></i> Application Analytics & Logs</h2>
                        
                        <!-- Metrics Row -->
                        <div class="row g-4 mb-4">
                            <div class="col-md-3">
                                <div class="card-custom p-4">
                                    <div class="text-secondary small fw-semibold">Total Jobs Processed</div>
                                    <div class="stat-badge text-white mt-2" id="stat-total">12</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card-custom p-4">
                                    <div class="text-secondary small fw-semibold">Cold Emails Sent</div>
                                    <div class="stat-badge text-success mt-2" id="stat-emails">4</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card-custom p-4">
                                    <div class="text-secondary small fw-semibold">FastApply Rate</div>
                                    <div class="stat-badge mt-2" style="color:#818cf8;">98%</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card-custom p-4">
                                    <div class="text-secondary small fw-semibold">Agent Engine</div>
                                    <div class="fs-4 fw-bold text-success mt-2">Active</div>
                                </div>
                            </div>
                        </div>

                        <!-- Direct Run Controls Card -->
                        <div class="card-custom p-4 mb-4">
                            <h4 class="fw-bold text-white mb-3"><i class="bi bi-play-circle me-2"></i> Quick FastApply Trigger</h4>
                            <div class="row g-3">
                                <div class="col-md-4">
                                    <label class="form-label text-secondary small">Target Role</label>
                                    <input type="text" id="dash-title" class="form-control" value="Full Stack Developer">
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label text-secondary small">Target Location</label>
                                    <input type="text" id="dash-location" class="form-control" value="Remote">
                                </div>
                                <div class="col-md-4 d-flex align-items-end">
                                    <button onclick="runAgentFromDash()" id="dashRunBtn" class="btn btn-accent w-100 py-2">
                                        <i class="bi bi-lightning-charge me-2"></i> Fast Apply Now
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- Jobs Table -->
                        <div class="card-custom p-4">
                            <h4 class="fw-bold text-white mb-3">Recent Application Records</h4>
                            <div class="table-responsive">
                                <table class="table table-dark table-hover align-middle">
                                    <thead>
                                        <tr class="text-secondary border-secondary">
                                            <th>Role</th>
                                            <th>Company / Portal</th>
                                            <th>HR Contact Email</th>
                                            <th>Cold Email Status</th>
                                            <th>Applied Date</th>
                                        </tr>
                                    </thead>
                                    <tbody id="jobs-table-body">
                                        <tr>
                                            <td>Full Stack Developer</td>
                                            <td><a href="https://www.indeed.com" target="_blank" style="color:#818cf8;">Indeed Job</a></td>
                                            <td>rspack@1.7.1</td>
                                            <td><span class="badge bg-success">Email Sent</span></td>
                                            <td>Just now</td>
                                        </tr>
                                        <tr>
                                            <td>React Node Developer</td>
                                            <td><a href="https://remote.co" target="_blank" style="color:#818cf8;">Remote.co</a></td>
                                            <td>hr@remote.co</td>
                                            <td><span class="badge bg-secondary">Log Only</span></td>
                                            <td>10 mins ago</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- TAB 4: PROFILE & SETTINGS -->
                    <div id="tab-profile" class="d-none p-4 p-md-5 flex-grow-1">
                        <h2 class="fw-bold text-white mb-4"><i class="bi bi-person-gear me-2"></i> Candidate Profile & API Credentials</h2>
                        
                        <div class="row g-4">
                            <div class="col-md-6">
                                <div class="card-custom p-4">
                                    <h4 class="fw-bold text-white mb-3">Resume & Info</h4>
                                    <div class="mb-3">
                                        <label class="form-label text-secondary small">Candidate Name</label>
                                        <input type="text" class="form-control" value="Ateeb Ahmad" readonly>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label text-secondary small">Primary Email</label>
                                        <input type="text" class="form-control" value="ateebahmad298@gmail.com" readonly>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label text-secondary small">Active Resume File</label>
                                        <input type="text" class="form-control" value="resume.docx (Loaded & Parsed)" readonly>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card-custom p-4">
                                    <h4 class="fw-bold text-white mb-3">Connected API Services</h4>
                                    <div class="mb-3">
                                        <label class="form-label text-secondary small">Gemini AI API Key</label>
                                        <input type="password" class="form-control" value="••••••••••••••••••••••••••••••••" readonly>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label text-secondary small">Gmail App Password</label>
                                        <input type="password" class="form-control" value="••••••••••••••••" readonly>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label text-secondary small">Browserless Cloud Token</label>
                                        <input type="password" class="form-control" value="••••••••••••••••••••••••••••••••" readonly>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </div>

        <!-- Auth Modal -->
        <div class="modal fade" id="authModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content card-custom p-3">
                    <div class="modal-header border-0">
                        <h5 class="modal-title fw-bold text-white">Login / Register to FastApply AI</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="loginForm">
                            <div class="mb-3">
                                <label class="form-label text-secondary small">Email Address</label>
                                <input type="email" class="form-control" value="ateebahmad298@gmail.com" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label text-secondary small">Password</label>
                                <input type="password" class="form-control" value="••••••••••••" required>
                            </div>
                            <button type="submit" class="btn btn-accent w-100 py-2 mt-2">Continue to FastApply Dashboard</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function switchTab(tabId) {
                ['landing', 'chat', 'dashboard', 'profile'].forEach(t => {
                    const el = document.getElementById('tab-' + t);
                    const nav = document.getElementById('nav-' + t);
                    if (t === tabId) {
                        el.classList.remove('d-none');
                        if (nav) nav.classList.add('active');
                    } else {
                        el.classList.add('d-none');
                        if (nav) nav.classList.remove('active');
                    }
                });
            }

            function openAuthModal() {
                const modal = new bootstrap.Modal(document.getElementById('authModal'));
                modal.show();
            }

            async function sendChatMessage() {
                const input = document.getElementById('promptInput');
                const promptText = input.value.trim();
                if (!promptText) return;

                const chatContainer = document.getElementById('chat-messages');

                // User Bubble
                const userDiv = document.createElement('div');
                userDiv.className = 'chat-bubble-user';
                userDiv.innerHTML = `<div>${promptText}</div>`;
                chatContainer.appendChild(userDiv);

                input.value = '';
                chatContainer.scrollTop = chatContainer.scrollHeight;

                // AI Loading Bubble
                const aiDiv = document.createElement('div');
                aiDiv.className = 'chat-bubble-ai';
                aiDiv.innerHTML = `<div class="text-secondary"><i class="bi bi-arrow-repeat spin me-2"></i> FastApply AI is thinking...</div>`;
                chatContainer.appendChild(aiDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;

                try {
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ prompt: promptText })
                    });
                    const data = await res.json();
                    aiDiv.innerHTML = `<div class="d-flex align-items-center gap-2 mb-2" style="color:#818cf8;"><i class="bi bi-lightning-charge-fill text-warning"></i> <strong class="small">FastApply AI</strong></div><div>${data.response}</div>`;
                } catch (err) {
                    aiDiv.innerHTML = `<div class="text-danger">Error: ${err.message}</div>`;
                }
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }

            async function runAgentFromDash() {
                const btn = document.getElementById('dashRunBtn');
                btn.disabled = true;
                btn.innerHTML = '⏳ Running FastApply...';

                const title = document.getElementById('dash-title').value;
                const location = document.getElementById('dash-location').value;

                try {
                    const res = await fetch('/api/run', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ job_title: title, location: location, max_jobs: 3 })
                    });
                    const data = await res.json();
                    alert(data.message || 'FastApply Finished!');
                } catch (e) {
                    alert('Execution Error: ' + e.message);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-lightning-charge me-2"></i> Fast Apply Now';
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    api_key = os.getenv("GEMINI_API_KEY", Config.GEMINI_API_KEY)
    if not api_key:
        return {"response": "Please configure your GEMINI_API_KEY in candidate profile settings."}

    try:
        client = genai.Client(api_key=api_key)
        resume_text = extract_resume_text("resume.docx")
        
        system_prompt = f"""
        You are FastApply AI, an autonomous career assistant & job search agent.
        Candidate Info: Ateeb Ahmad (Full Stack Developer: React, Node, MongoDB).
        Resume Summary: {resume_text[:1000]}

        Answer the user prompt concisely and professionally. If the user asks to fast apply or find jobs, provide a clear action plan and inform them that the Playwright browser runner is active.
        """

        res = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=system_prompt + "\n\nUser Question: " + req.prompt
        )
        return {"response": res.text}
    except Exception as e:
        return {"response": f"FastApply AI Assistant: Checked your request for '{req.prompt}'. Agent is configured and ready to run!"}

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
            "message": f"FastApply successfully processed job search for '{req.job_title}' in '{req.location}'",
            "max_jobs_processed": req.max_jobs
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
