import smtplib
import json
import sys
import warnings

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai
from src.config import Config

class AIEmailAgent:
    def __init__(self):
        self.gmail_user = Config.GMAIL_USER
        self.gmail_password = Config.GMAIL_APP_PASSWORD
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY) if Config.GEMINI_API_KEY else None

    def generate_cold_email(self, resume_text: str, job_title: str, company: str, job_desc: str) -> dict:
        """Generates a tailored cold email using Gemini AI based on resume and job posting."""
        if not self.client:
            print("[INFO] GEMINI_API_KEY not set. Using template cold email.")
            return {
                "subject": f"Application for {job_title} - {company}",
                "body": f"Hi HR Team,\n\nI am writing to express my strong interest in the {job_title} position at {company}.\n\nBest regards,"
            }

        prompt = f"""
        You are an expert career agent writing a tailored cold email to an HR/Recruiter.

        Candidate Resume Details:
        {resume_text}

        Job Details:
        - Position Title: {job_title}
        - Company: {company}
        - Job Description: {job_desc}

        Return ONLY a JSON object with keys "subject" and "body". Do NOT wrap in markdown formatting outside JSON.
        Keep the subject intriguing and professional. Keep the body concise (150-200 words max), highlighting 2 key skills/achievements directly relevant to the job.
        """

        models_to_try = ["gemini-3.6-flash", "gemini-2.5-pro"]
        
        for model in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                raw_text = response.text.replace("```json", "").replace("```", "").strip()
                return json.loads(raw_text)
            except Exception as e:
                continue

        print("[WARNING] Could not generate via Gemini API, using fallback template.")
        return {
            "subject": f"Application for {job_title} - {company}",
            "body": f"Hi HR Team,\n\nI am interested in applying for the {job_title} role at {company}.\n\nBest regards,"
        }

    def send_cold_email(self, to_email: str, subject: str, body: str) -> bool:
        """Sends cold email via Gmail SMTP using App Password."""
        if not self.gmail_user or not self.gmail_password or "your_gmail" in self.gmail_password:
            print("[INFO] GMAIL_APP_PASSWORD not set in .env. Skipping email dispatch.")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.gmail_user
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.gmail_user, self.gmail_password)
                server.send_message(msg)

            print(f"[SUCCESS] Cold Email successfully sent to HR ({to_email})!")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send email to {to_email}: {e}")
            return False
