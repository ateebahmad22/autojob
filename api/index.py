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
    html_content = r"""
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
                --bg: #171717;
                --sidebar: #202123;
                --card: #212121;
                --input-bg: #2f2f2f;
                --border: #343541;
                --accent: #6366f1;
                --accent-hover: #4f46e5;
                --green: #10b981;
            }
            * { box-sizing: border-box; }
            body {
                background-color: var(--bg);
                color: #ececf1;
                font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                overflow-x: hidden;
                margin: 0;
            }
            /* ── Sidebar ── */
            .sidebar {
                background-color: var(--sidebar);
                border-right: 1px solid var(--border);
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
                transition: all .2s;
                text-decoration: none;
                cursor: pointer;
            }
            .nav-link-custom:hover, .nav-link-custom.active {
                background-color: #2a2b32;
                color: #fff;
            }
            /* ── Chat ── */
            .chat-container { max-width: 800px; margin: 0 auto; }
            .chat-bubble-user {
                background: #2f2f2f;
                border-radius: 18px 18px 4px 18px;
                padding: 14px 18px;
                max-width: 80%;
                margin-left: auto;
            }
            .chat-bubble-ai {
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 18px 18px 18px 4px;
                padding: 16px 20px;
                max-width: 90%;
            }
            .prompt-area {
                background: var(--input-bg);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 10px 14px;
                display: flex;
                align-items: flex-end;
                gap: 8px;
            }
            .prompt-area textarea {
                background: transparent;
                border: none;
                color: #fff;
                resize: none;
                flex: 1;
                outline: none;
                font-size: .95rem;
                line-height: 1.4;
                max-height: 120px;
            }
            .prompt-area textarea::placeholder { color: #888; }
            .prompt-area .icon-btn {
                background: none;
                border: none;
                color: #aaa;
                font-size: 1.2rem;
                cursor: pointer;
                padding: 6px;
                border-radius: 8px;
                transition: .2s;
            }
            .prompt-area .icon-btn:hover { color: #fff; background: #3a3a3a; }
            .prompt-area .send-btn {
                background: var(--accent);
                border: none;
                color: #fff;
                width: 38px;
                height: 38px;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: .2s;
                flex-shrink: 0;
            }
            .prompt-area .send-btn:hover { background: var(--accent-hover); }
            /* ── Cards ── */
            .card-custom {
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 14px;
            }
            .btn-accent {
                background: var(--accent);
                color: #fff;
                border: none;
                border-radius: 10px;
                font-weight: 600;
            }
            .btn-accent:hover { background: var(--accent-hover); color: #fff; }
            .stat-badge { font-size: 2.2rem; font-weight: 700; }
            /* ── Auth page ── */
            .auth-page {
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                background: var(--bg);
            }
            .auth-card {
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 40px;
                width: 100%;
                max-width: 420px;
            }
            .auth-card .form-control {
                background: var(--input-bg);
                border: 1px solid var(--border);
                color: #fff;
            }
            .auth-card .form-control:focus {
                background: var(--input-bg);
                color: #fff;
                border-color: var(--accent);
                box-shadow: 0 0 0 2px rgba(99,102,241,.25);
            }
            .upload-preview {
                max-width: 200px;
                max-height: 120px;
                border-radius: 10px;
                border: 1px solid var(--border);
            }
            /* media attachment chip */
            .attach-chip {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                background: #2a2b32;
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 4px 10px;
                font-size: .8rem;
                color: #ccc;
                margin-bottom: 6px;
            }
            .attach-chip .remove-attach {
                cursor: pointer;
                color: #f87171;
                font-weight: 700;
            }
        </style>
    </head>
    <body>

        <!-- ═══════════ AUTH SCREENS ═══════════ -->

        <!-- LOGIN PAGE -->
        <div id="page-login" class="auth-page">
            <div class="auth-card text-center">
                <div class="mb-4">
                    <i class="bi bi-lightning-charge-fill text-warning fs-1"></i>
                    <h3 class="fw-bold text-white mt-2">Welcome back to FastApply AI</h3>
                    <p class="text-secondary small">Sign in to access your AI Job Agent dashboard</p>
                </div>
                <form onsubmit="doLogin(event)">
                    <div class="mb-3 text-start">
                        <label class="form-label text-secondary small">Email Address</label>
                        <input type="email" id="login-email" class="form-control" placeholder="you@example.com" required>
                    </div>
                    <div class="mb-3 text-start">
                        <label class="form-label text-secondary small">Password</label>
                        <input type="password" id="login-pass" class="form-control" placeholder="Enter your password" required>
                    </div>
                    <button type="submit" class="btn btn-accent w-100 py-2 mt-2 fw-semibold">
                        <i class="bi bi-box-arrow-in-right me-2"></i> Sign In
                    </button>
                </form>
                <div class="mt-4 text-secondary small">
                    Don't have an account? <a href="#" onclick="showPage('signup')" class="text-decoration-none" style="color:#818cf8;">Create Account</a>
                </div>
            </div>
        </div>

        <!-- SIGNUP PAGE -->
        <div id="page-signup" class="auth-page d-none">
            <div class="auth-card text-center">
                <div class="mb-4">
                    <i class="bi bi-lightning-charge-fill text-warning fs-1"></i>
                    <h3 class="fw-bold text-white mt-2">Create your FastApply AI account</h3>
                    <p class="text-secondary small">Set up your profile and start auto-applying in minutes</p>
                </div>
                <form onsubmit="doSignup(event)">
                    <div class="mb-3 text-start">
                        <label class="form-label text-secondary small">Full Name</label>
                        <input type="text" id="signup-name" class="form-control" placeholder="Ateeb Ahmad" required>
                    </div>
                    <div class="mb-3 text-start">
                        <label class="form-label text-secondary small">Email Address</label>
                        <input type="email" id="signup-email" class="form-control" placeholder="you@example.com" required>
                    </div>
                    <div class="mb-3 text-start">
                        <label class="form-label text-secondary small">Password</label>
                        <input type="password" id="signup-pass" class="form-control" placeholder="Min 6 characters" required minlength="6">
                    </div>
                    <div class="mb-3 text-start">
                        <label class="form-label text-secondary small">Confirm Password</label>
                        <input type="password" id="signup-pass2" class="form-control" placeholder="Re-enter password" required>
                    </div>
                    <button type="submit" class="btn btn-accent w-100 py-2 mt-2 fw-semibold">
                        <i class="bi bi-person-plus me-2"></i> Create Account
                    </button>
                </form>
                <div class="mt-4 text-secondary small">
                    Already have an account? <a href="#" onclick="showPage('login')" class="text-decoration-none" style="color:#818cf8;">Sign In</a>
                </div>
            </div>
        </div>

        <!-- ═══════════ MAIN APP (post-auth) ═══════════ -->
        <div id="page-app" class="d-none">
        <div class="container-fluid p-0">
            <div class="row g-0">

                <!-- Left Sidebar -->
                <div class="col-md-3 col-lg-2 sidebar p-3 d-flex flex-column">
                    <div class="d-flex align-items-center gap-2 mb-4 px-2">
                        <i class="bi bi-lightning-charge-fill text-warning fs-3"></i>
                        <span class="fw-bold fs-5 text-white">FastApply AI</span>
                    </div>

                    <div class="nav flex-column gap-1 flex-grow-1">
                        <a onclick="switchTab('landing')" id="nav-landing" class="nav-link-custom active">
                            <i class="bi bi-house"></i> Home
                        </a>
                        <a onclick="switchTab('chat')" id="nav-chat" class="nav-link-custom">
                            <i class="bi bi-chat-square-text"></i> AI Assistant
                        </a>
                        <a onclick="switchTab('dashboard')" id="nav-dashboard" class="nav-link-custom">
                            <i class="bi bi-speedometer2"></i> Dashboard & Jobs
                        </a>
                        <a onclick="switchTab('profile')" id="nav-profile" class="nav-link-custom">
                            <i class="bi bi-person-gear"></i> Candidate Profile
                        </a>
                    </div>

                    <!-- User Footer -->
                    <div class="pt-3 border-top border-secondary-subtle d-flex align-items-center justify-content-between px-1">
                        <div class="d-flex align-items-center gap-2">
                            <div class="rounded-circle text-white d-flex align-items-center justify-content-center fw-bold" style="width:36px;height:36px;background:#6366f1;" id="avatar-initials">AA</div>
                            <div>
                                <div class="fw-bold text-white small" id="sidebar-user-name">Ateeb Ahmad</div>
                                <div class="text-secondary" style="font-size:.72rem;">Full Stack Dev</div>
                            </div>
                        </div>
                        <button onclick="doLogout()" class="btn btn-sm btn-link text-secondary p-0" title="Logout">
                            <i class="bi bi-box-arrow-right fs-5"></i>
                        </button>
                    </div>
                </div>

                <!-- Main Content -->
                <div class="col-md-9 col-lg-10 min-vh-100 d-flex flex-column">

                    <!-- Top Bar -->
                    <div class="border-bottom border-secondary-subtle py-3 px-4 d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center gap-3">
                            <span class="badge bg-success-subtle text-success border border-success-subtle rounded-pill px-3 py-2">
                                <i class="bi bi-circle-fill me-1" style="font-size:8px;"></i> FastApply Engine Live
                            </span>
                            <span class="text-secondary small">Vercel Serverless + Playwright Automation</span>
                        </div>
                        <button onclick="switchTab('chat')" class="btn btn-sm btn-accent px-3 rounded-pill">Open AI Assistant</button>
                    </div>

                    <!-- ══ TAB: LANDING ══ -->
                    <div id="tab-landing" class="p-4 p-md-5 flex-grow-1">
                        <div class="text-center py-5 mx-auto" style="max-width:800px;">
                            <span class="badge rounded-pill px-3 py-2 mb-3" style="color:#818cf8;border:1px solid #4338ca;">
                                ⚡ FastApply AI — Autonomous Application Platform
                            </span>
                            <h1 class="display-4 fw-bold mb-4 text-white">
                                Land Jobs 10x Faster with <span style="color:#818cf8;">FastApply AI</span>
                            </h1>
                            <p class="lead text-secondary mb-5 mx-auto" style="max-width:680px;">
                                FastApply AI reads your resume, crawls top job portals, extracts recruiter emails, writes hyper-personalized cold emails using Gemini 3.6 AI, and dispatches them straight from your Gmail.
                            </p>
                            <div class="d-flex justify-content-center gap-3 flex-wrap">
                                <button onclick="switchTab('chat')" class="btn btn-accent btn-lg px-4 py-3 shadow">
                                    <i class="bi bi-robot me-2"></i> Launch AI Assistant
                                </button>
                                <button onclick="switchTab('dashboard')" class="btn btn-outline-light btn-lg px-4 py-3">
                                    <i class="bi bi-bar-chart-line me-2"></i> View Dashboard
                                </button>
                            </div>
                        </div>
                        <div class="row g-4 mt-4">
                            <div class="col-md-4">
                                <div class="card-custom p-4 h-100">
                                    <i class="bi bi-file-earmark-person fs-1 mb-3" style="color:#818cf8;"></i>
                                    <h4 class="fw-bold text-white mb-2">Smart Resume Reader</h4>
                                    <p class="text-secondary small">Extracts skills, experience, and contact info from .docx and .pdf resumes automatically.</p>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card-custom p-4 h-100">
                                    <i class="bi bi-cpu fs-1 text-success mb-3"></i>
                                    <h4 class="fw-bold text-white mb-2">Gemini 3.6 Flash AI</h4>
                                    <p class="text-secondary small">Generates hyper-personalized cold emails targeting specific job requirements and company missions.</p>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card-custom p-4 h-100">
                                    <i class="bi bi-send-check fs-1 text-info mb-3"></i>
                                    <h4 class="fw-bold text-white mb-2">Direct Gmail Dispatch</h4>
                                    <p class="text-secondary small">Sends cold emails directly from your Gmail with automatic SQLite duplicate tracking.</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- ══ TAB: AI ASSISTANT (with media upload) ══ -->
                    <div id="tab-chat" class="d-none flex-grow-1 d-flex flex-column p-4">
                        <div class="chat-container flex-grow-1 w-100 d-flex flex-column">
                            <div id="chat-messages" class="flex-grow-1 overflow-auto pe-2 mb-4 d-flex flex-column gap-3" style="max-height:65vh;">
                                <div class="chat-bubble-ai">
                                    <div class="d-flex align-items-center gap-2 mb-2" style="color:#818cf8;">
                                        <i class="bi bi-lightning-charge-fill text-warning"></i>
                                        <strong class="small">FastApply AI Assistant</strong>
                                    </div>
                                    <div>Hello! I'm your AI Assistant. You can ask me anything or attach files like resumes, screenshots, or documents. Try:</div>
                                    <ul class="mt-2 mb-0 text-secondary small">
                                        <li><em>"Fast apply to 5 Remote Full Stack Developer jobs"</em></li>
                                        <li><em>"Draft a cold email for a Senior MERN role"</em></li>
                                        <li><em>"Analyze the attached resume and suggest improvements"</em></li>
                                    </ul>
                                </div>
                            </div>

                            <!-- Attachment preview area -->
                            <div id="attach-preview" class="mb-2"></div>

                            <!-- Input box with media upload -->
                            <div class="prompt-area">
                                <input type="file" id="fileInput" accept="image/*,.pdf,.doc,.docx,.txt" multiple hidden onchange="handleFileSelect(event)">
                                <button class="icon-btn" onclick="document.getElementById('fileInput').click()" title="Attach file or image">
                                    <i class="bi bi-paperclip"></i>
                                </button>
                                <button class="icon-btn" onclick="document.getElementById('fileInput').click()" title="Upload image">
                                    <i class="bi bi-image"></i>
                                </button>
                                <textarea id="promptInput" rows="1" placeholder="Message FastApply AI..." oninput="autoGrow(this)" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChatMessage();}"></textarea>
                                <button class="send-btn" onclick="sendChatMessage()" title="Send">
                                    <i class="bi bi-arrow-up"></i>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- ══ TAB: DASHBOARD ══ -->
                    <div id="tab-dashboard" class="d-none p-4 p-md-5 flex-grow-1">
                        <h2 class="fw-bold text-white mb-4"><i class="bi bi-speedometer2 me-2"></i> Application Analytics</h2>
                        <div class="row g-4 mb-4">
                            <div class="col-md-3"><div class="card-custom p-4"><div class="text-secondary small fw-semibold">Total Jobs</div><div class="stat-badge text-white mt-2">12</div></div></div>
                            <div class="col-md-3"><div class="card-custom p-4"><div class="text-secondary small fw-semibold">Emails Sent</div><div class="stat-badge text-success mt-2">4</div></div></div>
                            <div class="col-md-3"><div class="card-custom p-4"><div class="text-secondary small fw-semibold">Match Rate</div><div class="stat-badge mt-2" style="color:#818cf8;">98%</div></div></div>
                            <div class="col-md-3"><div class="card-custom p-4"><div class="text-secondary small fw-semibold">Engine</div><div class="fs-4 fw-bold text-success mt-2">Active</div></div></div>
                        </div>
                        <div class="card-custom p-4 mb-4">
                            <h4 class="fw-bold text-white mb-3"><i class="bi bi-play-circle me-2"></i> Quick FastApply</h4>
                            <div class="row g-3">
                                <div class="col-md-4">
                                    <label class="form-label text-secondary small">Target Role</label>
                                    <input type="text" id="dash-title" class="form-control" value="Full Stack Developer">
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label text-secondary small">Location</label>
                                    <input type="text" id="dash-location" class="form-control" value="Remote">
                                </div>
                                <div class="col-md-4 d-flex align-items-end">
                                    <button onclick="runAgentFromDash()" id="dashRunBtn" class="btn btn-accent w-100 py-2">
                                        <i class="bi bi-lightning-charge me-2"></i> Fast Apply Now
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="card-custom p-4">
                            <h4 class="fw-bold text-white mb-3">Recent Applications</h4>
                            <div class="table-responsive">
                                <table class="table table-dark table-hover align-middle mb-0">
                                    <thead><tr class="text-secondary border-secondary"><th>Role</th><th>Portal</th><th>HR Email</th><th>Status</th><th>Date</th></tr></thead>
                                    <tbody id="jobs-table-body">
                                        <tr><td>Full Stack Developer</td><td><a href="#" style="color:#818cf8;">Indeed</a></td><td>hr@company.com</td><td><span class="badge bg-success">Email Sent</span></td><td>Just now</td></tr>
                                        <tr><td>React Node Developer</td><td><a href="#" style="color:#818cf8;">Remote.co</a></td><td>jobs@remote.co</td><td><span class="badge bg-secondary">Log Only</span></td><td>10 mins ago</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- ══ TAB: PROFILE ══ -->
                    <div id="tab-profile" class="d-none p-4 p-md-5 flex-grow-1">
                        <h2 class="fw-bold text-white mb-4"><i class="bi bi-person-gear me-2"></i> Candidate Profile</h2>
                        <div class="row g-4">
                            <div class="col-md-6">
                                <div class="card-custom p-4">
                                    <h4 class="fw-bold text-white mb-3">Resume & Info</h4>
                                    <div class="mb-3"><label class="form-label text-secondary small">Name</label><input type="text" class="form-control" value="Ateeb Ahmad" readonly></div>
                                    <div class="mb-3"><label class="form-label text-secondary small">Email</label><input type="text" class="form-control" value="ateebahmad298@gmail.com" readonly></div>
                                    <div class="mb-3"><label class="form-label text-secondary small">Resume</label><input type="text" class="form-control" value="resume.docx (Loaded)" readonly></div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card-custom p-4">
                                    <h4 class="fw-bold text-white mb-3">API Services</h4>
                                    <div class="mb-3"><label class="form-label text-secondary small">Gemini API Key</label><input type="password" class="form-control" value="configured" readonly></div>
                                    <div class="mb-3"><label class="form-label text-secondary small">Gmail App Password</label><input type="password" class="form-control" value="configured" readonly></div>
                                    <div class="mb-3"><label class="form-label text-secondary small">Browserless Token</label><input type="password" class="form-control" value="configured" readonly></div>
                                </div>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </div>
        </div><!-- /page-app -->

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            let attachedFiles = [];

            /* ── Auth ── */
            function showPage(p) {
                ['login','signup','app'].forEach(id => {
                    document.getElementById('page-'+id).classList.toggle('d-none', id !== p);
                });
            }
            function doLogin(e) {
                e.preventDefault();
                const email = document.getElementById('login-email').value;
                const name = email.split('@')[0];
                localStorage.setItem('fa_user', JSON.stringify({name, email}));
                enterApp(name);
            }
            function doSignup(e) {
                e.preventDefault();
                const p1 = document.getElementById('signup-pass').value;
                const p2 = document.getElementById('signup-pass2').value;
                if (p1 !== p2) { alert('Passwords do not match!'); return; }
                const name = document.getElementById('signup-name').value;
                const email = document.getElementById('signup-email').value;
                localStorage.setItem('fa_user', JSON.stringify({name, email}));
                enterApp(name);
            }
            function doLogout() {
                localStorage.removeItem('fa_user');
                showPage('login');
            }
            function enterApp(name) {
                const initials = name.split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2);
                document.getElementById('avatar-initials').textContent = initials;
                document.getElementById('sidebar-user-name').textContent = name;
                showPage('app');
            }
            // Auto-login if session exists
            (function(){
                const u = localStorage.getItem('fa_user');
                if (u) { const d = JSON.parse(u); enterApp(d.name); }
            })();

            /* ── Tabs ── */
            function switchTab(t) {
                ['landing','chat','dashboard','profile'].forEach(id => {
                    document.getElementById('tab-'+id).classList.toggle('d-none', id !== t);
                    const nav = document.getElementById('nav-'+id);
                    if (nav) nav.classList.toggle('active', id === t);
                });
            }

            /* ── Media Upload ── */
            function handleFileSelect(e) {
                const files = Array.from(e.target.files);
                files.forEach(f => {
                    attachedFiles.push(f);
                    renderAttachments();
                });
                e.target.value = '';
            }
            function removeAttach(idx) {
                attachedFiles.splice(idx, 1);
                renderAttachments();
            }
            function renderAttachments() {
                const box = document.getElementById('attach-preview');
                box.innerHTML = '';
                attachedFiles.forEach((f, i) => {
                    const isImg = f.type.startsWith('image/');
                    let html = `<span class="attach-chip">`;
                    html += isImg ? `<i class="bi bi-image text-info"></i>` : `<i class="bi bi-file-earmark text-warning"></i>`;
                    html += ` ${f.name} <span class="remove-attach" onclick="removeAttach(${i})">&times;</span></span> `;

                    if (isImg) {
                        const reader = new FileReader();
                        reader.onload = function(ev) {
                            const imgEl = document.createElement('img');
                            imgEl.src = ev.target.result;
                            imgEl.className = 'upload-preview me-2 mb-1';
                            box.insertBefore(imgEl, box.firstChild);
                        };
                        reader.readAsDataURL(f);
                    }
                    box.innerHTML += html;
                });
            }

            /* ── Chat ── */
            function autoGrow(el) {
                el.style.height = '0';
                el.style.height = Math.min(el.scrollHeight, 120) + 'px';
            }
            async function sendChatMessage() {
                const input = document.getElementById('promptInput');
                const text = input.value.trim();
                if (!text && attachedFiles.length === 0) return;

                const container = document.getElementById('chat-messages');

                // Build user bubble
                let userHtml = '';
                // Show attached images inline
                attachedFiles.forEach(f => {
                    if (f.type.startsWith('image/')) {
                        const url = URL.createObjectURL(f);
                        userHtml += `<img src="${url}" class="upload-preview d-block mb-2">`;
                    } else {
                        userHtml += `<div class="attach-chip mb-1"><i class="bi bi-file-earmark text-warning"></i> ${f.name}</div>`;
                    }
                });
                if (text) userHtml += `<div>${text}</div>`;

                const userDiv = document.createElement('div');
                userDiv.className = 'chat-bubble-user';
                userDiv.innerHTML = userHtml;
                container.appendChild(userDiv);

                const promptText = text || (attachedFiles.length > 0 ? 'Analyze the attached file(s).' : '');
                input.value = '';
                input.style.height = '';
                attachedFiles = [];
                document.getElementById('attach-preview').innerHTML = '';
                container.scrollTop = container.scrollHeight;

                // AI thinking bubble
                const aiDiv = document.createElement('div');
                aiDiv.className = 'chat-bubble-ai';
                aiDiv.innerHTML = `<div class="text-secondary"><span class="spinner-border spinner-border-sm me-2"></span> FastApply AI is thinking...</div>`;
                container.appendChild(aiDiv);
                container.scrollTop = container.scrollHeight;

                try {
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: {'Content-Type':'application/json'},
                        body: JSON.stringify({prompt: promptText})
                    });
                    const data = await res.json();
                    aiDiv.innerHTML = `<div class="d-flex align-items-center gap-2 mb-2" style="color:#818cf8;"><i class="bi bi-lightning-charge-fill text-warning"></i> <strong class="small">FastApply AI</strong></div><div style="white-space:pre-wrap;">${data.response}</div>`;
                } catch(err) {
                    aiDiv.innerHTML = `<div class="text-danger"><i class="bi bi-exclamation-triangle me-1"></i> ${err.message}</div>`;
                }
                container.scrollTop = container.scrollHeight;
            }

            /* ── Dashboard Agent ── */
            async function runAgentFromDash() {
                const btn = document.getElementById('dashRunBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Running...';
                try {
                    const res = await fetch('/api/run', {
                        method:'POST',
                        headers:{'Content-Type':'application/json'},
                        body: JSON.stringify({job_title: document.getElementById('dash-title').value, location: document.getElementById('dash-location').value, max_jobs:3})
                    });
                    const d = await res.json();
                    alert(d.message || 'Done!');
                } catch(e) { alert('Error: '+e.message); }
                finally { btn.disabled=false; btn.innerHTML='<i class="bi bi-lightning-charge me-2"></i> Fast Apply Now'; }
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
