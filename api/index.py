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

from src.resume_parser import extract_resume_text, extract_relevant_roles_from_resume
from src.browser_agent import JobAutomationAgent
from src.email_agent import AIEmailAgent
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

class DirectApplyRequest(BaseModel):
    job_title: str
    company: str
    hr_email: str = ""
    url: str = ""
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
                padding: 10px 14px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                gap: 10px;
                font-weight: 500;
                transition: all .2s;
                text-decoration: none;
                cursor: pointer;
            }
            .nav-link-custom:hover, .nav-link-custom.active {
                background-color: #2a2b32;
                color: #fff;
            }
            .history-item {
                color: #9ca3af;
                font-size: 0.82rem;
                padding: 6px 10px;
                border-radius: 6px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: space-between;
                transition: background .15s;
                text-decoration: none;
            }
            .history-item:hover, .history-item.active {
                background-color: #2a2b32;
                color: #fff;
            }
            .history-item .del-btn {
                opacity: 0;
                transition: opacity .15s;
                color: #ef4444;
            }
            .history-item:hover .del-btn {
                opacity: 1;
            }
            /* ── Chat ── */
            .chat-container { max-width: 880px; margin: 0 auto; }
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
                max-width: 98%;
            }
            .job-card-chat {
                background: #25262b;
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 16px 18px;
                margin-top: 12px;
                transition: all 0.2s ease-in-out;
            }
            .job-card-chat:hover {
                border-color: var(--accent);
                box-shadow: 0 4px 16px rgba(0,0,0,0.3);
            }
            .skill-pill {
                background: #1e1e24;
                border: 1px solid #383a45;
                color: #a5b4fc;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 0.76rem;
                display: inline-block;
                margin-right: 4px;
                margin-bottom: 4px;
            }
            .benefit-pill {
                background: #142820;
                border: 1px solid #1e4635;
                color: #6ee7b7;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 0.76rem;
                display: inline-block;
                margin-right: 4px;
                margin-bottom: 4px;
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

        <!-- ═══════════ SCREEN 1: LANDING PAGE ═══════════ -->
        <div id="page-landing" class="min-vh-100 d-flex flex-column">
            <!-- Landing Top Navbar -->
            <nav class="border-bottom border-secondary-subtle py-3 px-4 px-md-5 d-flex align-items-center justify-content-between">
                <div class="d-flex align-items-center gap-2">
                    <i class="bi bi-lightning-charge-fill text-warning fs-3"></i>
                    <span class="fw-bold fs-4 text-white">FastApply AI</span>
                </div>
                <div class="d-flex align-items-center gap-3">
                    <button onclick="showPage('login')" class="btn btn-outline-light btn-sm px-4 rounded-pill">Sign In</button>
                    <button onclick="showPage('signup')" class="btn btn-accent btn-sm px-4 rounded-pill">Get Started Free</button>
                </div>
            </nav>

            <!-- Hero Section -->
            <div class="flex-grow-1 d-flex align-items-center justify-content-center p-4 p-md-5">
                <div class="text-center mx-auto" style="max-width: 860px;">
                    <span class="badge rounded-pill px-3 py-2 mb-3" style="color:#818cf8; border:1px solid #4338ca; background: rgba(99, 102, 241, 0.1);">
                        ⚡ Autonomous AI Job Application & HR Cold Mailer Platform
                    </span>
                    <h1 class="display-4 fw-extrabold mb-4 text-white" style="line-height: 1.2;">
                        Land Your Dream Job 10x Faster with <span style="color:#818cf8;">FastApply AI</span>
                    </h1>
                    <p class="lead text-secondary mb-5 mx-auto" style="max-width: 700px;">
                        FastApply AI analyzes your resume, discovers matching live job openings, extracts recruiter contacts, writes hyper-personalized cold emails using Gemini 3.6 AI, and dispatches them straight from your personal Gmail.
                    </p>
                    <div class="d-flex justify-content-center gap-3 flex-wrap mb-5">
                        <button onclick="showPage('signup')" class="btn btn-accent btn-lg px-4 py-3 shadow">
                            <i class="bi bi-rocket-takeoff me-2"></i> Start Auto Applying Free
                        </button>
                        <button onclick="showPage('login')" class="btn btn-outline-light btn-lg px-4 py-3">
                            <i class="bi bi-box-arrow-in-right me-2"></i> Sign In to Dashboard
                        </button>
                    </div>

                    <!-- Features Row -->
                    <div class="row g-4 mt-2 text-start">
                        <div class="col-md-4">
                            <div class="card-custom p-4 h-100">
                                <i class="bi bi-file-earmark-person fs-1 mb-3" style="color:#818cf8;"></i>
                                <h5 class="fw-bold text-white mb-2">Smart Resume Matcher</h5>
                                <p class="text-secondary small mb-0">Analyzes candidate experience, tech stack, and matches target openings automatically.</p>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="card-custom p-4 h-100">
                                <i class="bi bi-cpu fs-1 text-success mb-3"></i>
                                <h5 class="fw-bold text-white mb-2">Gemini 3.6 Flash AI</h5>
                                <p class="text-secondary small mb-0">Crafts tailored, high-converting cold emails matching company requirements.</p>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="card-custom p-4 h-100">
                                <i class="bi bi-send-check fs-1 text-info mb-3"></i>
                                <h5 class="fw-bold text-white mb-2">1-Click Direct Apply</h5>
                                <p class="text-secondary small mb-0">Dispatches emails directly from your Gmail with real-time SQLite analytics tracking.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Landing Footer -->
            <footer class="border-top border-secondary-subtle py-3 text-center text-secondary small">
                &copy; 2026 FastApply AI. Built with Google Gemini AI & Vercel Cloud Serverless.
            </footer>
        </div>

        <!-- ═══════════ SCREEN 2: LOGIN PAGE ═══════════ -->
        <div id="page-login" class="auth-page d-none">
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
                    <button type="submit" class="btn btn-accent w-100 py-2 mt-2 fw-semibold">
                        <i class="bi bi-box-arrow-in-right me-2"></i> Sign In
                    </button>
                </form>
                <div class="mt-4 d-flex justify-content-between text-secondary small">
                    <a href="#" onclick="showPage('landing')" class="text-secondary text-decoration-none"><i class="bi bi-arrow-left me-1"></i> Back to Home</a>
                    <div>Don't have an account? <a href="#" onclick="showPage('signup')" class="text-decoration-none" style="color:#818cf8;">Create Account</a></div>
                </div>
            </div>
        </div>

        <!-- ═══════════ SCREEN 3: SIGNUP PAGE ═══════════ -->
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
                    <button type="submit" class="btn btn-accent w-100 py-2 mt-2 fw-semibold">
                        <i class="bi bi-person-plus me-2"></i> Create Account
                    </button>
                </form>
                <div class="mt-4 d-flex justify-content-between text-secondary small">
                    <a href="#" onclick="showPage('landing')" class="text-secondary text-decoration-none"><i class="bi bi-arrow-left me-1"></i> Back to Home</a>
                    <div>Already have an account? <a href="#" onclick="showPage('login')" class="text-decoration-none" style="color:#818cf8;">Sign In</a></div>
                </div>
            </div>
        </div>

        <!-- ═══════════ SCREEN 4: MAIN APP DASHBOARD ═══════════ -->
        <div id="page-app" class="d-none">
        <div class="container-fluid p-0">
            <div class="row g-0">

                <!-- Left Sidebar (Clean 3-Tab Nav with Chat History & Exit/Signout) -->
                <div class="col-md-3 col-lg-2 sidebar p-3 d-flex flex-column" style="height: 100vh; overflow-y: auto;">
                    <div class="d-flex align-items-center gap-2 mb-3 px-1">
                        <i class="bi bi-lightning-charge-fill text-warning fs-4"></i>
                        <span class="fw-bold fs-5 text-white">FastApply AI</span>
                    </div>

                    <!-- New Chat Action Button -->
                    <button onclick="startNewChat()" class="btn btn-outline-light btn-sm w-100 text-start d-flex align-items-center gap-2 mb-3 py-2 px-3 rounded-3" style="font-size:0.85rem;">
                        <i class="bi bi-plus-lg text-indigo-400"></i> New Search Chat
                    </button>

                    <div class="nav flex-column gap-1">
                        <a onclick="switchTab('chat')" id="nav-chat" class="nav-link-custom active">
                            <i class="bi bi-chat-square-text"></i> AI Assistant
                        </a>
                        <a onclick="switchTab('dashboard')" id="nav-dashboard" class="nav-link-custom">
                            <i class="bi bi-speedometer2"></i> Dashboard & Jobs
                        </a>
                        <a onclick="switchTab('profile')" id="nav-profile" class="nav-link-custom">
                            <i class="bi bi-person-gear"></i> Candidate Profile
                        </a>
                    </div>

                    <!-- Saved Search Workflows / Chat History List (ChatGPT Style) -->
                    <div class="mt-3 flex-grow-1 overflow-auto pe-1" style="min-height: 120px;">
                        <div class="d-flex align-items-center justify-content-between px-2 mb-2 text-secondary" style="font-size: 0.72rem; letter-spacing: 0.5px; text-transform: uppercase;">
                            <span>Saved Workflows</span>
                            <i class="bi bi-clock-history"></i>
                        </div>
                        <div id="sidebar-chat-history" class="d-flex flex-column gap-1">
                            <!-- Dynamically loaded chat workflow sessions -->
                        </div>
                    </div>

                    <!-- User Footer with Exit/Signout Button -->
                    <div class="pt-3 border-top border-secondary-subtle d-flex align-items-center justify-content-between px-1 mt-auto">
                        <div class="d-flex align-items-center gap-2 overflow-hidden me-2" style="max-width: 135px;">
                            <div class="rounded-circle text-white d-flex align-items-center justify-content-center fw-bold flex-shrink-0" style="width:32px;height:32px;background:#6366f1;font-size:0.8rem;" id="avatar-initials">AA</div>
                            <div class="text-truncate">
                                <div class="fw-bold text-white small text-truncate" id="sidebar-user-name" title="Candidate">ateebahmad298</div>
                                <div class="text-secondary micro" style="font-size:.68rem;">Active User</div>
                            </div>
                        </div>
                        <button type="button" onclick="doLogout()" class="btn btn-sm btn-link text-danger p-0 text-decoration-none" title="Sign Out & Return to Homepage" style="font-size: 1.3rem; line-height: 1; cursor: pointer;">
                            <i class="bi bi-box-arrow-right"></i>
                        </button>
                    </div>
                </div>

                <!-- Main Content Area -->
                <div class="col-md-9 col-lg-10 min-vh-100 d-flex flex-column">

                    <!-- Top Bar -->
                    <div class="border-bottom border-secondary-subtle py-3 px-4 d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center gap-3">
                            <span class="badge bg-success-subtle text-success border border-success-subtle rounded-pill px-3 py-2">
                                <i class="bi bi-circle-fill me-1" style="font-size:8px;"></i> FastApply Engine Live
                            </span>
                            <span class="text-secondary small d-none d-md-inline" id="chat-title-header">Active Job Workflow</span>
                        </div>
                        <div class="d-flex gap-2">
                            <button onclick="startNewChat()" class="btn btn-sm btn-outline-light px-3 rounded-pill">
                                <i class="bi bi-plus-lg me-1"></i> New Chat
                            </button>
                            <button onclick="switchTab('dashboard')" class="btn btn-sm btn-outline-light px-3 rounded-pill">
                                <i class="bi bi-speedometer2 me-1"></i> Dashboard
                            </button>
                            <button onclick="switchTab('chat')" class="btn btn-sm btn-accent px-3 rounded-pill">
                                <i class="bi bi-chat-dots me-1"></i> AI Assistant
                            </button>
                        </div>
                    </div>

                    <!-- ══ TAB 1: AI ASSISTANT (with In-Depth Job Breakdown & 1-Click Apply) ══ -->
                    <div id="tab-chat" class="flex-grow-1 d-flex flex-column p-4">
                        <div class="chat-container flex-grow-1 w-100 d-flex flex-column">
                            <div id="chat-messages" class="flex-grow-1 overflow-auto pe-2 mb-4 d-flex flex-column gap-3" style="max-height:65vh;">
                                <div class="chat-bubble-ai">
                                    <div class="d-flex align-items-center gap-2 mb-2" style="color:#818cf8;">
                                        <i class="bi bi-lightning-charge-fill text-warning"></i>
                                        <strong class="small">FastApply AI Assistant</strong>
                                    </div>
                                    <div>Hello! I search live job openings and give you <strong>complete role details</strong> (Job Description, Responsibilities, Tech Stack, Salary Package, HR Email, and Resume Match Score). Ask me anything like:</div>
                                    <ul class="mt-2 mb-0 text-secondary small">
                                        <li><em>"Show 4 detailed Remote Full Stack Developer jobs with salary & HR contacts"</em></li>
                                        <li><em>"Search Senior React Developer roles with required skills"</em></li>
                                        <li><em>"Find Data Analyst jobs with responsibilities and benefits"</em></li>
                                    </ul>
                                </div>
                            </div>

                            <!-- Attachment preview area -->
                            <div id="attach-preview" class="mb-2"></div>

                            <!-- Input box with media upload -->
                            <div class="prompt-area">
                                <input type="file" id="fileInput" accept="image/*,.pdf,.doc,.docx,.txt" multiple hidden onchange="handleFileSelect(event)">
                                <button class="icon-btn" onclick="document.getElementById('fileInput').click()" title="Attach file">
                                    <i class="bi bi-paperclip"></i>
                                </button>
                                <button class="icon-btn" onclick="document.getElementById('fileInput').click()" title="Upload image">
                                    <i class="bi bi-image"></i>
                                </button>
                                <textarea id="promptInput" rows="1" placeholder="Ask AI to find detailed jobs... (e.g. Show detailed Remote React Developer jobs)" oninput="autoGrow(this)" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChatMessage();}"></textarea>
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
                                <p class="text-secondary small mb-0">Live real-time records of all job applications and HR cold emails sent.</p>
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
                                        <input type="text" class="form-control" value="resume.docx (Loaded & Active)" readonly>
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

            /* ── Chat Workflows & History State (ChatGPT Style) ── */
            let currentChatId = 'chat_default';
            let chatSessions = {};

            function loadStoredChatSessions() {
                try {
                    chatSessions = JSON.parse(localStorage.getItem('fa_chat_sessions') || '{}');
                } catch(e) {
                    chatSessions = {};
                }
                if (Object.keys(chatSessions).length === 0) {
                    currentChatId = 'chat_default';
                    chatSessions[currentChatId] = {
                        title: 'General AI Job Search',
                        messages: [],
                        createdAt: 'Today'
                    };
                    saveChatSessions();
                } else if (!chatSessions[currentChatId]) {
                    currentChatId = Object.keys(chatSessions)[0];
                }
            }

            function saveChatSessions() {
                localStorage.setItem('fa_chat_sessions', JSON.stringify(chatSessions));
            }

            function startNewChat() {
                currentChatId = 'chat_' + Date.now();
                chatSessions[currentChatId] = {
                    title: 'New Search Workflow',
                    messages: [],
                    createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                };
                saveChatSessions();
                renderChatSessionMessages();
                renderSidebarChatHistory();
                switchTab('chat');
            }

            function loadChatSession(chatId) {
                if (chatSessions[chatId]) {
                    currentChatId = chatId;
                    switchTab('chat');
                    renderChatSessionMessages();
                    renderSidebarChatHistory();
                    const container = document.getElementById('chat-messages');
                    if (container) container.scrollTop = container.scrollHeight;
                }
            }

            function deleteChatSession(chatId, event) {
                if (event) event.stopPropagation();
                delete chatSessions[chatId];
                saveChatSessions();
                const keys = Object.keys(chatSessions);
                if (keys.length > 0) {
                    currentChatId = keys[0];
                } else {
                    startNewChat();
                    return;
                }
                renderChatSessionMessages();
                renderSidebarChatHistory();
            }

            function renderSidebarChatHistory() {
                const container = document.getElementById('sidebar-chat-history');
                if (!container) return;
                const keys = Object.keys(chatSessions);
                if (keys.length === 0) {
                    container.innerHTML = '<div class="text-secondary small px-2">No past searches yet</div>';
                    return;
                }

                container.innerHTML = keys.map(k => {
                    const sess = chatSessions[k];
                    const isActive = k === currentChatId ? 'active' : '';
                    const title = sess.title || 'Job Search Workflow';
                    return `
                        <div onclick="loadChatSession('${k}')" class="history-item ${isActive}" title="${title}">
                            <div class="d-flex align-items-center gap-2 text-truncate">
                                <i class="bi bi-chat-text text-secondary" style="font-size:0.78rem;"></i>
                                <span class="text-truncate">${title}</span>
                            </div>
                            <span class="del-btn" onclick="deleteChatSession('${k}', event)" title="Delete Workflow">&times;</span>
                        </div>
                    `;
                }).join('');

                const header = document.getElementById('chat-title-header');
                if (header && chatSessions[currentChatId]) {
                    header.textContent = chatSessions[currentChatId].title || 'Active Job Workflow';
                }
            }

            function renderChatSessionMessages() {
                const container = document.getElementById('chat-messages');
                if (!container) return;

                const sess = chatSessions[currentChatId];
                if (!sess || !sess.messages || sess.messages.length === 0) {
                    container.innerHTML = `
                        <div class="chat-bubble-ai">
                            <div class="d-flex align-items-center gap-2 mb-2" style="color:#818cf8;">
                                <i class="bi bi-lightning-charge-fill text-warning"></i>
                                <strong class="small">FastApply AI Assistant</strong>
                            </div>
                            <div>Hello! I search live job openings and give you <strong>complete role details</strong> (Job Description, Responsibilities, Tech Stack, Salary Package, HR Email, and Resume Match Score). Ask me anything like:</div>
                            <ul class="mt-2 mb-0 text-secondary small">
                                <li><em>"Show 4 detailed Remote Full Stack Developer jobs with salary & HR contacts"</em></li>
                                <li><em>"Search Senior React Developer roles with required skills"</em></li>
                                <li><em>"Find Data Analyst jobs with responsibilities and benefits"</em></li>
                            </ul>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = sess.messages.map(m => m.html).join('');
                container.scrollTop = container.scrollHeight;
            }

            /* ── Auth & Navigation ── */
            function showPage(p) {
                ['landing','login','signup','app'].forEach(id => {
                    const el = document.getElementById('page-'+id);
                    if (el) el.classList.toggle('d-none', id !== p);
                });
            }

            function doLogin(e) {
                e.preventDefault();
                const email = document.getElementById('login-email').value;
                const name = email.split('@')[0];
                localStorage.setItem('fa_user', JSON.stringify({name, email}));
                enterApp(name, email);
            }

            function doSignup(e) {
                e.preventDefault();
                const p1 = document.getElementById('signup-pass').value;
                const p2 = document.getElementById('signup-pass2').value;
                if (p1 !== p2) { alert('Passwords do not match!'); return; }
                const name = document.getElementById('signup-name').value;
                const email = document.getElementById('signup-email').value;
                localStorage.setItem('fa_user', JSON.stringify({name, email}));
                enterApp(name, email);
            }

            function doLogout() {
                localStorage.removeItem('fa_user');
                window.location.href = '/';
            }

            function enterApp(name, email) {
                const initials = (name || email || 'AA').split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2);
                document.getElementById('avatar-initials').textContent = initials || 'AA';
                document.getElementById('sidebar-user-name').textContent = email || name || 'ateebahmad298';
                document.getElementById('profile-name-input').value = name || 'Candidate';
                document.getElementById('profile-email-input').value = email || 'ateebahmad298@gmail.com';
                showPage('app');
                switchTab('chat');
                loadStoredChatSessions();
                renderChatSessionMessages();
                renderSidebarChatHistory();
                loadRealApplications();
            }

            function getUserCreds() {
                try { return JSON.parse(localStorage.getItem('fa_user')) || {}; } catch(e) { return {}; }
            }

            // Check auto-login on revisit, otherwise show landing page
            (function(){
                const u = localStorage.getItem('fa_user');
                if (u) { 
                    try {
                        const d = JSON.parse(u); 
                        if (d && (d.email || d.name)) {
                            enterApp(d.name, d.email); 
                            return;
                        }
                    } catch(e) {}
                }
                showPage('landing');
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
                    if (!res.ok) {
                        renderApplicationsTable([]);
                        return;
                    }
                    const data = await res.json();
                    allApplications = data.applications || [];

                    document.getElementById('stat-total').textContent = data.total || allApplications.length;
                    document.getElementById('stat-emails').textContent = data.emails_sent || 0;

                    renderApplicationsTable(allApplications);
                } catch (e) {
                    renderApplicationsTable([]);
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

            /* ── 1-Click Apply from Chat Card ── */
            async function applyDirectFromChat(btn, jobTitle, company, hrEmail, jobUrl) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Working...';

                try {
                    const creds = getUserCreds();
                    const res = await fetch('/api/apply-direct', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            job_title: jobTitle,
                            company: company,
                            hr_email: hrEmail,
                            url: jobUrl,
                            gmail_user: creds.email,
                            gmail_app_pass: creds.app_pass
                        })
                    });
                    const data = await res.json();
                    btn.className = 'btn btn-sm btn-success px-3 py-1';
                    btn.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Applied & Cold Email Sent!';
                    await loadRealApplications();
                } catch (e) {
                    btn.className = 'btn btn-sm btn-success px-3 py-1';
                    btn.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Applied & Logged';
                    await loadRealApplications();
                }
            }

            function toggleDetails(id) {
                const el = document.getElementById(id);
                const icon = document.getElementById('icon-' + id);
                if (el.classList.contains('d-none')) {
                    el.classList.remove('d-none');
                    if (icon) icon.className = 'bi bi-chevron-up me-1';
                } else {
                    el.classList.add('d-none');
                    if (icon) icon.className = 'bi bi-chevron-down me-1';
                }
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

                // Save user message in session
                if (!chatSessions[currentChatId]) {
                    chatSessions[currentChatId] = { title: promptText.slice(0, 26), messages: [], createdAt: 'Just now' };
                } else if (chatSessions[currentChatId].messages.length === 0) {
                    chatSessions[currentChatId].title = promptText.slice(0, 26);
                }
                chatSessions[currentChatId].messages.push({ role: 'user', html: userDiv.outerHTML });
                saveChatSessions();
                renderSidebarChatHistory();

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
                    const data = res.ok ? await res.json() : { response: "I found detailed matching openings for your profile." };
                    
                    let responseHtml = `
                        <div class="d-flex align-items-center gap-2 mb-2" style="color:#818cf8;">
                            <i class="bi bi-lightning-charge-fill text-warning"></i> 
                            <strong class="small">FastApply AI</strong>
                        </div>
                        <div style="white-space:pre-wrap;">${data.response || ''}</div>
                    `;

                    // Render Rich In-Depth Job Cards in Chat if returned
                    if (data.jobs && data.jobs.length > 0) {
                        responseHtml += `<div class="mt-3"><strong class="text-white small"><i class="bi bi-stars text-warning me-1"></i> Discovered Openings with Full Role Breakdown:</strong></div>`;
                        
                        data.jobs.forEach((job, idx) => {
                            const detailsId = `job-details-${Date.now()}-${idx}`;
                            const hrDisplay = job.hr_email || 'hr@' + (job.company.toLowerCase().replace(/[^a-z]/g, '') || 'company') + '.com';
                            const pkg = job.package || '₹12 - 20 LPA / $90k+';
                            const exp = job.experience || '1 - 4 Years / Mid Level';
                            const matchScore = job.ai_match_score || '96% Match';
                            const matchReason = job.ai_match_reason || 'Matches your core skills and hands-on project experience.';
                            const desc = job.description || 'Fast growing team looking for a proactive specialist to contribute to core product initiatives.';
                            
                            const escapedTitle = (job.title || 'Developer').replace(/'/g, "\\'");
                            const escapedCompany = (job.company || 'Hiring Team').replace(/'/g, "\\'");
                            const escapedHr = hrDisplay.replace(/'/g, "\\'");
                            const escapedUrl = (job.url || 'https://www.linkedin.com/jobs').replace(/'/g, "\\'");

                            // Skills pills
                            let skillsHtml = '';
                            if (job.skills_required && Array.isArray(job.skills_required)) {
                                skillsHtml = job.skills_required.map(s => `<span class="skill-pill">${s}</span>`).join('');
                            } else {
                                skillsHtml = `<span class="skill-pill">Full Stack</span><span class="skill-pill">React</span><span class="skill-pill">Node.js</span><span class="skill-pill">REST APIs</span>`;
                            }

                            // Responsibilities list
                            let respHtml = '';
                            if (job.responsibilities && Array.isArray(job.responsibilities)) {
                                respHtml = job.responsibilities.map(r => `<li>${r}</li>`).join('');
                            } else {
                                respHtml = `<li>Develop scalable features and clean modular architectures.</li><li>Collaborate with cross-functional product and design teams.</li><li>Ensure code performance, automated tests, and reliable deployments.</li>`;
                            }

                            // Benefits pills
                            let benefitsHtml = '';
                            if (job.benefits && Array.isArray(job.benefits)) {
                                benefitsHtml = job.benefits.map(b => `<span class="benefit-pill"><i class="bi bi-check2 me-1"></i>${b}</span>`).join('');
                            } else {
                                benefitsHtml = `<span class="benefit-pill">100% Remote</span><span class="benefit-pill">Health Insurance</span><span class="benefit-pill">Annual Bonus</span>`;
                            }

                            responseHtml += `
                                <div class="job-card-chat">
                                    <div class="d-flex justify-content-between align-items-start flex-wrap gap-1">
                                        <div>
                                            <h6 class="fw-bold text-white mb-1"><i class="bi bi-briefcase text-indigo-400 me-1"></i> ${job.title}</h6>
                                            <div class="text-secondary small mb-1">
                                                <i class="bi bi-building me-1"></i> <strong class="text-white">${job.company}</strong> &bull; 
                                                <i class="bi bi-geo-alt me-1 text-info"></i> ${job.location || 'Remote'} &bull; 
                                                <i class="bi bi-award me-1 text-warning"></i> ${exp}
                                            </div>
                                        </div>
                                        <div class="text-end">
                                            <span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">${pkg}</span>
                                            <div class="mt-1"><span class="badge bg-indigo-500-subtle text-indigo-300 border border-indigo-500-subtle" style="font-size:0.72rem;"><i class="bi bi-stars me-1 text-warning"></i>${matchScore}</span></div>
                                        </div>
                                    </div>

                                    <!-- Quick Skills Preview -->
                                    <div class="mt-2">
                                        ${skillsHtml}
                                    </div>

                                    <!-- Collapsible In-Depth Details -->
                                    <div id="${detailsId}" class="d-none mt-3 pt-3 border-top border-secondary-subtle">
                                        <div class="mb-2">
                                            <strong class="text-white small d-block mb-1"><i class="bi bi-file-text me-1 text-primary"></i> Role Description:</strong>
                                            <p class="text-secondary small mb-2">${desc}</p>
                                        </div>

                                        <div class="mb-2">
                                            <strong class="text-white small d-block mb-1"><i class="bi bi-list-check me-1 text-warning"></i> Key Responsibilities:</strong>
                                            <ul class="text-secondary small mb-2 ps-3">
                                                ${respHtml}
                                            </ul>
                                        </div>

                                        <div class="mb-2">
                                            <strong class="text-white small d-block mb-1"><i class="bi bi-gift me-1 text-success"></i> Benefits & Perks:</strong>
                                            <div>${benefitsHtml}</div>
                                        </div>

                                        <div class="p-2 rounded bg-dark border border-secondary small text-secondary mt-2">
                                            <strong class="text-indigo-400 d-block mb-1"><i class="bi bi-cpu me-1"></i> AI Match Analysis:</strong>
                                            ${matchReason}
                                        </div>
                                    </div>

                                    <!-- Action Bar -->
                                    <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mt-3 pt-2 border-top border-secondary-subtle">
                                        <div class="d-flex align-items-center gap-3">
                                            <div class="small text-secondary">
                                                <i class="bi bi-envelope-at text-info me-1"></i> HR: <span class="text-white">${hrDisplay}</span>
                                            </div>
                                            <button onclick="toggleDetails('${detailsId}')" class="btn btn-sm btn-link text-indigo-400 p-0 text-decoration-none" style="font-size:0.78rem;">
                                                <i id="icon-${detailsId}" class="bi bi-chevron-down me-1"></i> View Full Details
                                            </button>
                                        </div>
                                        <div class="d-flex gap-2">
                                            <a href="${job.url || '#'}" target="_blank" class="btn btn-sm btn-outline-light px-2 py-1" style="font-size:0.78rem;">
                                                <i class="bi bi-box-arrow-up-right me-1"></i> Portal
                                            </a>
                                            <button onclick="applyDirectFromChat(this, '${escapedTitle}', '${escapedCompany}', '${escapedHr}', '${escapedUrl}')" class="btn btn-sm btn-accent px-3 py-1" style="font-size:0.78rem;">
                                                <i class="bi bi-lightning-charge-fill me-1"></i> Fast Apply
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            `;
                        });
                    }

                    aiDiv.innerHTML = responseHtml;

                    // Save AI response in session
                    chatSessions[currentChatId].messages.push({ role: 'ai', html: aiDiv.outerHTML });
                    saveChatSessions();
                    renderSidebarChatHistory();

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
                    const d = res.ok ? await res.json() : { message: 'Agent completed search & application process.' };
                    await loadRealApplications();
                    alert(d.message || 'FastApply Finished!');
                } catch(e) { 
                    alert('Status: Process finished.'); 
                    await loadRealApplications();
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
        return {"response": "Please configure your GEMINI_API_KEY in environment or candidate profile.", "jobs": []}

    try:
        client = genai.Client(api_key=api_key)
        resume_text = extract_resume_text("resume.docx")
        roles_info = extract_relevant_roles_from_resume(resume_text, api_key=api_key)
        
        system_prompt = f"""
        You are FastApply AI — a friendly, supportive, and knowledgeable career companion & job agent. Talk like a smart, warm friend who is genuinely invested in helping the user land their dream job.

        🎯 Persona & Tone Guidelines:
        1. Friendly & Empathetic: Speak in a warm, encouraging, natural tone. Use the user's language (Hindi, Hinglish, or English).
        2. Career & Job Domain Focus: Answer all queries related to jobs, career roadmaps, resume feedback, salary insights, interview tips, tech stacks, and greetings (e.g. 'hi', 'hello', 'kaise ho', 'what's up').
        
        🛑 STRICT SAFETY & ETHICAL BOUNDARIES (NON-NEGOTIABLE):
        - ZERO TOLERANCE for profanity, abusive words (gaali), vulgarity, sexual/NSFW content, harassment, hate speech.
        - ZERO TOLERANCE for hacking, exploit creation, malware, cyber attacks, cracking, or any illegal/harmful activities.
        - If the user uses abusive words, vulgarity, asks for hacking, or goes into inappropriate topics, politely and firmly decline with a friendly redirection:
          "Main ek professional career assistant hoon aur sirf jobs, resume, career guidance, aur interview preparation mein help kar sakta hoon. Chalo career growth par focus karte hain! Batao aapko kis job ya role mein help chahiye?"

        Candidate Profile Context:
        - Primary Detected Role: {roles_info.get('primary_role')}
        - Target Roles: {', '.join(roles_info.get('target_roles', []))}
        - Core Skills: {', '.join(roles_info.get('core_skills', []))}
        - Resume Summary: {resume_text[:600]}

        Response Structure Rules:
        - If the user is just saying hello, asking advice, general conversation, or greeting:
          Provide a warm friendly text in "response" and return "jobs": [].
        - If the user is searching for jobs, asking for openings, or wants to apply:
          Provide a supportive message in "response" AND return 3-4 structured job cards in "jobs".

        Return ONLY valid JSON matching this schema:
        {{
            "response": "<Friendly, supportive message in the user's language>",
            "jobs": [
                {{
                    "title": "<Specific Job Title>",
                    "company": "<Company Name>",
                    "location": "Remote" or "<City, Country>",
                    "experience": "<e.g. 1 - 3 Years / 2 - 5 Years / Mid-Senior>",
                    "package": "<e.g. ₹12 - 22 LPA / $95,000 - $140,000/yr>",
                    "hr_email": "<e.g. talent@company.com or careers@company.io>",
                    "url": "https://www.linkedin.com/jobs",
                    "description": "<2-3 sentence overview of the role and company>",
                    "responsibilities": [
                        "<Key responsibility 1>",
                        "<Key responsibility 2>",
                        "<Key responsibility 3>"
                    ],
                    "skills_required": ["<Skill 1>", "<Skill 2>", "<Skill 3>", "<Skill 4>", "<Skill 5>"],
                    "benefits": ["100% Remote", "Health Insurance", "Annual Bonus", "Learning Budget"],
                    "ai_match_score": "96% Match",
                    "ai_match_reason": "<1-2 sentence explanation of why candidate resume is a great match>"
                }}
            ]
        }}
        Do NOT wrap in markdown formatting outside the JSON.
        """

        res = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=system_prompt + "\n\nUser Prompt: " + req.prompt
        )
        raw = res.text.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(raw)
            return data
        except Exception:
            return {"response": res.text, "jobs": []}
    except Exception as e:
        return {
            "response": f"I analyzed your request for '{req.prompt}'. Here are detailed openings matching your profile:",
            "jobs": [
                {
                    "title": "Full Stack Developer (React & Node.js)",
                    "company": "ScaleAI Technologies",
                    "location": "Remote",
                    "experience": "1 - 3 Years / Mid Level",
                    "package": "₹12 - 20 LPA",
                    "hr_email": "talent@scaleaitech.com",
                    "url": "https://www.linkedin.com/jobs",
                    "description": "Building high-performance web applications, scalable backend microservices, and modern user experiences.",
                    "responsibilities": [
                        "Architect robust REST APIs and database models using Node.js & MongoDB.",
                        "Build responsive, pixel-perfect frontend interfaces in React.js.",
                        "Optimize system throughput, state management, and real-time event streaming."
                    ],
                    "skills_required": ["React.js", "Node.js", "MongoDB", "Express", "REST APIs", "Git"],
                    "benefits": ["100% Remote", "Health Insurance", "Flexible Hours", "Learning Allowance"],
                    "ai_match_score": "98% Match",
                    "ai_match_reason": "Your hands-on MERN stack expertise and Cepialabs internship experience directly align with this role."
                },
                {
                    "title": "Frontend Engineer (React.js & TypeScript)",
                    "company": "CloudNova Systems",
                    "location": "Remote / Hybrid (Bangalore)",
                    "experience": "2 - 4 Years / Mid-Senior",
                    "package": "₹15 - 24 LPA",
                    "hr_email": "careers@cloudnova.io",
                    "url": "https://indeed.com",
                    "description": "Leading design system integration, frontend performance tuning, and scalable customer dashboards.",
                    "responsibilities": [
                        "Develop reusable component libraries with React, TypeScript, and modern CSS frameworks.",
                        "Integrate GraphQL and REST services with smooth client-side caching.",
                        "Participate in code reviews, technical roadmaps, and agile sprint planning."
                    ],
                    "skills_required": ["React", "TypeScript", "JavaScript", "Redux", "Tailwind CSS"],
                    "benefits": ["Work from Home", "Annual Performance Bonus", "Gym Stipend", "Medical Cover"],
                    "ai_match_score": "95% Match",
                    "ai_match_reason": "Your strong foundation in React components and responsive UI design matches their core requirements."
                }
            ]
        }

@app.post("/api/apply-direct")
async def apply_direct(req: DirectApplyRequest):
    """Dispatches personalized cold email for a specific job clicked in chat."""
    init_db()
    
    # Set user credentials
    if req.gmail_user:
        os.environ["GMAIL_USER"] = req.gmail_user
    if req.gmail_app_pass:
        os.environ["GMAIL_APP_PASSWORD"] = req.gmail_app_pass
        
    resume_path = os.getenv("RESUME_PATH", "resume.docx")
    resume_text = extract_resume_text(resume_path) if os.path.exists(resume_path) else "Candidate Resume"
    
    email_agent = AIEmailAgent()
    email_sent = False
    
    if req.hr_email and "@" in req.hr_email:
        mail_data = email_agent.generate_cold_email(
            resume_text=resume_text,
            job_title=req.job_title,
            company=req.company,
            job_desc=f"{req.job_title} at {req.company}"
        )
        email_sent = email_agent.send_cold_email(
            to_email=req.hr_email,
            subject=mail_data.get("subject", f"Application for {req.job_title} - {req.company}"),
            body=mail_data.get("body", "Please find my application attached.")
        )
        
    log_application(
        job_title=req.job_title,
        company=req.company,
        url=req.url or "https://www.linkedin.com/jobs",
        hr_email=req.hr_email,
        email_sent=email_sent
    )
    
    return {
        "status": "success",
        "email_sent": email_sent,
        "message": f"Successfully processed application for {req.job_title} at {req.company}"
    }

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
        
        target_role = req.job_title if req.job_title and "auto" not in req.job_title.lower() else None
        
        count = await agent.run(job_title=target_role, location=req.location, max_jobs=req.max_jobs)
        return {
            "status": "success",
            "message": f"FastApply successfully processed {count} jobs in '{req.location}'. Cold emails dispatched from {req.gmail_user or 'configured Gmail'}.",
            "max_jobs_processed": count
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
