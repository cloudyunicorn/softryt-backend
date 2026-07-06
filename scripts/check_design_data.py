import sys
sys.path.insert(0, ".")

from app.database import get_supabase_client
import json

db = get_supabase_client()

# Fetch design tools
tools = db.table("tools").select("id, name, slug, category").eq("category", "design-tool").execute()

print(f"Design tools found: {len(tools.data)}")

for tool in tools.data:
    print(f"\n--- {tool['name']} ({tool['id']}) ---")
    
    # Fetch features
    features = db.table("tool_features").select("*").eq("tool_id", tool["id"]).maybe_single().execute()
    if features and features.data:
        raw_content = features.data.get("raw_content") or ""
        comprehensive = features.data.get("comprehensive_data") or {}
        pricing_tiers = features.data.get("pricing_tiers") or []
        key_features = features.data.get("key_features") or []
        
        print(f"  raw_content length: {len(raw_content)} chars")
        print(f"  pricing_tiers count: {len(pricing_tiers)}")
        print(f"  key_features count: {len(key_features)}")
        print(f"  comprehensive_data: {bool(comprehensive)} (length in string: {len(json.dumps(comprehensive))})")
    else:
        print("  No features found in tool_features table!")
