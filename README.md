# AI Auto Job Application & HR Cold Email Sender Agent

An autonomous AI Agent that:
1. Reads your Resume (`.docx` or `.pdf`).
2. Searches job portals (LinkedIn, Indeed, Wellfound, Glassdoor, Naukri).
3. Automatically extracts HR / Recruiter email addresses from postings.
4. Generates a personalized cold email tailored to the job description using Gemini AI.
5. Sends cold emails directly from your Gmail account via SMTP.
6. Tracks applied jobs in a local SQLite database to prevent duplicates.

## Setup & Execution

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install
```

### 2. Configure Credentials (.env)
Edit `.env` and add:
- `GEMINI_API_KEY`: Your Gemini API Key from Google AI Studio.
- `GMAIL_USER`: Your Gmail address.
- `GMAIL_APP_PASSWORD`: Your Gmail App Password (generated via Google Account -> Security -> 2-Step Verification -> App Passwords).
- `RESUME_PATH`: Path to your resume (`resume.docx` or `resume.pdf`).

### 3. Place Resume File
Copy your `resume.docx` (or `resume.pdf`) into this directory.

### 4. Run the Agent
```bash
python main.py
```
