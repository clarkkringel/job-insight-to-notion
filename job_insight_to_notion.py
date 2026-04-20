import os
import sys
import anthropic
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Initialize clients
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
notion = Client(auth=NOTION_API_KEY)

# User's background for prompt injection
user_background = """
Clark is a Senior Endpoint Support Analyst at UCLA with over 3 years of experience in IT support and automation projects.
He has worked at UCLA and TikTok, where he led initiatives like automated MacBook imaging with C++ and Arduino, migrated
knowledge bases to cloud platforms, and designed internal onboarding tools. He is certified in Azure (AZ-900), has hands-on
experience with REST APIs, Python, Flask, and Anthropic/Claude integrations, and is currently building AI-powered internal tooling.
He has some experience in C++, JavaScript, and HTML, and is actively learning React, Next.js, CI/CD, and web architecture
fundamentals to transition into a Cloud or AI Solutions Engineering role.
"""

def fetch_job_posting(url):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        sys.exit(1)
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)

# Template for Anthropic prompt
def generate_prompt(job_description):
    return f"""
You are a technical career coach. The user analyzing this job posting is Clark Kringel. Here is his professional background:

{user_background}

First, identify the company name and job title from the posting. Then evaluate Clark's alignment with the role.

Format your response EXACTLY like this (do not deviate from this structure):

COMPANY: [Company Name]
JOB_TITLE: [Job Title]

### 🔍 Skill Insight Summary – [Company Name] [Job Title]

**Strong Fit:**
- [2-3 most relevant skills/experiences]

**Skills to Strengthen:**
- [2-3 most important areas to improve]

**Bonus Areas (Stretch Goals):**
- [1-2 key stretch goals]

IMPORTANT: Everything after the COMPANY/JOB_TITLE lines must be under 2000 characters total. Be concise but specific.

Here is the job posting:

{job_description}
"""

# Call Anthropic to generate skill insight summary
def get_skill_insight(job_description):
    prompt = generate_prompt(job_description)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system="You are a helpful assistant.",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

def parse_response(raw):
    lines = raw.strip().splitlines()
    company, job_title = "", ""
    summary_lines = []
    for i, line in enumerate(lines):
        if line.startswith("COMPANY:"):
            company = line.replace("COMPANY:", "").strip()
        elif line.startswith("JOB_TITLE:"):
            job_title = line.replace("JOB_TITLE:", "").strip()
        elif line.startswith("###"):
            summary_lines = lines[i:]
            break
    summary = "\n".join(summary_lines).strip()
    return company, job_title, summary

# Add new page to Notion database
def send_to_notion(company, job_title, job_link, skill_summary):
    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Company": {"title": [{"text": {"content": company}}]},
            "Job Title": {"rich_text": [{"text": {"content": job_title}}]},
            "Link to Posting": {"url": job_link},
            "Status": {"select": {"name": "Wishlist"}},
            "Fit Summary": {"multi_select": [{"name": "Needs Learning"}]}
        },
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": skill_summary[:1999]}}]
                }
            }
        ]
    )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 job_insight_to_notion.py <job_posting_url>")
        sys.exit(1)

    url = sys.argv[1]

    print("\nFetching job posting...")
    job_description = fetch_job_posting(url)

    print("Generating skill insight summary...")
    raw_response = get_skill_insight(job_description)

    company, job_title, skill_summary = parse_response(raw_response)
    print(f"\nCompany: {company}")
    print(f"Job Title: {job_title}")
    print(f"\n{skill_summary}")

    print("\nSending to Notion...")
    send_to_notion(company, job_title, url, skill_summary)
    print("Done.")
