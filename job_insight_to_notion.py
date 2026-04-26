import os
import sys
import json
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

def migrate_notion_schema():
    response = requests.patch(
        f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}",
        headers={
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "properties": {
                "Fit Score":       {"number": {"format": "number"}},
                "Skills to Learn": {"multi_select": {}},
                "Next Steps":      {"rich_text": {}},
                "Salary Range":    {"rich_text": {}},
                "Summary":         {"rich_text": {}},
            }
        }
    )
    response.raise_for_status()
    print("Notion schema updated.")

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

def generate_prompt(job_description):
    return f"""
You are a technical career coach. The user is Clark Kringel. Here is his background:

{user_background}

Analyze the job posting below and return ONLY a valid JSON object with these exact keys:
- "company": string
- "job_title": string
- "fit_score": integer 1-10 (10 = perfect match)
- "skills_to_learn": list of 2-4 strings (specific skills Clark is missing or should strengthen; each must be a short tag-style label, 1-4 words, no commas — e.g. "SQL", "Fintech Domain", "OAuth 2.0")
- "next_steps": list of 2-3 strings (concrete action items Clark should take before applying)
- "salary_range": string (extract from posting or estimate based on role/level, e.g. "$130k–$160k")
- "summary": string (2-3 sentences: overall fit, biggest gap, and one concrete reason to apply or skip)

Return only the JSON object. No markdown fences, no explanation.

Job posting:
{job_description}
"""

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
    return json.loads(raw.strip())

def send_to_notion(data, job_link):
    children = [
        {
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": f"{data['company']} — {data['job_title']}"}}]}
        },
        {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Fit Score"}}]}
        },
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"{data['fit_score']} / 10"}}]}
        },
        {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Summary"}}]}
        },
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": data["summary"]}}]}
        },
        {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Salary Range"}}]}
        },
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": data["salary_range"]}}]}
        },
        {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Skills to Learn"}}]}
        },
        *[
            {
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": s}}]}
            }
            for s in data["skills_to_learn"]
        ],
        {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Next Steps"}}]}
        },
        *[
            {
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": s}}]}
            }
            for s in data["next_steps"]
        ],
    ]

    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Company":         {"title":     [{"text": {"content": data["company"]}}]},
            "Job Title":       {"rich_text": [{"text": {"content": data["job_title"]}}]},
            "Link to Posting": {"url": job_link},
            "Status":          {"select": {"name": "Wishlist"}},
            "Fit Score":       {"number": data["fit_score"]},
            "Skills to Learn": {"multi_select": [{"name": s.replace(",", "")} for s in data["skills_to_learn"]]},
            "Next Steps":      {"rich_text": [{"text": {"content": "\n".join(f"• {s}" for s in data["next_steps"])}}]},
            "Salary Range":    {"rich_text": [{"text": {"content": data["salary_range"]}}]},
            "Summary":         {"rich_text": [{"text": {"content": data["summary"]}}]},
        },
        children=children
    )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 job_insight_to_notion.py <job_posting_url>")
        sys.exit(1)

    url = sys.argv[1]

    print("\nUpdating Notion schema...")
    migrate_notion_schema()

    print("Fetching job posting...")
    job_description = fetch_job_posting(url)

    print("Generating skill insight summary...")
    raw_response = get_skill_insight(job_description)

    data = parse_response(raw_response)
    print(f"\nCompany:      {data['company']}")
    print(f"Job Title:    {data['job_title']}")
    print(f"Fit Score:    {data['fit_score']}/10")
    print(f"Salary Range: {data['salary_range']}")
    print(f"\nSummary: {data['summary']}")

    print("\nSending to Notion...")
    send_to_notion(data, url)
    print("Done.")
