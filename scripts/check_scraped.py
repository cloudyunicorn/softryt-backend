"""Quick script to find tools that haven't been scraped yet."""
import sys
sys.path.insert(0, ".")

from app.config import get_settings
from supabase import create_client

settings = get_settings()
db = create_client(settings.supabase_url, settings.supabase_key)

# Get all tools
all_tools = db.table("tools").select("id, name, category").execute()

# Get all scraped tool IDs
scraped = db.table("tool_features").select("tool_id").execute()
scraped_ids = {row["tool_id"] for row in scraped.data} if scraped.data else set()

print(f"Total tools: {len(all_tools.data)}")
print(f"Scraped: {len(scraped_ids)}")
print(f"Missing: {len(all_tools.data) - len(scraped_ids)}")
print()

for tool in all_tools.data:
    if tool["id"] not in scraped_ids:
        print(f"  MISSING: {tool['name']} ({tool['category']})")
