import sys

file_path = 'backend/services/project_db_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    orig_code = f.read()

# Replace slug generation in project_db_service.py
code = orig_code.replace('''    # slug is cleaned project name
    slug = re.sub(r'[^a-z0-9-]', '-', name.lower().strip()).strip('-')
    # Revert to old approach: workspace/slug-id
    clone_code = f"{workspace_slug}/{slug}-{project_id}"''', '''    # Slugs deprecated. Verbatim name mapping.
    clone_code = f"{workspace_slug}/{name}"''')

# Also wait, they didn't have -project_id in the previous diffs, they had clone_code = f"{workspace_slug}/{slug}"
# If the replace fails, we run a flexible fallback
if 'clone_code = f"{workspace_slug}/{slug}' not in code and 'slug =' in code:
    import re
    # We will just strip out slug generation completely using regex on the python code!
    code = re.sub(r'slug = re\.sub[^\n]+\n', '', code)
    code = re.sub(r'clone_code = [^\n]+\n', 'clone_code = f"{workspace_slug}/{name}"\n', code)

code = code.replace('"workspace_slug": workspace_slug', '"workspace": workspace_slug')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(code)

print('Updated project_db_service.py')
