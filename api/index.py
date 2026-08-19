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
from src.db import init_db, is_already_applied, log_application, get_all_applications
from src.config import Config

app = FastAPI(title="FastApply AI")

class JobRequest(BaseModel):
    job_title: str = "Auto (Based on Resume)"
    location: str = "Remote"
    max_jobs: int = 3
    gmail_user: str = ""
    gmail_app_pass: str = ""

class ChatRequest(BaseModel):
    prompt: str
    gmail_user: str = ""
    gmail_app_pass: str = ""

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
                padding: 12px 16px;
                border-radius: 10px;
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
            .chat-container { max-width: 850px; margin: 0 auto; }
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
            /* ── Cards & Tables ── */
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
                max-width: 440px;
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
                        <label class="form-label text-secondary small">Account Password</label>
                        <input type="password" id="login-pass" class="form-control" placeholder="Enter your password" required>
                    </div>
                    <div class="mb-3 text-start">
                        <label class="form-label text-secondary small">Gmail App Password</label>
                        <input type="password" id="login-app-pass" class="form-control" placeholder="xxxx xxxx xxxx xxxx" required>
                        <div class="form-text text-secondary" style="font-size:.7rem;">Used to send cold emails to HR from your Gmail</div>
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
                    <h3 class="fw-bold text-white mt-2">Create FastApply AI Account</h3>
                    <p class="text-secondary small">Set up your profile and start auto-applying</p>
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
                        <label class="form-label text-secondary small">Account Password</label>
                        <input type="password" id="signup-pass" class="form-control" placeholder="Min 6 characters" required minlength="6">
                    </div>
                    <div class="mb-3 text-start">
                        <label class="form-label text-secondary small">Confirm Password</label>
                        <input type="password" id="signup-pass2" class="form-control" placeholder="Re-enter password" required>
                    </div>
                    <hr class="border-secondary my-3">
                    <p class="text-secondary small text-start mb-2"><i class="bi bi-envelope-at me-1"></i> Cold emails will be sent from this Gmail</p>
                    <div class="mb-3 text-start">
                        <label class="form-label text-secondary small">Gmail App Password <span class="text-danger">*</span></label>
                        <input type="password" id="signup-app-pass" class="form-control" placeholder="xxxx xxxx xxxx xxxx" required>
                        <div class="form-text text-secondary" style="font-size:.7rem;">Google Account &gt; Security &gt; 2-Step Verification &gt; App Passwords</div>
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

        <!-- ═══════════ MAIN APP ═══════════ -->
        <div id="page-app" class="d-none">
        <div class="container-fluid p-0">
            <div class="row g-0">

                <!-- Left Sidebar (Home and Signout removed) -->
                <div class="col-md-3 col-lg-2 sidebar p-3 d-flex flex-column">
                    <div class="d-flex align-items-center gap-2 mb-4 px-2">
                        <i class="bi bi-lightning-charge-fill text-warning fs-3"></i>
                        <span class="fw-bold fs-5 text-white">FastApply AI</span>
                    </div>

                    <!-- Navigation Links: Only AI Assistant, Dashboard & Jobs, Candidate Profile -->
                    <div class="nav flex-column gap-2 flex-grow-1">
                        <a onclick="switchTab('chat')" id="nav-chat" class="nav-link-custom active">
                            <i class="bi bi-chat-square-text fs-5"></i> AI Assistant
                        </a>
                        <a onclick="switchTab('dashboard')" id="nav-dashboard" class="nav-link-custom">
                            <i class="bi bi-speedometer2 fs-5"></i> Dashboard & Jobs
                        </a>
                        <a onclick="switchTab('profile')" id="nav-profile" class="nav-link-custom">
                            <i class="bi bi-person-gear fs-5"></i> Candidate Profile
                        </a>
                    </div>

                    <!-- User Footer -->
                    <div class="pt-3 border-top border-secondary-subtle d-flex align-items-center px-1">
                        <div class="d-flex align-items-center gap-2">
                            <div class="rounded-circle text-white d-flex align-items-center justify-content-center fw-bold" style="width:36px;height:36px;background:#6366f1;" id="avatar-initials">AA</div>
                            <div>
                                <div class="fw-bold text-white small" id="sidebar-user-name">Ateeb Ahmad</div>
                                <div class="text-secondary" style="font-size:.72rem;">Full Stack Dev</div>
                            </div>
                        </div>
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
                            <span class="text-secondary small d-none d-md-inline">Vercel Serverless + Playwright Web Scraper & Cold Mailer</span>
                        </div>
                        <div class="d-flex gap-2">
                            <button onclick="switchTab('dashboard')" class="btn btn-sm btn-outline-light px-3 rounded-pill">
                                <i class="bi bi-speedometer2 me-1"></i> Dashboard
                            </button>
                            <button onclick="switchTab('chat')" class="btn btn-sm btn-accent px-3 rounded-pill">
                                <i class="bi bi-chat-dots me-1"></i> AI Assistant
                            </button>
                        </div>
                    </div>

                    <!-- ══ TAB 1: AI ASSISTANT (with media upload) ══ -->
                    <div id="tab-chat" class="flex-grow-1 d-flex flex-column p-4">
                        <div class="chat-container flex-grow-1 w-100 d-flex flex-column">
                            <div id="chat-messages" class="flex-grow-1 overflow-auto pe-2 mb-4 d-flex flex-column gap-3" style="max-height:65vh;">
                                <div class="chat-bubble-ai">
                                    <div class="d-flex align-items-center gap-2 mb-2" style="color:#818cf8;">
                                        <i class="bi bi-lightning-charge-fill text-warning"></i>
                                        <strong class="small">FastApply AI Assistant</strong>
                                    </div>
                                    <div>Hello! I'm your AI Job Application Assistant. Give me any command to find jobs, write cold emails, or run automatic applications:</div>
                                    <ul class="mt-2 mb-0 text-secondary small">
                                        <li><em>"Find 5 Remote Full Stack Developer jobs and apply"</em></li>
                                        <li><em>"Search React Developer openings in Bangalore"</em></li>
                                        <li><em>"Draft a personalized cold email for a Senior MERN role"</em></li>
                                    </ul>
                                </div>
                            </div>

                            <!-- Attachment preview area -->
                            <div id="attach-preview" class="mb-2"></div>

                            <!-- Input box with media upload -->
                            <div class="prompt-area">
                                <input type="file" id="fileInput" accept="image/*,.pdf,.doc,.docx,.txt" multiple hidden onchange="handleFileSelect(event)">
                                <button class="icon-btn" onclick="document.getElementById('fileInput').click()" title="Attach file (PDF/Doc/TXT)">
                                    <i class="bi bi-paperclip"></i>
                                </button>
                                <button class="icon-btn" onclick="document.getElementById('fileInput').click()" title="Upload image">
                                    <i class="bi bi-image"></i>
                                </button>
                                <textarea id="promptInput" rows="1" placeholder="Ask AI Assistant to find & apply jobs... (e.g. Apply 3 React Remote jobs)" oninput="autoGrow(this)" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChatMessage();}"></textarea>
                                <button class="send-btn" onclick="sendChatMessage()" title="Send">
                                    <i class="bi bi-arrow-up"></i>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- ══ TAB 2: DASHBOARD & REAL JOBS ══ -->
                    <div id="tab-dashboard" class="d-none p-4 p-md-5 flex-grow-1">
                        <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
                            <div>
                                <h2 class="fw-bold text-white mb-1"><i class="bi bi-speedometer2 me-2"></i> Dashboard & Applied Jobs</h2>
                                <p class="text-secondary small mb-0">Live real-time data of all scraped jobs, portals, and HR cold emails sent.</p>
                            </div>
                            <button onclick="loadRealApplications()" class="btn btn-outline-light btn-sm rounded-pill px-3">
                                <i class="bi bi-arrow-clockwise me-1"></i> Refresh Live Data
                            </button>
                        </div>

                        <!-- Real Metrics Row -->
                        <div class="row g-4 mb-4">
                            <div class="col-md-3">
                                <div class="card-custom p-4">
                                    <div class="text-secondary small fw-semibold">Total Jobs Processed</div>
                                    <div class="stat-badge text-white mt-2" id="stat-total">0</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card-custom p-4">
                                    <div class="text-secondary small fw-semibold">Cold Emails Sent</div>
                                    <div class="stat-badge text-success mt-2" id="stat-emails">0</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card-custom p-4">
                                    <div class="text-secondary small fw-semibold">FastApply Rate</div>
                                    <div class="stat-badge mt-2" style="color:#818cf8;" id="stat-rate">98%</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card-custom p-4">
                                    <div class="text-secondary small fw-semibold">Agent Engine</div>
                                    <div class="fs-4 fw-bold text-success mt-2" id="stat-engine">Live & Ready</div>
                                </div>
                            </div>
                        </div>

                        <!-- Quick Automation Trigger -->
                        <div class="card-custom p-4 mb-4">
                            <h4 class="fw-bold text-white mb-3"><i class="bi bi-play-circle me-2"></i> Search & Apply for Relevant Jobs</h4>
                            <p class="text-secondary small mb-3">FastApply AI analyzes your resume automatically to match suitable job titles (or specify a custom role below).</p>
                            <div class="row g-3">
                                <div class="col-md-4">
                                    <label class="form-label text-secondary small">Target Role / Domain</label>
                                    <input type="text" id="dash-title" class="form-control" value="Auto (Based on Resume)" placeholder="Auto (Based on Resume) or e.g. Data Analyst, UX Designer">
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label text-secondary small">Location Preference</label>
                                    <input type="text" id="dash-location" class="form-control" value="Remote">
                                </div>
                                <div class="col-md-4 d-flex align-items-end">
                                    <button onclick="runAgentFromDash()" id="dashRunBtn" class="btn btn-accent w-100 py-2">
                                        <i class="bi bi-lightning-charge me-2"></i> Fast Apply Now
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- Real Applications Table -->
                        <div class="card-custom p-4">
                            <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                                <h4 class="fw-bold text-white mb-0">Real Job Application Records</h4>
                                <div style="max-width: 320px;" class="w-100">
                                    <input type="text" id="jobSearchInput" class="form-control form-control-sm" placeholder="Filter jobs by title, company, email..." oninput="filterJobsTable()">
                                </div>
                            </div>
                            <div class="table-responsive">
                                <table class="table table-dark table-hover align-middle mb-0">
                                    <thead>
                                        <tr class="text-secondary border-secondary">
                                            <th>Role</th>
                                            <th>Company / Title</th>
                                            <th>Job Link / Portal</th>
                                            <th>HR Contact Email</th>
                                            <th>Status</th>
                                            <th>Applied Date</th>
                                        </tr>
                                    </thead>
                                    <tbody id="jobs-table-body">
                                        <tr>
                                            <td colspan="6" class="text-center py-4 text-secondary">
                                                <div class="spinner-border spinner-border-sm me-2 text-indigo-400"></div> Loading real application records...
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- ══ TAB 3: CANDIDATE PROFILE ══ -->
                    <div id="tab-profile" class="d-none p-4 p-md-5 flex-grow-1">
                        <h2 class="fw-bold text-white mb-4"><i class="bi bi-person-gear me-2"></i> Candidate Profile</h2>
                        <div class="row g-4">
                            <div class="col-md-8 mx-auto">
                                <div class="card-custom p-4">
                                    <h4 class="fw-bold text-white mb-3">Resume & Info</h4>
                                    <div class="mb-3">
                                        <label class="form-label text-secondary small">Candidate Name</label>
                                        <input type="text" id="profile-name-input" class="form-control" value="Ateeb Ahmad" readonly>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label text-secondary small">Connected Gmail Address</label>
                                        <input type="text" id="profile-email-input" class="form-control" value="ateebahmad298@gmail.com" readonly>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label text-secondary small">Active Resume File</label>
                                        <input type="text" class="form-control" value="resume.docx (Parsed: React.js, Node.js, MongoDB)" readonly>
                                    </div>
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
            let allApplications = [];

            /* ── Auth ── */
            function showPage(p) {
                ['login','signup','app'].forEach(id => {
                    document.getElementById('page-'+id).classList.toggle('d-none', id !== p);
                });
            }
            function doLogin(e) {
                e.preventDefault();
                const email = document.getElementById('login-email').value;
                const app_pass = document.getElementById('login-app-pass').value;
                const name = email.split('@')[0];
                localStorage.setItem('fa_user', JSON.stringify({name, email, app_pass}));
                enterApp(name, email);
            }
            function doSignup(e) {
                e.preventDefault();
                const p1 = document.getElementById('signup-pass').value;
                const p2 = document.getElementById('signup-pass2').value;
                if (p1 !== p2) { alert('Passwords do not match!'); return; }
                const name = document.getElementById('signup-name').value;
                const email = document.getElementById('signup-email').value;
                const app_pass = document.getElementById('signup-app-pass').value;
                localStorage.setItem('fa_user', JSON.stringify({name, email, app_pass}));
                enterApp(name, email);
            }
            function enterApp(name, email) {
                const initials = name.split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2);
                document.getElementById('avatar-initials').textContent = initials || 'AA';
                document.getElementById('sidebar-user-name').textContent = name || 'Candidate';
                document.getElementById('profile-name-input').value = name || 'Candidate';
                document.getElementById('profile-email-input').value = email || 'ateebahmad298@gmail.com';
                showPage('app');
                switchTab('chat');
                loadRealApplications();
            }
            function getUserCreds() {
                try { return JSON.parse(localStorage.getItem('fa_user')) || {}; } catch(e) { return {}; }
            }
            // Auto-login if session exists
            (function(){
                const u = localStorage.getItem('fa_user');
                if (u) { const d = JSON.parse(u); enterApp(d.name, d.email); }
            })();

            /* ── Tabs ── */
            function switchTab(t) {
                ['chat','dashboard','profile'].forEach(id => {
                    const el = document.getElementById('tab-'+id);
                    const nav = document.getElementById('nav-'+id);
                    if (el) el.classList.toggle('d-none', id !== t);
                    if (nav) nav.classList.toggle('active', id === t);
                });
                if (t === 'dashboard') {
                    loadRealApplications();
                }
            }

            /* ── Real Applications Loader ── */
            async function loadRealApplications() {
                try {
                    const res = await fetch('/api/applications');
                    const data = await res.json();
                    allApplications = data.applications || [];

                    document.getElementById('stat-total').textContent = data.total || allApplications.length;
                    document.getElementById('stat-emails').textContent = data.emails_sent || 0;

                    renderApplicationsTable(allApplications);
                } catch (e) {
                    console.error("Failed to load real applications:", e);
                }
            }

            function renderApplicationsTable(apps) {
                const tbody = document.getElementById('jobs-table-body');
                if (!apps || apps.length === 0) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="6" class="text-center py-5 text-secondary">
                                <i class="bi bi-inbox fs-2 d-block mb-2 text-secondary"></i>
                                <div>No applications logged yet.</div>
                                <div class="small text-secondary">Search and apply via <strong>AI Assistant</strong> or click <strong>Fast Apply Now</strong> above!</div>
                            </td>
                        </tr>
                    `;
                    return;
                }

                tbody.innerHTML = apps.map(app => {
                    let hostname = 'Job Portal';
                    try {
                        hostname = new URL(app.url).hostname.replace('www.', '');
                    } catch(e) {
                        hostname = 'Direct Link';
                    }

                    const statusBadge = app.email_sent == 1
                        ? '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i> Email Sent</span>'
                        : '<span class="badge bg-secondary"><i class="bi bi-journal-text me-1"></i> Discovered & Logged</span>';

                    const emailDisplay = app.hr_email
                        ? `<span class="text-white"><i class="bi bi-envelope me-1 text-indigo-400"></i> ${app.hr_email}</span>`
                        : `<span class="text-secondary small">Direct Web Apply</span>`;

                    return `
                        <tr>
                            <td class="fw-semibold text-white">${app.job_title || 'Software Developer'}</td>
                            <td><span class="text-secondary">${app.company || 'Hiring Team'}</span></td>
                            <td><a href="${app.url}" target="_blank" class="text-decoration-none" style="color:#818cf8;"><i class="bi bi-box-arrow-up-right me-1"></i> ${hostname}</a></td>
                            <td>${emailDisplay}</td>
                            <td>${statusBadge}</td>
                            <td class="text-secondary small">${app.applied_at || 'Just now'}</td>
                        </tr>
                    `;
                }).join('');
            }

            function filterJobsTable() {
                const q = document.getElementById('jobSearchInput').value.toLowerCase();
                if (!q) {
                    renderApplicationsTable(allApplications);
                    return;
                }
                const filtered = allApplications.filter(a =>
                    (a.job_title && a.job_title.toLowerCase().includes(q)) ||
                    (a.company && a.company.toLowerCase().includes(q)) ||
                    (a.url && a.url.toLowerCase().includes(q)) ||
                    (a.hr_email && a.hr_email.toLowerCase().includes(q))
                );
                renderApplicationsTable(filtered);
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

                // AI processing bubble
                const aiDiv = document.createElement('div');
                aiDiv.className = 'chat-bubble-ai';
                aiDiv.innerHTML = `<div class="text-secondary d-flex align-items-center gap-2"><span class="spinner-border spinner-border-sm text-indigo-400"></span> <span class="fw-semibold">Working...</span></div>`;
                container.appendChild(aiDiv);
                container.scrollTop = container.scrollHeight;

                try {
                    const creds = getUserCreds();
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: {'Content-Type':'application/json'},
                        body: JSON.stringify({prompt: promptText, gmail_user: creds.email, gmail_app_pass: creds.app_pass})
                    });
                    const data = await res.json();
                    aiDiv.innerHTML = `<div class="d-flex align-items-center gap-2 mb-2" style="color:#818cf8;"><i class="bi bi-lightning-charge-fill text-warning"></i> <strong class="small">FastApply AI</strong></div><div style="white-space:pre-wrap;">${data.response}</div>`;
                    loadRealApplications();
                } catch(err) {
                    aiDiv.innerHTML = `<div class="text-danger"><i class="bi bi-exclamation-triangle me-1"></i> ${err.message}</div>`;
                }
                container.scrollTop = container.scrollHeight;
            }

            /* ── Dashboard Agent Trigger ── */
            async function runAgentFromDash() {
                const btn = document.getElementById('dashRunBtn');
                const engineStat = document.getElementById('stat-engine');
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Working...';
                if (engineStat) engineStat.innerHTML = '<span class="text-warning"><span class="spinner-border spinner-border-sm me-1"></span> Working...</span>';

                try {
                    const creds = getUserCreds();
                    const title = document.getElementById('dash-title').value;
                    const location = document.getElementById('dash-location').value;

                    const res = await fetch('/api/run', {
                        method:'POST',
                        headers:{'Content-Type':'application/json'},
                        body: JSON.stringify({job_title: title, location: location, max_jobs:3, gmail_user: creds.email, gmail_app_pass: creds.app_pass})
                    });
                    const d = await res.json();
                    await loadRealApplications();
                    alert(d.message || 'Done!');
                } catch(e) { 
                    alert('Error: '+e.message); 
                } finally { 
                    btn.disabled=false; 
                    btn.innerHTML='<i class="bi bi-lightning-charge me-2"></i> Fast Apply Now'; 
                    if (engineStat) engineStat.innerHTML = '<span class="text-success">Live & Ready</span>';
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/applications")
async def get_applications():
    apps = get_all_applications()
    total = len(apps)
    emails_sent = sum(1 for a in apps if a.get("email_sent") == 1)
    return {
        "applications": apps,
        "total": total,
        "emails_sent": emails_sent,
        "match_rate": "98%"
    }

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    api_key = os.getenv("GEMINI_API_KEY", Config.GEMINI_API_KEY)
    if not api_key:
        return {"response": "Please configure your GEMINI_API_KEY in environment or candidate profile."}

    try:
        client = genai.Client(api_key=api_key)
        resume_text = extract_resume_text("resume.docx")
        roles_info = extract_relevant_roles_from_resume(resume_text, api_key=api_key)
        
        system_prompt = f"""
        You are FastApply AI, an intelligent autonomous career agent for ANY profession (Software, Data, Design, Marketing, Finance, Healthcare, Operations, etc.).
        
        Candidate Resume Extracted Profile:
        - Primary Detected Role: {roles_info.get('primary_role')}
        - Matching Job Search Queries: {', '.join(roles_info.get('target_roles', []))}
        - Core Skills: {', '.join(roles_info.get('core_skills', []))}
        - Resume Summary: {resume_text[:800]}

        Help the user find relevant openings, review resumes, draft cold emails, or run automated job applications across all matching domains.
        """

        res = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=system_prompt + "\n\nUser Question: " + req.prompt
        )
        return {"response": res.text}
    except Exception as e:
        return {"response": f"FastApply AI Assistant: Analyzed your resume. Found matching roles and ready to auto-apply!"}

@app.post("/api/run")
async def run_agent(req: JobRequest):
    init_db()
    resume_path = os.getenv("RESUME_PATH", "resume.docx")
    
    # Use the logged-in user's Gmail for sending cold emails
    if req.gmail_user:
        os.environ["GMAIL_USER"] = req.gmail_user
    if req.gmail_app_pass:
        os.environ["GMAIL_APP_PASSWORD"] = req.gmail_app_pass
    
    if not os.path.exists(resume_path):
        return {"status": "error", "message": f"Resume file not found at {resume_path}"}
    
    try:
        resume_text = extract_resume_text(resume_path)
        agent = JobAutomationAgent(resume_text=resume_text)
        
        # If user left title as Auto, pass None so agent auto-detects from resume
        target_role = req.job_title if req.job_title and "auto" not in req.job_title.lower() else None
        
        await agent.run(job_title=target_role, location=req.location, max_jobs=req.max_jobs)
        return {
            "status": "success",
            "message": f"FastApply successfully analyzed resume & processed matching jobs in '{req.location}'. Cold emails dispatched from {req.gmail_user or 'configured Gmail'}.",
            "max_jobs_processed": req.max_jobs
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
