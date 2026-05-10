$env:PYTHONPATH = "e:\VScode(study)\Project\AI-Novels\src"
Set-Location "e:\VScode(study)\Project\AI-Novels"
python -c "
import sys
import os
sys.path.insert(0, 'src')
from deepnovel.services.health_service import check_system_health
import json

print('Testing health check...')
result = check_system_health()
print(f'Overall status: {result[\"overall_status\"]}')
print(f'Component count: {result[\"component_count\"]}')
print(f'Healthy count: {result[\"healthy_count\"]}')
print(f'Unhealthy count: {result[\"unhealthy_count\"]}')
print('\nDetailed component status:')
for name, health in result['components'].items():
    status = health['status']
    details = health.get('details', {})
    error = health.get('error')
    print(f'  {name}: {status}')
    if error:
        print(f'    Error: {error}')
    if details:
        print(f'    Details: {details}')

# Save result to file
output_file = 'tests/health_check_result.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(f'\nResult saved to {output_file}')
"
