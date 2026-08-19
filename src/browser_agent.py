import asyncio
import os
import re
import sys
import urllib.parse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright
from src.db import is_already_applied, log_application
from src.email_agent import AIEmailAgent
from src.resume_parser import extract_relevant_roles_from_resume

class JobAutomationAgent:
    def __init__(self, resume_text: str):
        self.resume_text = resume_text
        self.email_agent = AIEmailAgent()

    def extract_hr_emails(self, text: str) -> list:
        """Extracts HR/recruiter emails from web page content."""
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        emails = re.findall(email_pattern, text)
        filtered = []
        ignored = ['png', 'jpg', 'jpeg', 'sentry', 'w3.org', 'schema.org', 'example.com', 'github.com', 'google.com', 'domain.com', 'bootstrap']
        for email in set(emails):
            if not any(ign in email.lower() for ign in ignored):
                filtered.append(email)
        return filtered

    def decode_url(self, href: str) -> str:
        if "uddg=" in href:
            try:
                extracted = href.split("uddg=")[1].split("&")[0]
                return urllib.parse.unquote(extracted)
            except Exception:
                pass
        if href and href.startswith("//"):
            return "https:" + href
        return href or ""

    async def run(self, job_title: str = None, location: str = "Remote", max_jobs: int = 5):
        """
        Dynamically analyzes candidate resume if no explicit title is passed,
        and applies to any relevant jobs discovered matching the candidate's exact background.
        """
        # Determine search queries based on candidate resume
        search_queries = []
        if job_title and job_title.strip() and job_title.lower() != "auto":
            search_queries = [job_title.strip()]
        else:
            analysis = extract_relevant_roles_from_resume(self.resume_text)
            search_queries = analysis.get("target_roles", [analysis.get("primary_role", "Professional")])
            print(f"[RESUME ANALYSIS] Auto-detected matching job roles: {search_queries}")

        async with async_playwright() as p:
            browserless_token = os.getenv("BROWSERLESS_TOKEN")
            
            if browserless_token:
                print("[INFO] Connecting to Cloud Browser via Browserless.io...")
                browser = await p.chromium.connect_over_cdp(f"wss://chrome.browserless.io?token={browserless_token}")
            else:
                print("[INFO] Launching local Chromium browser automation engine...")
                browser = await p.chromium.launch(headless=False)

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            processed_count = 0

            for query_role in search_queries:
                if processed_count >= max_jobs:
                    break

                encoded_query = urllib.parse.quote(f"{query_role} {location} jobs apply hr email hiring")
                search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
                
                print(f"\n[SEARCH] Searching relevant openings for role '{query_role}' in '{location}'...")
                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(2000)

                    hrefs = await page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('a'))
                            .map(a => a.getAttribute('href'))
                            .filter(h => h && h.length > 5);
                    }""")

                    job_urls = []
                    for h in hrefs:
                        decoded = self.decode_url(h)
                        if decoded.startswith("http") and not any(ign in decoded for ign in ["duckduckgo.com", "google.com", "bing.com"]):
                            if decoded not in job_urls:
                                job_urls.append(decoded)

                    print(f"[FOUND] Discovered {len(job_urls)} potential job links for '{query_role}'.")

                    for target_url in job_urls:
                        if processed_count >= max_jobs:
                            break

                        if is_already_applied(target_url):
                            print(f"[SKIP] Already processed: {target_url[:60]}")
                            continue

                        print(f"\n[APPLYING {processed_count+1}/{max_jobs}] Visiting Page: {target_url[:70]}")
                        try:
                            await page.goto(target_url, timeout=15000, wait_until="domcontentloaded")
                            await page.wait_for_timeout(2000)
                            page_content = await page.content()

                            hr_emails = self.extract_hr_emails(page_content)
                            email_sent = False

                            if hr_emails:
                                target_hr_email = hr_emails[0]
                                print(f" [EMAIL DETECTED] HR Email: {target_hr_email}")
                                
                                mail_data = self.email_agent.generate_cold_email(
                                    resume_text=self.resume_text,
                                    job_title=query_role,
                                    company="Hiring Team",
                                    job_desc=page_content[:2500]
                                )

                                email_sent = self.email_agent.send_cold_email(
                                    to_email=target_hr_email,
                                    subject=mail_data["subject"],
                                    body=mail_data["body"]
                                )
                            else:
                                print(" [INFO] Page visited & recorded. No surface HR email found.")

                            log_application(
                                job_title=query_role,
                                company="Web Job Opportunity",
                                url=target_url,
                                hr_email=hr_emails[0] if hr_emails else None,
                                email_sent=email_sent
                            )
                            processed_count += 1

                        except Exception as e:
                            print(f" [WARNING] Could not process {target_url[:60]}: {e}")

                except Exception as e:
                    print(f" [WARNING] Search query error for '{query_role}': {e}")

            await browser.close()
            print(f"\n[COMPLETE] Successfully processed {processed_count} relevant job applications!")
