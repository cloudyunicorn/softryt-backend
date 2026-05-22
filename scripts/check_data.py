from app.database import get_supabase_client
import json

db = get_supabase_client()
result = db.table('tool_features').select('*').execute()

if result.data:
    found = False
    for row in result.data:
        if row.get('comprehensive_data'):
            tool_id = row['tool_id']
            data = row['comprehensive_data']
            print(f'Found comprehensive data for tool_id: {tool_id}')
            
            print(f'\nTechnical Summary:\n{data.get("technical_summary", "")[:200]}...')
            print(f'\nCore Capabilities: {len(data.get("core_capabilities", []))} items')
            print(f'Advanced Features: {len(data.get("advanced_features", []))} items')
            print(f'Developer Experience: {len(data.get("developer_experience", []))} items')
            print(f'Integration Ecosystem: {len(data.get("integration_ecosystem", []))} items')
            print(f'Pricing Architecture: {len(data.get("pricing_architecture", []))} tiers')
            print(f'Compliance & Security: {len(data.get("compliance_and_security", []))} items')
            
            print('\nFirst Pricing Tier Sample:')
            if data.get('pricing_architecture'):
                print(json.dumps(data['pricing_architecture'][0], indent=2))
            found = True
            break
            
    if not found:
        print('No tool in the database has comprehensive_data populated yet.')
else:
    print('No tools found in the database. Has the scrape completed yet?')
