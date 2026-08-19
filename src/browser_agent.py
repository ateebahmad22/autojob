import asyncio
import os
import re
import sys
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

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
        ignored = ['png', 'jpg', 'jpeg', 'sentry', 'w3.org', 'schema.org', 'example.com', 'github.com', 'google.com', 'domain.com', 'bootstrap', 'duckduckgo']
        for email in set(emails):
            if not any(ign in email.lower() for ign in ignored):
                filtered.append(email)
        return filtered

    def decode_url(self, href: str) -> str:
        if not href:
            return ""
        if "uddg=" in href:
            try:
                extracted = href.split("uddg=")[1].split("&")[0]
                return urllib.parse.unquote(extracted)
            except Exception:
                pass
        if href.startswith("//"):
            return "https:" + href
        return href

    def http_scrape_search(self, query: str) -> list:
        """Lightweight HTTP fallback search for DuckDuckGo."""
        encoded_query = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(html, 'html.parser')
                links = []
                for a in soup.find_all('a', href=True):
                    decoded = self.decode_url(a['href'])
                    if decoded.startswith("http") and not any(ign in decoded for ign in ["duckduckgo.com", "google.com", "bing.com", "yandex", "yahoo"]):
                        if decoded not in links:
                            links.append(decoded)
                return links
        except Exception as e:
            print(f"[HTTP SCRAPE ERROR] {e}")
            return []

    def http_fetch_page(self, target_url: str) -> str:
        """Fetches page content via HTTP with browser headers."""
        try:
            req = urllib.request.Request(
                target_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            return ""

    async def run(self, job_title: str = None, location: str = "Remote", max_jobs: int = 5):
        """
        Dynamically analyzes candidate resume if no explicit title is passed,
        and applies to matching jobs using Playwright or lightweight serverless HTTP engine.
        """
        search_queries = []
        if job_title and job_title.strip() and "auto" not in job_title.lower():
            search_queries = [job_title.strip()]
        else:
            analysis = extract_relevant_roles_from_resume(self.resume_text)
            search_queries = analysis.get("target_roles", [analysis.get("primary_role", "Software Developer")])
            print(f"[RESUME ANALYSIS] Auto-detected matching job roles: {search_queries}")

        browserless_token = os.getenv("BROWSERLESS_TOKEN")
        use_playwright = bool(browserless_token)
        processed_count = 0

        if use_playwright:
            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as p:
                    print("[INFO] Connecting to Cloud Browser via Browserless.io...")
                    browser = await p.chromium.connect_over_cdp(f"wss://chrome.browserless.io?token={browserless_token}")
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()

                    for query_role in search_queries:
                        if processed_count >= max_jobs:
                            break

                        encoded_query = urllib.parse.quote(f"{query_role} {location} jobs apply hr email hiring")
                        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
                        
                        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(1500)

                        hrefs = await page.evaluate("""() => {
                            return Array.from(document.querySelectorAll('a'))
                                .map(a => a.getAttribute('href'))
                                .filter(h => h && h.length > 5);
                        }""")

                        job_urls = [self.decode_url(h) for h in hrefs if self.decode_url(h).startswith("http") and not any(ign in self.decode_url(h) for ign in ["duckduckgo.com", "google.com", "bing.com"])]

                        for target_url in job_urls:
                            if processed_count >= max_jobs:
                                break
                            if is_already_applied(target_url):
                                continue

                            try:
                                await page.goto(target_url, timeout=12000, wait_until="domcontentloaded")
                                page_content = await page.content()
                                hr_emails = self.extract_hr_emails(page_content)
                                email_sent = False

                                if hr_emails:
                                    target_hr_email = hr_emails[0]
                                    mail_data = self.email_agent.generate_cold_email(
                                        resume_text=self.resume_text,
                                        job_title=query_role,
                                        company="Hiring Team",
                                        job_desc=page_content[:2000]
                                    )
                                    email_sent = self.email_agent.send_cold_email(
                                        to_email=target_hr_email,
                                        subject=mail_data["subject"],
                                        body=mail_data["body"]
                                    )

                                log_application(
                                    job_title=query_role,
                                    company="Web Job Opportunity",
                                    url=target_url,
                                    hr_email=hr_emails[0] if hr_emails else None,
                                    email_sent=email_sent
                                )
                                processed_count += 1
                            except Exception as e:
                                print(f"[WARNING] Page crawl error: {e}")

                    await browser.close()
                    return processed_count
            except Exception as e:
                print(f"[PLAYWRIGHT FALLBACK] Cloud browser failed, using Serverless HTTP Scraper: {e}")

        # Serverless HTTP Fallback Mode (Fast, 100% Reliable on Vercel)
        print("[INFO] Running in Serverless Scraper mode...")
        for query_role in search_queries:
            if processed_count >= max_jobs:
                break
            query = f"{query_role} {location} jobs apply hr email hiring"
            links = self.http_scrape_search(query)
            print(f"[FOUND LINKS] {len(links)} links found for {query_role}")

            for target_url in links:
                if processed_count >= max_jobs:
                    break
                if is_already_applied(target_url):
                    continue

                page_content = self.http_fetch_page(target_url)
                hr_emails = self.extract_hr_emails(page_content) if page_content else []
                email_sent = False

                if hr_emails:
                    target_hr_email = hr_emails[0]
                    mail_data = self.email_agent.generate_cold_email(
                        resume_text=self.resume_text,
                        job_title=query_role,
                        company="Hiring Team",
                        job_desc=page_content[:2000] if page_content else "Job Opening"
                    )
                    email_sent = self.email_agent.send_cold_email(
                        to_email=target_hr_email,
                        subject=mail_data["subject"],
                        body=mail_data["body"]
                    )

                log_application(
                    job_title=query_role,
                    company="Web Job Opportunity",
                    url=target_url,
                    hr_email=hr_emails[0] if hr_emails else None,
                    email_sent=email_sent
                )
                processed_count += 1

        return processed_count
