import sys
sys.path.insert(0, ".")

from app.database import get_supabase_client
import json
from collections import defaultdict

db = get_supabase_client()

# Fetch all tools
tools = db.table("tools").select("id, name, slug, category").execute()

category_stats = defaultdict(list)

for tool in tools.data:
    features = db.table("tool_features").select("raw_content").eq("tool_id", tool["id"]).maybe_single().execute()
    raw_len = len(features.data.get("raw_content") or "") if features and features.data else 0
    category_stats[tool["category"]].append((tool["name"], raw_len))

for cat, items in category_stats.items():
    print(f"\nCategory: {cat}")
    for name, raw_len in items:
        print(f"  - {name}: {raw_len} chars")
