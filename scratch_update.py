import sys

file_path = 'backend/services/auth_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    orig_code = f.read()

# Remove generate_slug
code = orig_code.replace('''def generate_slug(name: str):
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug''', '''# Slugs deprecated. Using plain workspace names.''')

code = code.replace('workspace_slug = generate_slug(workspace_name)', 'workspace_slug = workspace_name.strip()')
code = code.replace('''    while workspaces.find_one({"slug": workspace_slug}):
        workspace_slug = f"{base_slug}-{counter}"''', '''    while workspaces.find_one({"workspace": workspace_slug}): # Check new primary key 'workspace'
        workspace_slug = f"{base_slug} {counter}"''')

code = code.replace('"slug": workspace_slug,', '"workspace": workspace_slug,')
code = code.replace('"workspace_slug": workspace_slug,', '"workspace": workspace_slug,')

code = code.replace('''    workspace = workspaces.find_one({"slug": user["workspace_slug"]})
    
    token = create_access_token({"sub": email, "workspace": user["workspace_slug"]})''',
'''    # Legacy migration support: try "workspace", fallback to "workspace_slug"
    workspace_id = user.get("workspace", user.get("workspace_slug"))
    workspace = workspaces.find_one({"workspace": workspace_id}) or workspaces.find_one({"slug": workspace_id})
    token = create_access_token({"sub": email, "workspace": workspace_id})''')

code = code.replace('"workspace": user["workspace_slug"]', '"workspace": workspace_id')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(code)

print('Updated auth_service.py')
