# ⚡ FastApply AI - Autonomous Job Application & HR Cold Mailer SaaS

FastApply AI is an autonomous, full-stack AI Agent SaaS platform that:
1. Parses your `.docx` / `.pdf` resume (**Ateeb Ahmad - Full Stack Developer**).
2. Searches job portals (LinkedIn, Indeed, Wellfound, Glassdoor).
3. Automatically extracts HR / Recruiter email addresses.
4. Generates hyper-personalized cold emails using **Gemini 3.6 Flash AI**.
5. Dispatches cold emails directly from your Gmail account via SMTP.
6. Features a **ChatGPT-themed dark Web UI**, interactive **AI Prompt Chatbox**, **Auth System**, and **Analytics Dashboard**.

## 🚀 Live Vercel Deployment

Deploy directly to Vercel with 1-click:
1. Import repository `ateebahmad22/autojob`.
2. Add Environment Variables:
   - `GEMINI_API_KEY`: Your Gemini API Key
   - `GMAIL_USER`: `ateebahmad298@gmail.com`
   - `GMAIL_APP_PASSWORD`: Your 16-letter Gmail App Password
   - `BROWSERLESS_TOKEN`: Your Browserless.io Token
3. Deploy!

## 🏃 Local Run

```bash
pip install -r requirements.txt
playwright install
python main.py
```
