"""Retry scraping for failed tools."""
import sys
sys.path.insert(0, ".")

from app.config import get_settings
from supabase import create_client

settings = get_settings()
db = create_client(settings.supabase_url, settings.supabase_key)

# Get IDs for failed tools
for name in ["Adobe XD", "Hashnode", "Beehiiv"]:
    result = db.table("tools").select("id, name").eq("name", name).single().execute()
    if result.data:
        print(f"{result.data['name']}: {result.data['id']}")
