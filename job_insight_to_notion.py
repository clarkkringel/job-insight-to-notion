import os
import anthropic
from notion_client import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Initialize the Anthropic client
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

# Template for Anthropic prompt
def generate_prompt(job_description):
    return f"""
You are a technical career coach. The user analyzing this job posting is Clark Kringel. Here is his professional background:

{user_background}

Now, given the job posting below, evaluate Clark's alignment with the role. Identify:

1. Skills and experiences he is already a strong fit for  
2. Skills or knowledge areas he should strengthen  
3. Bonus or stretch skills for long-term growth  

IMPORTANT: Your response MUST be under 2000 characters total. Be concise but specific. Focus on the most relevant points only.

Format your response exactly like this (keep each section brief):

### 🔍 Skill Insight Summary – [Company Name] [Job Title]

**Strong Fit:**  
- [2-3 most relevant skills/experiences]  

**Skills to Strengthen:**  
- [2-3 most important areas to improve]  

**Bonus Areas (Stretch Goals):**  
- [1-2 key stretch goals]  

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

# Add new page to Notion database
def send_to_notion(company, job_title, job_link, skill_summary):
    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Company": {"title": [{"text": {"content": company}}]},
            "Job Title": {"rich_text": [{"text": {"content": job_title}}]},
            "Link to Posting": {"url": job_link},
            "Status": {"select": {"name": "Wishlist"}},  # Always set to Wishlist
            "Fit Summary": {"multi_select": [{"name": "Needs Learning"}]}  # Can be improved with parsing logic
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

# Example usage
if __name__ == "__main__":
    job_description = open("vercel_job_posting.txt").read()  # Load job post
    company = "Vercel"
    job_title = "Customer Support Engineer"
    job_link = "https://vercel.com/careers/customer-support-engineer"  # Placeholder

    print("\nGenerating skill insight summary...")
    skill_summary = get_skill_insight(job_description)
    print(skill_summary)

    print("\nSending to Notion...")
    send_to_notion(company, job_title, job_link, skill_summary)
    print("Done.")

