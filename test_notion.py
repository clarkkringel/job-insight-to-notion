import os
from notion_client import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Initialize Notion client
notion = Client(auth=NOTION_API_KEY)

# Try to retrieve the database
try:
    response = notion.databases.retrieve(database_id=NOTION_DATABASE_ID)
    print("✅ Success: Connected to Notion database.")
    print("Database name:", response["title"][0]["text"]["content"])
except Exception as e:
    print("❌ Error accessing database:", e)
